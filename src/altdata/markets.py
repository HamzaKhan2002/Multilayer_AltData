"""Market definitions for the EIA-release tests (T1, T2) and the NG sample rule fixed in the pre-registration."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import eia
from .calendars import front_log_returns, release_table

PERIOD = (pd.Timestamp("2010-01-04"), pd.Timestamp("2024-04-05"))

MARKETS = {
    "WTI": {"area": "pet", "c1": "RCLC1", "c2": "RCLC2", "rule": "CL", "stock_area": "pet", "stock": "WCESTUS1",
            "release": "wednesday", "seas_k": 2},
    "NG": {"area": "ng", "c1": "RNGC1", "c2": "RNGC2", "rule": "NG", "stock_area": "ng", "stock": "NW2_EPG0_SWO_R48_BCF",
           "release": "thursday", "seas_k": 3},
}


def business_day_gaps(index: pd.DatetimeIndex, min_missing: int = 6) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """Gaps between consecutive observations with more than 5 missing weekdays (Monday to Friday, no holiday calendar)."""
    out = []
    d = index.values.astype("datetime64[D]")
    for a, b in zip(d[:-1], d[1:]):
        missing = int(np.busday_count(a, b)) - 1
        if missing >= min_missing:
            out.append((pd.Timestamp(a), pd.Timestamp(b), missing))
    return out


def ng_sample_start(c1: pd.Series, c2: pd.Series) -> pd.Timestamp:
    """Pre-registered rule: if RNGC1 or RNGC2 has a gap longer than 5 business days inside the period, the NG sample
    starts on the first trading day after the last such gap."""
    start = PERIOD[0]
    for s in (c1, c2):
        w = s.dropna()
        w = w[(w.index >= PERIOD[0]) & (w.index <= PERIOD[1])]
        for _, b, _ in business_day_gaps(w.index):
            start = max(start, b)
    return start


@dataclass
class Market:
    name: str
    returns: pd.DataFrame      # index = trading days, columns r (log return), roll
    stocks: pd.Series          # weekly stocks, index = week-ending Friday
    releases: pd.DataFrame     # week_end, release, shifted, is_trading_day
    start: pd.Timestamp        # first date of the test sample
    seas_k: int


def build(name: str) -> Market:
    cfg = MARKETS[name]
    c1 = eia.load(cfg["area"], cfg["c1"], "d")
    c2 = eia.load(cfg["area"], cfg["c2"], "d")
    returns = front_log_returns(c1, c2, cfg["rule"])
    stocks = eia.load(cfg["stock_area"], cfg["stock"], "w")
    releases = release_table(stocks.index, cfg["release"], returns.index)
    start = ng_sample_start(c1, c2) if name == "NG" else PERIOD[0]
    return Market(name, returns, stocks, releases, start, cfg["seas_k"])
