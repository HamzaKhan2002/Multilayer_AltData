"""Futures expiry and EIA release calendars. The rules are fixed in prereg/tests_v1.json."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

HOLIDAYS = USFederalHolidayCalendar().holidays(start="1980-01-01", end="2030-12-31")
ONE = pd.Timedelta(days=1)


def last_trading_days(B: pd.DatetimeIndex, rule: str) -> pd.Series:
    """Last trading day of each delivery month, indexed by month.

    CL: 3 business days before the 25th of the month before delivery (or before the last business day preceding the 25th).
    NG: 3 business days before the first calendar day of the delivery month, i.e. the third-last business day of the prior month.
    Business days are the trading days observed in the data. Adapted from deliverables_v2/analysis/storage_curve_pretest.py.
    """
    last, out = B[-1], {}
    for M in pd.period_range(B[0].to_period("M"), last.to_period("M") + 6, freq="M"):
        prior = M - 1
        if prior.start_time < B[0]:
            continue
        if rule == "CL":
            d25 = pd.Timestamp(prior.year, prior.month, 25)
            if d25 > last:
                out[M] = pd.Timestamp.max
                continue
            i = B.get_loc(d25) if d25 in B else B.get_loc(B[B < d25][-1])
            if i < 3:
                continue
            out[M] = B[i - 3]
        elif rule == "NG":
            if prior.end_time > last:
                out[M] = pd.Timestamp.max
                continue
            inm = B[(B >= prior.start_time) & (B <= prior.end_time)]
            if len(inm) < 3:
                continue
            out[M] = inm[-3]
        else:
            raise ValueError(rule)
    return pd.Series(out).sort_index()


def front_log_returns(c1: pd.Series, c2: pd.Series, rule: str) -> pd.DataFrame:
    """Daily front-month log returns on trading days (non-missing C1).

    On the first trading day after the front contract's last trading day, r = ln(C1_t / C2_{t-1}) so that both prices
    refer to the same contract. Non-positive prices have no log return (WTI, April 2020): r is NaN.
    """
    B = c1.dropna().index
    ltd = last_trading_days(B, rule)
    L = ltd.values.astype("datetime64[ns]")
    idx = np.searchsorted(L, B.values, side="left")
    roll = np.zeros(len(B), dtype=bool)
    roll[1:] = idx[1:] != idx[:-1]
    p1 = c1.reindex(B).to_numpy(float)
    p2 = c2.reindex(B).to_numpy(float)
    prev1 = np.r_[np.nan, p1[:-1]]
    prev2 = np.r_[np.nan, p2[:-1]]
    denom = np.where(roll, prev2, prev1)
    ok = (p1 > 0) & (denom > 0)
    r = np.full(len(B), np.nan)
    r[ok] = np.log(p1[ok] / denom[ok])
    return pd.DataFrame({"r": r, "roll": roll}, index=B)


def roll_diagnostic(c1: pd.Series, c2: pd.Series, rule: str) -> dict[int, float]:
    """Integrity check of the expiry rule (no return statistic): share of days, by offset from the rule's roll day,
    where C1 today is closer to yesterday's C2 than to yesterday's C1. Offset 0 should dominate."""
    B = c1.dropna().index
    ltd = last_trading_days(B, rule)
    pos = {d: i for i, d in enumerate(B)}
    lp1 = np.log(c1.reindex(B).where(lambda s: s > 0))
    lp2 = np.log(c2.reindex(B).where(lambda s: s > 0))
    res: dict[int, float] = {}
    for o in range(-2, 3):
        good = tot = 0
        for d in ltd.tolist():
            if d == pd.Timestamp.max or d not in pos:
                continue
            i = pos[d] + 1 + o
            if i < 1 or i >= len(B):
                continue
            a = abs(lp1.iloc[i] - lp2.iloc[i - 1])
            b = abs(lp1.iloc[i] - lp1.iloc[i - 1])
            if np.isfinite(a) and np.isfinite(b):
                tot += 1
                good += a < b
        res[o] = round(good / tot, 3) if tot else float("nan")
    return res


def release_date(F: pd.Timestamp, kind: str) -> tuple[pd.Timestamp, bool]:
    """Release day of the weekly report for the week ending Friday F, and whether a holiday shifted it.

    wednesday (WPSR): F+5; F+6 if a US federal holiday falls between F+3 and F+5 inclusive.
    thursday (WNGSR): F+6; F+5 if F+6 is a US federal holiday.
    Approximate calendar: a few weeks a year may be misdated, which biases tests toward no effect.
    """
    if kind == "wednesday":
        mon, wed = F + 3 * ONE, F + 5 * ONE
        if ((HOLIDAYS >= mon) & (HOLIDAYS <= wed)).any():
            return F + 6 * ONE, True
        return wed, False
    if kind == "thursday":
        thu = F + 6 * ONE
        if thu in HOLIDAYS:
            return F + 5 * ONE, True
        return thu, False
    raise ValueError(kind)


def release_table(weeks: pd.DatetimeIndex, kind: str, trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    for f in weeks:
        r, shifted = release_date(f, kind)
        rows.append((f, r, shifted, r in trading_days))
    return pd.DataFrame(rows, columns=["week_end", "release", "shifted", "is_trading_day"])
