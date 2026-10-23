"""Load two Sentinel-1 dates (same orbit) over Thessaly and show the backscatter change in dB."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import planetary_computer
from odc.stac import load
from pystac_client import Client

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-1-rtc"
BBOX = [21.70, 39.30, 22.20, 39.55]
ORBIT = 102
DATE_BEFORE = "2023-08-26"
DATE_AFTER = "2023-09-07"
CRS = "EPSG:32634"  # UTM zone 34N covers the study area
RESOLUTION = 20     # meters per pixel (coarser than the native 10 m, to keep it fast)

OUT_DIR = Path("outputs")


def load_db(client, day):
    """Mosaic the scenes of one day and return VV backscatter in dB."""
    items = client.search(collections=[COLLECTION], bbox=BBOX, datetime=day).item_collection()
    items = [i for i in items if i.properties.get("sat:relative_orbit") == ORBIT]
    print(day, "scenes:", len(items))
    ds = load(items, bands=["vv"], bbox=BBOX, crs=CRS, resolution=RESOLUTION, groupby="solar_day")
    vv = ds["vv"].isel(time=0)
    vv = vv.where(vv > 0)  # nodata and zeros become NaN
    return 10 * np.log10(vv)


def main():
    client = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    before = load_db(client, DATE_BEFORE)
    after = load_db(client, DATE_AFTER)
    diff = after - before

    print("Image size (pixels):", before.shape)
    print("Mean change (dB):", float(diff.mean()))
    print("Share of pixels darker by more than 3 dB:", float((diff < -3).mean()))

    OUT_DIR.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for ax, data, title, vmin, vmax, cmap in [
        (axes[0], before, f"VV before ({DATE_BEFORE})", -25, 0, "gray"),
        (axes[1], after, f"VV after ({DATE_AFTER})", -25, 0, "gray"),
        (axes[2], diff, "Change (after minus before, dB)", -10, 10, "RdBu"),
    ]:
        im = ax.imshow(data, vmin=vmin, vmax=vmax, cmap=cmap)
        ax.set_title(title)
        ax.axis("off")
        fig.colorbar(im, ax=ax, shrink=0.6)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "change_preview.png", dpi=120)
    print("Saved outputs/change_preview.png")


if __name__ == "__main__":
    main()