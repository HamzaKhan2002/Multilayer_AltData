"""EIA dnav history files: XLS downloads without an API key."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from .paths import DATA

UA = {"User-Agent": "Mozilla/5.0"}
EIA_DIR = DATA / "eia"


def path(sid: str, freq: str) -> Path:
    return EIA_DIR / f"{sid}{freq}.xls"


def fetch(area: str, sid: str, freq: str) -> Path:
    """Download the history file once; later calls reuse the cached copy."""
    EIA_DIR.mkdir(parents=True, exist_ok=True)
    p = path(sid, freq)
    if not p.exists():
        r = requests.get(f"https://www.eia.gov/dnav/{area}/hist_xls/{sid}{freq}.xls", headers=UA, timeout=120)
        r.raise_for_status()
        p.write_bytes(r.content)
    return p


def load(area: str, sid: str, freq: str, dropna: bool = True) -> pd.Series:
    """Series indexed by date (sheet 'Data 1', first value column); parsing as in the 2026-10-22 pre-test."""
    df = pd.read_excel(fetch(area, sid, freq), sheet_name="Data 1", header=2, engine="xlrd")
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values, index=pd.to_datetime(df.iloc[:, 0], errors="coerce"))
    s = s[s.index.notna()]
    if dropna:
        s = s.dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()
