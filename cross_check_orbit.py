"""Cross-check the flood mask between two independent Sentinel-1 orbits acquired about a day apart."""
import planetary_computer
from pystac_client import Client

import compare_dates as cd
from flood_mask import PIXEL_KM2, WATER_DB, flood_mask

# orbit: (date before the storm, date after the flooding)
RUNS = {
    102: ("2023-08-26", "2023-09-19"),
    80: ("2023-08-25", "2023-09-18"),
}


def mask_for(client, orbit):
    """Flood mask and image coverage for one orbit."""
    cd.ORBIT = orbit  # switch the helper to this orbit
    day_before, day_after = RUNS[orbit]
    before = cd.load_db(client, day_before)
    after = cd.load_db(client, day_after)
    return flood_mask(before, after, WATER_DB).values, after.notnull().values


def main():
    client = Client.open(cd.STAC_URL, modifier=planetary_computer.sign_inplace)
    mask_a, cover_a = mask_for(client, 102)
    mask_b, cover_b = mask_for(client, 80)
    assert mask_a.shape == mask_b.shape, "grids differ"

    covered = cover_a & cover_b
    a = mask_a & covered
    b = mask_b & covered
    inter = (a & b).sum()
    union = (a | b).sum()
    print(f"\nArea covered by both orbits: {covered.sum() * PIXEL_KM2:,.0f} km2")
    print(f"Flooded, orbit 102 ({RUNS[102][1]}): {a.sum() * PIXEL_KM2:,.1f} km2")
    print(f"Flooded, orbit 80 ({RUNS[80][1]}): {b.sum() * PIXEL_KM2:,.1f} km2")
    print(f"Flooded in both: {inter * PIXEL_KM2:,.1f} km2")
    print(f"Agreement (intersection over union): {inter / union:.2f}")
    print(f"Share of the orbit-80 flooding also found by orbit 102: {inter / b.sum():.2f}")
    print(f"Share of the orbit-102 flooding also found by orbit 80: {inter / a.sum():.2f}")


if __name__ == "__main__":
    main()