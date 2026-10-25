"""Figures for the pre-registered tests, drawn from results/T*.json (no statistic is computed here).

Usage: python scripts/fig_tests.py [--only T1 T2 ...]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from altdata import plotting as P  # noqa: E402
from altdata.paths import RESULTS  # noqa: E402

GREY = "#64748b"


def mn(v: float, p: int = 1) -> str:
    """Signed number with a true minus sign (U+2212), for annotations."""
    return f"{v:+.{p}f}".replace("-", "\u2212")


def load(name: str) -> dict:
    return json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8"))


def ratio_bar(ax, x, r, color):
    ax.bar(x, r["ratio"] - 1, bottom=1, color=color, width=0.62, zorder=3)
    ax.errorbar(x, r["ratio"], yerr=[[r["ratio"] - r["ci95"][0]], [r["ci95"][1] - r["ratio"]]], color=P.FG, capsize=6, lw=1.8, zorder=4)
    ax.plot([x], [r["ratio"]], marker="D", color=P.FG, ms=6, zorder=5)
    ax.text(x, r["ci95"][1] + 0.012, f"{r['ratio']:.2f}", ha="center", color=P.FG, fontsize=17, fontweight="bold", zorder=6)


def fig_t1() -> None:
    d = load("T1")["markets"]
    P.theme()
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.8), gridspec_kw={"width_ratios": [1.15, 1]})
    left = [(d["WTI"]["primary"], "WTI\nreports", P.BLUE), (d["NG"]["primary"], "Gas\nreports", P.VIOLET),
            (d["WTI"]["placebo_on_NG_release_days"], "WTI on\ngas days", GREY), (d["NG"]["placebo_on_WTI_release_days"], "Gas on\nWTI days", GREY)]
    for i, (r, lab, col) in enumerate(left):
        ratio_bar(ax[0], i, r, col)
    ax[0].set_xticks(range(4), [x[1] for x in left], fontsize=13.5)
    ax[0].set_title("Main test and placebos", fontsize=15)
    right = [(d["WTI"]["sub_2010-2016"], "WTI\n2010\u201316", P.BLUE), (d["WTI"]["sub_2017-2024"], "WTI\n2017\u201324", P.BLUE),
             (d["NG"]["sub_2010-2016"], "Gas\n2010\u201316", P.VIOLET), (d["NG"]["sub_2017-2024"], "Gas\n2017\u201324", P.VIOLET)]
    for i, (r, lab, col) in enumerate(right):
        ratio_bar(ax[1], i, r, col)
    ax[1].set_xticks(range(4), [x[1] for x in right], fontsize=13.5)
    ax[1].set_title("By sub-period", fontsize=15)
    lo = min(0.85, min(r["ci95"][0] for r, _, _ in left + right) - 0.03)
    hi = max(r["ci95"][1] for r, _, _ in left + right) + 0.09
    for a in ax:
        a.axhline(1, color=P.AMBER, lw=1.4, ls="--", zorder=2)
        a.set_ylim(lo, hi)
        a.set_axisbelow(True)
        a.grid(axis="x", visible=False)
        a.tick_params(axis="y", labelsize=13.5)
    ax[0].set_ylabel("ratio of mean |return|", fontsize=14)
    ax[0].legend(handles=[Patch(color=P.BLUE, label="WTI crude"), Patch(color=P.VIOLET, label="natural gas"), Patch(color=GREY, label="placebo")],
                 loc="upper right", fontsize=12.5, ncol=1, framealpha=0.85)
    fig.suptitle("Are EIA report days more volatile? (ratio, 95% interval)", fontsize=16.5, y=0.985)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    P.finish(fig, "T1_release_day_ratio", "Source: U.S. Energy Information Administration (NYMEX settlements and weekly reports); own computation. Pre-registered test; diamond = point estimate; placebo = the other report's days.")


def fig_t2() -> None:
    d = load("T2")["markets"]
    P.theme()
    fig, ax = plt.subplots(1, 2, figsize=(6.8, 4.9), sharey=True)
    for a, (n, col, name) in zip(ax, (("WTI", P.BLUE, "WTI crude"), ("NG", P.VIOLET, "Natural gas"))):
        r = d[n]
        qs = r["quintiles"]
        a.bar(range(5), [x["mean_r_bp"] for x in qs], yerr=[1.96 * x["se_bp"] for x in qs], color=col, capsize=4,
              error_kw={"ecolor": P.FG, "lw": 1.5}, width=0.62, zorder=3)
        a.axhline(0, color=P.MUTED, lw=1, zorder=2)
        a.set_xticks(range(5), [str(i + 1) for i in range(5)], fontsize=13)
        a.set_title(f"{name}\n{mn(1e4 * r['slope_b_per_sd'], 0)} bp per sd, t = {mn(r['t_nw4'], 1)}\nn = {r['n']}", fontsize=12.5)
        a.set_axisbelow(True)
        a.grid(axis="x", visible=False)
        a.tick_params(axis="y", labelsize=12.5)
    ax[0].set_ylabel("mean report-day return (bp)", fontsize=13)
    fig.supxlabel("surprise quintile (1 = smaller build than expected)", fontsize=12.5, y=0.045)
    fig.suptitle("Report-day return by size of the inventory surprise", fontsize=14, y=0.985)
    fig.tight_layout(rect=(0, 0.09, 1, 0.95))
    P.finish(fig, "T2_surprise_quintiles", "Source: U.S. Energy Information Administration; surprise = change minus an expanding AR(2)+seasonal forecast; own computation. Pre-registered test; bars show 95% intervals.")


def fig_t3() -> None:
    d = load("T3")
    P.theme()
    fig, ax = plt.subplots(figsize=(5.4, 4.5))
    order = ["bottom", "middle", "top"]
    ts = d["terciles"]
    ax.bar(range(3), [ts[k]["mean_abs_r_bp"] for k in order], yerr=[1.96 * ts[k]["se_bp"] for k in order], color=[P.CYAN, GREY, P.BLUE],
           capsize=5, error_kw={"ecolor": P.FG, "lw": 1.5}, width=0.6, zorder=3)
    ax.set_xticks(range(3), [f"{'least' if k == 'bottom' else 'most' if k == 'top' else 'middle'}\ncloud\nn={ts[k]['n']}" for k in order], fontsize=12.5)
    ax.set_ylabel("mean |WTI return| on report day (bp)", fontsize=12.5)
    r = d["ratio_top_over_bottom"]
    ax.set_title(f"Cloudiest vs least cloudy third:\nratio {r['ratio']:.2f} [{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}]", fontsize=12.5)
    ax.tick_params(axis="y", labelsize=12.5)
    ax.set_axisbelow(True)
    ax.grid(axis="x", visible=False)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    P.finish(fig, "T3_cloud_terciles", "Source: Open-Meteo (ERA5), EIA; own computation. Exploratory pre-registered check; 95% intervals; WTI front month, 2016 to April 2024.")


def fig_t4(compact: bool = False) -> None:
    import numpy as np
    import pandas as pd

    d = load("T4")
    df = pd.read_csv(RESULTS / "T4_daily.csv", index_col=0, parse_dates=True)
    key = df.index.to_period("M")
    x = (df["S"] - df.groupby(key)["S"].transform("mean")) * 100
    y = df["P"] - df.groupby(key)["P"].transform("mean")
    P.theme()
    fig, ax = plt.subplots(figsize=(5.4, 4.5) if compact else (6.6, 4.2))
    ax.scatter(x, y, s=7, color=P.VIOLET, alpha=0.22, zorder=2)
    bins = pd.qcut(x, 10, duplicates="drop")
    g = pd.DataFrame({"x": x, "y": y, "b": bins}).groupby("b", observed=True).agg(x=("x", "mean"), y=("y", "mean"), se=("y", lambda v: v.std(ddof=1) / np.sqrt(len(v))))
    ax.errorbar(g["x"], g["y"], yerr=1.96 * g["se"], color=P.AMBER, marker="o", ms=7, lw=2, capsize=4, zorder=4, label="decile means")
    ax.axhline(0, color=P.MUTED, lw=1)
    ax.set_xlabel("wind + solar share vs month mean (pp)", fontsize=13)
    ax.set_ylabel("price vs month mean (EUR/MWh)", fontsize=13)
    if compact:
        ax.set_title(f"Germany 2019\u20132025:\n{mn(d['b_eur_mwh_per_10pp'])} EUR/MWh per +10 pp\nNewey\u2013West t = {mn(d['t_nw7'])}", fontsize=12.5)
    else:
        ax.set_title(f"Germany 2019\u20132025: {mn(d['b_eur_mwh_per_10pp'])} EUR/MWh per +10 pp\nNewey\u2013West t = {mn(d['t_nw7'])}", fontsize=13)
    ax.set_ylim(np.percentile(y, 1), np.percentile(y, 99))
    ax.tick_params(labelsize=12.5)
    ax.legend(loc="upper right", fontsize=12, framealpha=0.85)
    ax.set_axisbelow(True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    P.finish(fig, "T4_merit_order_c" if compact else "T4_merit_order", "Source: ENTSO-E Transparency Platform, bidding zone DE-LU; own computation. Pre-registered check; variables relative to their month-year mean, as in the regression.")


def fig_t5(compact: bool = False) -> None:
    import numpy as np
    import pandas as pd

    d = load("T5")
    fill = pd.read_csv(RESULTS / "T5_fill.csv", index_col=0, parse_dates=True)
    wd = pd.read_csv(RESULTS / "T5_daily.csv", index_col=0, parse_dates=True)
    P.theme()
    if compact:
        fig, axs = plt.subplots(figsize=(5.4, 4.5))
        sc = axs
    else:
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1.1, 1]})
        sc = ax[1]
        for gy, g in fill.groupby("gas_year"):
            if gy < 2015 or gy > 2024:
                continue
            doy = (g.index - pd.Timestamp(year=int(gy), month=10, day=1)).days
            hl = gy == 2022
            ax[0].plot(doy, g["fill"], color=P.AMBER if hl else P.BLUE, lw=2.6 if hl else 1.0, alpha=1 if hl else 0.45, zorder=3 if hl else 2)
        ax[0].plot([], [], color=P.BLUE, alpha=0.6, label="gas years 2015\u20132024")
        ax[0].plot([], [], color=P.AMBER, lw=2.6, label="gas year 2022")
        ax[0].set_xticks([0, 91, 182, 273], ["Oct", "Jan", "Apr", "Jul"], fontsize=13)
        ax[0].set_ylabel("EU storage fill (%)", fontsize=13.5)
        ax[0].set_title("Fill level by gas year", fontsize=14)
        ax[0].tick_params(axis="y", labelsize=12.5)
        ax[0].legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), fontsize=12, ncol=2, framealpha=0.85)
    sc.scatter(wd["HDD"], wd["NW"] / 1000, s=6, color=P.VIOLET, alpha=0.25, zorder=2)
    xs = np.linspace(0, wd["HDD"].max(), 50)
    sc.plot(xs, wd["NW"].mean() / 1000 + d["b_gwh_per_hdd_degree"] / 1000 * (xs - wd["HDD"].mean()), color=P.AMBER, lw=2.2, zorder=4)
    sc.set_xlabel("heating degree days (base 15.5 \u00b0C)", fontsize=13)
    sc.set_ylabel("net withdrawal (TWh/d)", fontsize=13.5)
    ttl = f"Nov\u2013Mar: {mn(d['b_gwh_per_hdd_degree'], 0)} GWh/d per degree"
    sc.set_title(ttl + (f"\nt = {d['t_nw7']:.1f}" if compact else f", t = {d['t_nw7']:.1f}"), fontsize=13)
    sc.tick_params(labelsize=12.5)
    for a in ([sc] if compact else list(ax)):
        a.set_axisbelow(True)
        a.grid(axis="x", visible=False)
    if not compact:
        fig.suptitle("Cold days drive EU gas storage withdrawals", fontsize=15, y=0.985)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95 if not compact else 1), w_pad=3.0)
    P.finish(fig, "T5_gas_storage_hdd_c" if compact else "T5_gas_storage_hdd", "Source: GIE AGSI+ (EU aggregate), Open-Meteo (ERA5); own computation. Pre-registered check; fixed effects for gas year and weekday in the regression.")


FIGS = {"T1": fig_t1, "T2": fig_t2, "T3": fig_t3, "T4": fig_t4, "T4c": lambda: fig_t4(True), "T5": fig_t5, "T5c": lambda: fig_t5(True)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=[k for k in FIGS if (RESULTS / f"{k[:2]}.json").exists()], choices=list(FIGS))
    for name in ap.parse_args().only:
        FIGS[name]()
        print("wrote", name)


if __name__ == "__main__":
    main()
