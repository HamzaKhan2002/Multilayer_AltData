"""BS2 (prereg/tests_v2.json): aggregate roof-depth proxy against the first-published EIA Cushing change. Run once, after the extraction.

Weekly proxy: for EIA week F the clear acquisition (at least 50% of the tank area with diameter >= 40 m clear) closest to F 07:00 CT within
+-2 days (ties: earlier). Delta V_F = -sum over tanks with an identified d at both dates of A_i (d_F - d_{F-1}), A_i the disk area, in barrels
(6.2898 bbl per m3), reported in kbbl. Primary sample: consecutive weeks, both acquisitions with sun elevation <= 45 degrees, identified tanks
covering at least 50% of the tank area at both dates. Statistic: Pearson r with the EIA change, Fisher-z 95% interval (verdict), moving-block
bootstrap of weeks (block 4, 5,000 draws, seed 20261025) as a check. Secondary: slope and RMSE, all-season sample, nowcast gain (B1 preliminary).

Usage: python scripts/bs2_aggregate.py
Outputs: results/v2/BS2/bs2.json, results/v2/BS2/weekly_table.csv
"""
import json
import math
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata import v2common as V  # noqa: E402

HALF_WINDOW = pd.Timedelta(days=2)
MIN_CLEAR_SHARE = 0.5          # acquisition clear for BS2 / BS0: at least 50% of the tank area clear
MIN_VALID_SHARE = 0.5          # tank area with an identified d at both dates
SUN_MAX = 45.0
MIN_HISTORY = 104              # AR(2) training rows before the first forecast
MIN_BETA_WEEKS = 20            # earlier valid weeks needed to estimate beta
Z95 = 1.959963984540054


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


# ------------------------------------------------------------------ weekly proxy
def analysis_weeks(eia: pd.DataFrame) -> pd.DatetimeIndex:
    """Consecutive EIA data weeks (Fridays) from the first one whose +-2 day window starts inside the catalogue, to the last published."""
    start = V.to_utc(pd.Series([V.CAT_START])).iloc[0]
    first = next(F for F in eia.index if V.ref_time_utc(F) - HALF_WINDOW >= start)
    return pd.date_range(first, eia.index.max(), freq="7D")


def select_weekly(summ: pd.DataFrame, weeks) -> pd.DataFrame:
    rows = []
    for F in weeks:
        ref = V.ref_time_utc(F)
        w = summ[((summ["t"] - ref).abs() <= HALF_WINDOW) & (summ["clear_area_share"] >= MIN_CLEAR_SHARE)]
        row = {"week_ending": F, "ref_time_utc": ref, "acq_id": None, "acq_time_utc": pd.NaT, "dt_hours": np.nan, "sun_elev": np.nan,
               "clear_area_share": np.nan, "n_clear_candidates": int(len(w))}
        if len(w):
            b = w.assign(dt=(w["t"] - ref).abs()).sort_values(["dt", "t"]).iloc[0]
            row.update(acq_id=b["acq_id"], acq_time_utc=b["t"], dt_hours=(b["t"] - ref).total_seconds() / 3600, sun_elev=float(b["sun_elev"]),
                       clear_area_share=float(b["clear_area_share"]))
        rows.append(row)
    return pd.DataFrame(rows).set_index("week_ending")


