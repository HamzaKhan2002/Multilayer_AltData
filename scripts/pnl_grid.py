"""Conditional PnL grid for the idea cards (docs/PNL_METHOD.md). Every number is an order of magnitude that depends on
explicit assumptions; none is a result.

Model: constant-size bets on the sign of a forecast, Gaussian approximation.
    IR_net = sqrt(N) * (sqrt(2/pi) * rho - k)        PnL_net = IR_net * B
N = independent bets per year; rho = correlation between the forecast and the move over the bet's horizon;
k = round-trip cost divided by the standard deviation of the move; B = annual risk budget (standard deviation of PnL).
Reference B = 1 M$ per year (10 M$ of capital at 10% volatility). Break-even correlation: rho* = k / sqrt(2/pi).

Usage: python scripts/pnl_grid.py         Output: results/v2/pnl_grid_v2.csv (I1: N = 52, one decision per Cushing report)
       python scripts/pnl_grid.py --v1    Output: results/pnl_grid.csv (first grid, I1: N = 104 = 52 oil + 52 gas reports)
       python scripts/pnl_grid.py --windows   Output: results/v3/pnl_grid_windows.csv (I1, k set from the sd of three holding windows, results/v3/a_price_proxy.json, AH)

v2 change: I1 is now a single Cushing/WTI decision per weekly report; the gas report is no longer counted as an
independent I1 bet, and two expressions of one signal (outright, spread) are not independent bets either.
"""
import json
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
COST_USD = 20.0       # round trip per contract: about one tick plus fees (assumption, 15 to 25 USD)
WINDOWS = {"api_to_1036": "API release 16:30 to 10:36", "wed_0930_to_1036": "09:30 to 10:36", "print_1030_to_1036": "10:30 to 10:36 (six minutes after the print)"}


def windows() -> None:
    """I1 break-even and conditional PnL when k is the cost over the sd of the move across the holding window (sd measured in a_price_proxy.json, AH, 2013-2023)."""
    ah = json.loads((RESULTS / "v3" / "a_price_proxy.json").read_text(encoding="utf-8"))["AH"]
    rows = []
    for key, label in WINDOWS.items():
        sd_cents = ah[key]["pooled_overlap_post"]["sd_cents"]
        k = COST_USD / (sd_cents * 10.0)          # 1 cent x 1,000 barrels = 10 USD per contract
        for rho in RHOS:
            rows.append({"window": label, "sd_cents": sd_cents, "cost_usd": COST_USD, "k": k, "rho_star": k / C, "rho": rho, "pnl_musd_per_1musd_risk": math.sqrt(52) * (C * rho - k)})
    df = pd.DataFrame(rows)
    out = RESULTS / "v3" / "pnl_grid_windows.csv"
    df.to_csv(out, index=False)
    print(df.pivot_table(index=["window", "sd_cents", "k", "rho_star"], columns="rho", values="pnl_musd_per_1musd_risk").round(3).to_string())
    print(f"wrote {out.relative_to(RESULTS.parent).as_posix()}")


def main() -> None:
    if "--windows" in sys.argv[1:]:
        windows()
        return
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
