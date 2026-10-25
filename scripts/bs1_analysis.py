"""BS0 availability and BS1 descriptive analysis (prereg/tests_v2.json): coverage and abstention, identifiability simulation, stability.

Descriptive only (no verdict). No EIA value is read: the EIA data weeks are used as dates only. Run after scripts/bs1_extract.py.

Outputs: results/v2/BS1/coverage.csv, coverage_summary.json, identifiability.csv, identifiability_levels.json, stability.csv,
         results/v2/BS0/availability.csv, availability_summary.json
"""
import argparse
import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata import tankshadow as ts  # noqa: E402
from altdata import v2common as V  # noqa: E402

STATUSES = ["ok", "wide_interval", "full_or_fixed", "no_contrast", "few_pixels", "cloudy"]
D_TRUE = list(range(0, 15, 2))            # true roof depths of the simulation, m
OFFSET_M = 5.0                            # random centre offsets up to +-5 m in each coordinate
LATENCY_H = 24.0                          # assumed processing latency of the availability matrix
PAIR_DAYS = 2.0
FITTED = V.KEPT + ("no_contrast",)


def mad_sd(x) -> float:
    x = np.asarray(x, float)
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if x.size else float("nan")


# ---------------------------------------------------------------- (a) coverage and abstention
def coverage(fits: pd.DataFrame, summ: pd.DataFrame, out_dir: Path) -> dict:
    f = fits.assign(year=fits["t"].dt.year.astype(str), sun_bin=V.sun_bin(fits["sun_elev"]).to_numpy(), all_=1)

    def table(keys, year="ALL", sbin="ALL"):
        g = f.groupby(keys)
        t = g["status"].value_counts().unstack(fill_value=0).reindex(columns=STATUSES, fill_value=0)
        t["n_tank_rows"] = t[STATUSES].sum(axis=1)
        t["n_acquisitions"] = g["acq_id"].nunique()
        t["share_with_estimate"] = t[list(V.KEPT)].sum(axis=1) / t["n_tank_rows"]
        t["share_tank_clear"] = g["clear"].mean()
        t = t.reset_index()
        if "year" not in t:
            t["year"] = year
        if "sun_bin" not in t:
            t["sun_bin"] = sbin
        return t.drop(columns=[c for c in ("all_",) if c in t])

    tab = pd.concat([table(["year", "sun_bin"]), table(["year"]), table(["sun_bin"]), table(["all_"])], ignore_index=True)
    lead = ["year", "sun_bin", "n_acquisitions", "n_tank_rows", *STATUSES, "share_with_estimate", "share_tank_clear"]
    tab[lead].to_csv(out_dir / "coverage.csv", index=False, float_format="%.4f")
    kept = f[f["status"].isin(V.KEPT)]
    ok_ = f[f["status"] == "ok"]
    summary = {
        "n_acquisitions": int(f["acq_id"].nunique()), "n_tank_rows": int(len(f)),
        "status_counts": {k: int(v) for k, v in f["status"].value_counts().items()},
        "share_with_estimate": float(f["status"].isin(V.KEPT).mean()),
        "diagnostic_share_of_estimates_with_b_below_zero": float((kept["b"] < 0).mean()) if len(kept) else None,
        "diagnostic_share_of_ok_with_b_below_zero": float((ok_["b"] < 0).mean()) if len(ok_) else None,
        "acquisitions": {
            "shift_flag_share": float(summ["shift_flag"].mean()), "median_abs_shift_x_m": float(summ["shift_x_m"].abs().median()),
            "median_abs_shift_y_m": float(summ["shift_y_m"].abs().median()),
            "p95_abs_shift_m": float(np.percentile(np.hypot(summ["shift_x_m"], summ["shift_y_m"]), 95)),
            "reg_corr_median": float(summ["reg_corr"].median()), "clear_area_share_median": float(summ["clear_area_share"].median()),
            "share_acquisitions_clear_area_ge_50pct": float((summ["clear_area_share"] >= 0.5).mean()),
            "n_acquisitions_with_nodata_tanks": int((summ["n_nodata_tanks"] > 0).sum())}}
    (out_dir / "coverage_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


# ---------------------------------------------------------------- (b) identifiability simulation (ILL)
def levels_from_fits(fits: pd.DataFrame) -> dict:
    """Lit-roof level, lit-minus-shadow contrast and the residual sigmas of the real fits, by sun-elevation bin (fallback: all bins)."""
    f = fits.assign(sun_bin=V.sun_bin(fits["sun_elev"]).to_numpy())
    fitted, good = f[f["status"].isin(FITTED)], f[f["status"].isin(("ok", "wide_interval"))]

    def make(fa, go):
        if len(fa) < 20 or len(go) < 20:
            return None
        return {"a": float(go["a"].median()), "contrast": float((go["a"] - go["b"]).median()), "sigma": fa["sigma"].to_numpy(),
                "n_real_fits": int(len(fa)), "median_cnr": float(((go["a"] - go["b"]) / go["sigma"]).median())}

    out = {"ALL": make(fitted, good) or {"a": 3000.0, "contrast": 1500.0, "sigma": np.array([150.0]), "n_real_fits": 0, "median_cnr": float("nan")}}
    for b in sorted(f["sun_bin"].dropna().unique()):
        out[b] = make(fitted[fitted["sun_bin"] == b], good[good["sun_bin"] == b]) or out["ALL"]
    return out


def simulate(cat: pd.DataFrame, reg_big: pd.DataFrame, levels: dict, n_acq: int, n_tank: int, seed: int) -> pd.DataFrame:
    """Synthetic tanks with the registry diameters, true depths 0..14 m, the sun angles of the catalogue, random sub-pixel offsets up to 5 m
    and noise equal to the residual sigma of real fits; the fit assumes the nominal centre, the truth is rendered at the displaced centre."""
    rng = np.random.default_rng(seed)
    c = cat.assign(sun_bin=V.sun_bin(cat["sun_elev"]).to_numpy())
    rows = []
    for sbin, sub in c.groupby("sun_bin"):
        lev = levels.get(sbin, levels["ALL"])
        a0, b0 = lev["a"], lev["a"] - lev["contrast"]
        for i in rng.choice(len(sub), size=min(n_acq, len(sub)), replace=False):
            az, el = float(sub["sun_az"].iloc[i]), float(sub["sun_elev"].iloc[i])
            for k in rng.choice(len(reg_big), size=min(n_tank, len(reg_big)), replace=False):
                R = float(reg_big["R"].iloc[k])
                phase = rng.uniform(-ts.PIX / 2, ts.PIX / 2, 2)               # tank centre relative to the pixel lattice
                half = int(np.ceil(R / ts.PIX)) + 2
                g = np.arange(-half, half + 1) * ts.PIX
                gx, gy = np.meshgrid(g, g)
                qx, qy = gx.ravel() - phase[0], gy.ravel() - phase[1]
                keep, F = ts.pixel_design(qx, qy, R, az, el)
                sigma = float(rng.choice(lev["sigma"]))
                for d in D_TRUE:
                    off = rng.uniform(-OFFSET_M, OFFSET_M, 2)
                    x = ts.render(qx, qy, R, d, az, el, a0, b0, ground=b0, offset=off, sigma=sigma, rng=rng)[keep]
                    r = ts.fit(x, F)
                    rows.append((sbin, el, d, 2 * R, r["n"], r["status"], r["d_hat"], r["lo"], r["hi"]))
    return pd.DataFrame(rows, columns=["sun_bin", "sun_elev", "d_true", "diameter_m", "n_pix", "status", "d_hat", "d_lo", "d_hi"])


def summarize_sim(sim: pd.DataFrame, levels: dict) -> pd.DataFrame:
    def stat(g, sbin, d):
        e = g[g["status"].isin(V.KEPT)]
        err = e["d_hat"] - e["d_true"]
        return {"sun_bin": sbin, "d_true": d, "n_sim": int(len(g)), "share_with_estimate": len(e) / len(g) if len(g) else np.nan,
                "share_few_pixels": float((g["status"] == "few_pixels").mean()), "share_no_contrast": float((g["status"] == "no_contrast").mean()),
                "rmse_m": float(np.sqrt((err ** 2).mean())) if len(e) else np.nan, "bias_m": float(err.mean()) if len(e) else np.nan,
                "mae_m": float(err.abs().mean()) if len(e) else np.nan,
                "interval_coverage": float(((e["d_lo"] <= e["d_true"]) & (e["d_true"] <= e["d_hi"])).mean()) if len(e) else np.nan,
                "median_interval_width_m": float((e["d_hi"] - e["d_lo"]).median()) if len(e) else np.nan,
                "median_real_cnr": levels.get(sbin, levels["ALL"])["median_cnr"] if sbin != "ALL" else levels["ALL"]["median_cnr"]}
    out = []
    for sbin, g in sim.groupby("sun_bin"):
        out += [stat(g[g["d_true"] == d], sbin, d) for d in D_TRUE] + [stat(g, sbin, "all")]
    out += [stat(sim[sim["d_true"] == d], "ALL", d) for d in D_TRUE] + [stat(sim, "ALL", "all")]
    return pd.DataFrame(out)


# ---------------------------------------------------------------- (c) stability of d_hat between close acquisitions
def pairs_within(fits: pd.DataFrame, days: float = PAIR_DAYS) -> pd.DataFrame:
    k = fits[fits["status"].isin(V.KEPT)].sort_values(["osm_id", "t"])
    rows = []
    for osm, g in k.groupby("osm_id"):
        td = ((g["t"] - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds() / 86400).to_numpy()
        d, el, dia = g["d_hat"].to_numpy(), g["sun_elev"].to_numpy(), float(g["diameter_m"].iloc[0])
        end = np.searchsorted(td, td + days + 1e-9, side="right")
        for i in range(len(g)):
            for j in range(i + 1, end[i]):
                rows.append((osm, dia, (td[j] - td[i]) * 24, (el[i] + el[j]) / 2, d[j] - d[i]))
    return pd.DataFrame(rows, columns=["osm_id", "diameter_m", "gap_h", "sun_elev_mean", "diff_m"])


def stability(fits: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    p = pairs_within(fits)
    cols = ["scope", "sun_bin", "gap_class", "osm_id", "n_pairs", "n_tanks", "median_diff_m", "robust_spread_m"]
    if p.empty:
        out = pd.DataFrame(columns=cols)
        out.to_csv(out_dir / "stability.csv", index=False)
        return out
    p["sun_bin"] = V.sun_bin(p["sun_elev_mean"]).to_numpy()
    p["gap_class"] = np.where(p["gap_h"] < 1.0, "same_pass", "later_days")
    rows = []
    for sbin in ["ALL"] + sorted(p["sun_bin"].dropna().unique()):
        pb = p if sbin == "ALL" else p[p["sun_bin"] == sbin]
        for gc, pg in (("all", pb), ("same_pass", pb[pb["gap_class"] == "same_pass"]), ("later_days", pb[pb["gap_class"] == "later_days"])):
            if len(pg):
                rows.append({"scope": "pooled", "sun_bin": sbin, "gap_class": gc, "osm_id": "ALL", "n_pairs": len(pg),
                             "n_tanks": pg["osm_id"].nunique(), "median_diff_m": float(pg["diff_m"].median()), "robust_spread_m": mad_sd(pg["diff_m"])})
        per = [(o, len(g), mad_sd(g["diff_m"]), float(g["diff_m"].median())) for o, g in pb.groupby("osm_id") if len(g) >= 3]
        if per:
            rows.append({"scope": "median_over_tanks_with_3plus_pairs", "sun_bin": sbin, "gap_class": "all", "osm_id": "ALL",
                         "n_pairs": int(sum(x[1] for x in per)), "n_tanks": len(per), "median_diff_m": float(np.median([x[3] for x in per])),
                         "robust_spread_m": float(np.median([x[2] for x in per]))})
            rows += [{"scope": "tank", "sun_bin": sbin, "gap_class": "all", "osm_id": o, "n_pairs": n, "n_tanks": 1, "median_diff_m": md,
                      "robust_spread_m": sp} for o, n, sp, md in per] if sbin != "ALL" else []
    out = pd.DataFrame(rows)[cols]
    out.to_csv(out_dir / "stability.csv", index=False, float_format="%.4f")
    return out


# ---------------------------------------------------------------- (d) BS0 availability per EIA data week
def availability(cat_all: pd.DataFrame, summ: pd.DataFrame, s1: pd.DataFrame, weeks, out_dir: Path, latency_h: float = LATENCY_H) -> dict:
    """For every EIA data week F: acquisition within +-2 days of F 07:00 CT, available (time + latency) before Tuesday 16:30 ET (API) and
    before Wednesday 10:30 ET (EIA). Sentinel-2: at least 50% of the tank area (diameter >= 40 m) clear; Sentinel-1: any covering pass."""
    lat = pd.Timedelta(hours=latency_h)
    clear = summ.set_index("acq_id")["clear_area_share"]
    c = cat_all.assign(share=cat_all["acq_id"].map(clear))
    s1c = s1[s1["covers_window"]] if len(s1) else s1
    t1 = V.to_utc(s1c["datetime_utc"]) if len(s1c) else pd.Series([], dtype="datetime64[ns, UTC]")
    start, end = V.to_utc(pd.Series([V.CAT_START, V.CAT_END]))
    rows = []
    for F in weeks:
        ref = V.ref_time_utc(F)
        if ref - pd.Timedelta(days=2) < start or ref + pd.Timedelta(days=2) > end:
            continue
        api, eia = V.release_deadlines_utc(F)
        inw = (c["t"] - ref).abs() <= pd.Timedelta(days=2)
        w = c[inw]
        usable = w[w["share"] >= 0.5]
        ok_api, ok_eia = usable[usable["t"] + lat <= api], usable[usable["t"] + lat <= eia]
        best = usable.assign(dt=(usable["t"] - ref).abs()).sort_values(["dt", "t"]).head(1)
        i1 = (t1 - ref).abs() <= pd.Timedelta(days=2)
        s1w = t1[i1]
        rows.append({"week_ending": F.date().isoformat(), "ref_time_utc": ref.isoformat(), "api_deadline_utc": api.isoformat(),
                     "eia_deadline_utc": eia.isoformat(), "s2_n_in_window": int(len(w)), "s2_n_clear50": int(len(usable)),
                     "s2_usable_api": bool(len(ok_api)), "s2_usable_eia": bool(len(ok_eia)),
                     "s2_usable_api_sun_le45": bool((ok_api["sun_elev"] <= 45).any()),
                     "s2_best_acq_id": best["acq_id"].iloc[0] if len(best) else "", "s2_best_dt_hours": float((best["t"].iloc[0] - ref).total_seconds() / 3600) if len(best) else np.nan,
                     "s1_n_in_window": int(len(s1w)), "s1_usable_api": bool((s1w + lat <= api).any()), "s1_usable_eia": bool((s1w + lat <= eia).any())})
    av = pd.DataFrame(rows)
    av.to_csv(out_dir / "availability.csv", index=False, float_format="%.3f")
    flags = ["s2_usable_api", "s2_usable_eia", "s2_usable_api_sun_le45", "s1_usable_api", "s1_usable_eia"]
    av["month"] = pd.to_datetime(av["week_ending"]).dt.month
    av["year"] = pd.to_datetime(av["week_ending"]).dt.year
    summ_out = {"assumed_latency_hours": latency_h, "n_weeks": int(len(av)), "first_week": av["week_ending"].min(), "last_week": av["week_ending"].max(),
                "share_of_weeks": {k: float(av[k].mean()) for k in flags},
                "by_month": {int(m): {"n_weeks": int(len(g)), **{k: float(g[k].mean()) for k in flags}} for m, g in av.groupby("month")},
                "by_year": {int(y): {"n_weeks": int(len(g)), **{k: float(g[k].mean()) for k in flags}} for y, g in av.groupby("year")}}
    lp = V.BS0 / "latency.json"
    if out_dir == V.BS0 and lp.exists():
        summ_out["observed_publication_latency_hours"] = json.loads(lp.read_text(encoding="utf-8")).get("latency_hours")
    (out_dir / "availability_summary.json").write_text(json.dumps(summ_out, indent=1), encoding="utf-8")
    return summ_out


# ---------------------------------------------------------------- driver
def run(fits, summ, cat_all, s1, weeks, reg, out1: Path, out0: Path, n_acq: int, n_tank: int, seed: int = V.SEED_BS2) -> dict:
    out1.mkdir(parents=True, exist_ok=True)
    out0.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cov = coverage(fits, summ, out1)
    print(f"coverage: {cov['n_acquisitions']} acquisitions, {cov['n_tank_rows']} tank rows, estimate share {cov['share_with_estimate']:.1%} ({time.time() - t0:.0f}s)", flush=True)
    st = stability(fits, out1)
    print(f"stability: {int(st.loc[(st['scope'] == 'pooled') & (st['sun_bin'] == 'ALL') & (st['gap_class'] == 'all'), 'n_pairs'].sum())} pairs <= {PAIR_DAYS:.0f} days ({time.time() - t0:.0f}s)", flush=True)
    lev = levels_from_fits(fits)
    (out1 / "identifiability_levels.json").write_text(json.dumps({k: {kk: (vv if kk != "sigma" else {"median": float(np.median(vv)), "n": int(len(vv))})
                                                                      for kk, vv in v.items()} for k, v in lev.items()}, indent=1), encoding="utf-8")
    sim = simulate(cat_all, reg[reg["big"]].reset_index(drop=True), lev, n_acq, n_tank, seed)
    summarize_sim(sim, lev).to_csv(out1 / "identifiability.csv", index=False, float_format="%.4f")
    print(f"identifiability simulation: {len(sim)} synthetic fits ({time.time() - t0:.0f}s)", flush=True)
    av = availability(cat_all, summ, s1, weeks, out0)
    print(f"availability: {av['n_weeks']} EIA weeks; share of weeks with a usable acquisition {av['share_of_weeks']} ({time.time() - t0:.0f}s)", flush=True)
    return {"coverage": cov, "availability": av}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-acq-per-bin", type=int, default=30)
    ap.add_argument("--tanks-per-acq", type=int, default=40)
    args = ap.parse_args()
    V.ensure_dirs()
    V.assert_prereg_v2_frozen()
    fits, summ, cat = V.read_fits(), V.read_acq_summary(), V.read_s2_catalog()
    s1 = pd.read_csv(V.BS0 / "s1_catalog.csv")
    weeks = V.eia_weekly().index        # data weeks only (dates); no EIA value is used
    run(fits, summ, cat, s1, weeks, V.registry(), V.BS1, V.BS0, args.n_acq_per_bin, args.tanks_per_acq)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
