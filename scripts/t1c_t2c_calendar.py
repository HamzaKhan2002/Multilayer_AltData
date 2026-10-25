"""T1c / T2c (prereg/tests_v2.json): the WTI blocks of T1 and T2 recomputed with the EIA archive release calendar.

--calendar rule     built-in check: the WTI blocks computed with the v1 rule calendar must reproduce the WTI blocks of results/T1.json and
                    results/T2.json (every number within 1e-12 relative, every string identical); nothing is written but the log.
--calendar archive  runs the same check first, then T1c and T2c. Release day of a data week = EIA archive release date where
                    audit/eia_release_registry.csv holds the week (rows of data-only re-issue folders ignored; the earliest date if a week has
                    several rows), the v1 rule date otherwise. Natural gas keeps the v1 calendar (it only enters the WTI placebo of T1).
The statistics are those of scripts/t1_release_volatility.py and scripts/t2_inventory_surprise.py: their functions are imported, and the
T2 block copies the body of its main loop for WTI.

Usage: python scripts/t1c_t2c_calendar.py --calendar rule|archive
Outputs (archive): results/v2/T1c.json, results/v2/T2c.json, one line per test in results/v2/trial_log_v2.csv; log: results/v2/T1c_T2c.log
"""
import argparse
import csv
import dataclasses
import datetime as dt
import io
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

import t1_release_volatility as t1  # noqa: E402
import t2_inventory_surprise as t2  # noqa: E402
from altdata.markets import PERIOD, build  # noqa: E402
from altdata.paths import RESULTS, assert_prereg_frozen  # noqa: E402
from altdata.stats import ols_hac, one_sided_p_from_t  # noqa: E402
from altdata.v2common import V2, assert_prereg_v2_frozen  # noqa: E402

TOL = 1e-12
REGISTRY = ROOT / "audit" / "eia_release_registry.csv"
TRIAL_LOG = V2 / "trial_log_v2.csv"
SCRIPT = "scripts/t1c_t2c_calendar.py"
ARCHIVE_START = pd.Timestamp("2011-07-22")


class Log:
    def __init__(self, path: Path):
        self.f = open(path, "a", encoding="utf-8", newline="\n")

    def __call__(self, *parts) -> None:
        line = f"{dt.datetime.now().isoformat(timespec='seconds')} " + " ".join(str(p) for p in parts)
        print(line, flush=True)
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


def t1_block(m, ng_days: pd.DatetimeIndex) -> dict:
    """WTI block of T1 (body of the loop in t1_release_volatility.main for n = WTI, other = NG)."""
    a = t1.abs_returns(m)
    days = t1.release_days(m)
    res = {"sample_start": str(a.index.min().date()), "sample_end": str(a.index.max().date()), "n_days": int(len(a)),
           "primary": t1.ratio(a, days), "placebo_on_NG_release_days": t1.ratio(a, ng_days)}
    for k, (lo, hi) in t1.SUBPERIODS.items():
        res[f"sub_{k}"] = t1.ratio(t1.abs_returns(m, lo, hi), days)
    res["verdict"] = "SUPPORTED" if res["primary"]["ci95"][0] > 1.00 else "NOT SUPPORTED"
    return res


def t2_block(m, s: pd.Series) -> dict:
    """WTI block of T2 (body of the loop in t2_inventory_surprise.main for n = WTI)."""
    rel = m.releases[m.releases["is_trading_day"]].set_index("week_end")["release"]
    df = pd.DataFrame({"s": s, "R": rel}).dropna()
    df = df[(df["R"] >= m.start) & (df["R"] <= PERIOD[1])]
    df["r"] = m.returns["r"].reindex(df["R"]).to_numpy()
    df = df.dropna(subset=["r"])
    sd = float(df["s"].std(ddof=1))
    df["z"] = df["s"] / sd
    reg = ols_hac(df["r"].to_numpy(), df["z"].to_numpy(), t2.LAGS)
    t = reg["t"][0]
    nz = (df["s"] != 0) & (df["r"] != 0)
    q = pd.qcut(df["z"], 5, labels=False)
    quint = [{"quintile": int(i + 1), "n": int((q == i).sum()), "mean_r_bp": float(1e4 * df.loc[q == i, "r"].mean()),
              "se_bp": float(1e4 * df.loc[q == i, "r"].std(ddof=1) / np.sqrt((q == i).sum()))} for i in range(5)]
    rho = stats.spearmanr(df["z"], df["r"])
    return {"units": t2.UNITS["WTI"], "first_release": str(df["R"].min().date()), "last_release": str(df["R"].max().date()),
            "n": reg["n"], "sd_surprise": sd, "slope_b_per_sd": reg["b"][0], "se": reg["se"][0], "t_nw4": t, "r2": reg["r2"],
            "p_one_sided_normal": one_sided_p_from_t(t, "neg"), "spearman": float(rho.statistic), "spearman_p": float(rho.pvalue),
            "sign_hit_rate": float((np.sign(df.loc[nz, "r"]) == -np.sign(df.loc[nz, "s"])).mean()), "n_sign": int(nz.sum()),
            "quintiles": quint, "verdict": "SUPPORTED" if t <= -2.0 else "NOT SUPPORTED"}


