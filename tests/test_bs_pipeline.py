"""Synthetic-data checks of scripts/bs1_analysis.py, bs2_aggregate.py and fig_bs.py. No real fit and no real EIA value is read.

Run: pytest tests/test_bs_pipeline.py
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from altdata import plotting  # noqa: E402
from altdata import v2common as V  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bs1a, bs2, figs = load("bs1_analysis"), load("bs2_aggregate"), load("fig_bs")


# ------------------------------------------------------------------ synthetic world: tanks, depths, fits, EIA
def make_world(tmp_path, seed=11, coupling=3.0, null=False, n_tanks=60):
    rng = np.random.default_rng(seed)
    weeks = pd.date_range("2011-07-22", "2026-10-16", freq="7D")
    diam = rng.uniform(40, 80, n_tanks)
    area = np.pi * (diam / 2) ** 2
    osm = [f"way/{i}" for i in range(n_tanks)]
    sat = [F for F in weeks if F >= pd.Timestamp("2018-12-07")]
    d = np.empty((len(sat), n_tanks))
    d[0] = rng.uniform(4, 12, n_tanks)
    for i in range(1, len(sat)):
        d[i] = np.clip(d[i - 1] + rng.normal(0, 0.6, n_tanks), 1, 15)
    dv_true = np.r_[np.nan, -(area * np.diff(d, axis=0)).sum(axis=1) * V.BBL_PER_M3 / 1000]
    y = rng.normal(0, 700, len(weeks))
    ar = np.zeros(len(weeks))
    for i in range(2, len(weeks)):
        ar[i] = 0.4 * ar[i - 1] - 0.15 * ar[i - 2] + y[i]
    y = ar.copy()
    start = list(weeks).index(sat[0])
    for k, F in enumerate(sat):
        if k > 0:
            y[start + k] = (rng.normal(0, 150) if null else coupling * dv_true[k] + rng.normal(0, 90))
    stock = 20000 + np.cumsum(y)
    eia = pd.DataFrame({"release_date": weeks + pd.Timedelta(days=5), "week_ending": weeks, "cushing_kbbl": stock,
                        "cushing_prior_kbbl": np.r_[stock[0] - y[0], stock[:-1]]})
    eia_path = tmp_path / "eia.csv"
    eia.to_csv(eia_path, index=False)
    rows, srows = [], []
    for k, F in enumerate(sat):
        ref = V.ref_time_utc(F)
        t = ref + pd.Timedelta(hours=4)
        clear_week = rng.random() < 0.8
        sun = rng.uniform(30, 50)
        aid = f"ACQ{F.date()}"
        n_ok = 0
        for j in range(n_tanks):
            ok = clear_week and rng.random() < 0.92
            n_ok += ok
            rows.append({"acq_id": aid, "datetime_utc": t.isoformat(), "sun_elev": sun, "sun_az": 160.0, "osm_id": osm[j], "diameter_m": diam[j],
                         "clear": clear_week, "n_pix": 20, "d_hat": d[k, j] + rng.normal(0, 0.25) if ok else np.nan, "d_lo": d[k, j] - 1,
                         "d_hi": d[k, j] + 1, "a": 3000.0, "b": 1500.0, "sigma": 100.0,
                         "status": "ok" if ok else ("cloudy" if not clear_week else "no_contrast"), "rss_const_ratio": 0.3})
        srows.append({"acq_id": aid, "datetime_utc": t.isoformat(), "sun_elev": sun, "sun_az": 160.0, "cloud_cover": 3.0,
                      "clear_area_share": 0.9 if clear_week else 0.2, "shift_x_m": 1.0, "shift_y_m": -1.0, "shift_flag": False, "reg_corr": 0.6,
                      "n_nodata_tanks": 0})
    fits, summ = pd.DataFrame(rows), pd.DataFrame(srows)
    fits["t"], summ["t"] = V.to_utc(fits["datetime_utc"]), V.to_utc(summ["datetime_utc"])
    return fits, summ, V.eia_weekly(eia_path), eia_path


# ------------------------------------------------------------------ BS2
def test_bs2_recovers_planted_relation(tmp_path):
    fits, summ, eia, _ = make_world(tmp_path)
    res = bs2.run(fits, summ, eia, tmp_path / "out", sha="test")
    p = res["primary"]
    assert p["n"] >= 80, p["n"]
    assert p["r"] > 0.6 and p["fisher_ci95"][0] > 0.45 and p["verdict"] == "SIGNAL" and p["verdicts_agree"], p
    assert 2.0 < p["slope_eia_kbbl_per_kbbl"] < 5.0                      # planted 3.0; tanks are missing at each date and d_hat is noisy (attenuation)
    assert res["secondary"]["all_season"]["n"] >= p["n"]
    nc = res["secondary"]["nowcast_primary_sample"]
    assert nc["n_evaluated"] > 40 and nc["mse_ratio_m1_over_m0"] < 0.85 and nc["verdict"] == "GAIN", nc
    assert (tmp_path / "out" / "bs2.json").exists() and (tmp_path / "out" / "weekly_table.csv").exists()
    json.loads((tmp_path / "out" / "bs2.json").read_text(encoding="utf-8"))


def test_bs2_null_is_not_a_signal(tmp_path):
    fits, summ, eia, _ = make_world(tmp_path, seed=5, null=True)
    res = bs2.run(fits, summ, eia, tmp_path / "out", sha="test")
    p = res["primary"]
    assert p["verdict"] in ("INCONCLUSIVE", "NO SIGNAL DETECTED") and abs(p["r"]) < 0.3, p
    assert res["secondary"]["nowcast_primary_sample"]["verdict"] == "NO GAIN DETECTED"


def test_verdict_rule_and_fisher():
    assert bs2.verdict_r(0.10, 0.50, 100)[0] == "SIGNAL"
    assert bs2.verdict_r(-0.20, 0.15, 100)[0] == "NO SIGNAL DETECTED"
    assert bs2.verdict_r(-0.10, 0.40, 100)[0] == "INCONCLUSIVE"
    v, note = bs2.verdict_r(0.05, 0.15, 500)
    assert v == "SIGNAL" and "both hold" in note
    assert bs2.verdict_r(0.1, 0.9, 4)[0] == "INCONCLUSIVE"
    lo, hi = bs2.fisher_ci(0.5, 30)
    z, se = math.atanh(0.5), 1 / math.sqrt(27)
    assert abs(lo - math.tanh(z - 1.959964 * se)) < 1e-6 and abs(hi - math.tanh(z + 1.959964 * se)) < 1e-6
    r, slope, n = bs2.pearson_slope(np.array([1.0, 2, 3, 4, np.nan]), np.array([2.0, 4, 6, 8.5, 5]))
    assert n == 4 and r > 0.99 and abs(slope - np.polyfit([1, 2, 3, 4], [2, 4, 6, 8.5], 1)[0]) < 1e-9


def test_moving_blocks_are_consecutive_runs():
    rng = np.random.default_rng(0)
    idx = V.moving_blocks(rng, 23, 4)
    assert idx.size == 23 and idx.min() >= 0 and idx.max() <= 22
    first = idx[:20].reshape(5, 4)
    assert (np.diff(first, axis=1) == 1).all()
    assert V.moving_blocks(rng, 3, 4).max() <= 2


def test_ar2_forecast_uses_only_earlier_weeks():
    rng = np.random.default_rng(1)
    n = 260
    y = np.zeros(n)
    for t in range(2, n):
        y[t] = 0.5 * y[t - 1] - 0.2 * y[t - 2] + rng.normal()
    s = pd.Series(y, index=pd.date_range("2012-01-06", periods=n, freq="7D"))
    f = bs2.ar2_forecast(s)
    assert f.iloc[:105].isna().all() and f.iloc[110:].notna().all()
    t = 200
    s2 = s.copy()
    s2.iloc[t:] += 1000.0                       # change the target week and the future: the forecast of week t cannot move
    assert abs(bs2.ar2_forecast(s2).iloc[t] - f.iloc[t]) < 1e-9
    assert abs(np.corrcoef(f.iloc[110:], s.iloc[110:])[0, 1]) > 0.3


def test_weekly_selection_ties_and_clear_rule():
    F = pd.Timestamp("2019-03-08")
    ref = V.ref_time_utc(F)
    summ = pd.DataFrame({"acq_id": ["early", "late", "cloudy", "far"], "t": [ref - pd.Timedelta(hours=10), ref + pd.Timedelta(hours=10),
                                                                            ref + pd.Timedelta(hours=2), ref + pd.Timedelta(hours=47)],
                         "clear_area_share": [0.9, 0.9, 0.3, 0.9], "sun_elev": 40.0})
    sel = bs2.select_weekly(summ, pd.DatetimeIndex([F]))
    assert sel.loc[F, "acq_id"] == "early" and sel.loc[F, "n_clear_candidates"] == 3     # tie between +-10 h: the earlier; cloudy one ignored
    summ2 = summ[summ["acq_id"] == "cloudy"]
    assert bs2.select_weekly(summ2, pd.DatetimeIndex([F])).loc[F, "acq_id"] is None


def test_proxy_sign_and_units():
    F0, F1 = pd.Timestamp("2019-01-04"), pd.Timestamp("2019-01-11")
    fits = pd.DataFrame({"acq_id": ["a0"] * 3 + ["a1"] * 3, "osm_id": ["t1", "t2", "t3"] * 2, "diameter_m": [40.0, 50.0, 60.0] * 2,
                         "d_hat": [5.0, 10.0, 3.0, 7.0, 9.0, np.nan], "status": ["ok", "ok", "ok", "ok", "wide_interval", "cloudy"]})
    sel = pd.DataFrame({"acq_id": ["a0", "a1"], "sun_elev": [40.0, 40.0]}, index=pd.DatetimeIndex([F0, F1], name="week_ending"))
    pt = bs2.proxy_table(fits, sel)
    a1, a2 = math.pi * 20 ** 2, math.pi * 25 ** 2
    expect = -(a1 * 2.0 + a2 * (-1.0)) * 6.2898 / 1000          # roof 2 m deeper on t1 (volume down), 1 m higher on t2 (volume up)
    assert abs(pt.loc[F1, "dV_kbbl"] - expect) < 1e-9 and pt.loc[F1, "n_valid_tanks_both"] == 2
    assert abs(pt.loc[F1, "valid_area_share_both"] - (a1 + a2) / (a1 + a2 + math.pi * 30 ** 2)) < 1e-9
    assert np.isnan(pt.loc[F0, "dV_kbbl"])


# ------------------------------------------------------------------ BS1 analysis and BS0 availability
def test_pairs_and_stability(tmp_path):
    t0 = pd.Timestamp("2025-03-01 17:24", tz="UTC")
    times = [t0, t0 + pd.Timedelta(seconds=27), t0 + pd.Timedelta(days=1.5), t0 + pd.Timedelta(days=6)]
    f = pd.DataFrame({"osm_id": "way/1", "diameter_m": 60.0, "status": "ok", "sun_elev": [30.0, 30.0, 31.0, 36.0], "d_hat": [5.0, 5.5, 7.0, 9.0], "t": times})
    p = bs1a.pairs_within(f)
    assert len(p) == 3 and np.allclose(sorted(p["diff_m"]), [0.5, 1.5, 2.0])
    out = bs1a.stability(f, tmp_path)
    row = out[(out["scope"] == "pooled") & (out["sun_bin"] == "ALL") & (out["gap_class"] == "all")].iloc[0]
    assert row["n_pairs"] == 3
    assert (out["gap_class"] == "same_pass").any() and (tmp_path / "stability.csv").exists()
    assert bs1a.stability(f.assign(status="cloudy"), tmp_path).empty


def synthetic_fits_for_coverage(n_acq=12, n_tank=30, seed=2):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_acq):
        t = pd.Timestamp("2022-01-02 17:24", tz="UTC") + pd.Timedelta(days=37 * i)
        el = 25 + 4 * i
        for j in range(n_tank):
            st = rng.choice(bs1a.STATUSES, p=[0.5, 0.05, 0.1, 0.1, 0.1, 0.15])
            has = st in ("ok", "wide_interval", "full_or_fixed", "no_contrast")
            rows.append({"acq_id": f"A{i}", "datetime_utc": t.isoformat(), "t": t, "sun_elev": el, "sun_az": 160.0, "osm_id": f"way/{j}",
                         "diameter_m": 60.0, "clear": st != "cloudy", "n_pix": 20, "status": st, "d_hat": rng.uniform(0, 15) if has else np.nan,
                         "d_lo": 1.0, "d_hi": 3.0, "a": 3000 + rng.normal(0, 100) if has else np.nan, "b": 1500.0 if has else np.nan,
                         "sigma": 150.0 if has else np.nan, "rss_const_ratio": 0.4})
    return pd.DataFrame(rows)


def test_coverage_counts(tmp_path):
    f = synthetic_fits_for_coverage()
    summ = pd.DataFrame({"acq_id": [f"A{i}" for i in range(12)], "shift_flag": False, "shift_x_m": 1.0, "shift_y_m": 2.0, "reg_corr": 0.5,
                         "clear_area_share": 0.7, "n_nodata_tanks": 0})
    s = bs1a.coverage(f, summ, tmp_path)
    tab = pd.read_csv(tmp_path / "coverage.csv")
    allrow = tab[(tab["year"] == "ALL") & (tab["sun_bin"] == "ALL")].iloc[0]
    assert allrow["n_tank_rows"] == len(f) and sum(allrow[c] for c in bs1a.STATUSES) == len(f)
    assert s["n_acquisitions"] == 12 and abs(s["share_with_estimate"] - f["status"].isin(V.KEPT).mean()) < 1e-12


def test_identifiability_simulation_runs_and_is_sensible(tmp_path):
    f = synthetic_fits_for_coverage(n_acq=20, n_tank=40)
    lev = bs1a.levels_from_fits(f)
    assert "ALL" in lev and lev["ALL"]["contrast"] > 0
    rng = np.random.default_rng(3)
    cat = pd.DataFrame({"sun_az": 160.0, "sun_elev": rng.uniform(28, 62, 60)})
    reg = pd.DataFrame({"R": rng.uniform(21, 41, 25)})
    lev_easy = {"ALL": {"a": 3000.0, "contrast": 2500.0, "sigma": np.array([5.0]), "n_real_fits": 99, "median_cnr": 500.0}}
    sim = bs1a.simulate(cat, reg, lev_easy, n_acq=2, n_tank=6, seed=1)
    tab = bs1a.summarize_sim(sim, lev_easy)
    assert set(tab["d_true"].astype(str)) >= {"0", "6", "14", "all"} and tab["n_sim"].sum() > 0
    big = tab[(tab["sun_bin"] == "ALL") & (tab["d_true"].astype(str) == "all")].iloc[0]
    assert big["share_with_estimate"] > 0.5 and big["rmse_m"] < 8.0           # high contrast, tiny noise: the depth is found within a few metres
    assert sim["d_true"].nunique() == len(bs1a.D_TRUE)


def test_availability_rules(tmp_path):
    F = pd.Timestamp("2025-03-07")
    ref = V.ref_time_utc(F)
    cat = pd.DataFrame({"acq_id": ["ok", "cloudy", "outside", "ok_high_sun"], "t": [ref + pd.Timedelta(hours=30), ref - pd.Timedelta(hours=20),
                                                                                  ref + pd.Timedelta(hours=60), ref - pd.Timedelta(hours=40)],
                        "sun_elev": [38.0, 38.0, 38.0, 60.0]})
    summ = pd.DataFrame({"acq_id": ["ok", "cloudy", "outside", "ok_high_sun"], "clear_area_share": [0.8, 0.3, 0.9, 0.9]})
    s1 = pd.DataFrame({"datetime_utc": [(ref - pd.Timedelta(hours=40)).isoformat()], "covers_window": [True]})
    av = bs1a.availability(cat, summ, s1, pd.DatetimeIndex([F]), tmp_path)
    row = pd.read_csv(tmp_path / "availability.csv").iloc[0]
    assert row["s2_n_in_window"] == 3 and row["s2_n_clear50"] == 2
    assert bool(row["s2_usable_api"]) and bool(row["s2_usable_eia"]) and bool(row["s2_usable_api_sun_le45"]) and bool(row["s1_usable_api"])
    assert av["share_of_weeks"]["s2_usable_api"] == 1.0
    # a 200 h latency misses both release deadlines
    bs1a.availability(cat, summ, s1, pd.DatetimeIndex([F]), tmp_path, latency_h=200)
    late = pd.read_csv(tmp_path / "availability.csv").iloc[0]
    assert not bool(late["s2_usable_api"]) and not bool(late["s2_usable_eia"]) and not bool(late["s1_usable_api"])


def test_release_deadlines_follow_dst():
    api, eia = V.release_deadlines_utc(pd.Timestamp("2025-03-07"))      # EST until 9 March 2025: Tuesday 11 March is EDT (UTC-4)
    assert api == pd.Timestamp("2025-03-11 20:30", tz="UTC") and eia == pd.Timestamp("2025-03-12 14:30", tz="UTC")
    api, _ = V.release_deadlines_utc(pd.Timestamp("2025-01-10"))
    assert api == pd.Timestamp("2025-01-14 21:30", tz="UTC")
    assert V.ref_time_utc(pd.Timestamp("2025-01-10")) == pd.Timestamp("2025-01-10 13:00", tz="UTC")      # 07:00 CST
    assert V.ref_time_utc(pd.Timestamp("2025-07-11")) == pd.Timestamp("2025-07-11 12:00", tz="UTC")      # 07:00 CDT


# ------------------------------------------------------------------ figures (written to a temporary folder)
def test_figures_render(tmp_path, monkeypatch):
    monkeypatch.setattr(plotting, "FIGURES", tmp_path)
    fits, summ, eia, _ = make_world(tmp_path)
    res = bs2.run(fits, summ, eia, tmp_path / "bs2", sha="test")
    weekly = pd.read_csv(tmp_path / "bs2" / "weekly_table.csv")
    figs.fig_proxy(weekly, res)
    f = synthetic_fits_for_coverage(n_acq=20, n_tank=40)
    lev = bs1a.levels_from_fits(f)
    rng = np.random.default_rng(3)
    sim = bs1a.simulate(pd.DataFrame({"sun_az": 160.0, "sun_elev": rng.uniform(28, 62, 60)}), pd.DataFrame({"R": rng.uniform(21, 41, 25)}), lev, 2, 4, 1)
    ident = bs1a.summarize_sim(sim, lev)
    t0 = pd.Timestamp("2025-03-01 17:24", tz="UTC")
    pairs = pd.DataFrame({"osm_id": "way/1", "diameter_m": 60.0, "status": "ok", "sun_elev": [30.0, 30.0, 31.0, 36.0, 40.0, 41.0],
                          "d_hat": [5.0, 5.5, 7.0, 9.0, 4.0, 4.4], "t": [t0, t0 + pd.Timedelta(seconds=27), t0 + pd.Timedelta(days=1.5),
                                                                          t0 + pd.Timedelta(days=6), t0 + pd.Timedelta(days=11), t0 + pd.Timedelta(days=12)]})
    stab = bs1a.stability(pairs, tmp_path)
    figs.fig_identifiability(ident, stab)
    cat = pd.DataFrame({"acq_id": ["a"], "t": [V.ref_time_utc(pd.Timestamp("2025-03-07"))], "sun_elev": [38.0]})
    bs1a.availability(cat, pd.DataFrame({"acq_id": ["a"], "clear_area_share": [0.9]}), pd.DataFrame(columns=["datetime_utc", "covers_window"]),
                      pd.date_range("2025-01-03", "2025-12-26", freq="7D"), tmp_path)
    figs.fig_availability(pd.read_csv(tmp_path / "availability.csv"))
    for n in ("BS2_proxy_vs_eia", "BS1_identifiability", "BS0_availability"):
        assert (tmp_path / f"{n}.png").stat().st_size > 20_000 and (tmp_path / f"{n}.svg").exists()


def test_shadow_figure_on_cached_sanity_acquisitions(tmp_path, monkeypatch):
    san = V.CACHE / "sanity"
    files = sorted(san.glob("*.csv.gz")) if san.exists() else []
    if not files:
        pytest.skip("no cached sanity acquisitions (run scripts/bs1_extract.py --sanity)")
    monkeypatch.setattr(plotting, "FIGURES", tmp_path)
    fits = pd.concat([pd.read_csv(p) for p in files], ignore_index=True)
    summ = pd.DataFrame([json.loads(p.with_suffix("").with_suffix(".json").read_text(encoding="utf-8")) for p in files])
    figs.fig_shadow_model(fits, summ, V.registry(), V.CACHE)
    assert (tmp_path / "BS1_shadow_model.png").stat().st_size > 20_000
