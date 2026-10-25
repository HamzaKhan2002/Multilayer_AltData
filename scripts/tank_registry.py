"""Tank registry for Cushing, Oklahoma from OpenStreetMap (figure V3 input; illustrative, not a validated registry).

Writes results/tank_registry.csv and results/tank_registry_summary.json: number of tanks, equivalent diameters, the densest
1 km cell, and the tank count inside the satellite window.

Usage: python scripts/tank_registry.py
Data: (c) OpenStreetMap contributors (ODbL).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata import osm  # noqa: E402
from altdata.paths import RESULTS  # noqa: E402

AREA = (-96.82, 35.89, -96.68, 35.99)           # satellite window plus a margin
WINDOW = (-96.782, 35.915, -96.708, 35.968)     # satellite window used in fig_sentinel_cushing.py


def main() -> None:
    tanks = pd.DataFrame(osm.storage_tanks(AREA))
    tanks.to_csv(RESULTS / "tank_registry.csv", index=False)
    d = tanks["diameter_m"].dropna()
    inside = tanks[(tanks["lon"].between(WINDOW[0], WINDOW[2])) & (tanks["lat"].between(WINDOW[1], WINDOW[3]))]
    # density on a 0.01 degree grid (about 0.9 km x 1.1 km)
    gx = np.floor((tanks["lon"] - AREA[0]) / 0.01).astype(int)
    gy = np.floor((tanks["lat"] - AREA[1]) / 0.01).astype(int)
    cells = tanks.assign(gx=gx, gy=gy).groupby(["gx", "gy"]).size().sort_values(ascending=False)
    top = [{"lon_min": round(AREA[0] + gx_ * 0.01, 3), "lat_min": round(AREA[1] + gy_ * 0.01, 3), "tanks": int(n)} for (gx_, gy_), n in cells.head(8).items()]
    summary = {"source": "OpenStreetMap contributors (ODbL), Overpass API", "area": AREA, "n_tanks": int(len(tanks)),
               "with_polygon": int(d.shape[0]), "diameter_m_median": float(d.median()), "diameter_m_p10_p90": [float(d.quantile(.1)), float(d.quantile(.9))],
               "footprint_km2": float(tanks["area_m2"].sum() / 1e6), "n_in_window": int(len(inside)), "window": WINDOW, "densest_cells_0.01deg": top}
    (RESULTS / "tank_registry_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
