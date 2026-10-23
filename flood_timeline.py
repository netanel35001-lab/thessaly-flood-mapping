"""Flooded area over time, using every post-storm Sentinel-1 date and orbit available."""
import csv
from datetime import datetime

import matplotlib.pyplot as plt
import planetary_computer
from pystac_client import Client

import compare_dates as cd
from flood_mask import PIXEL_KM2, WATER_DB, flood_mask

# (orbit, date before the storm, dates after the storm)
RUNS = [
    (102, "2023-08-26", ["2023-09-07", "2023-09-19"]),
    (80, "2023-08-25", ["2023-09-06", "2023-09-18"]),
    (7, "2023-09-01", ["2023-09-13"]),
]


def main():
    client = Client.open(cd.STAC_URL, modifier=planetary_computer.sign_inplace)
    rows = []
    for orbit, day_before, days_after in RUNS:
        cd.ORBIT = orbit  # switch the helper to this orbit
        before = cd.load_db(client, day_before)
        for day_after in days_after:
            after = cd.load_db(client, day_after)
            flooded_km2 = float(flood_mask(before, after, WATER_DB).sum()) * PIXEL_KM2
            covered_km2 = float(after.notnull().sum()) * PIXEL_KM2
            rows.append({"orbit": orbit, "date": day_after, "flooded_km2": round(flooded_km2, 1),
                         "covered_km2": round(covered_km2), "flooded_pct": round(100 * flooded_km2 / covered_km2, 1)})

    rows.sort(key=lambda r: r["date"])
    print("\norbit  date        flooded_km2  covered_km2  flooded_pct")
    for r in rows:
        print(f"{r['orbit']:>5}  {r['date']}  {r['flooded_km2']:>11}  {r['covered_km2']:>11}  {r['flooded_pct']:>10}")

    cd.OUT_DIR.mkdir(exist_ok=True)
    with open(cd.OUT_DIR / "flood_timeline.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for orbit in sorted({r["orbit"] for r in rows}):
        pts = [r for r in rows if r["orbit"] == orbit]
        ax.plot([datetime.fromisoformat(r["date"]) for r in pts], [r["flooded_km2"] for r in pts],
                marker="o", linestyle="", label=f"orbit {orbit}")
    ax.set_ylabel("Flooded area (km2)")
    ax.set_title("Flooded area in the study area after Storm Daniel (Sentinel-1)")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(cd.OUT_DIR / "flood_timeline.png", dpi=120)
    print("\nSaved outputs/flood_timeline.csv and outputs/flood_timeline.png")


if __name__ == "__main__":
    main()