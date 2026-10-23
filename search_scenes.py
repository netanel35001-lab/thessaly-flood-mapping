"""List Sentinel-1 scenes over the Thessaly plain before and after Storm Daniel (Sept 2023)."""
from collections import defaultdict

import planetary_computer
from pystac_client import Client

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-1-rtc"  # radiometrically terrain-corrected Sentinel-1

# Study area: part of the Thessaly plain around Karditsa and Palamas (lon_min, lat_min, lon_max, lat_max)
BBOX = [21.70, 39.30, 22.20, 39.55]

BEFORE = "2023-08-20/2023-09-03"  # before the storm
AFTER = "2023-09-06/2023-09-20"   # during and after the flooding


def search(client, period):
    items = client.search(collections=[COLLECTION], bbox=BBOX, datetime=period).item_collection()
    return sorted(items, key=lambda i: i.datetime)


def describe(label, items):
    print(f"\n=== {label}: {len(items)} scenes ===")
    by_orbit = defaultdict(list)
    for item in items:
        p = item.properties
        key = (p.get("sat:orbit_state"), p.get("sat:relative_orbit"))
        by_orbit[key].append(item)
        print(item.datetime.strftime("%Y-%m-%d %H:%M"), key, item.id)
    return by_orbit


def main():
    client = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    before = describe("BEFORE", search(client, BEFORE))
    after = describe("AFTER", search(client, AFTER))

    shared = sorted(set(before) & set(after), key=str)
    print("\nOrbits (direction, relative orbit) present both before and after:", shared)


if __name__ == "__main__":
    main()