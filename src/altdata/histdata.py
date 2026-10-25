"""HistData M1 (ASCII) loader: minute closes indexed by America/New_York timestamps (start of the minute).

File clock = amendment AM1 of deliverables_v2/analysis/prereg_intraday_momentum_amendments.json (evidence: histdata_clock_audit2-4.py):
file time before 2019-01-01 is New York local time; from 2019-01-01 it is Europe/Athens local time minus 7 hours. Local times that are
repeated or do not exist at a clock change give NaT and are dropped (they fall on weekends). The bars are bid-only and are not filled:
a minute without a bar is absent from the series. Bars that share one instant (vendor duplicates) are reduced to the one with the widest
high-low range, ties to the later row of the file.
"""
from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# HistData zips are not redistributed: download DAT_ASCII_WTIUSD_M1_<year|yyyymm>.zip from histdata.com and point
# ALTDATA_HISTDATA_DIR at the folder (default: the author's local folder).
DATA_DIR = Path(os.environ.get("ALTDATA_HISTDATA_DIR", "C:/Users/Hamza/market_data/histdata"))
NY = "America/New_York"
AM1_SWITCH = pd.Timestamp("2019-01-01")
ATHENS_SHIFT = pd.Timedelta(hours=7)
_NAME = re.compile(r"DAT_ASCII_(?P<pair>[A-Z0-9]+)_M1_(?P<ym>\d{4}|\d{6})\.zip$")


def file_span(path: Path) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calendar span covered by a file name (year or year-month), widened by two days for the clock offset."""
    ym = _NAME.search(path.name).group("ym")
    first = pd.Timestamp(int(ym[:4]), int(ym[4:]) if len(ym) == 6 else 1, 1)
    last = first + (pd.offsets.MonthEnd(0) if len(ym) == 6 else pd.offsets.YearEnd(0))
    return first - pd.Timedelta(days=2), last + pd.Timedelta(days=2)


def list_files(pair: str, start=None, end=None, data_dir: Path = DATA_DIR) -> list[Path]:
    """Zip files of one instrument, in chronological order, optionally only those that can hold bars of the NY dates start..end."""
    out = []
    for f in sorted(data_dir.glob(f"DAT_ASCII_{pair}_M1_*.zip")):
        if not _NAME.search(f.name):
            continue
        lo, hi = file_span(f)
        if (start is not None and hi < pd.Timestamp(start)) or (end is not None and lo > pd.Timestamp(end)):
            continue
        out.append(f)
    return out


def read_zip(path: Path) -> pd.DataFrame:
    """Raw bars of one zip: file_time (naive, file clock), high, low, close; file order kept."""
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as fh:
            raw = pd.read_csv(fh, sep=";", header=None, names=["ts", "o", "h", "l", "c", "v"], usecols=["ts", "h", "l", "c"],
                              dtype={"ts": str, "h": float, "l": float, "c": float})
    return pd.DataFrame({"file_time": pd.to_datetime(raw["ts"], format="%Y%m%d %H%M%S"), "high": raw["h"], "low": raw["l"], "close": raw["c"]})


def file_time_to_utc(file_time: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    """UTC instants (naive datetime64[ns], NaT where the local time is repeated or missing) of file-clock times, rule AM1."""
    ft = pd.DatetimeIndex(file_time)
    out = np.full(len(ft), np.datetime64("NaT"), dtype="datetime64[ns]")
    old = np.asarray(ft < AM1_SWITCH)
    for mask, shift, tz in ((old, pd.Timedelta(0), NY), (~old, ATHENS_SHIFT, "Europe/Athens")):
        if mask.any():
            local = (ft[mask] + shift).tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
            out[mask] = local.tz_convert("UTC").tz_localize(None).values.astype("datetime64[ns]")
    return out


def load_bars(pair: str = "WTIUSD", start=None, end=None, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Bars (close, high, low) indexed by the New York start of the minute, duplicates reduced, sorted, restricted to NY dates start..end."""
    frames = []
    for f in list_files(pair, start, end, data_dir):
        d = read_zip(f)
        d["order"] = np.arange(len(d))
        d["file"] = f.name
        frames.append(d)
    if not frames:
        raise FileNotFoundError(f"no HistData M1 files for {pair} in {data_dir}")
    df = pd.concat(frames, ignore_index=True)
    df["utc"] = file_time_to_utc(df["file_time"])
    df = df[df["utc"].notna()].copy()
    df["range"] = df["high"] - df["low"]
    df = df.sort_values(["utc", "range", "file", "order"]).drop_duplicates("utc", keep="last").sort_values("utc")
    df.index = pd.DatetimeIndex(df["utc"]).tz_localize("UTC").tz_convert(NY)
    df.index.name = "minute_start_ny"
    if start is not None:
        df = df[df.index >= pd.Timestamp(start, tz=NY)]
    if end is not None:
        df = df[df.index < pd.Timestamp(end, tz=NY) + pd.Timedelta(days=1)]
    return df[["close", "high", "low"]]


def load_close(pair: str = "WTIUSD", start=None, end=None, data_dir: Path = DATA_DIR) -> pd.Series:
    """Series of minute closes (bid) indexed by America/New_York timestamps of the start of the minute; no fill of missing minutes."""
    s = load_bars(pair, start, end, data_dir)["close"]
    s.name = pair
    return s


def selftest() -> None:
    """Known conversions of rule AM1 (summer, winter, the March / October windows where US and EU clocks differ, skipped and repeated hours)."""
    def ny(ts: str) -> str:
        u = file_time_to_utc(pd.DatetimeIndex([ts]))[0]
        return "NaT" if np.isnat(u) else str(pd.Timestamp(u, tz="UTC").tz_convert(NY))

    assert ny("2016-07-13 10:30") == "2016-07-13 10:30:00-04:00"
    assert ny("2016-12-14 10:30") == "2016-12-14 10:30:00-05:00"
    assert ny("2021-07-14 10:30") == "2021-07-14 10:30:00-04:00"
    assert ny("2021-12-15 10:30") == "2021-12-15 10:30:00-05:00"
    assert ny("2021-03-17 09:30") == "2021-03-17 10:30:00-04:00"      # US summer time, EU winter time: file clock one hour behind New York
    assert ny("2021-11-03 09:30") == "2021-11-03 10:30:00-04:00"
    assert ny("2021-10-27 09:30") == "2021-10-27 09:30:00-04:00"      # both on summer time: file clock equals New York
    assert ny("2016-03-16 10:30") == "2016-03-16 10:30:00-04:00"      # before 2019 the file follows New York dates
    assert ny("2021-10-30 20:30") == "NaT"                            # Athens 03:30 on 2021-10-31 is repeated
    assert ny("2021-03-27 20:30") == "NaT"                            # Athens 03:30 on 2021-03-28 does not exist
    assert ny("2016-11-06 01:30") == "NaT"                            # New York 01:30 repeated


if __name__ == "__main__":
    selftest()
    print("histdata selftest ok")
