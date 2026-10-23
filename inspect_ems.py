"""List every layer in the downloaded Copernicus EMS products: geometry, size, columns and sample values."""
from pathlib import Path

import geopandas as gpd

EMS_DIR = Path("data") / "ems"
MAX_VALUES = 8  # how many distinct values to show per text column


def describe(path):
    gdf = gpd.read_file(path)
    print("=" * 80)
    print("FILE:", path.parent.name, "/", path.name)
    print(f"  rows: {len(gdf)} | geometry: {sorted(gdf.geom_type.dropna().unique())} | CRS: {gdf.crs}")
    for col in gdf.columns:
        if col == "geometry":
            continue
        values = gdf[col].dropna().unique()
        if gdf[col].dtype == object:
            shown = ", ".join(str(v) for v in values[:MAX_VALUES])
            more = f" ... (+{len(values) - MAX_VALUES} more)" if len(values) > MAX_VALUES else ""
            print(f"  - {col} [text, {len(values)} distinct]: {shown}{more}")
        else:
            print(f"  - {col} [{gdf[col].dtype}]: {len(values)} distinct")


def main():
    shapefiles = sorted(EMS_DIR.glob("*/*.shp"))
    print(f"Found {len(shapefiles)} shapefiles under {EMS_DIR}\n")
    for path in shapefiles:
        try:
            describe(path)
        except Exception as err:  # keep going if one layer fails to read
            print("=" * 80)
            print("FILE:", path.name, "-> could not read:", err)


if __name__ == "__main__":
    main()