"""B0 (prereg/tests_v2.json): ex post transmission diagnostic at the EIA print. Not a strategy: no position uses the surprise.

Events: Wednesday releases of audit/eia_release_registry.csv (release assumed 10:30 ET), 2013-08-01..2023-12-31 and 2026-06-01..2026-10-24.
Outcome: dP = close of the minute starting 10:35 minus close of the minute starting 10:29 (HistData WTI bid, New York clock, rule AM1);
secondary: minute starting 11:00 minus minute starting 10:29. Surprise: first-published weekly change minus a recursive AR(2) forecast
(Cushing, US commercial crude excluding Cushing, gasoline, distillate; million barrels). Model: OLS of dP on a constant and the four
surprises with HC1 errors. The clock check runs first; below 70% the test is BLOCKED and no outcome statistic is computed.

Usage: python scripts/b0_transmission.py [--dry] [--amended]
  --dry       event availability only (exclusions by reason); no price difference, no statistic, nothing written
  --amended   amendment AM-B0-1 (results/v2/deviations_v2.md): year-wise clock gate instead of the argmax share; output results/v2/B0_amended
Outputs: results/v2/B0/b0.json, events.csv, sanity_clock.json, b0.log; one line in results/v2/trial_log_v2.csv
"""
import argparse
import csv
import datetime as dt
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

from altdata import histdata  # noqa: E402
from altdata.v2common import V2, assert_prereg_v2_frozen  # noqa: E402

OUT = V2 / "B0"
REGISTRY = ROOT / "audit" / "eia_release_registry.csv"
TIMES = ROOT / "audit" / "eia_release_times.csv"
FIRST = V2 / "eia_first_release.csv"
TRIAL_LOG = V2 / "trial_log_v2.csv"
SCRIPT = "scripts/b0_transmission.py"
NY = histdata.NY
PERIODS = [("2013-08-01", "2023-12-31"), ("2026-06-01", "2026-10-24")]
SANITY_MIN_SHARE = 0.70
MIN_ROWS = 104
VARS = ["cushing", "us_ex_cushing", "gasoline", "distillate"]
REASONS = ["holiday_shifted", "data_only_same_day", "other_release_time", "no_minute_data", "missing_1029_or_1035", "no_surprise"]
GRID_START = "09:59"      # grid of 62 minute starts: 09:59 .. 11:00; position of HH:MM = 60 * (HH - 9) + MM - 59
POS = {"1029": 30, "1030": 31, "1035": 36, "1100": 61}


class Log:
    def __init__(self, path: Path | None):
        self.f = open(path, "a", encoding="utf-8", newline="\n") if path else None

    def __call__(self, *parts) -> None:
        line = f"{dt.datetime.now().isoformat(timespec='seconds')} " + " ".join(str(p) for p in parts)
        print(line, flush=True)
        if self.f:
            self.f.write(line + "\n")
            self.f.flush()


def append_trial(test_id: str, sha: str, verdict: str, seconds: float, note: str) -> None:
    """One line in the shared trial log (append only, one write call); a 6-column header written by another process gets the note inside the verdict."""
    row = [test_id, dt.datetime.now().isoformat(timespec="seconds"), SCRIPT, sha, verdict, f"{seconds:.1f}", note]
    head = None
    if TRIAL_LOG.exists():
        with open(TRIAL_LOG, "r", encoding="utf-8") as f:
            head = f.readline().strip().split(",")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    if head is None:
        w.writerow(["id", "timestamp", "script", "prereg_v2_sha256", "verdict", "seconds", "note"])
    elif "note" not in head:
        row = row[:4] + [f"{verdict} [{note}]", row[5]]
    w.writerow(row)
    with open(TRIAL_LOG, "ab") as f:
        f.write(buf.getvalue().encode("utf-8"))


def folder_day(url: pd.Series) -> pd.Series:
    return pd.to_datetime(url.str.extract(r"/archive/\d{4}/([^/]+)/")[0].str[:10], format="%Y_%m_%d")


