"""Compare the Sentinel-1 flood mask with the official Copernicus EMS flood delineation (EMSR692)."""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rioxarray
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from rasterio.features import rasterize

from compare_dates import DATE_AFTER, OUT_DIR, RESOLUTION

MASK_PATH = OUT_DIR / "flood_mask.tif"
EMS_DIR = Path("data") / "ems"
EMS_DATE = "2023-09-10"
AOIS = {"AOI02 Palamas": "AOI02", "AOI05 Karditsa": "AOI05"}
PIXEL_KM2 = (RESOLUTION / 1000) ** 2


def read_layer(aoi, name):
    """Read one layer of an EMS delineation product, e.g. 'observedEventA'."""
    folder = EMS_DIR / f"EMSR692_{aoi}_DEL_PRODUCT_v2"
    return gpd.read_file(folder / f"EMSR692_{aoi}_DEL_PRODUCT_{name}_v2.shp")


def burn(gdf, grid):
    """Rasterize polygons onto the flood-mask grid (True = inside a polygon)."""
    gdf = gdf.to_crs(grid.rio.crs)
    shapes = [g for g in gdf.geometry if g is not None and not g.is_empty]
    if not shapes:
        return np.zeros(grid.shape, dtype=bool)
    raster = rasterize(shapes, out_shape=grid.shape, transform=grid.rio.transform(),
                       fill=0, default_value=1, dtype="uint8")
    return raster.astype(bool)


def metrics(name, layer, s1, ems, region):
    """Agreement statistics between the two flood maps, inside the compared region only."""
    s1, ems = s1 & region, ems & region
    both, s1_n, ems_n, union = (s1 & ems).sum(), s1.sum(), ems.sum(), (s1 | ems).sum()
    return {
        "area": name,
        "ems_layer": layer,
        "compared_km2": region.sum() * PIXEL_KM2,
        "s1_flooded_km2": s1_n * PIXEL_KM2,
        "ems_flooded_km2": ems_n * PIXEL_KM2,
        "both_km2": both * PIXEL_KM2,
        "iou": both / union if union else np.nan,
        "s1_confirmed_by_ems": both / s1_n if s1_n else np.nan,
        "ems_found_by_s1": both / ems_n if ems_n else np.nan,
    }


def main():
    grid = rioxarray.open_rasterio(MASK_PATH).squeeze("band", drop=True)
    values = grid.values
    s1 = values == 1
    valid = values != 255

    rows = []
    region_all = np.zeros(values.shape, dtype=bool)
    water_all = np.zeros(values.shape, dtype=bool)
    trace_all = np.zeros(values.shape, dtype=bool)
    for name, aoi in AOIS.items():
        events = read_layer(aoi, "observedEventA")
        region = burn(read_layer(aoi, "areaOfInterestA"), grid) & valid
        water = burn(events[events["notation"] == "Flooded area"], grid)  # open water on the EMS date
        trace = burn(events[events["notation"] == "Flood trace"], grid)   # receded, wet or debris-covered
        rows.append(metrics(name, "All EMS flooding", s1, water | trace, region))
        rows.append(metrics(name, "Open water only", s1, water, region))
        region_all |= region
        water_all |= water
        trace_all |= trace

    rows.append(metrics("Both AOIs", "All EMS flooding", s1, water_all | trace_all, region_all))
    rows.append(metrics("Both AOIs", "Open water only", s1, water_all, region_all))
    table = pd.DataFrame(rows).round(3)
    print(f"Sentinel-1 ({DATE_AFTER}) vs Copernicus EMS ({EMS_DATE}):")
    print(table.to_string(index=False))

    OUT_DIR.mkdir(exist_ok=True)
    table.to_csv(OUT_DIR / "ems_comparison.csv", index=False)
    print("\nSaved outputs/ems_comparison.csv")

    total = table[table["area"] == "Both AOIs"].set_index("ems_layer")
    found_water = total.loc["Open water only", "ems_found_by_s1"]
    confirmed = total.loc["All EMS flooding", "s1_confirmed_by_ems"]

    # 0 dry in both, 1 flooded in both, 2 Sentinel-1 only, 3 EMS open water missed, 4 EMS flood trace missed
    ems_any = water_all | trace_all
    category = np.zeros(values.shape, dtype=np.uint8)
    category[s1 & ems_any] = 1
    category[s1 & ~ems_any] = 2
    category[~s1 & water_all] = 3
    category[~s1 & trace_all & ~water_all] = 4
    shown = np.ma.masked_where(~region_all, category)
    colors = ["#eeeeee", "#2b6cb0", "#38a169", "#c53030", "#d4b483"]
    labels = ["Dry in both", "Flooded in both", "Sentinel-1 only",
              "EMS open water, missed by Sentinel-1", "EMS flood trace, missed by Sentinel-1"]

    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.imshow(shown, cmap=ListedColormap(colors), vmin=0, vmax=4, interpolation="nearest")
    ax.set_title(f"Sentinel-1 flood mask ({DATE_AFTER}) vs Copernicus EMS EMSR692 ({EMS_DATE})\n"
                 f"Sentinel-1 flooding confirmed by EMS: {confirmed:.0%}  |  "
                 f"EMS open water found by Sentinel-1: {found_water:.0%}", fontsize=11)
    ax.axis("off")
    ax.legend(handles=[Patch(color=c, label=l) for c, l in zip(colors, labels)],
              loc="lower left", frameon=True, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "ems_comparison.png", dpi=130)
    print("Saved outputs/ems_comparison.png")


if __name__ == "__main__":
    main()