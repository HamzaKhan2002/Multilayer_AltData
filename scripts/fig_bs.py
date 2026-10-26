"""Figures of the BS tests (deck style; 300 dpi PNG + SVG in figures/). Run after scripts/bs2_aggregate.py.

figures/BS1_shadow_model   crescent geometry | observed B04 pixels of one large tank on a clear winter date | fitted model pixels
figures/BS1_identifiability simulated RMSE of d_hat and empirical stability by sun elevation
figures/BS0_availability    share of EIA weeks with a usable acquisition, by month of year, Sentinel-2 vs Sentinel-1
figures/BS2_proxy_vs_eia    Delta V against the first-published EIA Cushing change, primary sample

The example tank and date of the first figure follow a fixed rule (largest registry diameter; clear acquisition with the lowest sun elevation),
not the quality of the fit. Attribution: Contains modified Copernicus Sentinel data (ESA).
"""
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Circle, Patch  # noqa: E402

from altdata import plotting as P  # noqa: E402
from altdata import tankshadow as ts  # noqa: E402
from altdata import v2common as V  # noqa: E402

W = 10.5
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SRC_ESA = "Contains modified Copernicus Sentinel data (ESA). "


def _style(ax, legend=False) -> None:
    ax.tick_params(labelsize=12)
    if legend:
        ax.legend(fontsize=12, frameon=True)


# ------------------------------------------------------------------ figure 1
def pick_example(fits: pd.DataFrame, summ: pd.DataFrame, reg: pd.DataFrame):
    """Largest registry tank with an estimate on a clear (scene cloud <= 5%) acquisition; its lowest-sun such acquisition."""
    ok = fits[fits["status"].isin(V.KEPT)].merge(summ[["acq_id", "cloud_cover"]], on="acq_id")
    ok = ok[ok["cloud_cover"] <= 5.0]
    if ok.empty:
        return None
    osm = ok.loc[ok["diameter_m"].idxmax(), "osm_id"]
    row = ok[ok["osm_id"] == osm].sort_values(["sun_elev", "datetime_utc"]).iloc[0]
    return row


