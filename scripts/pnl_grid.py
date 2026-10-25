"""Conditional PnL grid for the idea cards (docs/PNL_METHOD.md). Every number is an order of magnitude that depends on
explicit assumptions; none is a result.

Model: constant-size bets on the sign of a forecast, Gaussian approximation.
    IR_net = sqrt(N) * (sqrt(2/pi) * rho - k)        PnL_net = IR_net * B
N = independent bets per year; rho = correlation between the forecast and the move over the bet's horizon;
k = round-trip cost divided by the standard deviation of the move; B = annual risk budget (standard deviation of PnL).
Reference B = 1 M$ per year (10 M$ of capital at 10% volatility). Break-even correlation: rho* = k / sqrt(2/pi).

Usage: python scripts/pnl_grid.py         Output: results/v2/pnl_grid_v2.csv (I1: N = 52, one decision per Cushing report)
       python scripts/pnl_grid.py --v1    Output: results/pnl_grid.csv (first grid, I1: N = 104 = 52 oil + 52 gas reports)

v2 change: I1 is now a single Cushing/WTI decision per weekly report; the gas report is no longer counted as an
independent I1 bet, and two expressions of one signal (outright, spread) are not independent bets either.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from altdata.paths import RESULTS  # noqa: E402

C = math.sqrt(2 / math.pi)
RHOS = (0.03, 0.06, 0.10)
# id: (name, N bets per year, k = cost / sd of the move). N and k are assumptions, justified in docs/PNL_METHOD.md.
IDEAS = {
    "I1": ("Energy inventories before the EIA report", 52, 0.02),
    "I2": ("European power and gas, weather balance", 250, 0.05),
    "I3": ("Equity revenue before earnings", 400, 0.02),
    "I5": ("Crops from space", 60, 0.03),
    "I6": ("Event volatility (options)", 400, 0.05),
}
I1_N_V1 = 104


def main() -> None:
    v1 = "--v1" in sys.argv[1:]
    ideas = dict(IDEAS)
    if v1:
        ideas["I1"] = (ideas["I1"][0], I1_N_V1, ideas["I1"][2])
    rows = []
    for key, (name, n, k) in ideas.items():
        for rho in RHOS:
            ir = math.sqrt(n) * (C * rho - k)
            rows.append({"idea": key, "name": name, "N": n, "k": k, "rho_star": k / C, "rho": rho, "ir_net": ir,
                         "pnl_musd_per_1musd_risk": ir, "capital_musd_at_10pct_vol": 10})
    df = pd.DataFrame(rows)
    out = RESULTS / "pnl_grid.csv" if v1 else RESULTS / "v2" / "pnl_grid_v2.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    show = df.pivot(index="idea", columns="rho", values="pnl_musd_per_1musd_risk").round(2)
    show.insert(0, "rho*", [round(ideas[i][2] / C, 4) for i in show.index])
    show.insert(0, "N", [ideas[i][1] for i in show.index])
    print(show.to_string())
    print(f"wrote {out.relative_to(RESULTS.parent).as_posix()}")
    print("I4 (text): not quantified; the number of independent bets is unknown and rho falls with LLM adoption.")


if __name__ == "__main__":
    main()
