"""Classify OSM buildings by their exposure to the Sentinel-1 flood mask."""
import geopandas as gpd
import numpy as np
import planetary_computer
import rioxarray
from pystac_client import Client
from scipy import ndimage

from compare_dates import DATE_AFTER, OUT_DIR, RESOLUTION, STAC_URL, load_db

DATA_DIR = "data"
NEAR_M = 40  # a building counts as "next to flooding" if flooded pixels are within this distance
NEAR_PIXELS = round(NEAR_M / RESOLUTION)


def main():
    flood_da = rioxarray.open_rasterio(OUT_DIR / "flood_mask.tif").squeeze(drop=True)
    flooded = flood_da.values == 1
    near = ndimage.binary_dilation(flooded, iterations=NEAR_PIXELS)

    # Coverage: where the Sentinel-1 image has data (the swath does not cover the whole box).
    client = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    covered = load_db(client, DATE_AFTER).notnull().values
    assert covered.shape == flooded.shape, "Mask and image grids differ"

    buildings = gpd.read_parquet(f"{DATA_DIR}/osm_buildings.parquet").to_crs(flood_da.rio.crs)
    centroids = buildings.geometry.centroid
    inverse = ~flood_da.rio.transform()
    cols, rows = inverse * (centroids.x.values, centroids.y.values)
    cols = np.floor(cols).astype(int)
    rows = np.floor(rows).astype(int)

    height, width = flooded.shape
    in_grid = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
    r, c = rows[in_grid], cols[in_grid]

    buildings = buildings[in_grid].copy()
    buildings["covered"] = covered[r, c]
    state = np.where(flooded[r, c], "flooded", np.where(near[r, c], "next_to_flooding", "not_flooded"))
    buildings["exposure"] = state

    buildings = buildings[buildings["covered"]].copy()
    total = len(buildings)
    print(f"\nBuildings inside the Sentinel-1 coverage: {total:,}")
    counts = buildings["exposure"].value_counts()
    for name in ["flooded", "next_to_flooding", "not_flooded"]:
        n = int(counts.get(name, 0))
        print(f"  {name}: {n:,} ({100 * n / total:.1f}%)")

    print("\nShare flooded by building type (types with at least 100 buildings):")
    by_type = buildings.groupby("building")["exposure"].agg(
        n="size", flooded=lambda s: (s == "flooded").mean() * 100)
    print(by_type[by_type["n"] >= 100].sort_values("n", ascending=False).round(1).to_string())

    buildings.to_parquet(f"{DATA_DIR}/building_exposure.parquet")
    print("\nSaved data/building_exposure.parquet")


if __name__ == "__main__":
    main()