def fig_shadow_model(fits: pd.DataFrame, summ: pd.DataFrame, reg: pd.DataFrame, cache_dir: Path, name: str = "BS1_shadow_model") -> None:
    from pyproj import Transformer

    ex = pick_example(fits, summ, reg)
    P.theme()
    fig, axs = plt.subplots(1, 3, figsize=(W, 4.0), gridspec_kw={"width_ratios": [1, 1, 1], "wspace": 0.1})
    # (1) geometry of the crescent
    ax = axs[0]
    R, d, az, el = 30.0, 6.0, 160.0, 30.0
    gxs, gys = np.arange(-R - 10, R + 14, 0.5), np.arange(-R - 12, R + 10, 0.5)
    gx, gy = np.meshgrid(gxs, gys)
    inside, shadow = ts.shadow_mask(gx, gy, R, d, az, el)
    img = np.where(shadow, 2, np.where(inside, 1, 0)).astype(float)
    from matplotlib.colors import ListedColormap
    ax.imshow(img, extent=(gxs[0], gxs[-1] + 0.5, gys[0], gys[-1] + 0.5), origin="lower",
              cmap=ListedColormap([P.PANEL, "#cbd5e1", "#1e3a8a"]), vmin=0, vmax=2, interpolation="nearest")
    ax.add_patch(Circle((0, 0), R, fill=False, ec=P.FG, lw=2))
    u = ts.sun_unit(az)
    ax.annotate("", xy=(u[0] * 40, u[1] * 40), xytext=(u[0] * 31, u[1] * 31),
                arrowprops={"arrowstyle": "-|>", "color": P.AMBER, "lw": 3, "mutation_scale": 18})
    ax.text(u[0] * 40 + 3, u[1] * 40, "sun", color=P.AMBER, fontsize=13, fontweight="bold", ha="left", va="center")
    s = d / np.tan(np.radians(el))
    ax.set_xlim(gxs[0], gxs[-1] + 0.5)
    ax.set_ylim(gys[0], gys[-1] + 0.5)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title("Shadow geometry", fontsize=13)
    ax.legend(handles=[Patch(fc="#cbd5e1", label="lit roof"), Patch(fc="#1e3a8a", label="shadow")], loc="upper center",
              bbox_to_anchor=(0.5, -0.01), ncol=2, fontsize=12, frameon=False, handlelength=1.1, columnspacing=1.2)
    ax.text(0.5, -0.17, f"roof {d:.0f} m below the rim, sun {el:.0f}° high:\ns = d / tan θ = {s:.1f} m", transform=ax.transAxes, ha="center", va="top", fontsize=12)
    src = SRC_ESA + "Schematic: R = 30 m, d = 6 m, sun azimuth 160°, elevation 30°; amber arrow: direction of the sun."
    if ex is None:
        for a in axs[1:]:
            a.set_axis_off()
            a.text(0.5, 0.5, "no example available", transform=a.transAxes, ha="center", va="center", fontsize=13)
        P.finish(fig, name, src)
        return
    tank = reg[reg["osm_id"] == ex["osm_id"]].iloc[0]
    sm = summ[summ["acq_id"] == ex["acq_id"]].iloc[0]
    with np.load(cache_dir / f"{ex['acq_id']}.npz", allow_pickle=False) as z:
        red, tr, crs = z["red"], tuple(float(v) for v in z["transform"]), str(z["crs"])
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(float(tank["lon"]), float(tank["lat"]))
    cx, cy, Rr = x + float(sm["shift_x_m"]), y + float(sm["shift_y_m"]), float(tank["R"])
    rows, cols, qx, qy = ts.block(cx, cy, Rr + 15, tr[2], tr[5], red.shape)
    nr, nc = len(np.unique(rows)), len(np.unique(cols))
    obs = red[rows, cols].astype(float)
    keep, F = ts.pixel_design(qx, qy, Rr, float(ex["sun_az"]), float(ex["sun_elev"]))
    j = int(np.argmin(np.abs(ts.D_GRID - float(ex["d_hat"]))))
    model = np.full(rows.size, np.nan)
    model[keep] = float(ex["a"]) * (1 - F[:, j]) + float(ex["b"]) * F[:, j]
    ext = (qx.min() - 5, qx.max() + 5, qy.min() - 5, qy.max() + 5)
    vmin, vmax = np.percentile(obs, 2), np.percentile(obs, 98)
    us = ts.sun_unit(float(ex["sun_az"]))
    t2, t3 = "Observed B04 (10 m pixels)", rf"Fitted: $\hat{{d}}$ = {ex['d_hat']:.1f} m [{ex['d_lo']:.1f}, {ex['d_hi']:.1f}]"
    for a, vals, title in ((axs[1], obs, t2), (axs[2], model, t3)):
        a.imshow(vals.reshape(nr, nc), extent=ext, origin="upper", cmap="magma", vmin=vmin, vmax=vmax, interpolation="nearest")
        a.add_patch(Circle((0, 0), Rr, fill=False, ec="white", lw=1.6, ls="--"))
        a.annotate("", xy=(us[0] * 0.8 * Rr, us[1] * 0.8 * Rr), xytext=(us[0] * 0.2 * Rr, us[1] * 0.2 * Rr),
                   arrowprops={"arrowstyle": "-|>", "color": P.AMBER, "lw": 2.4, "mutation_scale": 16})
        a.set_xticks([])
        a.set_yticks([])
        a.set_title(title, fontsize=13)
        a.grid(False)
    axs[1].set_xlabel(f"{ex['datetime_utc'][:10]}, sun {ex['sun_elev']:.0f}° high", fontsize=12)
    axs[2].set_xlabel("interior pixels only (fitted)", fontsize=12)
    P.finish(fig, name, src + f" Tank {ex['osm_id']} ({tank['diameter_m']:.0f} m), acquisition {ex['acq_id']} chosen by a fixed rule (largest registry "
                         "diameter, clear scene, lowest sun), not by the quality of the fit. Dashed circle: registry outline after registration.")