def archive_market(m):
    """Market whose release table carries the archive date where the registry has the week; also the per-week table with both dates."""
    reg = pd.read_csv(REGISTRY, parse_dates=["release_date", "week_ending_friday"])
    reg = reg[~reg["note"].fillna("").str.contains("data-only folder")]
    arch = (reg.sort_values(["week_ending_friday", "release_date"]).drop_duplicates("week_ending_friday", keep="first")
            .set_index("week_ending_friday")["release_date"])
    rel = m.releases.copy()
    rel["release_rule"] = rel["release"]
    rel["release_archive"] = rel["week_end"].map(arch)
    rel["release"] = rel["release_archive"].fillna(rel["release_rule"])
    rel["is_trading_day"] = rel["release"].isin(m.returns.index)
    return dataclasses.replace(m, releases=rel[["week_end", "release", "shifted", "is_trading_day"]].copy()), rel


def flatten(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from flatten(v, f"{path}.{k}" if path else str(k))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from flatten(v, f"{path}[{i}]")
    else:
        yield path, x


def compare(new: dict, ref: dict, label: str) -> dict:
    """Every leaf of the recomputed block against the saved block: numbers within TOL relative, everything else identical; raises on any difference."""
    a, b = dict(flatten(json.loads(json.dumps(new)))), dict(flatten(ref))
    if a.keys() != b.keys():
        raise SystemExit(f"STOP: {label}: fields differ: only in new {sorted(a.keys() - b.keys())}, only in saved {sorted(b.keys() - a.keys())}")
    bad, n_num, worst = [], 0, 0.0
    for k in a:
        x, y = a[k], b[k]
        isnum = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
        if isnum(x) and isnum(y):
            n_num += 1
            if math.isnan(x) and math.isnan(y):
                continue
            rel = 0.0 if x == y else abs(x - y) / max(abs(x), abs(y))
            worst = max(worst, rel)
            if not rel <= TOL:
                bad.append((k, x, y, rel))
        elif x != y:
            bad.append((k, x, y, None))
    if bad:
        raise SystemExit(f"STOP: {label}: {len(bad)} fields differ from the saved block, first: {bad[:5]}")
    return {"label": label, "status": "PASS", "n_fields": len(a), "n_numbers_compared": n_num, "max_rel_diff": worst, "tolerance": TOL}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--calendar", choices=["rule", "archive"], required=True)
    args = ap.parse_args()
    t0 = time.time()
    sha1, sha2 = assert_prereg_frozen(), assert_prereg_v2_frozen()
    log = Log(V2 / "T1c_T2c.log")
    log(f"start calendar={args.calendar} prereg_v1 {sha1[:12]} prereg_v2 {sha2[:12]}")

    wti, ng = build("WTI"), build("NG")
    s = t2.surprises(wti.stocks, wti.seas_k)
    ng_days = t1.release_days(ng)
    ref1 = json.loads((RESULTS / "T1.json").read_text(encoding="utf-8"))["markets"]["WTI"]
    ref2 = json.loads((RESULTS / "T2.json").read_text(encoding="utf-8"))["markets"]["WTI"]

    chk1 = compare(t1_block(wti, ng_days), ref1, "T1 WTI block, rule calendar vs results/T1.json")
    chk2 = compare(t2_block(wti, s), ref2, "T2 WTI block, rule calendar vs results/T2.json")
    for c in (chk1, chk2):
        log(f"{c['label']}: {c['status']} ({c['n_numbers_compared']} numbers, {c['n_fields']} fields, max relative difference {c['max_rel_diff']:.3g})")
    if args.calendar == "rule":
        log(f"done in {time.time() - t0:.1f}s")
        return
    if (V2 / "T1c.json").exists() or (V2 / "T2c.json").exists():
        raise SystemExit("STOP: results/v2/T1c.json or T2c.json exists; T1c and T2c are run once")

    wa, rel = archive_market(wti)
    red = rel[rel["release_archive"].notna() & (rel["release_archive"] != rel["release_rule"])]
    inside = lambda d: (d >= PERIOD[0]) & (d <= PERIOD[1])  # noqa: E731
    red_in = red[inside(red["release_rule"]) | inside(red["release_archive"])]
    redated = [{"week_ending": r.week_end.date().isoformat(), "rule_release": r.release_rule.date().isoformat(),
                "archive_release": r.release_archive.date().isoformat(), "archive_minus_rule_days": int((r.release_archive - r.release_rule).days),
                "in_sample": bool(inside(pd.Series([r.release_rule, r.release_archive])).any())} for r in red.itertuples()]
    no_row = rel[(rel["week_end"] >= ARCHIVE_START) & rel["release_archive"].isna() & (rel["release_rule"] <= PERIOD[1])]
    fallback = [{"week_ending": r.week_end.date().isoformat(), "rule_release": r.release_rule.date().isoformat()} for r in no_row.itertuples()]
    log(f"weeks redated: {len(red_in)} in sample, {len(red)} in all years; weeks from {ARCHIVE_START.date()} on without a usable archive row "
        f"(rule date kept, rule date in sample): {[f['week_ending'] for f in fallback]}")
    for r in redated:
        log("  redated", r)
    extra = {"calendar": "archive", "prereg_sha256": sha1, "prereg_v2_sha256": sha2, "period": [str(PERIOD[0].date()), str(PERIOD[1].date())],
             "n_weeks_redated": int(len(red_in)), "n_weeks_redated_all_years": int(len(red)), "redated_weeks": redated,
             "weeks_with_rule_date_kept_after_archive_start": fallback}

    b1 = t1_block(wa, ng_days)
    out1 = {"id": "T1c", **extra, "rule_reproduction_check": chk1, "v1_primary": ref1["primary"], "markets": {"WTI": b1}}
    (V2 / "T1c.json").write_text(json.dumps(out1, indent=2), encoding="utf-8")
    p, q = b1["primary"], ref1["primary"]
    log(f"T1c WTI ratio {p['ratio']:.4f} ci95 [{p['ci95'][0]:.4f}, {p['ci95'][1]:.4f}] p {p['p_one_sided']:.4f} n_event {p['n_event']} n_other {p['n_other']} -> {b1['verdict']}"
        f" | v1 ratio {q['ratio']:.4f} ci95 [{q['ci95'][0]:.4f}, {q['ci95'][1]:.4f}] n_event {q['n_event']}")
    log("T1c placebo on NG days", round(b1["placebo_on_NG_release_days"]["ratio"], 4), "sub", {k: round(v["ratio"], 4) for k, v in b1.items() if k.startswith("sub_")})

    b2 = t2_block(wa, s)
    out2 = {"id": "T2c", **extra, "rule_reproduction_check": chk2, "v1_reference": {k: ref2[k] for k in ("n", "slope_b_per_sd", "se", "t_nw4", "spearman", "sign_hit_rate", "verdict")},
            "markets": {"WTI": b2}}
    (V2 / "T2c.json").write_text(json.dumps(out2, indent=2), encoding="utf-8")
    log(f"T2c WTI n {b2['n']} slope {1e4 * b2['slope_b_per_sd']:.2f} bp per sd se {1e4 * b2['se']:.2f} t {b2['t_nw4']:.3f} spearman {b2['spearman']:.3f} hit {b2['sign_hit_rate']:.3f} -> {b2['verdict']}"
        f" | v1 n {ref2['n']} slope {1e4 * ref2['slope_b_per_sd']:.2f} t {ref2['t_nw4']:.3f}")

    secs = time.time() - t0
    note = f"calendar archive; {len(red_in)} weeks redated in sample; rule check PASS"
    append_trial("T1c", sha2, f"WTI: {b1['verdict']}", secs, note)
    append_trial("T2c", sha2, f"WTI: {b2['verdict']}", secs, note)
    log(f"wrote results/v2/T1c.json, results/v2/T2c.json; trial log lines appended; done in {secs:.1f}s")


if __name__ == "__main__":
    main()
