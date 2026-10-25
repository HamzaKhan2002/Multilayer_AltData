"""GIE AGSI+ gas storage API. The free key is read from AGSI_API_KEY and sent in the x-key header; it is never printed."""
from __future__ import annotations

import time

import pandas as pd
import requests

from .paths import DATA
from .secrets import get_secret

BASE = "https://agsi.gie.eu/api"
NUMERIC = ["gasInStorage", "full", "injection", "withdrawal", "workingGasVolume", "injectionCapacity", "withdrawalCapacity", "trend", "consumption"]


def _get(params: dict) -> dict:
    key = get_secret("AGSI_API_KEY")
    err = "unknown"
    for attempt in range(4):
        try:
            r = requests.get(BASE, params=params, headers={"x-key": key, "User-Agent": "multilayer-altdata-research/0.1"}, timeout=60)
        except requests.RequestException as e:
            err = type(e).__name__
        else:
            if r.status_code == 200:
                return r.json()
            err = f"HTTP {r.status_code}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"AGSI+ request failed ({err})")


def eu_storage(start: str, end: str) -> pd.DataFrame:
    """EU aggregate, one row per gas day: injection and withdrawal (GWh/d), gas in storage (TWh), fill level (%). Cached in data/agsi/."""
    path = DATA / "agsi" / f"eu_{start}_{end}.csv"
    if path.exists():
        return pd.read_csv(path, parse_dates=["gasDayStart"], index_col="gasDayStart")
    rows, page = [], 1
    while True:
        js = _get({"type": "eu", "from": start, "till": end, "size": 300, "page": page})
        if "data" not in js:
            raise RuntimeError(f"AGSI+ response without data (keys {sorted(js)}, page {page})")
        rows += js["data"]
        if page >= int(js.get("last_page", 1)):
            break
        page += 1
        time.sleep(1.2)
    df = pd.DataFrame(rows)
    df["gasDayStart"] = pd.to_datetime(df["gasDayStart"])
    for c in NUMERIC:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values("gasDayStart").drop_duplicates("gasDayStart").set_index("gasDayStart")
    keep = [c for c in NUMERIC + ["status"] if c in df]
    path.parent.mkdir(parents=True, exist_ok=True)
    df[keep].to_csv(path)
    return df[keep]
