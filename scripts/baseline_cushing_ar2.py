"""AR(2) baseline for weekly changes in EIA Cushing crude stocks, ported from deliverables/analysis/eia_cushing_baseline.py.

Estimator: OLS of the weekly change on its two lags, refitted every week on data strictly before the forecast week (expanding window);
benchmark: expanding mean of the training changes; out-of-sample window 2016-01-01..2025-12-31; R2 is relative to the benchmark.
The V1 sample rule is kept: a week is usable only if its two lags and the V1 seasonal mean (at least 3 earlier observations of the same
ISO week number in earlier calendar years) exist. This drops 2016-01-01 (ISO week 53), hence n=521; --sample all removes the rule.
Weekly changes are taken between consecutive Fridays only; a missing week gives NaN for that change and for the next two lags.

Inputs (one block each in metrics.json):
  v1_csv         deliverables/analysis/eia_cushing_weekly.csv (levels, downloaded 2026-10-16)
  repo_cache     eia.load("pet", "W_EPC0_SAX_YCUOK_MBBL", "w"), if the xls is cached (levels)
  first_release  results/v2/eia_first_release.csv: change as published = cushing_kbbl - cushing_prior_kbbl in the same release
Prediction bands: share of forecasts with |y - forecast| <= 1.96 x RMSE of the in-sample residuals at that refit, and <= 1,200 kbbl.
For v1_csv and repo_cache, blocks suffixed _from_<date> repeat the estimation on changes from the first week of the first-release series,
so that all three inputs share the same training start.

Usage: python scripts/baseline_cushing_ar2.py [--sample v1|all] [--v1-csv PATH] [--first-release PATH] [--out DIR]
Outputs: results/v2/baseline_cushing/metrics.json, forecasts_<input>.csv (week_ending, y, ar2_forecast, mean_forecast, rmse_train)
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata import eia  # noqa: E402

SID = "W_EPC0_SAX_YCUOK_MBBL"
OOS_START, OOS_END = "2016-01-01", "2025-12-31"
BAND_KBBL = 1200.0
V1_PRINTED = {"n": 521, "r2": 0.307, "rmse_kbbl": 1200, "rmse_mean_kbbl": 1442, "sign_hit": 0.674}


def weekly_grid(s: pd.Series) -> tuple[pd.Series, dict]:
    grid = pd.date_range(s.index.min(), s.index.max(), freq="7D")
    g = s.reindex(grid)
    return g, {"off_grid_dates": int((~s.index.isin(grid)).sum()), "missing_weeks": int(g.isna().sum())}


def seasonal_mean(d: pd.Series) -> np.ndarray:
    wk, yr, v = d.index.isocalendar().week.to_numpy(), d.index.year.to_numpy(), d.to_numpy(float)
    out = np.full(len(d), np.nan)
    for i in range(len(d)):
        m = (wk == wk[i]) & (yr < yr[i]) & np.isfinite(v)
        if m.sum() >= 3:
            out[i] = v[m].mean()
    return out


def table(d: pd.Series, v1_rule: bool) -> pd.DataFrame:
    df = pd.DataFrame({"y": d, "l1": d.shift(1), "l2": d.shift(2)})
    if v1_rule:
        df["seas"] = seasonal_mean(d)
    return df.dropna()


def expanding_ar2(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t in df.index[(df.index >= OOS_START) & (df.index <= OOS_END)]:
        tr = df[df.index < t]
        X = np.column_stack([np.ones(len(tr)), tr["l1"].to_numpy(), tr["l2"].to_numpy()])
        y = tr["y"].to_numpy()
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        rows.append((t, df.at[t, "y"], np.array([1.0, df.at[t, "l1"], df.at[t, "l2"]]) @ b, y.mean(), np.sqrt(((y - X @ b) ** 2).mean())))
    return pd.DataFrame(rows, columns=["week_ending", "y", "ar2_forecast", "mean_forecast", "rmse_train"])


def metrics(f: pd.DataFrame, df: pd.DataFrame) -> dict:
    y, p, b0, err = f["y"].to_numpy(), f["ar2_forecast"].to_numpy(), f["mean_forecast"].to_numpy(), f["y"].to_numpy() - f["ar2_forecast"].to_numpy()
    half = 1.96 * f["rmse_train"].to_numpy()
    return {"n": int(len(f)), "oos_first": f["week_ending"].min().date().isoformat(), "oos_last": f["week_ending"].max().date().isoformat(),
            "train_first": df.index.min().date().isoformat(), "r2": float(1 - ((y - p) ** 2).sum() / ((y - b0) ** 2).sum()),
            "rmse_kbbl": float(np.sqrt((err ** 2).mean())), "rmse_mean_kbbl": float(np.sqrt(((y - b0) ** 2).mean())), "sign_hit": float(np.mean(np.sign(p) == np.sign(y))),
            "coverage_1.96_rmse_train": float((np.abs(err) <= half).mean()), "mean_halfwidth_1.96_rmse_train_kbbl": float(half.mean()),
            "coverage_pm_1200_kbbl": float((np.abs(err) <= BAND_KBBL).mean()), "n_inside_1.96_rmse_train": int((np.abs(err) <= half).sum()),
            "n_inside_pm_1200_kbbl": int((np.abs(err) <= BAND_KBBL).sum())}


def line(tag: str, m: dict) -> str:
    return (f"  {tag:34s} n={m['n']} ({m['oos_first']}..{m['oos_last']}) R2={m['r2']:.3f} RMSE={m['rmse_kbbl']:.0f} kbbl (mean forecast {m['rmse_mean_kbbl']:.0f}) "
            f"sign hit={m['sign_hit']:.3f} | inside 1.96*RMSE_train {m['coverage_1.96_rmse_train']:.3f}, inside +-1200 kbbl {m['coverage_pm_1200_kbbl']:.3f}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", choices=["v1", "all"], default="v1", help="sample rule used for forecasts_<input>.csv")
    ap.add_argument("--v1-csv", type=Path, default=ROOT.parent / "deliverables" / "analysis" / "eia_cushing_weekly.csv")
    ap.add_argument("--first-release", type=Path, default=ROOT / "results" / "v2" / "eia_first_release.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "v2" / "baseline_cushing")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    inputs = {}
    levels, info = weekly_grid(pd.read_csv(args.v1_csv, index_col=0, parse_dates=True)["kbbl"])
    inputs["v1_csv"] = (str(args.v1_csv), levels.diff(), info)
    if eia.path(SID, "w").exists():
        levels, info = weekly_grid(eia.load("pet", SID, "w"))
        inputs["repo_cache"] = (f'eia.load("pet", "{SID}", "w")', levels.diff(), info)
    else:
        print("repo_cache skipped: xls not cached")
    if args.first_release.exists():
        fr = pd.read_csv(args.first_release, parse_dates=["week_ending", "release_date"]).sort_values("release_date")
        # data-only re-issues of a week appear as a second archive folder: the first publication is kept
        fr = fr.drop_duplicates("week_ending", keep="first").set_index("week_ending").sort_index()
        changes, info = weekly_grid((fr["cushing_kbbl"] - fr["cushing_prior_kbbl"]).astype(float))
        inputs["first_release"] = (str(args.first_release), changes, info)
    else:
        print("first_release skipped: file not found")

    fr_start = inputs["first_release"][1].dropna().index.min() if "first_release" in inputs else None
    out = {"estimator": "AR(2) on weekly changes, expanding window refit each week on data strictly before the forecast week; benchmark = expanding mean",
           "oos_window": [OOS_START, OOS_END], "band_kbbl": BAND_KBBL, "v1_printed": V1_PRINTED, "forecast_csv_sample_rule": args.sample,
           "first_release_start": None if fr_start is None else fr_start.date().isoformat(), "inputs": {}}
    for name, (source, d, info) in inputs.items():
        variants = {"": d}
        if fr_start is not None and name != "first_release":
            variants[f"_from_{fr_start.date()}"] = d[d.index >= fr_start]
        blocks, fcst = {}, {}
        for suffix, dd in variants.items():
            for tag, rule in (("v1_sample_rule", True), ("all_rows", False)):
                df = table(dd, rule)
                f = expanding_ar2(df)
                blocks[tag + suffix], fcst[tag + suffix] = metrics(f, df), f
        keep = fcst["v1_sample_rule" if args.sample == "v1" else "all_rows"]
        keep.to_csv(args.out / f"forecasts_{name}.csv", index=False, float_format="%.6f")
        v = d.dropna()
        out["inputs"][name] = {"source": source, "n_changes": int(len(v)), "first_change": v.index.min().date().isoformat(), "last_change": v.index.max().date().isoformat(),
                               **info, **blocks}
        if name == "v1_csv":
            m = blocks["v1_sample_rule"]
            out["inputs"][name]["matches_v1_printout"] = bool(m["n"] == V1_PRINTED["n"] and round(m["r2"], 3) == V1_PRINTED["r2"] and round(m["rmse_kbbl"]) == V1_PRINTED["rmse_kbbl"]
                                                              and round(m["rmse_mean_kbbl"]) == V1_PRINTED["rmse_mean_kbbl"] and round(m["sign_hit"], 3) == V1_PRINTED["sign_hit"])
        print(f"{name}: {len(v)} weekly changes {v.index.min().date()}..{v.index.max().date()}, missing weeks {info['missing_weeks']}, off-grid dates {info['off_grid_dates']}")
        for tag, m in blocks.items():
            print(line(tag, m))
    if "matches_v1_printout" in out["inputs"].get("v1_csv", {}):
        print("v1_csv reproduces the V1 printout (n, R2, RMSE, mean-forecast RMSE, sign hit):", out["inputs"]["v1_csv"]["matches_v1_printout"])
    (args.out / "metrics.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", args.out / "metrics.json")


if __name__ == "__main__":
    main()