def proxy_table(fits: pd.DataFrame, sel: pd.DataFrame) -> pd.DataFrame:
    """Delta V (kbbl) and identified-area shares for every pair of consecutive weeks with a selected acquisition each."""
    kept = fits[fits["status"].isin(V.KEPT)]
    D = kept.pivot(index="osm_id", columns="acq_id", values="d_hat")
    area = (np.pi * (fits.drop_duplicates("osm_id").set_index("osm_id")["diameter_m"] / 2) ** 2)
    tot = float(area.sum())
    out = sel.copy()
    out["dV_kbbl"], out["valid_area_share_both"], out["n_valid_tanks_both"] = np.nan, np.nan, 0
    for F, r in sel.iterrows():
        a_prev = sel.loc[F - pd.Timedelta(days=7), "acq_id"] if (F - pd.Timedelta(days=7)) in sel.index else None
        a_cur = r["acq_id"]
        if a_prev is not None and a_cur is not None and isinstance(a_prev, str) and isinstance(a_cur, str) and a_prev in D and a_cur in D:
            d1, d2 = D[a_prev], D[a_cur]
            both = d1.notna() & d2.notna()
            ar = area.reindex(D.index)[both]
            out.loc[F, "dV_kbbl"] = float(-(ar * (d2[both] - d1[both])).sum() * V.BBL_PER_M3 / 1000.0)
            out.loc[F, "valid_area_share_both"] = float(ar.sum() / tot)
            out.loc[F, "n_valid_tanks_both"] = int(both.sum())
    out["sun_elev_prev"] = out["sun_elev"].shift(1)
    return out


# ------------------------------------------------------------------ statistics
def fisher_ci(r: float, n: int) -> tuple[float, float]:
    if not (n > 3 and math.isfinite(r)):
        return (float("nan"), float("nan"))
    z, se = math.atanh(max(min(r, 1 - 1e-12), -1 + 1e-12)), 1 / math.sqrt(n - 3)
    return math.tanh(z - Z95 * se), math.tanh(z + Z95 * se)


def pearson_slope(v: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    m = np.isfinite(v) & np.isfinite(y)
    n = int(m.sum())
    if n < 3:
        return float("nan"), float("nan"), n
    vv, yy = v[m], y[m]
    sv, sy = vv.std(), yy.std()
    if sv == 0 or sy == 0:
        return float("nan"), float("nan"), n
    c = float(((vv - vv.mean()) * (yy - yy.mean())).mean())
    return c / (sv * sy), c / (sv * sv), n


def boot_r_slope(v: np.ndarray, y: np.ndarray, draws: int = V.DRAWS, seed: int = V.SEED_BS2) -> dict:
    """Moving-block bootstrap (blocks of 4 consecutive calendar weeks) of r and the slope; v and y are on the calendar grid, NaN outside the sample."""
    rng = np.random.default_rng(seed)
    n = len(v)
    rs, bs = [], []
    for _ in range(draws):
        idx = V.moving_blocks(rng, n, V.BLOCK)
        r, b, k = pearson_slope(v[idx], y[idx])
        if math.isfinite(r):
            rs.append(r)
            bs.append(b)
    rs, bs = np.array(rs), np.array(bs)
    q = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))] if len(a) else [float("nan")] * 2  # noqa: E731
    return {"draws_used": int(len(rs)), "r_ci95": q(rs), "slope_ci95": q(bs)}


def verdict_r(lo: float, hi: float, n: int) -> tuple[str, str]:
    if not (n >= 5 and math.isfinite(lo)):
        return "INCONCLUSIVE", f"too few weeks (n={n})"
    note = "lower bound > 0 and upper bound < 0.20 both hold; SIGNAL listed first in the pre-registered rule" if (lo > 0 and hi < 0.20) else ""
    if lo > 0:
        return "SIGNAL", note
    if hi < 0.20:
        return "NO SIGNAL DETECTED", note
    return "INCONCLUSIVE", note


def sample_stats(v: np.ndarray, y: np.ndarray, with_verdict: bool) -> dict:
    r, slope, n = pearson_slope(v, y)
    lo, hi = fisher_ci(r, n)
    out = {"n": n, "r": r, "fisher_ci95": [lo, hi]}
    if n >= 3 and math.isfinite(slope):
        m = np.isfinite(v) & np.isfinite(y)
        icpt = float(y[m].mean() - slope * v[m].mean())
        res = y[m] - (icpt + slope * v[m])
        out.update(slope_eia_kbbl_per_kbbl=slope, intercept_kbbl=icpt, rmse_kbbl=float(np.sqrt((res ** 2).mean())),
                   rmse_constant_only_kbbl=float(y[m].std()), implied_coverage_share=(1 / slope if slope > 0 else None))
    boot = boot_r_slope(v, y)
    out["bootstrap"] = boot
    if with_verdict:
        out["verdict"], out["verdict_note"] = verdict_r(lo, hi, n)
        bl, bh = boot["r_ci95"]
        out["verdict_bootstrap_interval"] = verdict_r(bl, bh, n)[0]
        out["verdicts_agree"] = out["verdict"] == out["verdict_bootstrap_interval"]
    return out