def regime(day: pd.Timestamp) -> str:
    """Daylight-saving state of New York and of Athens (the file clock of rule AM1) at noon UTC of the day."""
    noon = pd.Timestamp(day.year, day.month, day.day, 12, tz="UTC")
    us, eu = noon.tz_convert(NY).dst() != pd.Timedelta(0), noon.tz_convert("Europe/Athens").dst() != pd.Timedelta(0)
    return {(True, True): "both_summer", (False, False): "both_winter", (True, False): "us_summer_eu_winter", (False, True): "us_winter_eu_summer"}[(us, eu)]


def candidate_events() -> pd.DataFrame:
    """Registry rows without the data-only note, dated by the archive folder, inside the two periods; flags for the first three exclusion reasons."""
    reg = pd.read_csv(REGISTRY, parse_dates=["release_date", "week_ending_friday"])
    reg["folder_day"] = folder_day(reg["source_url"])
    reg["data_only"] = reg["note"].fillna("").str.contains("data-only folder")
    ev = reg[~reg["data_only"]].copy()
    ev["page_release_date"], ev["event_day"] = ev["release_date"], ev["folder_day"]
    keep = np.zeros(len(ev), bool)
    for lo, hi in PERIODS:
        keep |= ((ev["event_day"] >= lo) & (ev["event_day"] <= hi)).to_numpy()
    ev = ev[keep].sort_values("event_day").reset_index(drop=True)
    if not ev["event_day"].is_unique:
        raise SystemExit("STOP: two registry rows share one archive folder date")
    times = pd.read_csv(TIMES, parse_dates=["release_date"])
    other = times[(times["weekday"] == "Wednesday") & times["release_time_et"].notna() & (times["release_time_et"].astype(str).str.strip() != "10:30 a.m.")]
    ev["weekday"] = ev["event_day"].dt.day_name()
    ev["holiday_shifted"] = ev["weekday"] != "Wednesday"
    ev["data_only_same_day"] = ev["event_day"].isin(set(reg.loc[reg["data_only"], "release_date"]))
    ev["other_release_time"] = ev["event_day"].isin(set(other["release_date"]))
    return ev[["event_day", "weekday", "page_release_date", "folder_day", "week_ending_friday", "holiday_shifted", "data_only_same_day", "other_release_time"]]


def minute_arrays(close: pd.Series, days: pd.Series) -> dict:
    """Closes at the 62 minute starts 09:59..11:00 ET of each day (NaN where there is no bar)."""
    out = {}
    for d in days:
        grid = pd.date_range(pd.Timestamp(f"{d:%Y-%m-%d} {GRID_START}", tz=NY), periods=62, freq="min")
        out[d] = close.reindex(grid).to_numpy(float)
    return out


def first_release_weekly() -> tuple[pd.DatetimeIndex, dict, pd.DataFrame]:
    """Weekly Friday grid, first-published changes (million barrels) of the four series, and the week of each archive folder day."""
    fr = pd.read_csv(FIRST, parse_dates=["release_date", "week_ending"])
    fr["folder_day"] = folder_day(fr["source_url"])
    fr = fr.sort_values(["week_ending", "release_date"]).drop_duplicates("week_ending", keep="first").set_index("week_ending").sort_index()
    cur = {"cushing": fr["cushing_kbbl"], "us_ex_cushing": fr["us_comm_crude_kbbl"] - fr["cushing_kbbl"], "gasoline": fr["gasoline_kbbl"], "distillate": fr["distillate_kbbl"]}
    pri = {"cushing": fr["cushing_prior_kbbl"], "us_ex_cushing": fr["us_comm_crude_prior_kbbl"] - fr["cushing_prior_kbbl"],
           "gasoline": fr["gasoline_prior_kbbl"], "distillate": fr["distillate_prior_kbbl"]}
    grid = pd.date_range(fr.index.min(), fr.index.max(), freq="7D")
    chg = {k: ((cur[k] - pri[k]).astype(float) / 1000.0).reindex(grid) for k in VARS}
    by_day = fr.reset_index().set_index("folder_day")[["week_ending"]]
    if not by_day.index.is_unique:
        raise SystemExit("STOP: two first-release rows share one archive folder date")
    return grid, chg, by_day


