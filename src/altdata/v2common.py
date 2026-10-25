"""Shared paths, guards and helpers of the pre-registered BS0-BS2 tests (prereg/tests_v2.json)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .paths import DATA, RESULTS, ROOT, sha256_file

V2 = RESULTS / "v2"
BS0, BS1, BS2, LOGS = V2 / "BS0", V2 / "BS1", V2 / "BS2", V2 / "BS_logs"
CACHE = DATA / "s2_tanks"
PREREG_V2 = ROOT / "prereg" / "tests_v2.json"
PREREG_V2_SHA = V2 / "prereg_v2.sha256"

WINDOW = (-96.782, 35.915, -96.708, 35.968)          # WGS84 lon_min, lat_min, lon_max, lat_max (prereg "common")
CAT_START, CAT_END = "2018-12-01T00:00:00Z", "2026-10-24T23:59:59Z"
PAD_M = 40.0                                         # window read from the rasters grown by this many metres
MIN_DIAM = 40.0                                      # tanks with diameter >= 40 m are fitted
CLEAR_BUFFER_M = 20.0
BAD_SCL = (3, 8, 9, 10, 11)                          # cloud shadow, cloud medium / high, thin cirrus, snow or ice
SCENE_CLOUD_MAX = 90.0
KEPT = ("ok", "wide_interval", "full_or_fixed")      # statuses that carry an estimate of d (the others abstain)
BBL_PER_M3 = 6.2898
SUN_BINS = [0, 25, 35, 45, 55, 65, 90]               # degrees; 45 is the primary-sample threshold of BS2
SEED_BS2 = 20261025
DRAWS = 5000
BLOCK = 4


def ensure_dirs() -> None:
    for p in (BS0, BS1, BS2, LOGS, CACHE):
        p.mkdir(parents=True, exist_ok=True)


def assert_prereg_v2_frozen() -> str:
    """Return the SHA-256 of prereg/tests_v2.json, or stop if it differs from the hash recorded when it was frozen."""
    recorded = PREREG_V2_SHA.read_text(encoding="ascii").split()[0].strip().lower()
    h = sha256_file(PREREG_V2)
    if h != recorded:
        raise SystemExit(f"STOP: prereg/tests_v2.json ({h}) differs from the frozen hash {recorded}")
    return h


def registry() -> pd.DataFrame:
    """The OpenStreetMap tank registry with a 'big' flag (diameter >= MIN_DIAM) and the radius in metres."""
    t = pd.read_csv(RESULTS / "tank_registry.csv")
    t["R"] = t["diameter_m"] / 2
    t["big"] = t["diameter_m"] >= MIN_DIAM
    return t


def eia_weekly(path=None) -> pd.DataFrame:
    """One row per EIA data week (index: Friday week_ending): first-published Cushing change in kbbl (earliest release kept)."""
    e = pd.read_csv(path or (V2 / "eia_first_release.csv"), parse_dates=["release_date", "week_ending"])
    e = e.sort_values(["week_ending", "release_date"]).drop_duplicates("week_ending", keep="first")
    e["change_kbbl"] = e["cushing_kbbl"] - e["cushing_prior_kbbl"]
    return e.set_index("week_ending")[["release_date", "cushing_kbbl", "cushing_prior_kbbl", "change_kbbl"]]


def ref_time_utc(F) -> pd.Timestamp:
    """Friday 07:00 America/Chicago of the data week F, in UTC."""
    d = pd.Timestamp(F).normalize()
    return pd.Timestamp(d.year, d.month, d.day, 7, tz="America/Chicago").tz_convert("UTC")


def release_deadlines_utc(F) -> tuple[pd.Timestamp, pd.Timestamp]:
    """(API Tuesday 16:30 ET, EIA Wednesday 10:30 ET) after the Friday F, in UTC."""
    d = pd.Timestamp(F).normalize()
    tue, wed = d + pd.Timedelta(days=4), d + pd.Timedelta(days=5)
    return (pd.Timestamp(tue.year, tue.month, tue.day, 16, 30, tz="America/New_York").tz_convert("UTC"),
            pd.Timestamp(wed.year, wed.month, wed.day, 10, 30, tz="America/New_York").tz_convert("UTC"))


def to_utc(s) -> pd.Series:
    """Parse ISO-8601 time stamps (with or without fractional seconds) to UTC."""
    return pd.to_datetime(s, utc=True, format="ISO8601")


def read_s2_catalog(path=None) -> pd.DataFrame:
    c = pd.read_csv(path or (BS0 / "s2_catalog.csv"))
    c["t"] = to_utc(c["datetime_utc"])
    return c


def read_fits(path=None) -> pd.DataFrame:
    f = pd.read_csv(path or (BS1 / "fits.csv.gz"))
    f["t"] = to_utc(f["datetime_utc"])
    return f


def read_acq_summary(path=None) -> pd.DataFrame:
    a = pd.read_csv(path or (BS1 / "acq_summary.csv"))
    a["t"] = to_utc(a["datetime_utc"])
    return a


def sun_bin(elev) -> pd.Series:
    """Sun-elevation bin labels such as '25-35' (left-closed)."""
    labels = [f"{SUN_BINS[i]}-{SUN_BINS[i + 1]}" for i in range(len(SUN_BINS) - 1)]
    return pd.cut(pd.Series(elev, dtype=float), SUN_BINS, right=False, labels=labels).astype(object)


def moving_blocks(rng: np.random.Generator, n: int, block: int = BLOCK) -> np.ndarray:
    """Indices 0..n-1 of one moving-block resample (overlapping blocks of `block` consecutive positions), length n."""
    block = max(1, min(block, n))
    k = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=k)
    return (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
