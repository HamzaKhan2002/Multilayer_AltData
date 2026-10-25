"""Figure V3: the OpenStreetMap tank registry drawn over the clear-day Sentinel-2 image, with a brightness check of the alignment.

Reads results/tank_registry.csv (scripts/tank_registry.py) and results/sentinel_cushing_pick.json (scripts/fig_sentinel_cushing.py).
The registry is illustrative and incomplete: coverage and tags are volunteered. The alignment check compares the mean brightness
inside the mapped tank footprints with the rest of the window (tank roofs are bright at 10 m).

Usage: python scripts/fig_tank_registry.py
Outputs: figures/V3_tank_registry.png/.svg, results/tank_registry_check.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402
from pyproj import Transformer  # noqa: E402

from altdata import plotting as P  # noqa: E402
from altdata import sentinel  # noqa: E402
from altdata.paths import RESULTS  # noqa: E402

ATTRIBUTION = "Contains modified Copernicus Sentinel data 2025 (ESA); tanks (c) OpenStreetMap contributors (ODbL). Illustrative and incomplete registry."


def main() -> None:
    pick = json.loads((RESULTS / "sentinel_cushing_pick.json").read_text(encoding="utf-8"))
    window = tuple(pick["window"])
    reg = pd.read_csv(RESULTS / "tank_registry.csv")
    reg = reg[(reg["lon"].between(window[0], window[2])) & (reg["lat"].between(window[1], window[3]))].copy()
    items = {it.id: it for it in sentinel.search((-96.78, 35.93, -96.72, 35.96), pick["clear"]["date"], pick["clear"]["date"])}
    img, transform, crs = sentinel.true_colour(items[pick["clear"]["id"]], window)
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(reg["lon"].to_numpy(), reg["lat"].to_numpy())
    col, row = (~transform) * (np.asarray(x), np.asarray(y))
    reg["col"], reg["row"] = col, row
    reg["r_px"] = reg["diameter_m"] / 2 / 10.0

    gray = img.mean(axis=2)
    yy, xx = np.mgrid[0:gray.shape[0], 0:gray.shape[1]]
    inside = np.zeros(gray.shape, bool)
    for c, r, rp in zip(reg["col"], reg["row"], reg["r_px"]):
        inside |= (xx - c) ** 2 + (yy - r) ** 2 <= max(rp, 1.5) ** 2
    ratio = float(gray[inside].mean() / gray[~inside].mean())
    p75 = float(np.percentile(gray, 75))
    ok = [(0 <= round(r) < gray.shape[0]) and (0 <= round(c) < gray.shape[1]) for c, r in zip(reg["col"], reg["row"])]
    bright_share = float(np.mean([gray[int(round(r)), int(round(c))] > p75 for (c, r), k in zip(zip(reg["col"], reg["row"]), ok) if k]))
    out = {"n_tanks": int(len(reg)), "diameter_m_median": float(reg["diameter_m"].median()), "footprint_km2": float(reg["area_m2"].sum() / 1e6),
           "mean_brightness_inside_over_outside": ratio, "share_of_tank_centres_brighter_than_window_p75": bright_share,
           "pixels_across_median_tank": float(reg["diameter_m"].median() / 10)}
    (RESULTS / "tank_registry_check.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))

    P.theme()
    fig, ax = plt.subplots(1, 2, figsize=(9, 4.7), gridspec_kw={"width_ratios": [1.15, 1]})
    ax[0].imshow(img, interpolation="lanczos")
    for c, r, rp in zip(reg["col"], reg["row"], reg["r_px"]):
        ax[0].add_patch(Circle((c, r), max(rp, 2.2), fill=False, ec=P.CYAN, lw=0.9))
    ax[0].set_axis_off()
    ax[0].set_title(f"{len(reg)} mapped tanks · {pick['clear']['date']}", fontsize=13.5)
    P.scale_bar(ax[0], img.shape[0], img.shape[1], 100)
    ax[0].legend(handles=[Line2D([0], [0], marker="o", mfc="none", mec=P.CYAN, color="none", markersize=9, label="tank in the registry")],
                 loc="upper left", fontsize=12, framealpha=0.85)
    ax[1].hist(reg["diameter_m"].dropna(), bins=np.arange(10, 105, 5), color=P.VIOLET, alpha=0.95, zorder=3)
    ax[1].axvline(10, color=P.AMBER, lw=1.6, ls="--", zorder=4)
    ax[1].text(13, ax[1].get_ylim()[1] * 0.95, "one 10 m pixel", color=P.AMBER, fontsize=13, va="top")
    ax[1].set_xlabel("tank diameter (m)", fontsize=13.5)
    ax[1].set_ylabel("tanks", fontsize=13.5)
    ax[1].set_xlim(5, 100)
    ax[1].tick_params(labelsize=12.5)
    ax[1].set_title(f"Median {reg['diameter_m'].median():.0f} m, about {reg['diameter_m'].median() / 10:.0f} pixels", fontsize=13.5)
    ax[1].set_axisbelow(True)
    ax[1].grid(axis="x", visible=False)
    fig.suptitle("Tank registry (OpenStreetMap; incomplete, illustrative)", fontsize=15, y=0.985)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    P.finish(fig, "V3_tank_registry", ATTRIBUTION)


if __name__ == "__main__":
    main()
