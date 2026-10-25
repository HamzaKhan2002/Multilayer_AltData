"""Figure V5: weekly EIA stocks at Cushing (level and weekly change) with the first-version no-satellite baseline error band.

The baseline numbers (expanding AR(2), 2016-2025: out-of-sample R2 0.31, RMSE 1.20 Mb against 1.44 Mb for the mean forecast)
come from deliverables/analysis/eia_cushing_baseline.py and were reproduced on 2026-10-23. Mb = million barrels.

Usage: python scripts/fig_eia_inventories.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from altdata import eia  # noqa: E402
from altdata import plotting as P  # noqa: E402

RMSE_MB = 1.20
BASE = (pd.Timestamp("2016-01-01"), pd.Timestamp("2025-12-31"))


def main() -> None:
    s = eia.load("pet", "W_EPC0_SAX_YCUOK_MBBL", "w") / 1000.0  # million barrels
    s = s[s.index >= pd.Timestamp("2010-01-01")]
    d = s.diff().dropna()
    P.theme()
    fig, (a, b) = plt.subplots(2, 1, figsize=(7.4, 5.2), sharex=True, gridspec_kw={"height_ratios": [1.1, 1]})
    a.plot(s.index, s.values, color=P.BLUE, lw=2)
    a.set_ylabel("stocks (Mb)", fontsize=14)
    a.set_title("Cushing crude stocks and weekly change", fontsize=16)
    a.grid(axis="x", visible=False)
    colors = [P.GREEN if v >= 0 else P.RED for v in d.values]
    b.bar(d.index, d.values, width=6.5, color=colors, alpha=0.95, zorder=3)
    b.axvspan(*BASE, color=P.AMBER, alpha=0.07, zorder=1)
    for y in (-RMSE_MB, RMSE_MB):
        b.hlines(y, BASE[0], BASE[1], color=P.AMBER, lw=1.6, ls="--", zorder=4)
    b.text(0.012, 0.96, "dashed lines: baseline error\n\u00b11.2 Mb, 2016\u20132025", transform=b.transAxes, color=P.AMBER,
           fontsize=13, va="top", bbox={"facecolor": P.PANEL, "edgecolor": "none", "alpha": 0.92, "pad": 4})
    b.set_ylabel("weekly change (Mb)", fontsize=14)
    b.grid(axis="x", visible=False)
    b.set_axisbelow(True)
    b.legend(handles=[Patch(color=P.GREEN, label="build"), Patch(color=P.RED, label="draw")], loc="lower left", fontsize=12.5, ncol=2, framealpha=0.85)
    for ax in (a, b):
        ax.tick_params(labelsize=13)
    fig.align_ylabels([a, b])
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    P.finish(fig, "V5_cushing_stocks", "Source: U.S. Energy Information Administration, series W_EPC0_SAX_YCUOK_MBBL (Mb = million barrels); baseline: own computation (expanding AR(2), 2016-2025).")
    print("wrote V5_cushing_stocks", len(s), "weeks", s.index.min().date(), "->", s.index.max().date(), "min", round(s.min(), 1), "max", round(s.max(), 1))


if __name__ == "__main__":
    main()
