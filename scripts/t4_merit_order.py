"""T4 (pre-registered): merit order in German day-ahead prices.

H: a higher forecast share of wind and solar in next-day load lowers the day-ahead price (DE-LU, ENTSO-E, 2019-2025).
Definitions: prereg/tests_v1.json and results/deviations.md. Run once on the full period (prereg common.run_once).

Usage: python scripts/t4_merit_order.py
Outputs: results/T4.json, results/T4_daily.csv, results/T4.log, a section appended to results/coverage.md
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata import entsoe_client as ec  # noqa: E402
from altdata.paths import RESULTS, assert_prereg_frozen  # noqa: E402
from altdata.runlog import RunLog, append_coverage, trial_log  # noqa: E402
from altdata.stats import ols_hac  # noqa: E402

YEARS = range(2019, 2026)
MIN_COVER = 0.90
LAGS = 7


def daily(series: pd.Series) -> pd.DataFrame:
    """Mean per Europe/Berlin delivery day, with the share of that day's hours that hold at least one observation."""
    s = series.dropna()
    frame = pd.DataFrame({"v": s.to_numpy(), "day": s.index.normalize(), "hour": s.index.tz_convert("UTC").floor("h")})
    g = frame.groupby("day")
    out = pd.DataFrame({"mean": g["v"].mean(), "hours": g["hour"].nunique(), "n_obs": g["v"].size()})
    expected = ((out.index + pd.DateOffset(days=1)) - out.index).total_seconds() / 3600.0
    out["cover"] = out["hours"] / expected
    out.index = out.index.tz_localize(None)
    return out


def design(df: pd.DataFrame, month_year: bool = True) -> np.ndarray:
    key = df.index.to_period("M").astype(str) if month_year else df.index.month.astype(str)
    m = pd.get_dummies(pd.Series(key, index=df.index), drop_first=True).to_numpy(float)
    w = pd.get_dummies(pd.Series(df.index.dayofweek, index=df.index), drop_first=True).to_numpy(float)
    return np.column_stack([df["S"].to_numpy(float), m, w])


def main() -> None:
    log = RunLog("T4")
    sha = assert_prereg_frozen()
    log("prereg hash", sha)
    prices, ws, load = [], [], []
    for y in YEARS:
        prices.append(ec.day_ahead_prices(y))
        ws.append(ec.wind_solar_forecast(y))
        load.append(ec.load_forecast(y))
        log("fetched", y, "prices", len(prices[-1]), "wind/solar", len(ws[-1]), "load", len(load[-1]))
    price_s = pd.concat(prices).sort_index()
    price_s = price_s[~price_s.index.duplicated(keep="last")]
    ws_df = pd.concat(ws).sort_index()
    ws_df = ws_df[~ws_df.index.duplicated(keep="last")]
    ws_s = ws_df[["Solar", "Wind Onshore", "Wind Offshore"]].sum(axis=1, min_count=3)
    load_s = pd.concat(load).sort_index()
    load_s = load_s[~load_s.index.duplicated(keep="last")]

    dp, dw, dl = daily(price_s), daily(ws_s), daily(load_s)
    d = pd.DataFrame({"P": dp["mean"], "ws": dw["mean"], "load": dl["mean"], "cp": dp["cover"], "cw": dw["cover"], "cl": dl["cover"]})
    d = d[(d.index >= "2019-01-01") & (d.index <= "2025-12-31")]
    complete = (d[["cp", "cw", "cl"]].min(axis=1) >= MIN_COVER) & d[["P", "ws", "load"]].notna().all(axis=1)
    d["S"] = d["ws"] / d["load"]
    used = d[complete].copy()

    # integrity checks (appended to coverage.md)
    by_year = pd.DataFrame({
        "calendar days": d.groupby(d.index.year).size(), "days used": used.groupby(used.index.year).size(),
        "price obs": price_s.groupby(price_s.index.tz_convert(ec.TZ).year).size(),
        "wind+solar obs": ws_s.dropna().groupby(ws_s.dropna().index.tz_convert(ec.TZ).year).size(),
        "load obs": load_s.dropna().groupby(load_s.dropna().index.tz_convert(ec.TZ).year).size()}).fillna(0).astype(int)
    by_year["share used"] = (by_year["days used"] / by_year["calendar days"]).round(3)
    body = (f"Zone {ec.ZONE} (EIC 10Y1001A1001A82H), time zone {ec.TZ}. Units: prices EUR/MWh (min {price_s.min():.1f}, max {price_s.max():.1f}); "
            f"wind and solar forecast MW (max {ws_s.max():.0f}); load forecast MW (min {load_s.min():.0f}, max {load_s.max():.0f}). "
            f"Rule: a day is used if prices, the wind and solar forecast and the load forecast each cover at least {MIN_COVER:.0%} of its hours.\n\n"
            + by_year.reset_index().rename(columns={"index": "year"}).to_markdown(index=False)
            + f"\n\nDays used: {len(used)} of {len(d)}; S_d range {used['S'].min():.2f} to {used['S'].max():.2f}.")
    append_coverage("8. T4 integrity checks (ENTSO-E DE-LU)", body)
    log("days used", len(used), "of", len(d), "; S range", round(used["S"].min(), 3), round(used["S"].max(), 3))

    reg = ols_hac(used["P"].to_numpy(float), design(used), LAGS)
    b, se, t = reg["b"][0], reg["se"][0], reg["t"][0]
    years = {}
    for y, g in used.groupby(used.index.year):
        r = ols_hac(g["P"].to_numpy(float), design(g, month_year=False), LAGS)
        years[int(y)] = {"n": r["n"], "b_per_1.00": r["b"][0], "t": r["t"][0]}
    out = {"id": "T4", "prereg_sha256": sha, "zone": ec.ZONE, "period": ["2019-01-01", "2025-12-31"], "n_days": int(reg["n"]),
           "days_in_period": int(len(d)), "b_eur_mwh_per_1.00_share": b, "b_eur_mwh_per_10pp": b / 10.0, "se": se, "t_nw7": t,
           "mean_price": float(used["P"].mean()), "mean_S": float(used["S"].mean()), "by_year": years,
           "verdict": "SUPPORTED" if t <= -5.0 else "NOT SUPPORTED"}
    (RESULTS / "T4.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    used[["P", "S"]].to_csv(RESULTS / "T4_daily.csv")
    log("b per +10 pp of S:", round(b / 10, 2), "EUR/MWh; t", round(t, 2), "n", reg["n"], "->", out["verdict"])
    log("by year", {y: (round(v["b_per_1.00"] / 10, 1), round(v["t"], 1)) for y, v in years.items()})
    secs = log.close()
    trial_log("T4", "scripts/t4_merit_order.py", sha, out["verdict"], secs)


if __name__ == "__main__":
    main()
