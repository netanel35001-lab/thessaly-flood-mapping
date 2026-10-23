"""Download OpenStreetMap building footprints for the Thessaly study area."""
from pathlib import Path

import osmnx as ox

from compare_dates import BBOX

DATA_DIR = Path("data")


def main():
    west, south, east, north = BBOX
    print("Downloading OSM buildings (this can take a few minutes)...")
    buildings = ox.features_from_bbox(bbox=(west, south, east, north), tags={"building": True})

    # Keep polygons only (drop building points) and a minimal set of columns.
    buildings = buildings[buildings.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    buildings = buildings[["geometry", "building"]].reset_index(drop=True)

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "osm_buildings.parquet"
    buildings.to_parquet(out_path)
    print(f"Saved {len(buildings):,} buildings to {out_path}")
    print(buildings["building"].value_counts().head(8).to_string())


if __name__ == "__main__":
    main()