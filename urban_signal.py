"""Check whether buildings near the flood show a backscatter INCREASE (urban flood signal)."""
import geopandas as gpd
import numpy as np
import planetary_computer
import rioxarray
from pystac_client import Client
from scipy import ndimage

from compare_dates import DATE_AFTER, DATE_BEFORE, OUT_DIR, RESOLUTION, STAC_URL, load_db

INCREASE_DB = 3.0
NEAR_M = 1000    # buildings closer than this to flooded pixels
FAR_M = 5000     # control group: buildings farther than this


def summarize(label, values):
    if len(values) == 0:
        print(f"  {label}: no buildings")
        return
    share = 100 * float((values > INCREASE_DB).mean())
    print(f"  {label}: {len(values):,} buildings, "
          f"{share:.1f}% with an increase above {INCREASE_DB:.0f} dB, median change {np.median(values):+.2f} dB")


def main():
    flood_da = rioxarray.open_rasterio(OUT_DIR / "flood_mask.tif").squeeze(drop=True)
    flooded = flood_da.values == 1
    distance_m = ndimage.distance_transform_edt(~flooded) * RESOLUTION

    client = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    before = load_db(client, DATE_BEFORE)
    after = load_db(client, DATE_AFTER)
    diff = (after - before).values
    diff_smooth = ndimage.uniform_filter(np.nan_to_num(diff), size=3)  # 3x3 mean around each pixel

    buildings = gpd.read_parquet("data/building_exposure.parquet").to_crs(flood_da.rio.crs)
    centroids = buildings.geometry.centroid
    cols, rows = (~flood_da.rio.transform()) * (centroids.x.values, centroids.y.values)
    cols = np.floor(cols).astype(int)
    rows = np.floor(rows).astype(int)

    change = diff_smooth[rows, cols]
    dist = distance_m[rows, cols]
    exposure = buildings["exposure"].values

    print("\nBackscatter change (after minus before) at building locations:")
    summarize(f"within {NEAR_M} m of flooded pixels (not marked flooded)", change[(dist <= NEAR_M) & (exposure != "flooded")])
    summarize(f"farther than {FAR_M / 1000:.0f} km from any flooding (control)", change[dist > FAR_M])
    summarize("marked flooded by the mask", change[exposure == "flooded"])


if __name__ == "__main__":
    main()