# ------------------------------------------------------------------ figure 2
def fig_identifiability(ident: pd.DataFrame, stab: pd.DataFrame, name: str = "BS1_identifiability") -> None:
    P.theme()
    fig, axs = plt.subplots(1, 2, figsize=(W, 4.7))
    ax = axs[0]
    bins = [b for b in ident["sun_bin"].unique() if b != "ALL"]
    bins = sorted(bins, key=lambda s: float(str(s).split("-")[0]))
    cols = {2: P.CYAN, 6: P.BLUE, 10: P.VIOLET, 14: P.AMBER}
    for d, c in cols.items():
        s = ident[(ident["d_true"].astype(str) == str(d)) & (ident["sun_bin"] != "ALL")].set_index("sun_bin").reindex(bins)
        ax.plot(range(len(bins)), s["rmse_m"], marker="o", lw=2.2, color=c, label=f"true d = {d} m")
    s = ident[(ident["d_true"].astype(str) == "all") & (ident["sun_bin"] != "ALL")].set_index("sun_bin").reindex(bins)
    ax.plot(range(len(bins)), s["rmse_m"], marker="s", lw=3.2, color=P.FG, label="all depths")
    ax.set_xticks(range(len(bins)))
    ax.set_xticklabels(bins)
    ax.set_xlabel("sun elevation (degrees)")
    ax.set_ylabel(r"RMSE of $\hat{d}$ (m)")
    ax.set_title("Simulated precision (illustrative)", fontsize=13.5)
    ax.set_ylim(bottom=0)
    _style(ax, legend=True)
    ax = axs[1]
    st = stab[(stab["scope"] == "pooled") & (stab["sun_bin"] != "ALL")] if len(stab) else stab
    if len(st):
        for gc, c, lab in (("all", P.FG, "all pairs"), ("same_pass", P.CYAN, "same pass (< 1 h)"), ("later_days", P.AMBER, "1-2 days apart")):
            s = st[st["gap_class"] == gc].set_index("sun_bin").reindex(bins)
            if s["robust_spread_m"].notna().any():
                ax.plot(range(len(bins)), s["robust_spread_m"], marker="o", lw=2.4, color=c, label=lab)
        n_all = st[st["gap_class"] == "all"].set_index("sun_bin").reindex(bins)["n_pairs"].fillna(0).astype(int)
        for i, n in enumerate(n_all):
            ax.text(i, 0.985, f"n={n}", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=11.5, color=P.MUTED)
        ax.set_xticks(range(len(bins)))
        ax.set_xticklabels(bins)
        ax.set_ylim(bottom=0)
        ax.legend(fontsize=12, frameon=True, loc="center right")
        ax.tick_params(labelsize=12)
    else:
        ax.text(0.5, 0.5, "no pair of clear acquisitions\nwithin 2 days", transform=ax.transAxes, ha="center", va="center", fontsize=13)
    ax.set_xlabel("sun elevation (degrees)")
    ax.set_ylabel(r"robust spread of $\hat{d}$ differences (m)")
    ax.set_title("Measured stability, pairs ≤ 2 days apart", fontsize=13.5)
    P.finish(fig, name, SRC_ESA + "Left: synthetic tanks with the registry diameters, sun angles of the catalogue, random centre offsets up to 5 m, "
                        "noise of the real fits. Right: 1.4826 x MAD of d-hat differences between acquisitions at most 2 days apart (includes real roof movement); "
                        "n = number of pairs.")


# ------------------------------------------------------------------ figure 3
def fig_availability(av: pd.DataFrame, name: str = "BS0_availability") -> None:
    P.theme()
    a = av.assign(month=pd.to_datetime(av["week_ending"]).dt.month)
    g = a.groupby("month")[["s2_usable_api", "s2_usable_eia", "s1_usable_api", "s1_usable_eia"]].mean().reindex(range(1, 13)) * 100
    fig, ax = plt.subplots(figsize=(W, 4.6))
    x = np.arange(12)
    ax.bar(x - 0.2, g["s2_usable_api"], 0.38, color=P.BLUE, label="Sentinel-2 (≥ 50% of tank area clear)")
    ax.bar(x + 0.2, g["s1_usable_api"], 0.38, color=P.VIOLET, label="Sentinel-1 (radar, any pass)")
    ax.plot(x - 0.2, g["s2_usable_eia"], ls="none", marker="_", ms=16, mew=2.5, color=P.FG)
    ax.plot(x + 0.2, g["s1_usable_eia"], ls="none", marker="_", ms=16, mew=2.5, color=P.FG, label="deadline Wednesday 10:30 ET (bars: Tuesday 16:30 ET)")
    ax.set_xticks(x)
    ax.set_xticklabels(MONTHS)
    ax.set_ylim(0, 100)
    ax.set_ylabel("EIA weeks with a usable acquisition (%)")
    ax.set_title(f"Availability within ±2 days of the Friday stock reference, {av['week_ending'].min()[:4]}-{av['week_ending'].max()[:4]}, {len(av)} weeks", fontsize=14)
    _style(ax, legend=True)
    P.finish(fig, name, SRC_ESA + "Sentinel-2 L2A (Earth Search) and Sentinel-1 RTC (Planetary Computer) catalogues; availability = acquisition time + 24 h "
                        "before the API (Tuesday 16:30 ET) or EIA (Wednesday 10:30 ET) release; Sentinel-2 requires at least 50% of the tank area clear.")


