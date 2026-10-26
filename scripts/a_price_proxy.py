"""A price-only proxy (prereg/tests_v3.json, frozen before any statistic): WTI return in the 30 minutes after the API release (16:30-17:00 ET on the day
before the EIA release) against the return from 60 minutes to 1 minute before the EIA release (09:30-10:29 ET), on HistData WTIUSD bid bars.
Exploratory proxy of branch A of I1: not the published API-minus-consensus portfolio, not a test of branch B, not an executable PnL on CL.

Usage: python scripts/a_price_proxy.py [--selftest] [--dry]
  --selftest  runs the statistics on synthetic data only; reads no price
  --dry       event availability and the structural clock check (no return and no AR or AH statistic); writes nothing
Outputs: results/v3/a_price_proxy.json, a_events.csv, a_price_proxy.log; one line in results/v3/trial_log_v3.csv
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402
from scipy import stats  # noqa: E402

from altdata import histdata  # noqa: E402
import b0_transmission as b0  # noqa: E402

OUT = ROOT / "results" / "v3"
PREREG = ROOT / "prereg" / "tests_v3.json"
SHA_FILE = OUT / "prereg_v3.sha256"
TRIAL_LOG = OUT / "trial_log_v3.csv"
SCRIPT = "scripts/a_price_proxy.py"
NY = histdata.NY
BLOCKS = {"overlap": ("2013-08-01", "2019-08-31"), "post": ("2019-09-01", "2023-12-31"), "recent": ("2026-06-01", "2026-10-24")}
MIN_OVERLAP = 150
CLOCK_RATIO_MAX = 0.25
COST_CENTS = (1.5, 2.5)
Z = 1.959964
REASONS = ["holiday_shifted", "data_only_same_day", "other_release_time", "missing_bar", "nonpositive_price", "structural_clock_year"]
# index = 60 * (hour - base hour) + minute; the API-day arrays start at 16:00, the event-day arrays at 09:00; the value at index k is the close of the bar starting at k
API0, API1 = 29, 59                  # P(16:30) and P(17:00) on the API day
PRE0, PRE1, P1030, P1036 = 29, 88, 89, 95   # P(09:30), P(10:29), P(10:30), P(10:36) on the event day
H = {"api_to_1036": "P(10:36 event day) - P(16:30 API day)", "wed_0930_to_1036": "P(10:36) - P(09:30)", "print_1030_to_1036": "P(10:36) - P(10:30)",
     "api_window": "P(17:00) - P(16:30) on the API day"}


def frozen_hash() -> str:
    rec = SHA_FILE.read_text(encoding="ascii").split()[0].strip().lower()
    h = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    if h != rec:
        raise SystemExit(f"STOP: prereg/tests_v3.json ({h}) differs from the frozen hash {rec}")
    return h


def hour_arrays(close: pd.Series, days, hour: int) -> dict:
    """Closes at the 120 minute starts from HH:00 of each day (NaN where there is no bar)."""
    out = {}
    for d in days:
        idx = pd.date_range(pd.Timestamp(f"{d:%Y-%m-%d} {hour:02d}:00", tz=NY), periods=120, freq="min")
        out[d] = close.reindex(idx).to_numpy(float)
    return out


def block_of(day: pd.Timestamp) -> str:
    s = f"{day:%Y-%m-%d}"
    for k, (lo, hi) in BLOCKS.items():
        if lo <= s <= hi:
            return k
    return ""


def minute_profile(arrs: list, k_print: int) -> tuple[float, float]:
    """Mean absolute one-minute change (cents) of the minute starting at index k_print and of the 15 minutes before it (indices k_print-15 .. k_print-1)."""
    C = np.vstack([np.abs(a[1:] - a[:-1]) for a in arrs])      # column j is the minute at index j + 1
    return float(100 * np.nanmean(C[:, k_print - 1])), float(100 * np.nanmean(C[:, k_print - 16:k_print - 1]))


def block_stats(r_api: np.ndarray, r_pre: np.ndarray, g_cents: np.ndarray) -> dict:
    """Correlation (Fisher-z interval), HC1 slope, Spearman, and the descriptive sign-rule result for one block."""
    n = len(r_api)
    out = {"n": int(n)}
    if n < 5:
        return out
    r = float(np.corrcoef(r_api, r_pre)[0, 1])
    zf, se = np.arctanh(r), 1.0 / np.sqrt(n - 3)
    lo, hi = float(np.tanh(zf - Z * se)), float(np.tanh(zf + Z * se))
    res = sm.OLS(r_pre, sm.add_constant(r_api)).fit(cov_type="HC1")
    ci = res.conf_int(alpha=0.05)
    rho, p_rho = stats.spearmanr(r_api, r_pre)
    gm, gs = float(g_cents.mean()), float(g_cents.std(ddof=1))
    out.update({"r": r, "r_ci95_fisher": [lo, hi], "r2": float(res.rsquared), "slope": float(res.params[1]), "slope_ci95_hc1": [float(ci[1, 0]), float(ci[1, 1])],
                "slope_t_hc1": float(res.tvalues[1]), "spearman": float(rho), "spearman_p": float(p_rho),
                "sd_r_api_pct": float(r_api.std(ddof=1)), "sd_r_pre_pct": float(r_pre.std(ddof=1)),
                "sign_rule_gross_cents": {"mean": gm, "sd": gs, "t_of_mean": float(gm / (gs / np.sqrt(n))), "share_positive": float((g_cents > 0).mean()),
                                          "exceeds_cost_1.5c": bool(gm > COST_CENTS[0]), "exceeds_cost_2.5c": bool(gm > COST_CENTS[1])}})
    return out


def verdict(lo: float, hi: float) -> str:
    """Rule of prereg AR: SIGNAL if the lower 95% bound of r is above 0; NO SIGNAL DETECTED if the upper bound is below 0.10; otherwise INCONCLUSIVE."""
    if lo > 0:
        return "SIGNAL"
    if hi < 0.10:
        return "NO SIGNAL DETECTED"
    return "INCONCLUSIVE"


def selftest() -> None:
    rng = np.random.default_rng(1)
    for n, beta, expect in ((300, 0.4, "SIGNAL"), (3000, 0.0, "NO SIGNAL DETECTED"), (40, 0.0, "INCONCLUSIVE")):
        x = rng.normal(0, 0.3, n)
        y = beta * x + rng.normal(0, 0.5, n)
        s = block_stats(x, y, np.sign(x) * y * 10)
        v = verdict(*s["r_ci95_fisher"])
        assert v == expect, (n, beta, v, expect, s["r"], s["r_ci95_fisher"])
    a = [np.r_[np.random.default_rng(2).normal(0, 1, 120)].cumsum() for _ in range(5)]
    p, b = minute_profile(a, 30)
    assert np.isfinite(p) and np.isfinite(b)
    print("selftest ok")


def append_trial(test_id: str, sha: str, verdict_txt: str, seconds: float) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    if not TRIAL_LOG.exists():
        w.writerow(["id", "timestamp", "script", "prereg_v3_sha256", "verdict", "seconds"])
    w.writerow([test_id, dt.datetime.now().isoformat(timespec="seconds"), SCRIPT, sha, verdict_txt, f"{seconds:.1f}"])
    with open(TRIAL_LOG, "ab") as f:
        f.write(buf.getvalue().encode("utf-8"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    t0 = time.time()
    sha = frozen_hash()
    histdata.selftest()
    if not args.dry:
        OUT.mkdir(parents=True, exist_ok=True)
        if (OUT / "a_price_proxy.json").exists():
            raise SystemExit("STOP: results/v3/a_price_proxy.json exists; the test is run once")
    log = b0.Log(None if args.dry else OUT / "a_price_proxy.log")
    log(f"start A price proxy dry={args.dry} prereg_v3 {sha[:12]}")

    ev = b0.candidate_events()
    close = histdata.load_close("WTIUSD", b0.PERIODS[0][0], b0.PERIODS[-1][1])
    api_days = ev["event_day"] - pd.Timedelta(days=1)
    A = hour_arrays(close, api_days, 16)
    E = hour_arrays(close, ev["event_day"], 9)
    a_arr = [A[d] for d in api_days]
    e_arr = [E[d] for d in ev["event_day"]]
    ev["api_day"] = api_days
    ev["block"] = [block_of(d) for d in ev["event_day"]]
    ev["missing_bar"] = [not (np.isfinite([a[API0], a[API1]]).all() and np.isfinite([e[PRE0], e[PRE1], e[P1030], e[P1036]]).all()) for a, e in zip(a_arr, e_arr)]
    px = np.array([[a[API0], a[API1], e[PRE0], e[PRE1], e[P1030], e[P1036]] for a, e in zip(a_arr, e_arr)])
    ev["nonpositive_price"] = ~ev["missing_bar"] & (np.nan_to_num(px, nan=1.0) <= 0).any(axis=1)

    # structural clock check (AM-A-1): bars starting 17:15..17:59 over bars in hour 16 on API days; the CME halt starts at 17:15 before 2015-09-21 and at 17:00 after
    pre_ok = ~(ev["holiday_shifted"] | ev["data_only_same_day"] | ev["other_release_time"])
    n16 = np.array([int(np.isfinite(a[0:60]).sum()) for a in a_arr])
    n17 = np.array([int(np.isfinite(a[75:120]).sum()) for a in a_arr])
    n17_early = np.array([int(np.isfinite(a[60:75]).sum()) for a in a_arr])
    yrs = ev["event_day"].dt.year.to_numpy()
    structural = {}
    for y in sorted(set(yrs)):
        m = pre_ok.to_numpy() & (yrs == y) & (n16 > 0)
        ratio = float(n17[m].sum() / n16[m].sum()) if m.any() and n16[m].sum() else float("nan")
        early = float(n17_early[m].sum() / n16[m].sum()) if m.any() and n16[m].sum() else float("nan")
        structural[str(y)] = {"n_events": int(m.sum()), "bars_hour16": int(n16[m].sum()), "bars_1715_1759": int(n17[m].sum()), "ratio_1715_1759_over_hour16": ratio,
                              "ratio_1700_1714_over_hour16_descriptive": early, "excluded": bool(np.isfinite(ratio) and ratio > CLOCK_RATIO_MAX)}
    bad_years = {int(y) for y, s in structural.items() if s["excluded"]}
    ev["structural_clock_year"] = pd.Series(yrs).isin(bad_years).to_numpy()
    first = np.full(len(ev), "", dtype=object)
    for r in REASONS:
        first = np.where((first == "") & ev[r].to_numpy(), r, first)
    ev["reason"], ev["status"] = first, np.where(first == "", "included", "excluded")
    waterfall = {r: int((first == r).sum()) for r in REASONS}
    inc_mask = first == ""
    by_block = {b: int((inc_mask & (ev["block"] == b).to_numpy()).sum()) for b in BLOCKS}
    log(f"candidates {len(ev)}; excluded by first reason {waterfall}; included by block {by_block}")
    log("structural clock check (bars 17:15-17:59 / hour 16; bars 17:00-17:14 / hour 16, descriptive):",
        {y: (s["n_events"], round(s["ratio_1715_1759_over_hour16"], 3), round(s["ratio_1700_1714_over_hour16_descriptive"], 3), s["excluded"]) for y, s in structural.items()})
    if args.dry:
        log("dry run: no return, no AR or AH statistic computed; nothing written")
        return
    if by_block["overlap"] < MIN_OVERLAP:
        out = {"id": "A_price_proxy", "prereg_v3_sha256": sha, "status": "BLOCKED", "verdict": "BLOCKED", "events": {"candidates": len(ev), "excluded_by_first_reason": waterfall, "included_by_block": by_block},
               "note": f"fewer than {MIN_OVERLAP} overlap events; no outcome statistic computed"}
        (OUT / "a_price_proxy.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        append_trial("AR", sha, "BLOCKED", time.time() - t0)
        log("BLOCKED")
        return

    # variables
    ev["r_api"] = 100 * np.log(px[:, 1] / px[:, 0])
    ev["r_pre"] = 100 * np.log(px[:, 3] / px[:, 2])
    ev["dP_pre_usd"] = px[:, 3] - px[:, 2]
    ev["G_cents"] = 100 * np.sign(ev["r_api"]) * ev["dP_pre_usd"]
    ev["h_api_to_1036"] = 100 * (px[:, 5] - px[:, 0])
    ev["h_wed_0930_to_1036"] = 100 * (px[:, 5] - px[:, 2])
    ev["h_print_1030_to_1036"] = 100 * (px[:, 5] - px[:, 4])
    ev["h_api_window"] = 100 * (px[:, 1] - px[:, 0])
    S = ev[inc_mask]

    ar = {}
    for b in BLOCKS:
        d = S[S["block"] == b]
        ar[b] = block_stats(d["r_api"].to_numpy(float), d["r_pre"].to_numpy(float), d["G_cents"].to_numpy(float))
    lo, hi = ar["overlap"]["r_ci95_fisher"]
    v = verdict(lo, hi)
    ar["overlap"]["verdict"] = v
    pooled = S[S["block"].isin(["overlap", "post"])]
    ah = {k: {"definition": H[k], "pooled_overlap_post": {"n": int(len(pooled)), "sd_cents": float(pooled[f"h_{k}"].std(ddof=1)), "mean_abs_cents": float(pooled[f"h_{k}"].abs().mean())}}
          for k in H}
    for k in H:
        for b in ("overlap", "post", "recent"):
            d = S[S["block"] == b]
            ah[k][b] = {"n": int(len(d)), "sd_cents": float(d[f"h_{k}"].std(ddof=1)) if len(d) > 1 else None}
    # descriptive clock profile per year on the events that passed the first three exclusions and have any bar in hour 16 or hour 9-10
    ac_desc = {}
    for y in sorted(set(yrs)):
        m = pre_ok.to_numpy() & (yrs == y) & (n16 > 0)
        if m.sum() < 3:
            continue
        pa, ba = minute_profile([a for a, k in zip(a_arr, m) if k], 30)
        pe, be = minute_profile([e for e, k in zip(e_arr, m) if k], 90)
        ac_desc[str(y)] = {"n": int(m.sum()), "api_1630_cents": pa, "api_1615_1629_cents": ba, "eia_1030_cents": pe, "eia_1015_1029_cents": be}
    top = S.reindex(S["r_pre"].abs().sort_values(ascending=False).index).head(5)
    out = {"id": "A_price_proxy", "prereg_v3_sha256": sha, "status": "COMPLETED", "verdict": v, "scope": "exploratory price-only proxy of branch A; bid-only HistData WTIUSD; not executable on CL; not evidence for B",
           "data": {"pair": "WTIUSD", "n_bars": int(len(close)), "first_bar": str(close.index[0]), "last_bar": str(close.index[-1])},
           "events": {"candidates": int(len(ev)), "excluded_by_first_reason": waterfall, "included_by_block": by_block},
           "AC": {"structural": structural, "descriptive": ac_desc}, "AR": ar, "AH": ah,
           "largest_abs_r_pre": [{"event_day": str(r.event_day.date()), "r_pre_pct": float(r.r_pre), "r_api_pct": float(r.r_api)} for r in top.itertuples()]}
    cols = ["event_day", "api_day", "block", "status", "reason", "r_api", "r_pre", "dP_pre_usd", "G_cents", "h_api_to_1036", "h_wed_0930_to_1036", "h_print_1030_to_1036", "h_api_window"]
    ev[cols].to_csv(OUT / "a_events.csv", index=False, date_format="%Y-%m-%d", float_format="%.6f")
    (OUT / "a_price_proxy.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    secs = time.time() - t0
    o = ar["overlap"]
    append_trial("AR", sha, v, secs)
    log(f"AR overlap n {o['n']} r {o['r']:.3f} [{lo:.3f}, {hi:.3f}] -> {v}; slope {o['slope']:.3f} HC1 [{o['slope_ci95_hc1'][0]:.3f}, {o['slope_ci95_hc1'][1]:.3f}]; R2 {o['r2']:.4f}")
    for b in ("post", "recent"):
        s = ar[b]
        if "r" in s:
            log(f"AR {b} n {s['n']} r {s['r']:.3f} [{s['r_ci95_fisher'][0]:.3f}, {s['r_ci95_fisher'][1]:.3f}]")
    log("sign rule gross cents:", {b: (round(s["sign_rule_gross_cents"]["mean"], 2), round(s["sign_rule_gross_cents"]["t_of_mean"], 2)) for b, s in ar.items() if "r" in s})
    log("AH pooled sd (cents):", {k: round(a["pooled_overlap_post"]["sd_cents"], 1) for k, a in ah.items()})
    log(f"wrote results/v3/a_price_proxy.json and a_events.csv; trial log line appended; done in {secs:.1f}s")


if __name__ == "__main__":
    main()