# ------------------------------------------------------------------ nowcast (B1 preliminary)
def ar2_forecast(y: pd.Series, min_hist: int = MIN_HISTORY) -> pd.Series:
    """Recursive AR(2) with intercept: forecast of week t from OLS on the rows of weeks strictly before t (expanding window)."""
    yv = y.to_numpy(float)
    n = len(yv)
    f = np.full(n, np.nan)
    X = np.column_stack([np.ones(n - 2), yv[1:-1], yv[:-2]])
    Y = yv[2:]
    ok = np.isfinite(Y) & np.isfinite(X).all(axis=1)
    for t in range(2, n):
        if not (np.isfinite(yv[t - 1]) and np.isfinite(yv[t - 2])):
            continue
        m = ok[: t - 2]                           # rows of weeks s = 2 .. t-1
        if m.sum() < min_hist:
            continue
        beta = np.linalg.lstsq(X[: t - 2][m], Y[: t - 2][m], rcond=None)[0]
        f[t] = beta[0] + beta[1] * yv[t - 1] + beta[2] * yv[t - 2]
    return pd.Series(f, index=y.index)


def nowcast(y: pd.Series, dV: pd.Series, f0: pd.Series, draws: int = V.DRAWS, seed: int = V.SEED_BS2) -> tuple[dict, pd.DataFrame]:
    """M1 = M0 + beta * dV with beta from OLS without intercept of earlier M0 residuals on dV over earlier valid weeks (at least 20)."""
    e0 = (y - f0).to_numpy(float)
    v = dV.to_numpy(float)
    valid = np.isfinite(v) & np.isfinite(e0)
    n = len(v)
    beta = np.full(n, np.nan)
    f1 = np.full(n, np.nan)
    for t in range(n):
        if not valid[t]:
            continue
        prior = valid[:t]
        if prior.sum() < MIN_BETA_WEEKS:
            continue
        den = float((v[:t][prior] ** 2).sum())
        if den == 0:
            continue
        beta[t] = float((v[:t][prior] * e0[:t][prior]).sum()) / den
        f1[t] = f0.iloc[t] + beta[t] * v[t]
    e1 = y.to_numpy(float) - f1
    ev = np.isfinite(e1) & np.isfinite(e0)
    tab = pd.DataFrame({"m0_forecast_kbbl": f0.to_numpy(), "m0_error_kbbl": e0, "beta": beta, "m1_forecast_kbbl": f1, "m1_error_kbbl": e1,
                        "nowcast_evaluated": ev}, index=y.index)
    out = {"n_evaluated": int(ev.sum()), "min_history_weeks": MIN_HISTORY, "min_beta_weeks": MIN_BETA_WEEKS}
    if ev.sum() < 1:
        out.update(verdict="NO GAIN DETECTED", note="not evaluable: no week has 20 earlier valid weeks")
        return out, tab
    loss0, loss1 = e0[ev] ** 2, e1[ev] ** 2
    delta = np.full(n, np.nan)
    delta[ev] = e1[ev] ** 2 - e0[ev] ** 2
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(draws):
        d = delta[V.moving_blocks(rng, n, V.BLOCK)]
        d = d[np.isfinite(d)]
        if len(d):
            diffs.append(d.mean())
    lo, hi = float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))
    out.update(mse0_kbbl2=float(loss0.mean()), mse1_kbbl2=float(loss1.mean()), mse_ratio_m1_over_m0=float(loss1.mean() / loss0.mean()),
               mse_diff_m1_minus_m0=float(loss1.mean() - loss0.mean()), mse_diff_ci95=[lo, hi], draws_used=int(len(diffs)),
               verdict="GAIN" if hi < 0 else "NO GAIN DETECTED", beta_last=float(beta[np.isfinite(beta)][-1]))
    return out, tab


