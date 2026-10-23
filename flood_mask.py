"""Derive a flood mask from two Sentinel-1 dates (same orbit) and report the flooded area."""
import matplotlib.pyplot as plt
import numpy as np
import planetary_computer
import rioxarray  # noqa: F401  (adds the .rio accessor)
from pystac_client import Client
from scipy import ndimage

from compare_dates import DATE_AFTER, DATE_BEFORE, OUT_DIR, RESOLUTION, STAC_URL, load_db

# VV below this value is treated as open water. Started at -18 dB (a common default);
# the threshold sweep against Copernicus EMS (threshold_tradeoff.py) showed -13 to -15 dB
# gives the best agreement, so -14 dB is used. Note: this calibrates on the same reference
# used for validation, so the reported agreement is somewhat optimistic.
WATER_DB = -14.0
DROP_DB = 3.0          # and the backscatter must have dropped by at least this much
MIN_AREA_HA = 1.0      # remove flooded patches smaller than this
SENSITIVITY_DB = [-13.0, -14.0, -15.0, -18.0]

PIXEL_KM2 = (RESOLUTION / 1000) ** 2


def flood_mask(before, after, water_db):
    """Newly flooded = water after, not water before, and a clear drop in backscatter."""
    mask = (after < water_db) & (before >= water_db) & ((after - before) < -DROP_DB)
    arr = ndimage.median_filter(mask.values.astype(np.uint8), size=3).astype(bool)  # reduce speckle
    labels, n = ndimage.label(arr)
    min_pixels = MIN_AREA_HA / (PIXEL_KM2 * 100)  # 1 km2 = 100 ha
    sizes = ndimage.sum(arr, labels, range(1, n + 1))
    keep = np.isin(labels, 1 + np.flatnonzero(sizes >= min_pixels))
    return mask.copy(data=keep)


def save_mask(flood, path):
    """Write the mask as a GeoTIFF (1 = flooded, 0 = not flooded, 255 = no data)."""
    out = flood.astype("uint8")
    out.attrs = {}
    out.encoding = {}
    out = out.rio.write_nodata(255)
    out.rio.to_raster(path)


def main():
    client = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    before = load_db(client, DATE_BEFORE)
    after = load_db(client, DATE_AFTER)

    print("\nSensitivity of the flooded area to the water threshold:")
    for threshold in SENSITIVITY_DB:
        area = float(flood_mask(before, after, threshold).sum()) * PIXEL_KM2
        print(f"  VV < {threshold:.0f} dB: {area:,.1f} km2")

    flood = flood_mask(before, after, WATER_DB)
    area_km2 = float(flood.sum()) * PIXEL_KM2
    valid_km2 = float(after.notnull().sum()) * PIXEL_KM2
    print(f"\nChosen threshold {WATER_DB:.0f} dB: flooded area {area_km2:,.1f} km2 "
          f"({100 * area_km2 / valid_km2:.1f}% of the {valid_km2:,.0f} km2 covered)")

    OUT_DIR.mkdir(exist_ok=True)
    save_mask(flood, OUT_DIR / "flood_mask.tif")
    print("Saved outputs/flood_mask.tif")

    overlay = np.ma.masked_where(~flood.values, flood.values)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(after, cmap="gray", vmin=-25, vmax=0)
    ax.imshow(overlay, cmap="autumn", alpha=0.7)
    ax.set_title(f"Flooded area (red) over Sentinel-1 VV, {DATE_AFTER}")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "flood_preview.png", dpi=120)
    print("Saved outputs/flood_preview.png")


if __name__ == "__main__":
    main()