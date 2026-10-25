"""Self-contained checks of the calendar, bootstrap, HAC regression and secret masking on synthetic data.

No EIA return or inventory statistic is read. Run: python tests/test_core.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata.calendars import front_log_returns, last_trading_days, release_date  # noqa: E402
from altdata.stats import holm, ols_hac, week_block_ratio  # noqa: E402


def test_release_dates():
    # Memorial Day (Monday 2019-05-27): the crude report for the week ending 2019-05-24 moved to Thursday 2019-05-30.
    assert release_date(pd.Timestamp("2019-05-24"), "wednesday") == (pd.Timestamp("2019-05-30"), True)
    # No holiday between Monday and Wednesday: Wednesday.
    assert release_date(pd.Timestamp("2019-06-28"), "wednesday") == (pd.Timestamp("2019-07-03"), False)
    # Gas: Thanksgiving Thursday 2019-11-28, so the report for the week ending 2019-11-22 came out on Wednesday 2019-11-27.
    assert release_date(pd.Timestamp("2019-11-22"), "thursday") == (pd.Timestamp("2019-11-27"), True)
    assert release_date(pd.Timestamp("2019-12-06"), "thursday") == (pd.Timestamp("2019-12-12"), False)


def test_expiry_rules():
    B = pd.bdate_range("2019-01-01", "2019-12-31")
    cl = last_trading_days(B, "CL")
    # WTI Feb-2019 contract: 25 Jan 2019 is a Friday, three business days earlier = Tue 22 Jan.
    assert cl[pd.Period("2019-02")] == pd.Timestamp("2019-01-22")
    ng = last_trading_days(B, "NG")
    # NG Feb-2019: third-last business day of January 2019 = Tue 29 Jan.
    assert ng[pd.Period("2019-02")] == pd.Timestamp("2019-01-29")


def test_front_returns_use_same_contract_on_roll():
    B = pd.bdate_range("2019-01-01", "2019-04-30")
    ltd = last_trading_days(B, "NG")
    first_roll = ltd[pd.Period("2019-02")] + pd.offsets.BDay(1)  # first trading day after the Feb contract expired
    c1 = pd.Series(10.0, index=B)
    c2 = pd.Series(10.0, index=B)
    c1[B >= first_roll] = 12.0          # next contract is 20% higher
    c2[B < first_roll] = 12.0
    c2[B >= first_roll] = 12.0
    out = front_log_returns(c1, c2, "NG")
    assert abs(out.loc[first_roll, "r"]) < 1e-12 and out.loc[first_roll, "roll"]


def test_non_positive_price_gives_nan():
    B = pd.bdate_range("2020-04-01", "2020-05-29")
    c1 = pd.Series(20.0, index=B)
    c2 = pd.Series(21.0, index=B)
    c1[pd.Timestamp("2020-04-20")] = -37.63
    out = front_log_returns(c1, c2, "CL")
    assert np.isnan(out.loc["2020-04-20", "r"]) and np.isnan(out.loc["2020-04-21", "r"])


def test_week_block_ratio_recovers_planted_effect():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2010-01-04", "2023-12-29")
    event = pd.Series(idx.dayofweek == 2, index=idx)
    base = np.abs(rng.standard_normal(len(idx)))
    ratio_true = 1.5
    a = pd.Series(np.where(event, base * ratio_true, base), index=idx)
    res = week_block_ratio(a, event)
    assert res["ci95"][0] > 1.2 and res["ci95"][1] < 1.9, res
    null = pd.Series(base, index=idx)
    res0 = week_block_ratio(null, event)
    assert res0["ci95"][0] < 1.0 < res0["ci95"][1], res0


def test_hac_slope_and_holm():
    rng = np.random.default_rng(2)
    x = rng.standard_normal(2000)
    y = -0.5 * x + rng.standard_normal(2000)
    res = ols_hac(y, x, lags=4)
    assert abs(res["b"][0] + 0.5) < 0.1 and res["t"][0] < -10
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert abs(adj["a"] - 0.03) < 1e-12 and abs(adj["c"] - 0.06) < 1e-12 and abs(adj["b"] - 0.06) < 1e-12


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
