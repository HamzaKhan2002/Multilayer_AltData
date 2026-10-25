"""T1 (pre-registered): release-day volatility of energy futures.

H: absolute daily returns of the front-month future are larger on scheduled EIA release days than on other trading days.
Run once on the full period after the coverage audit (prereg common.run_once). Definitions: prereg/tests_v1.json.

Usage: python scripts/t1_release_volatility.py
Outputs: results/T1.json, results/T1.log (figures: scripts/fig_tests.py)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from altdata.markets import MARKETS, PERIOD, build  # noqa: E402
from altdata.paths import RESULTS, assert_prereg_frozen  # noqa: E402
from altdata.runlog import RunLog, trial_log  # noqa: E402
from altdata.stats import week_block_ratio  # noqa: E402

SUBPERIODS = {"2010-2016": (pd.Timestamp("2010-01-04"), pd.Timestamp("2016-12-30")),
              "2017-2024": (pd.Timestamp("2017-01-03"), pd.Timestamp("2024-04-05"))}


def abs_returns(m, lo=None, hi=None) -> pd.Series:
    a = m.returns["r"].abs()
    lo = m.start if lo is None else max(m.start, lo)
    hi = PERIOD[1] if hi is None else min(PERIOD[1], hi)
    return a[(a.index >= lo) & (a.index <= hi)].dropna()


def release_days(m) -> pd.DatetimeIndex:
    rt = m.releases
    return pd.DatetimeIndex(sorted(rt.loc[rt["is_trading_day"], "release"]))


def ratio(a: pd.Series, days: pd.DatetimeIndex) -> dict:
    return week_block_ratio(a, pd.Series(a.index.isin(days), index=a.index))


def main() -> None:
    log = RunLog("T1")
    sha = assert_prereg_frozen()
    log("prereg hash", sha)
    markets = {n: build(n) for n in MARKETS}
    days = {n: release_days(m) for n, m in markets.items()}
    out = {"id": "T1", "prereg_sha256": sha, "period": [str(PERIOD[0].date()), str(PERIOD[1].date())], "markets": {}}
    other = {"WTI": "NG", "NG": "WTI"}
    for n, m in markets.items():
        a = abs_returns(m)
        res = {"sample_start": str(a.index.min().date()), "sample_end": str(a.index.max().date()), "n_days": int(len(a)),
               "primary": ratio(a, days[n]),
               f"placebo_on_{other[n]}_release_days": ratio(a, days[other[n]])}
        for k, (lo, hi) in SUBPERIODS.items():
            res[f"sub_{k}"] = ratio(abs_returns(m, lo, hi), days[n])
        lo95 = res["primary"]["ci95"][0]
        res["verdict"] = "SUPPORTED" if lo95 > 1.00 else "NOT SUPPORTED"
        out["markets"][n] = res
        p = res["primary"]
        log(n, "ratio", round(p["ratio"], 3), "ci95", [round(x, 3) for x in p["ci95"]], "p", round(p["p_one_sided"], 4),
            "n_event", p["n_event"], "->", res["verdict"])
        log(n, "placebo", {k: round(v["ratio"], 3) for k, v in res.items() if k.startswith("placebo")},
            "sub", {k: round(v["ratio"], 3) for k, v in res.items() if k.startswith("sub_")})
    (RESULTS / "T1.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    verdict = "; ".join(f"{n}: {out['markets'][n]['verdict']}" for n in markets)
    secs = log.close()
    trial_log("T1", "scripts/t1_release_volatility.py", sha, verdict, secs)


if __name__ == "__main__":
    main()
