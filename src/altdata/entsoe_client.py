"""ENTSO-E Transparency Platform through entsoe-py, bidding zone DE-LU (EIC 10Y1001A1001A82H).

The token (ENTSOE_API_TOKEN) travels in the request URL, so every exception is masked before it leaves this module.
Downloads are cached year by year in data/entsoe/ and written atomically, so several processes can prefetch in parallel.
"""
from __future__ import annotations

import os

import pandas as pd
from entsoe import EntsoePandasClient

from .paths import DATA
from .secrets import get_secret, mask

ZONE = "DE_LU"
TZ = "Europe/Berlin"


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"ENTSO-E request failed: {type(e).__name__}: {mask(str(e), 'ENTSOE_API_TOKEN')[:300]}") from None


def _client() -> EntsoePandasClient:
    return EntsoePandasClient(api_key=get_secret("ENTSOE_API_TOKEN"))


def _window(year: int):
    return pd.Timestamp(f"{year}-01-01", tz=TZ), pd.Timestamp(f"{year + 1}-01-01", tz=TZ)


def _write(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    df.to_csv(tmp)
    os.replace(tmp, path)


def _read(path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(TZ)
    return df


def day_ahead_prices(year: int) -> pd.Series:
    """EUR/MWh, 60- or 15-minute resolution as published."""
    start, end = _window(year)
    path = DATA / "entsoe" / f"{ZONE}_prices_{year}.csv"
    if not path.exists():
        s = _call(_client().query_day_ahead_prices, ZONE, start=start, end=end)
        _write(s.rename("eur_mwh").to_frame(), path)
    return _read(path)["eur_mwh"]


def wind_solar_forecast(year: int) -> pd.DataFrame:
    """Day-ahead generation forecast (MW) for solar, wind onshore and wind offshore (processType A01)."""
    start, end = _window(year)
    path = DATA / "entsoe" / f"{ZONE}_windsolar_{year}.csv"
    if not path.exists():
        _write(_call(_client().query_wind_and_solar_forecast, ZONE, start=start, end=end, psr_type=None), path)
    return _read(path)


def load_forecast(year: int) -> pd.Series:
    """Day-ahead total load forecast (MW), processType A01."""
    start, end = _window(year)
    path = DATA / "entsoe" / f"{ZONE}_load_{year}.csv"
    if not path.exists():
        s = _call(_client().query_load_forecast, ZONE, start=start, end=end)
        s = s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s
        _write(s.rename("mw").to_frame(), path)
    return _read(path)["mw"]