def ar2_forecast(v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Recursive AR(2) with intercept: forecast of week t from OLS on the weeks strictly before t whose value and two lags exist (at least MIN_ROWS)."""
    n = len(v)
    X = np.column_stack([np.ones(n), np.r_[np.nan, v[:-1]], np.r_[np.nan, np.nan, v[:-2]]])
    ok = np.isfinite(v) & np.isfinite(X).all(axis=1)
    fc, rows = np.full(n, np.nan), np.zeros(n, int)
    for t in range(n):
        idx = np.flatnonzero(ok[:t])
        rows[t] = len(idx)
        if len(idx) >= MIN_ROWS and np.isfinite(X[t]).all():
            fc[t] = X[t] @ np.linalg.lstsq(X[idx], v[idx], rcond=None)[0]
    return fc, rows


def sanity_check(G: dict, days: list) -> dict:
    """Minute (10:00..10:59 ET) with the largest absolute close-to-close change on each day; share that is the 10:30 minute; profile 10:15..10:45."""
    A = np.vstack([np.abs(G[d][1:61] - G[d][:60]) for d in days])
    has = np.isfinite(A).any(axis=1)
    arg = np.where(has, np.argmax(np.where(np.isfinite(A), A, -np.inf), axis=1), -1)
    dist = {f"10:{k:02d}": int((arg == k).sum()) for k in range(60) if (arg == k).any()}
    yrs, reg = np.array([d.year for d in days]), np.array([regime(d) for d in days])
    by = lambda lab: {str(k): {"n": int((lab == k).sum()), "share_1030": float((arg[lab == k] == 30).mean())} for k in sorted(set(lab))}  # noqa: E731
    prof = {f"10:{k:02d}": {"mean_abs_change_cents": float(100 * np.nanmean(A[:, k])), "n": int(np.isfinite(A[:, k]).sum())} for k in range(15, 46)}
    return {"n_events": len(days), "n_events_with_a_change": int(has.sum()), "n_argmax_1030": int((arg == 30).sum()), "share_1030": float((arg == 30).mean()),
            "share_within_1_minute_of_1030": float((np.abs(arg - 30) <= 1).mean()), "argmax_distribution": dist, "by_year": by(yrs), "by_clock_regime": by(reg),
            "profile_abs_change": prof}


def year_gate(G: dict, days: list) -> dict:
    """AM-B0-1: per calendar year, the mean absolute one-minute change over 10:15..10:45 must peak at 10:30 and exceed 3x its 10:15..10:29 mean."""
    A = np.vstack([np.abs(G[d][1:61] - G[d][:60]) for d in days])
    yrs = np.array([d.year for d in days])
    out = {}
    for y in sorted(set(yrs)):
        m = np.nanmean(A[yrs == y][:, 15:46], axis=0)
        peak, base = 15 + int(np.nanargmax(m)), float(np.nanmean(m[:15]))
        out[str(y)] = {"n": int((yrs == y).sum()), "peak_minute": f"10:{peak:02d}", "mean_1030_cents": float(100 * m[15]), "mean_1015_1029_cents": float(100 * base),
                       "passed": bool(peak == 30 and m[15] > 3 * base)}
    return out


def fit(y: np.ndarray, X: np.ndarray) -> dict:
    res = sm.OLS(y, sm.add_constant(X, has_constant="add")).fit(cov_type="HC1")
    ci = res.conf_int(alpha=0.05)
    coef = {}
    for i, name in enumerate(["const"] + VARS):
        coef[name] = {"coef_usd_per_mb": float(res.params[i]), "coef_cents_per_mb": float(100 * res.params[i]), "se_cents_per_mb": float(100 * res.bse[i]),
                      "t": float(res.tvalues[i]), "p_two_sided": float(res.pvalues[i]), "ci95_cents_per_mb": [float(100 * ci[i, 0]), float(100 * ci[i, 1])]}
    return {"n": int(res.nobs), "r2": float(res.rsquared), "r2_adjusted": float(res.rsquared_adj), "cov_type": "HC1", "interval": "normal approximation (statsmodels default for robust covariance)",
            "coefficients": coef}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--amended", action="store_true")
    args = ap.parse_args()
    global OUT
    if args.amended:
        OUT = V2 / "B0_amended"
    t0 = time.time()
    sha = assert_prereg_v2_frozen()
    if not args.dry:
        OUT.mkdir(parents=True, exist_ok=True)
        if (OUT / "b0.json").exists():
            raise SystemExit("STOP: results/v2/B0/b0.json exists; B0 is run once")
    log = Log(None if args.dry else OUT / "b0.log")
    log(f"start B0 dry={args.dry} prereg_v2 {sha[:12]}")
    histdata.selftest()

    ev = candidate_events()
    close = histdata.load_close("WTIUSD", PERIODS[0][0], PERIODS[-1][1])
    log(f"minute bars loaded: {len(close)} from {close.index[0]} to {close.index[-1]}")
    G = minute_arrays(close, ev["event_day"])
    ev["n_bars_1000_1059"] = [int(np.isfinite(G[d][1:61]).sum()) for d in ev["event_day"]]
    ev["no_minute_data"] = ev["n_bars_1000_1059"] == 0
    ev["missing_1029_or_1035"] = [not (np.isfinite(G[d][POS["1029"]]) and np.isfinite(G[d][POS["1035"]])) for d in ev["event_day"]]
    has_1100 = np.array([np.isfinite(G[d][POS["1100"]]) for d in ev["event_day"]])

    # surprises: availability here, values only after the clock check
    grid, chg, by_day = first_release_weekly()
    fc, rows = {}, {}
    for k in VARS:
        fc[k], rows[k] = ar2_forecast(chg[k].to_numpy(float))
    week = ev["event_day"].map(by_day["week_ending"])
    pos = np.array([grid.get_loc(w) if pd.notna(w) else -1 for w in week])
    detail = []
    for i in range(len(ev)):
        if pos[i] < 0:
            detail.append("no_first_release_row")
        elif not all(np.isfinite(fc[k][pos[i]]) for k in VARS):
            detail.append("short_history" if rows["cushing"][pos[i]] < MIN_ROWS else "lag_missing")
        else:
            detail.append("")
    ev["week_ending"], ev["no_surprise_detail"] = week, detail
    ev["no_surprise"] = ev["no_surprise_detail"] != ""

    first = np.full(len(ev), "", dtype=object)
    for r in REASONS:
        first = np.where((first == "") & ev[r].to_numpy(), r, first)
    ev["reason"] = first
    ev["status"] = np.where(first == "", "included", "excluded")
    n_cand = len(ev)
    waterfall = {r: int((first == r).sum()) for r in REASONS}
    flags = {r: int(ev[r].sum()) for r in REASONS}
    sanity_days = list(ev.loc[ev["reason"].isin(["", "no_surprise"]), "event_day"])
    log(f"candidate events {n_cand}; excluded by first reason {waterfall}; independent flags {flags}")
    log(f"no-surprise detail {dict(pd.Series(detail).value_counts())}; events entering the clock check {len(sanity_days)}; included {int((first == '').sum())}")
    if args.dry:
        log("dry run: no price difference, no statistic computed")
        return

    # clock check (first)
    san = sanity_check(G, sanity_days)
    any_bar = ev.loc[~ev["reason"].isin(REASONS[:3]) & (ev["n_bars_1000_1059"] > 0), "event_day"]
    san_all = sanity_check(G, list(any_bar))
    san.update({"threshold": SANITY_MIN_SHARE, "passed": bool(san["share_1030"] >= SANITY_MIN_SHARE), "prereg_v2_sha256": sha, "id": "B0_sanity_clock",
                "definition": "events not excluded for holiday shift, data-only day, other release time, no minute data or a missing 10:29 / 10:35 minute; "
                              "change of minute m = close(m) - close(m - 1 minute), both bars present; argmax over the minutes starting 10:00..10:59 ET",
                "alternative_denominator_all_event_days_with_a_bar_10_11": {k: san_all[k] for k in ("n_events", "n_argmax_1030", "share_1030")}})
    (OUT / "sanity_clock.json").write_text(json.dumps(san, indent=2), encoding="utf-8")
    log(f"clock check: {san['n_argmax_1030']} of {san['n_events']} events have the 10:30 minute as the largest move: share {san['share_1030']:.4f} "
        f"(threshold {SANITY_MIN_SHARE}); alternative denominator {san_all['n_argmax_1030']}/{san_all['n_events']} = {san_all['share_1030']:.4f}")
    log("argmax distribution (top 8):", dict(sorted(san["argmax_distribution"].items(), key=lambda kv: -kv[1])[:8]))

    common = {"id": "B0", "prereg_v2_sha256": sha, "periods": PERIODS, "data": {"pair": "WTIUSD", "n_bars": int(len(close)), "first_bar": str(close.index[0]), "last_bar": str(close.index[-1])},
              "events": {"candidates": n_cand, "excluded_by_first_reason": waterfall, "independent_flags": flags, "no_surprise_detail": {k: int(v) for k, v in pd.Series(detail).value_counts().items() if k}},
              "sanity_clock": {k: san[k] for k in ("n_events", "n_argmax_1030", "share_1030", "threshold", "passed", "share_within_1_minute_of_1030", "profile_abs_change", "argmax_distribution")}}
    cols = ["event_day", "weekday", "page_release_date", "folder_day", "week_ending", "status", "reason", "no_surprise_detail"] + REASONS + ["n_bars_1000_1059"]
    if args.amended:
        gate = year_gate(G, sanity_days)
        failed = {int(y) for y, g in gate.items() if not g["passed"]}
        first = np.where((first == "") & ev["event_day"].dt.year.isin(failed).to_numpy(), "clock_gate_year", first)
        ev["reason"] = first
        ev["status"] = np.where(first == "", "included", "excluded")
        san["passed"] = bool((first == "").sum() >= 200)
        common["amendment"] = {"id": "AM-B0-1", "status": "EXPLORATORY (validity gate amended after the first run)", "year_gate": gate,
                               "years_excluded": sorted(failed), "events_after_gate": int((first == "").sum())}
        log("AM-B0-1 year gate:", {y: (g["peak_minute"], round(g["mean_1030_cents"], 1), round(g["mean_1015_1029_cents"], 1), g["passed"]) for y, g in gate.items()})
    if not san["passed"]:
        out = {**common, "status": "BLOCKED", "verdict": "BLOCKED", "note": "clock check below the threshold; no outcome statistic computed"}
        ev[cols].to_csv(OUT / "events.csv", index=False, date_format="%Y-%m-%d")
        (OUT / "b0.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        secs = time.time() - t0
        append_trial("B0-AM1" if args.amended else "B0", sha, "BLOCKED", secs, f"clock share {san['share_1030']:.3f} < {SANITY_MIN_SHARE}")
        log(f"BLOCKED; wrote results/v2/B0; done in {secs:.1f}s")
        return

    # outcome, surprises, model
    inc = np.flatnonzero(first == "")
    for name in ("close_1029", "close_1035", "close_1100", "dP_1035_usd", "dP_1100_usd"):
        ev[name] = np.nan
    for k in VARS:
        for p in ("chg", "fc", "sur"):
            ev[f"{p}_{k}"] = np.nan
    for i in inc:
        g = G[ev.at[i, "event_day"]]
        ev.at[i, "close_1029"], ev.at[i, "close_1035"], ev.at[i, "close_1100"] = g[POS["1029"]], g[POS["1035"]], g[POS["1100"]]
        ev.at[i, "dP_1035_usd"], ev.at[i, "dP_1100_usd"] = g[POS["1035"]] - g[POS["1029"]], g[POS["1100"]] - g[POS["1029"]]
        for k in VARS:
            c, f = chg[k].to_numpy(float)[pos[i]], fc[k][pos[i]]
            ev.at[i, f"chg_{k}"], ev.at[i, f"fc_{k}"], ev.at[i, f"sur_{k}"] = c, f, c - f
    S = ev.loc[inc]
    Xs = S[[f"sur_{k}" for k in VARS]].to_numpy(float)
    m1 = fit(S["dP_1035_usd"].to_numpy(float), Xs)
    S2 = S[np.isfinite(S["dP_1100_usd"])]
    m2 = fit(S2["dP_1100_usd"].to_numpy(float), S2[[f"sur_{k}" for k in VARS]].to_numpy(float))
    cu = m1["coefficients"]["cushing"]
    verdict = "TRANSMISSION DETECTED" if cu["ci95_cents_per_mb"][1] < 0 else "NOT DETECTED"
    top = S.reindex(S["dP_1035_usd"].abs().sort_values(ascending=False).index).head(5)
    desc = {"n": int(len(S)), "mean_dP_1035_cents": float(100 * S["dP_1035_usd"].mean()), "sd_dP_1035_cents": float(100 * S["dP_1035_usd"].std(ddof=1)),
            "sd_dP_1100_cents": float(100 * S2["dP_1100_usd"].std(ddof=1)), "sd_surprise_million_bbl": {k: float(S[f"sur_{k}"].std(ddof=1)) for k in VARS},
            "events_by_year": {str(k): int(v) for k, v in S["event_day"].dt.year.value_counts().sort_index().items()},
            "largest_abs_dP_1035": [{"event_day": str(r.event_day.date()), "dP_1035_usd": float(r.dP_1035_usd)} for r in top.itertuples()]}
    out = {**common, "status": "COMPLETED", "verdict": verdict, "included_events": int(len(S)), "secondary_events_with_1100": int(len(S2)), "descriptives": desc,
           "primary": {"outcome": "close(10:35) - close(10:29), USD per barrel", "unit": "cents per barrel per million barrels", "cushing": cu, "n": m1["n"], "verdict": verdict,
                       "us_ex_cushing_reference": m1["coefficients"]["us_ex_cushing"]},
           "model_primary": m1, "model_secondary": {"outcome": "close(11:00) - close(10:29), USD per barrel", **m2}}
    ev[cols + ["close_1029", "close_1035", "close_1100", "dP_1035_usd", "dP_1100_usd"] + [f"{p}_{k}" for k in VARS for p in ("chg", "fc", "sur")]].to_csv(
        OUT / "events.csv", index=False, date_format="%Y-%m-%d", float_format="%.6f")
    (OUT / "b0.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(f"included {len(S)} events (secondary {len(S2)}); sd dP {desc['sd_dP_1035_cents']:.1f} cents; sd surprises {({k: round(v, 3) for k, v in desc['sd_surprise_million_bbl'].items()})}")
    for nm, m in (("primary 10:35", m1), ("secondary 11:00", m2)):
        log(nm, f"n {m['n']} R2 {m['r2']:.4f}", {k: (round(v["coef_cents_per_mb"], 2), round(v["t"], 2)) for k, v in m["coefficients"].items()})
    log(f"PRIMARY Cushing {cu['coef_cents_per_mb']:.3f} cents per barrel per Mb, t {cu['t']:.3f}, 95% CI [{cu['ci95_cents_per_mb'][0]:.3f}, {cu['ci95_cents_per_mb'][1]:.3f}] -> {verdict}")
    secs = time.time() - t0
    ex = m1["coefficients"]["us_ex_cushing"]
    append_trial("B0-AM1" if args.amended else "B0", sha, verdict, secs, f"n {m1['n']}; clock share {san['share_1030']:.3f}; Cushing {cu['coef_cents_per_mb']:.2f} c/bbl per Mb "
                 f"(95% CI {cu['ci95_cents_per_mb'][0]:.2f} to {cu['ci95_cents_per_mb'][1]:.2f}); US ex-Cushing {ex['coef_cents_per_mb']:.2f}")
    log(f"wrote results/v2/B0/b0.json, events.csv, sanity_clock.json; trial log line appended; done in {secs:.1f}s")


if __name__ == "__main__":
    main()
