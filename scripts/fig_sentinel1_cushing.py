"""Figure V2: radar sees through clouds. Sentinel-2 true colour on the cloudy pass next to the nearest Sentinel-1 VV backscatter.

Reads results/sentinel_cushing_pick.json (written by scripts/fig_sentinel_cushing.py), finds the Sentinel-1 RTC scene closest in time
to the cloudy optical pass, and draws both over the same window. Light 3x3 smoothing in linear power reduces speckle (display only).
Check without looking at the image: mean backscatter inside the OpenStreetMap tank footprints against the rest of the window.

Usage: python scripts/fig_sentinel1_cushing.py
Outputs: figures/V2_sentinel1_radar.png/.svg, results/sentinel1_cushing_pick.json
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
from pyproj import Transformer  # noqa: E402
from scipy.ndimage import uniform_filter  # noqa: E402

from altdata import plotting as P  # noqa: E402
from altdata import sentinel  # noqa: E402
from altdata.paths import RESULTS  # noqa: E402

ATTRIBUTION = "Contains modified Copernicus Sentinel data 2025 (ESA). Radar: Sentinel-1 RTC via Microsoft Planetary Computer. 10 m pixels, window about 6.8 km x 6.0 km."


def main() -> None:
    pick = json.loads((RESULTS / "sentinel_cushing_pick.json").read_text(encoding="utf-8"))
    window = tuple(pick["window"])
    cloudy = pick["cloudy"]
    d0 = pd.Timestamp(cloudy["date"])
    start, end = (d0 - pd.Timedelta(days=12)).date().isoformat(), (d0 + pd.Timedelta(days=12)).date().isoformat()
    s1 = sentinel.search_s1_rtc(window, start, end)
    if not s1:
        raise SystemExit("no Sentinel-1 RTC scene within 12 days of the cloudy pass")
    item = min(s1, key=lambda it: abs((pd.Timestamp(it.datetime.date()) - d0).days))
    gap = (pd.Timestamp(item.datetime.date()) - d0).days
    print("radar scene:", item.id, item.datetime.date(), f"({gap:+d} days from the optical pass)")

    db, transform, crs = sentinel.backscatter_db(item, window, "vv")
    lin = np.where(np.isfinite(db), 10 ** (db / 10), 0.0)
    sm = 10 * np.log10(np.maximum(uniform_filter(lin, size=3), 1e-6))
    lo, hi = np.nanpercentile(sm, [2, 99.7])

    # radar response inside the mapped tanks
    reg = pd.read_csv(RESULTS / "tank_registry.csv")
    reg = reg[(reg["lon"].between(window[0], window[2])) & (reg["lat"].between(window[1], window[3]))]
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(reg["lon"].to_numpy(), reg["lat"].to_numpy())
    col, row = (~transform) * (np.asarray(x), np.asarray(y))
    yy, xx = np.mgrid[0:sm.shape[0], 0:sm.shape[1]]
    inside = np.zeros(sm.shape, bool)
    for c, r, d in zip(col, row, reg["diameter_m"]):
        inside |= (xx - c) ** 2 + (yy - r) ** 2 <= max(d / 20.0, 1.5) ** 2
    db_in, db_out = float(np.nanmean(sm[inside])), float(np.nanmean(sm[~inside]))
    print(f"mean VV inside mapped tanks {db_in:.1f} dB, elsewhere {db_out:.1f} dB, difference {db_in - db_out:+.1f} dB")

    items = {it.id: it for it in sentinel.search((-96.78, 35.93, -96.72, 35.96), cloudy["date"], cloudy["date"])}
    img_k, _, _ = sentinel.true_colour(items[cloudy["id"]], window)

    P.theme()
    fig, ax = plt.subplots(1, 2, figsize=(9, 4.7))
    ax[0].imshow(img_k, interpolation="lanczos")
    ax[0].set_title(f"Optical · {cloudy['date']} · {cloudy['local_cloud']:.0%} cloud", fontsize=13.5)
    ax[1].imshow(sm, cmap="gray", vmin=lo, vmax=hi, interpolation="lanczos")
    ax[1].set_title(f"Radar (VV) · {item.datetime.date()} · {gap} days later", fontsize=13.5)
    for a, h, w in ((ax[0], img_k.shape[0], img_k.shape[1]), (ax[1], sm.shape[0], sm.shape[1])):
        a.set_axis_off()
        P.scale_bar(a, h, w, 100)
    ax[1].text(0.02, 0.985, "brighter = stronger return", transform=ax[1].transAxes, color="white", fontsize=13, va="top",
               path_effects=[pe.withStroke(linewidth=3.5, foreground="black")])
    fig.suptitle("Radar is unaffected by the clouds that hide the optical image", fontsize=15, y=0.985)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    P.finish(fig, "V2_sentinel1_radar", ATTRIBUTION)

    (RESULTS / "sentinel1_cushing_pick.json").write_text(json.dumps({
        "item": item.id, "date": str(item.datetime.date()), "days_from_cloudy_optical": gap, "orbit": item.properties.get("sat:orbit_state"),
        "valid_radar_pixels": float(np.isfinite(db).mean()), "optical_cloud_fraction": cloudy["local_cloud"], "shape": list(sm.shape),
        "mean_vv_db_inside_mapped_tanks": db_in, "mean_vv_db_elsewhere": db_out}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