# ------------------------------------------------------------------ figure 4
def fig_proxy(weekly: pd.DataFrame, bs2: dict, name: str = "BS2_proxy_vs_eia") -> None:
    P.theme()
    d = weekly[weekly["in_primary"].astype(bool)]
    fig, ax = plt.subplots(figsize=(W * 0.75, 5.0))
    p = bs2["primary"]
    if len(d):
        ax.scatter(d["dV_kbbl"], d["eia_change_kbbl"], s=46, color=P.BLUE, alpha=0.85, edgecolor=P.BG, lw=0.6)
        if p.get("slope_eia_kbbl_per_kbbl") is not None:
            xs = np.array([d["dV_kbbl"].min(), d["dV_kbbl"].max()])
            ax.plot(xs, p["intercept_kbbl"] + p["slope_eia_kbbl_per_kbbl"] * xs, color=P.AMBER, lw=2.4)
    lo, hi = p["fisher_ci95"]
    f2 = lambda v: "n/a" if v is None or not np.isfinite(v) else f"{v:.2f}"  # noqa: E731
    txt = f"r = {f2(p['r'])}  [{f2(lo)}, {f2(hi)}]\nn = {p['n']} weeks\n{p['verdict']}"
    ax.text(0.03, 0.97, txt, transform=ax.transAxes, va="top", fontsize=13.5, color=P.FG, bbox={"boxstyle": "round,pad=0.4", "fc": P.PANEL, "ec": "#334155"})
    ax.axhline(0, color="#475569", lw=1)
    ax.axvline(0, color="#475569", lw=1)
    ax.set_xlabel("satellite proxy ΔV (kbbl)")
    ax.set_ylabel("EIA Cushing weekly change (kbbl)")
    ax.set_title("Satellite roof-depth proxy vs EIA, primary sample", fontsize=14)
    _style(ax)
    P.finish(fig, name, SRC_ESA + "ΔV: week-on-week change of the volume under the roofs of the tanks measured at both dates; EIA: Cushing change as first published. "
                        "Primary sample: consecutive weeks, sun elevation ≤ 45°, identified tanks covering ≥ 50% of the tank area at both dates. "
                        "95% interval by Fisher z; moving-block bootstrap in results/v2/BS2/bs2.json.")


def main() -> int:
    V.ensure_dirs()
    V.assert_prereg_v2_frozen()
    failures = 0
    jobs = {
        "BS1_shadow_model": lambda: fig_shadow_model(V.read_fits(), V.read_acq_summary(), V.registry(), V.CACHE),
        "BS1_identifiability": lambda: fig_identifiability(pd.read_csv(V.BS1 / "identifiability.csv"), pd.read_csv(V.BS1 / "stability.csv")),
        "BS0_availability": lambda: fig_availability(pd.read_csv(V.BS0 / "availability.csv")),
        "BS2_proxy_vs_eia": lambda: fig_proxy(pd.read_csv(V.BS2 / "weekly_table.csv"), json.loads((V.BS2 / "bs2.json").read_text(encoding="utf-8"))),
    }
    for k, fn in jobs.items():
        try:
            fn()
            print(f"wrote figures/{k}.png/.svg", flush=True)
        except Exception as e:  # noqa: BLE001  (one missing input must not hide the other figures)
            failures += 1
            print(f"FAILED {k}: {type(e).__name__}: {e}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