# ------------------------------------------------------------------ driver
def run(fits: pd.DataFrame, summ: pd.DataFrame, eia: pd.DataFrame, out_dir: Path, sha: str = "") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    weeks = analysis_weeks(eia)
    sel = select_weekly(summ, weeks)
    pt = proxy_table(fits, sel)
    pt["eia_change_kbbl"] = eia["change_kbbl"].reindex(pt.index)
    has = pt["dV_kbbl"].notna() & (pt["valid_area_share_both"] >= MIN_VALID_SHARE)
    primary = has & (pt["sun_elev"] <= SUN_MAX) & (pt["sun_elev_prev"] <= SUN_MAX)
    pt["in_all_season"], pt["in_primary"] = has, primary
    y = pt["eia_change_kbbl"].to_numpy(float)
    v_all = np.where(has, pt["dV_kbbl"], np.nan)
    v_pri = np.where(primary, pt["dV_kbbl"], np.nan)
    prim = sample_stats(v_pri, y, with_verdict=True)
    allseason = sample_stats(v_all, y, with_verdict=False)
    series = eia["change_kbbl"].reindex(pd.date_range(eia.index.min(), eia.index.max(), freq="7D"))
    f0 = ar2_forecast(series)
    nc, nct = nowcast(series.reindex(pt.index), pd.Series(v_pri, index=pt.index), f0.reindex(pt.index))
    pt = pt.join(nct)
    res = {"prereg_v2_sha256": sha, "seed": V.SEED_BS2, "bootstrap_draws": V.DRAWS, "block_weeks": V.BLOCK,
           "definitions": {"clear_acquisition": f"clear_area_share >= {MIN_CLEAR_SHARE}", "valid_tank": "status in " + "/".join(V.KEPT),
                           "primary_sun_elevation_max_deg": SUN_MAX, "min_valid_area_share_both_dates": MIN_VALID_SHARE,
                           "dV_units": "kbbl; EIA change in kbbl", "verdict_interval": "Fisher z 95%; bootstrap reported as a check"},
           "n_weeks_in_period": int(len(pt)), "n_weeks_with_selected_acquisition": int(pt["acq_id"].notna().sum()),
           "n_weeks_with_dV": int(pt["dV_kbbl"].notna().sum()), "n_weeks_all_season_sample": int(has.sum()), "n_weeks_primary_sample": int(primary.sum()),
           "period": [str(pt.index.min().date()), str(pt.index.max().date())],
           "primary": prim, "secondary": {"all_season": allseason, "nowcast_primary_sample": nc},
           "seconds": round(time.time() - t0, 1)}
    (out_dir / "bs2.json").write_text(json.dumps(clean(res), indent=1), encoding="utf-8")
    cols = ["ref_time_utc", "acq_id", "acq_time_utc", "dt_hours", "sun_elev", "clear_area_share", "n_clear_candidates", "dV_kbbl",
            "valid_area_share_both", "n_valid_tanks_both", "eia_change_kbbl", "in_all_season", "in_primary", "m0_forecast_kbbl", "m0_error_kbbl",
            "beta", "m1_forecast_kbbl", "m1_error_kbbl", "nowcast_evaluated"]
    pt[cols].to_csv(out_dir / "weekly_table.csv", float_format="%.5g")
    return res


def main() -> None:
    V.ensure_dirs()
    sha = V.assert_prereg_v2_frozen()
    res = run(V.read_fits(), V.read_acq_summary(), V.eia_weekly(), V.BS2, sha)
    p = res["primary"]
    print(f"BS2 primary: n={p['n']} r={p['r']:.3f} Fisher 95% [{p['fisher_ci95'][0]:.3f}, {p['fisher_ci95'][1]:.3f}] verdict {p['verdict']} "
          f"(bootstrap interval verdict {p['verdict_bootstrap_interval']})", flush=True)
    print(f"nowcast: {res['secondary']['nowcast_primary_sample']}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
