"""Figure B0 from results/v2/B0_amended/b0.json if it exists, else results/v2/B0/b0.json (no statistic is computed here).

Left: mean absolute one-minute WTI change around the 10:30 ET release on the event days of the clock check.
Right (status COMPLETED): coefficients of the four AR(2) surprises on the 10:29-10:35 change (cents per barrel per million barrels), HC1 95% intervals.
Right (status BLOCKED, no coefficient exists): share of event days by minute of the largest move of 10:00-10:59, against the 70% rule.

Usage: python scripts/fig_b0.py
Output: figures/B0_transmission.png|svg (COMPLETED) or figures/B0_clock_check.png|svg (BLOCKED)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt  # noqa: E402

from altdata import plotting as P  # noqa: E402
from altdata.v2common import V2  # noqa: E402

ROWS = [("cushing", "Cushing", P.BLUE), ("us_ex_cushing", "US crude\nex-Cushing", P.CYAN), ("gasoline", "Gasoline", P.VIOLET), ("distillate", "Distillate", P.AMBER)]


def mn(v: float, p: int = 1) -> str:
    """Signed number with a true minus sign (U+2212)."""
    return f"{v:+.{p}f}".replace("-", "\u2212")


def profile_panel(a, prof: dict, title: str = "Average move per minute\naround the 10:30 release") -> None:
    mins = list(prof)
    y = [prof[m]["mean_abs_change_cents"] for m in mins]
    cols = [P.AMBER if m == "10:30" else P.BLUE for m in mins]
    a.bar(range(len(mins)), y, color=cols, width=0.78, zorder=3)
    a.set_xticks([i for i, m in enumerate(mins) if int(m[-2:]) % 5 == 0], [m for m in mins if int(m[-2:]) % 5 == 0], fontsize=12)
    a.tick_params(axis="y", labelsize=13)
    a.set_ylabel("mean |1-minute change| (cents)", fontsize=13.5)
    a.set_xlabel("minute (New York time)", fontsize=13.5)
    a.set_title(title, fontsize=14.5)
    k = mins.index("10:30")
    before = [y[i] for i, m in enumerate(mins) if "10:15" <= m <= "10:29"]
    a.text(k + 1.0, y[k] * 0.97, f"10:30: {y[k]:.1f} cents,\n{y[k] / (sum(before) / len(before)):.1f}x the 15 minutes before", fontsize=12.5, color=P.AMBER,
           ha="left", va="top", linespacing=1.35)
    a.set_ylim(0, max(y) * 1.1)
    a.set_axisbelow(True)
    a.grid(axis="x", visible=False)


def draw_blocked(b0: dict) -> None:
    sc = b0["sanity_clock"]
    n = sc["n_events"]
    dist = sc["argmax_distribution"]
    mins = [f"10:{k:02d}" for k in range(25, 46)]
    P.theme()
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.8), gridspec_kw={"width_ratios": [1.1, 1]})
    profile_panel(ax[0], sc["profile_abs_change"])
    b = ax[1]
    share = [dist.get(m, 0) / n for m in mins]
    b.bar(range(len(mins)), share, color=[P.AMBER if m == "10:30" else P.BLUE for m in mins], width=0.78, zorder=3)
    b.axhline(sc["threshold"], color=P.RED, lw=1.8, ls="--", zorder=4)
    b.text(len(mins) - 0.5, sc["threshold"] + 0.015, f"required: {sc['threshold']:.0%}", color=P.RED, fontsize=12.5, ha="right", va="bottom")
    k = mins.index("10:30")
    b.text(k + 1.2, share[k] * 0.98, f"10:30: {sc['share_1030']:.0%}\n({sc['n_argmax_1030']} of {n})", color=P.AMBER, fontsize=12.5, ha="left", va="top", linespacing=1.35)
    b.set_xticks([i for i, m in enumerate(mins) if int(m[-2:]) % 5 == 0], [m for m in mins if int(m[-2:]) % 5 == 0], fontsize=12)
    b.set_ylim(0, 0.8)
    b.set_yticks([0, 0.2, 0.4, 0.6, 0.8], ["0%", "20%", "40%", "60%", "80%"], fontsize=13)
    b.set_ylabel("share of release days", fontsize=13.5)
    b.set_xlabel("minute of the largest move of 10:00-10:59", fontsize=13.5)
    b.set_title("Which minute has the largest\none-minute move of the hour?", fontsize=14.5)
    b.set_axisbelow(True)
    b.grid(axis="x", visible=False)
    fig.suptitle(f"B0 clock check, {n} Wednesday releases: blocked at {sc['share_1030']:.0%} (rule 70%)", fontsize=16, y=0.985)
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    P.finish(fig, "B0_clock_check", "Source: HistData WTI minute bid prices, New York clock (amendment AM1); EIA report archive for the release days; own computation. "
             "Left: mean absolute one-minute change on the release days of the clock check. Right: pre-registered clock check; below 70% the transmission test is blocked and no coefficient is computed.")


def draw(b0: dict) -> None:
    prof = b0["sanity_clock"]["profile_abs_change"]
    coef = b0["model_primary"]["coefficients"]
    n, n_clock = b0["model_primary"]["n"], b0["sanity_clock"]["n_events"]
    P.theme()
    fig, ax = plt.subplots(1, 2, figsize=(10, 5.6), gridspec_kw={"width_ratios": [1.1, 1]})
    profile_panel(ax[0], prof, f"Average move per minute around 10:30\n({n_clock} release days, incl. 2026)")

    b = ax[1]
    lo = min(coef[k]["ci95_cents_per_mb"][0] for k, _, _ in ROWS)
    hi = max(coef[k]["ci95_cents_per_mb"][1] for k, _, _ in ROWS)
    span = hi - lo
    for i, (key, lab, col) in enumerate(ROWS):
        c = coef[key]
        yy = len(ROWS) - 1 - i
        l, h = c["ci95_cents_per_mb"]
        b.errorbar(c["coef_cents_per_mb"], yy, xerr=[[c["coef_cents_per_mb"] - l], [h - c["coef_cents_per_mb"]]], fmt="o", color=col, ecolor=col, ms=9, lw=2.4, capsize=6, zorder=4)
        b.text(h + 0.04 * span, yy, f"{mn(c['coef_cents_per_mb'])}", fontsize=13, color=P.FG, va="center", fontweight="bold", zorder=5)
    b.axvline(0, color=P.MUTED, lw=1.2, zorder=2)
    b.set_yticks(range(len(ROWS)), [lab for _, lab, _ in ROWS][::-1], fontsize=12.5)
    b.set_ylim(-0.6, len(ROWS) - 0.4)
    b.set_xlim(lo - 0.08 * span, hi + 0.30 * span)
    b.tick_params(axis="x", labelsize=13)
    b.set_xlabel("cents per barrel per million barrels", fontsize=13.5)
    b.set_title(f"Change in the 6 minutes after 10:30\nper 1 Mb surprise ({n} releases)", fontsize=14.5)
    b.set_axisbelow(True)
    b.grid(axis="y", visible=False)
    fig.suptitle("Does the EIA print move WTI within minutes?  (Wednesday releases, 2013\u20132023)", fontsize=16, y=0.985)
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    P.finish(fig, "B0_transmission", "Source: U.S. Energy Information Administration (first-published weekly stocks, report archive); HistData WTI minute bid prices, New York clock; own computation. "
             f"Left: {n_clock} release days of the clock check. Right: OLS of the 10:29-10:35 close change on four AR(2) surprises, HC1 intervals. "
             "Exploratory diagnostic (clock gate amended after the first run, AM-B0-1), not a strategy.")


def main() -> None:
    amended = V2 / "B0_amended" / "b0.json"
    b0 = json.loads((amended if amended.exists() else V2 / "B0" / "b0.json").read_text(encoding="utf-8"))
    if b0["status"] == "COMPLETED":
        draw(b0)
        print("wrote figures/B0_transmission.png and .svg")
    else:
        draw_blocked(b0)
        print(f"B0 status {b0['status']}: no coefficient figure; wrote figures/B0_clock_check.png and .svg")


if __name__ == "__main__":
    main()
