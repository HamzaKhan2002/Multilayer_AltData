"""Collect the verdicts of T1 to T5 into results/verdicts.md, with the Holm-adjusted one-sided p-values of the four primary tests
(T1-WTI, T1-NG, T2-WTI, T2-NG) reported for information, as pre-registered.

Usage: python scripts/verdicts.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from altdata.paths import PREREG_SHA256, RESULTS  # noqa: E402
from altdata.stats import holm, one_sided_p_from_t  # noqa: E402


def load(name: str):
    p = RESULTS / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main() -> None:
    t1, t2, t3, t4, t5 = (load(n) for n in ("T1", "T2", "T3", "T4", "T5"))
    lines = ["# Verdicts of the pre-registered tests", "", f"Pre-registration SHA-256: `{PREREG_SHA256}`. Each test was run once; see `trial_log.csv` and `deviations.md`.", ""]
    primary = {}
    if t1:
        for n, r in t1["markets"].items():
            primary[f"T1-{n}"] = r["primary"]["p_one_sided"]
    if t2:
        for n, r in t2["markets"].items():
            primary[f"T2-{n}"] = r["p_one_sided_normal"]
    adj = holm(primary) if primary else {}
    lines += ["| Test | Question | Result | Verdict | Holm-adjusted one-sided p |", "|---|---|---|---|---|"]
    if t1:
        for n, r in t1["markets"].items():
            p = r["primary"]
            lines.append(f"| T1 {n} | Report days more volatile? | ratio {p['ratio']:.2f}, 95% interval {p['ci95'][0]:.2f} to {p['ci95'][1]:.2f}, {p['n_event']} report days | {r['verdict']} | {adj.get(f'T1-{n}', float('nan')):.3f} |")
    if t2:
        for n, r in t2["markets"].items():
            lines.append(f"| T2 {n} | Surprise moves the price against its sign? | slope {1e4 * r['slope_b_per_sd']:+.1f} bp per sd, Newey-West t {r['t_nw4']:.2f}, n {r['n']} | {r['verdict']} | {adj.get(f'T2-{n}', float('nan')):.3f} |")
    if t3:
        lines.append(f"| T3 | Cloudier weeks, larger release-day move? (exploratory) | b {t3['b']:+.3g}, one-sided t {t3['t_nw4']:.2f}, n {t3['n']} | {t3['verdict']} | not in the primary family |")
    if t4:
        lines.append(f"| T4 | More forecast wind and solar, lower German day-ahead price? | {t4['b_eur_mwh_per_10pp']:+.2f} EUR/MWh per +10 pp, Newey-West t {t4['t_nw7']:.1f}, n {t4['n_days']} days | {t4['verdict']} | mechanism check |")
    if t5:
        lines.append(f"| T5 | Colder days, larger net EU storage withdrawals? | {t5['b_gwh_per_hdd_degree']:+.0f} GWh/d per degree-day, Newey-West t {t5['t_nw7']:.1f}, n {t5['n_days']} days | {t5['verdict']} | mechanism check |")
    (RESULTS / "verdicts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
