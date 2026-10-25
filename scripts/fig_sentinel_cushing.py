"""Figure V1: Sentinel-2 true-colour view of the Cushing, Oklahoma tank farms on a clear day and on a cloudy day, plus a zoom.

Steps: (1) list Sentinel-2 L2A scenes whose footprint contains the window and measure the local cloud fraction in the scene
classification (SCL); (2) pick a clear scene (<= 0.5% cloud) and a mostly cloudy scene close in time, in the low-sun season;
(3) draw both side by side, and a 1 km zoom on the densest cluster of the OpenStreetMap registry (scripts/tank_registry.py).

Usage: python scripts/fig_sentinel_cushing.py [--refresh]      (--refresh re-measures the cloud fraction of every scene)
Outputs: figures/V1_sentinel2_cushing.png/.svg, figures/V1b_sentinel2_zoom.png/.svg, results/sentinel_cushing_candidates.csv,
         results/sentinel_cushing_pick.json
Attribution: Contains modified Copernicus Sentinel data 2025 (ESA).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from pyproj import Transformer  # noqa: E402

from altdata import plotting as P  # noqa: E402
from altdata import sentinel  # noqa: E402
from altdata.paths import RESULTS  # noqa: E402

START, END = "2025-03-01", "2026-09-30"
SEARCH_BBOX = (-96.78, 35.93, -96.72, 35.96)
WINDOW = (-96.782, 35.915, -96.708, 35.968)       # about 6.8 km x 5.9 km; contains all 333 OpenStreetMap tanks of the area
ZOOM_SIZE = (0.0111, 0.0090)                      # about 1 km x 1 km (lon, lat degrees)
SEASON = ("2025-10-01", "2026-03-31")
ATTR_WINDOW = "Contains modified Copernicus Sentinel data 2025 (ESA). True colour, 10 m pixels, window about 6.8 km x 6.0 km."
ATTR_ZOOM = "Contains modified Copernicus Sentinel data 2025 (ESA). Crop about 1 km x 1 km, 10 m pixels, smoothed for display."


def candidates() -> pd.DataFrame:
    cache = RESULTS / "sentinel_cushing_candidates.csv"
    if cache.exists() and "--refresh" not in sys.argv:
        return pd.read_csv(cache)
    rows = []
    for it in sentinel.search(SEARCH_BBOX, START, END):
        try:
            f = sentinel.local_cloud_fraction(it, WINDOW)
        except Exception as e:  # noqa: BLE001
            print("skip", it.id, type(e).__name__)
            continue
        if f is None:
            continue
        rows.append({"id": it.id, "date": it.datetime.date().isoformat(), "scene_cloud_pct": it.properties.get("eo:cloud_cover"),
                     "local_cloud": f, "tile": it.properties.get("grid:code")})
    df = pd.DataFrame(rows)
    df.to_csv(cache, index=False)
    return df


def densest_zoom() -> tuple:
    """1 km window holding the most tanks of the OpenStreetMap registry."""
    reg = RESULTS / "tank_registry.csv"
    if not reg.exists():
        return (-96.7475, 35.9325, -96.7364, 35.9415)
    t = pd.read_csv(reg)
    best = (-1, None)
    for lon0 in np.arange(WINDOW[0], WINDOW[2] - ZOOM_SIZE[0], 0.0005):
        for lat0 in np.arange(WINDOW[1], WINDOW[3] - ZOOM_SIZE[1], 0.0005):
            n = int(((t["lon"] >= lon0) & (t["lon"] < lon0 + ZOOM_SIZE[0]) & (t["lat"] >= lat0) & (t["lat"] < lat0 + ZOOM_SIZE[1])).sum())
            if n > best[0]:
                best = (n, (lon0, lat0, lon0 + ZOOM_SIZE[0], lat0 + ZOOM_SIZE[1]))
    print(f"densest 1 km window holds {best[0]} OpenStreetMap tanks: {tuple(round(float(v), 4) for v in best[1])}")
    return best[1]


def pick(df: pd.DataFrame):
    s = df[(df["date"] >= SEASON[0]) & (df["date"] <= SEASON[1])].copy()
    s["d"] = pd.to_datetime(s["date"])
    clear = s[s["local_cloud"] <= 0.005]
    cloudy = s[(s["local_cloud"] >= 0.6) & (s["local_cloud"] <= 0.97)]
    best = None
    for _, c in clear.iterrows():
        for _, k in cloudy.iterrows():
            gap = abs((c["d"] - k["d"]).days)
            if best is None or gap < best[0]:
                best = (gap, c, k)
    if best is None:
        raise SystemExit("no clear/cloudy pair found in the season; widen SEASON or the cloud thresholds")
    return best[1], best[2]


def main() -> None:
    df = candidates()
    n_clear, n_cloudy = int((df["local_cloud"] <= 0.005).sum()), int((df["local_cloud"] >= 0.6).sum())
    print(f"{len(df)} scenes contain the window; {n_clear} are clear, {n_cloudy} are at least 60% cloudy")
    clear, cloudy = pick(df)
    print("clear :", clear["id"], clear["date"], f"local cloud {clear['local_cloud']:.1%}")
    print("cloudy:", cloudy["id"], cloudy["date"], f"local cloud {cloudy['local_cloud']:.1%}")
    items = {it.id: it for it in sentinel.search(SEARCH_BBOX, START, END)}
    img_c, transform, crs = sentinel.true_colour(items[clear["id"]], WINDOW)
    img_k, _, _ = sentinel.true_colour(items[cloudy["id"]], WINDOW)
    zoom = densest_zoom()
    img_z, _, _ = sentinel.true_colour(items[clear["id"]], zoom)
    (RESULTS / "sentinel_cushing_pick.json").write_text(json.dumps({
        "window": WINDOW, "zoom": [float(v) for v in zoom],
        "clear": {k: (v.item() if hasattr(v, "item") else v) for k, v in clear.items() if k != "d"},
        "cloudy": {k: (v.item() if hasattr(v, "item") else v) for k, v in cloudy.items() if k != "d"},
        "scenes_in_window": int(len(df)), "scenes_clear_le_0.5pct": n_clear, "scenes_cloudy_ge_60pct": n_cloudy,
        "period": [START, END]}, indent=2, default=str), encoding="utf-8")

    # crop marker on the clear panel
    to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    (c0, r0) = (~transform) * to_utm.transform(zoom[0], zoom[3])
    (c1, r1) = (~transform) * to_utm.transform(zoom[2], zoom[1])

    P.theme()
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 5.4))
    for a, img, lab, cl in ((ax[0], img_c, "Clear pass", clear), (ax[1], img_k, "Cloudy pass", cloudy)):
        a.imshow(img, interpolation="lanczos")
        a.set_axis_off()
        a.set_title(f"{lab} · {cl['date']} · {cl['local_cloud']:.0%} cloud", fontsize=14.5, color=P.FG)
        P.scale_bar(a, img.shape[0], img.shape[1], 100)
    ax[0].add_patch(Rectangle((c0, r0), c1 - c0, r1 - r0, fill=False, ec=P.AMBER, lw=1.6))
    ax[0].text(c1 + 8, r0, "zoom", color=P.AMBER, fontsize=14, va="top", fontweight="bold", path_effects=[pe.withStroke(linewidth=3.5, foreground="black")])
    fig.suptitle("Cushing, Oklahoma: the same tank farms from orbit (Sentinel-2, 10 m optical)", fontsize=15.5, y=0.985)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    P.finish(fig, "V1_sentinel2_cushing", ATTR_WINDOW)

    fig, a = plt.subplots(figsize=(3.6, 3.8))
    a.imshow(img_z, interpolation="bicubic")
    a.set_axis_off()
    a.set_title(f"1 km zoom · {clear['date']}", fontsize=13)
    P.scale_bar(a, img_z.shape[0], img_z.shape[1], 100, km=0.2, label="200 m")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    P.finish(fig, "V1b_sentinel2_zoom", ATTR_ZOOM)
    print("zoom shape", img_z.shape, "window shapes", img_c.shape, img_k.shape)


if __name__ == "__main__":
    main()
