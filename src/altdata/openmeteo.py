"""Open-Meteo archive API (ERA5-based). Weather data by Open-Meteo.com, CC BY 4.0; free for non-commercial use (below 10,000 calls a day)."""
from __future__ import annotations

import json
import time

import pandas as pd
import requests

from .paths import DATA

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def _fetch(params: dict, cache_name: str) -> dict:
    path = DATA / "openmeteo" / f"{cache_name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    err = "unknown"
    for attempt in range(4):
        try:
            r = requests.get(ARCHIVE, params=params, timeout=120)
        except requests.RequestException as e:
            err = type(e).__name__
        else:
            if r.status_code == 200:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(r.text, encoding="utf-8")
                return r.json()
            err = f"HTTP {r.status_code}"
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Open-Meteo request failed ({err})")


def daily_mean_temperature(lat: float, lon: float, start: str, end: str, tz: str = "Europe/Berlin") -> pd.Series:
    js = _fetch({"latitude": lat, "longitude": lon, "start_date": start, "end_date": end, "daily": "temperature_2m_mean", "timezone": tz},
                f"t2m_{lat}_{lon}_{start}_{end}")
    return pd.Series(js["daily"]["temperature_2m_mean"], index=pd.to_datetime(js["daily"]["time"]), dtype=float)


def hourly_cloud_cover(lat: float, lon: float, start: str, end: str) -> pd.Series:
    """Hourly cloud cover (%), UTC."""
    js = _fetch({"latitude": lat, "longitude": lon, "start_date": start, "end_date": end, "hourly": "cloud_cover", "timezone": "UTC"},
                f"cloud_{lat}_{lon}_{start}_{end}")
    return pd.Series(js["hourly"]["cloud_cover"], index=pd.to_datetime(js["hourly"]["time"]), dtype=float)
