"""Measure how the water threshold trades false alarms against missed flooding, using Copernicus EMS as the reference."""
import os

# PostgreSQL/PostGIS sets PROJ_LIB/PROJ_DATA to its own, older PROJ database, which breaks
# rasterio and pyproj. Drop that setting for this script only, before those libraries load.
for var in ("PROJ_LIB", "PROJ_DATA"):
    if "postgresql" in os.environ.get(var, "").lower():
        print(f"Ignoring {var} for this run (points to PostgreSQL)")
        del os.environ[var]

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import planetary_computer  # noqa: E402
import rioxarray  # noqa: E402
from pystac_client import Client  # noqa: E402

from compare_dates import DATE_AFTER, DATE_BEFORE, OUT_DIR, RESOLUTION, STAC_URL, load_db  # noqa: E402
from compare_ems import AOIS, EMS_DATE, MASK_PATH, burn, read_layer  # noqa: E402
from flood_mask import WATER_DB, flood_mask  # noqa: E402

THRESHOLDS_DB = [-10.0, -11.0, -12.0, -13.0, -14.0, -15.0, -16.0, -17.0,
                 -18.0, -19.0, -20.0, -21.0, -22.0]
PIXEL_KM2 = (RESOLUTION / 1000) ** 2


def load_reference(grid):
    """EMS open water and flood trace, rasterized onto the Sentinel-1 grid, plus the compared region."""
    valid = grid.values != 255
    region = np.zeros(grid.shape, dtype=bool)
    water = np.zeros(grid.shape, dtype=bool)
    trace = np.zeros(grid.shape, dtype=bool)
    for aoi in AOIS.values():
        events = read_layer(aoi, "observedEventA")
        region |= burn(read_layer(aoi, "areaOfInterestA"), grid) & valid
        water |= burn(events[events["notation"] == "Flooded area"], grid)
        trace |= burn(events[events["notation"] == "Flood trace"], grid)
    return region, water & region, (water | trace) & region


def main():
    grid = rioxarray.open_rasterio(MASK_PATH).squeeze("band", drop=True)
    region, water, ems_any = load_reference(grid)

    client = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    before = load_db(client, DATE_BEFORE)
    after = load_db(client, DATE_AFTER)
    if before.shape != grid.shape:
        raise SystemExit(f"Grid mismatch: Sentinel-1 {before.shape} vs saved mask {grid.shape}")

    rows = []
    for threshold in THRESHOLDS_DB:
        s1 = flood_mask(before, after, threshold).values.astype(bool) & region
        s1_n = s1.sum()
        rows.append({
            "threshold_db": threshold,
            "s1_flooded_km2": s1_n * PIXEL_KM2,
            "s1_confirmed_by_ems": (s1 & ems_any).sum() / s1_n if s1_n else np.nan,
            "ems_open_water_found": (s1 & water).sum() / water.sum(),
            "ems_all_flooding_found": (s1 & ems_any).sum() / ems_any.sum(),
            "iou_open_water": (s1 & water).sum() / (s1 | water).sum(),
        })
        print(f"  {threshold:.0f} dB done")

    table = pd.DataFrame(rows).round(3)
    best = table.loc[table["iou_open_water"].idxmax()]
    print(f"\nThreshold trade-off, Sentinel-1 ({DATE_AFTER}) vs Copernicus EMS ({EMS_DATE}):")
    print(table.to_string(index=False))
    print(f"\nBest open-water IoU: {best['iou_open_water']:.3f} at {best['threshold_db']:.0f} dB")

    OUT_DIR.mkdir(exist_ok=True)
    table.to_csv(OUT_DIR / "threshold_tradeoff.csv", index=False)
    print("\nSaved outputs/threshold_tradeoff.csv")

    fig, ax = plt.subplots(figsize=(9, 6.5))
    x = table["threshold_db"]
    ax.plot(x, table["s1_confirmed_by_ems"] * 100, "o-", color="#2b6cb0",
            label="Sentinel-1 flooding confirmed by EMS (fewer false alarms)")
    ax.plot(x, table["ems_open_water_found"] * 100, "o-", color="#c53030",
            label="EMS open water found by Sentinel-1")
    ax.plot(x, table["ems_all_flooding_found"] * 100, "o--", color="#b7791f",
            label="EMS open water + flood trace found by Sentinel-1")
    ax.plot(x, table["iou_open_water"] * 100, "s:", color="#555555",
            label="Open-water IoU (overall agreement)")
    ax.axvline(WATER_DB, color="gray", linestyle=":")
    ax.text(WATER_DB, 3, f" used: {WATER_DB:.0f} dB", color="gray")
    ax.axvline(best["threshold_db"], color="#2f855a", linestyle="--")
    ax.text(best["threshold_db"], 9, f" best IoU: {best['threshold_db']:.0f} dB", color="#2f855a")
    ax.set_xlabel("Water threshold, VV backscatter after the flood (dB)\n"
                  "← looser                                                    stricter →")
    ax.invert_xaxis()
    ax.set_ylabel("%")
    ax.set_ylim(0, 105)
    ax.set_title("How the water threshold trades false alarms against missed flooding")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=8, frameon=False)
    ax.grid(alpha=0.3)
    fig.savefig(OUT_DIR / "threshold_tradeoff.png", dpi=130, bbox_inches="tight")
    print("Saved outputs/threshold_tradeoff.png")


if __name__ == "__main__":
    main()