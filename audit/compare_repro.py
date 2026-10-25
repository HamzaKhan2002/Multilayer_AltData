"""Compare T1-T5 outputs re-run in a scratch copy of the repo with the originals in results/.

Usage: python audit/compare_repro.py [--new C:\\...\\mla_repro\\results]
Compares every field of results/T{1..5}.json recursively (numbers: absolute and relative difference; other types: equality)
and the CSV outputs column by column. Writes audit/repro_T1_T5.md.
"""
import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import statsmodels

ROOT = Path(__file__).resolve().parents[1]
ORIG = ROOT / "results"
NEW_DEFAULT = Path(r"C:\Users\Hamza\AppData\Local\Temp\mla_repro\results")
OUT = ROOT / "audit" / "repro_T1_T5.md"
REL_TOL = 1e-9
JSONS = [f"T{i}.json" for i in range(1, 6)]
CSVS = ["T3_weeks.csv", "T4_daily.csv", "T5_daily.csv", "T5_fill.csv"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def diff_pair(a: float, b: float) -> tuple[float, float]:
    a, b = float(a), float(b)
    if math.isnan(a) and math.isnan(b):
        return 0.0, 0.0
    if math.isnan(a) or math.isnan(b):
        return math.inf, math.inf
    if a == b:
        return 0.0, 0.0
    ad = abs(a - b)
    return ad, ad / max(abs(a), abs(b))


def walk(a, b, path: str, nums: list, others: list, problems: list) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else k
            if k not in b:
                problems.append((p, "field only in original"))
            elif k not in a:
                problems.append((p, "field only in re-run"))
            else:
                walk(a[k], b[k], p, nums, others, problems)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            problems.append((path, f"list length {len(a)} vs {len(b)}"))
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", nums, others, problems)
    elif is_num(a) and is_num(b):
        ad, rd = diff_pair(a, b)
        nums.append((path, float(a), float(b), ad, rd))
    else:
        others.append(path)
        if a != b or type(a) is not type(b):
            problems.append((path, f"{a!r} vs {b!r}"))


def compare_json(name: str, new_dir: Path) -> dict:
    a = json.loads((ORIG / name).read_text(encoding="utf-8"))
    b = json.loads((new_dir / name).read_text(encoding="utf-8"))
    nums, others, problems = [], [], []
    walk(a, b, "", nums, others, problems)
    worst_abs = max(nums, key=lambda r: r[3])
    worst_rel = max(nums, key=lambda r: r[4])
    over = [r for r in nums if r[4] > REL_TOL]
    return {"file": name, "sha_orig": sha(ORIG / name), "sha_new": sha(new_dir / name), "n_num": len(nums), "n_other": len(others),
            "max_abs": worst_abs[3], "max_abs_path": worst_abs[0], "max_rel": worst_rel[4], "max_rel_path": worst_rel[0],
            "over": over, "problems": problems}


def compare_csv(name: str, new_dir: Path) -> dict:
    a, b = pd.read_csv(ORIG / name), pd.read_csv(new_dir / name)
    res = {"file": name, "sha_orig": sha(ORIG / name), "sha_new": sha(new_dir / name), "rows": (len(a), len(b)), "cols": (list(a.columns) == list(b.columns)),
           "max_abs": 0.0, "max_abs_col": "-", "text_equal": True}
    if len(a) != len(b) or list(a.columns) != list(b.columns):
        return res | {"max_abs": math.inf}
    for c in a.columns:
        if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]):
            x, y = a[c].to_numpy(float), b[c].to_numpy(float)
            both_nan = np.isnan(x) & np.isnan(y)
            d = np.where(both_nan, 0.0, np.abs(x - y))
            if np.isnan(d).any():
                d = np.where(np.isnan(d), np.inf, d)
            if d.max() > res["max_abs"]:
                res["max_abs"], res["max_abs_col"] = float(d.max()), c
        elif not a[c].equals(b[c]):
            res["text_equal"] = False
    return res


def fmt(x: float) -> str:
    return "0" if x == 0 else f"{x:.3e}"


def sections(path: Path) -> dict[str, str]:
    """'## heading' -> section text, in file order."""
    out, head = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            head = line
            out[head] = []
        elif head is not None:
            out[head].append(line)
    return {h: "\n".join(b).strip() for h, b in out.items()}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", type=Path, default=NEW_DEFAULT)
    new_dir = ap.parse_args().new
    jr = [compare_json(n, new_dir) for n in JSONS]
    cr = [compare_csv(n, new_dir) for n in CSVS]
    trial = pd.read_csv(new_dir / "trial_log.csv")

    L = ["# Reproduction of T1-T5 in a scratch copy", "",
         f"Original outputs: `multilayer-altdata/results/` (not modified). Re-run: `{new_dir.parent}` (copy of src, scripts, prereg, data, results; "
         "T*.json, T*.log, T*_*.csv and trial_log.csv deleted in the copy before the run). Scripts run in the order T1, T2, T3, T4, T5 on the cached data in `data/`; "
         "no download was attempted and all five exited with code 0.", "",
         "## Environment", "",
         f"- Python {platform.python_version()} ({platform.python_implementation()}, {platform.platform()})",
         f"- numpy {np.__version__}, pandas {pd.__version__}, scipy {scipy.__version__}, statsmodels {statsmodels.__version__}", "",
         "## Re-run log (copy's trial_log.csv)", "", "| id | timestamp | seconds | verdict |", "|---|---|---|---|"]
    for _, r in trial.iterrows():
        L.append(f"| {r['id']} | {r['timestamp']} | {r['seconds']} | {r['verdict']} |")
    L += ["", f"## JSON outputs (relative tolerance {REL_TOL:g})", "",
          "| file | numeric fields | other fields | max abs diff | max rel diff | fields with rel diff > 1e-9 | structural/string mismatches | bytes identical |",
          "|---|---|---|---|---|---|---|---|"]
    for r in jr:
        L.append(f"| {r['file']} | {r['n_num']} | {r['n_other']} | {fmt(r['max_abs'])} | {fmt(r['max_rel'])} | {len(r['over'])} | {len(r['problems'])} | "
                 f"{'yes' if r['sha_orig'] == r['sha_new'] else 'no'} |")
    L += ["", "SHA-256 (original / re-run):", ""]
    for r in jr:
        L.append(f"- {r['file']}: `{r['sha_orig']}` / `{r['sha_new']}`")
    for r in jr:
        if r["over"] or r["problems"]:
            L += ["", f"### Differences in {r['file']}", ""]
            L += [f"- `{p}`: original {o:.12g}, re-run {n:.12g}, abs {fmt(ad)}, rel {fmt(rd)}" for p, o, n, ad, rd in r["over"]]
            L += [f"- `{p}`: {msg}" for p, msg in r["problems"]]
    L += ["", "## CSV outputs", "", "| file | rows (orig / re-run) | same columns | max abs diff (numeric columns) | non-numeric columns equal | bytes identical |", "|---|---|---|---|---|---|"]
    for r in cr:
        L.append(f"| {r['file']} | {r['rows'][0]} / {r['rows'][1]} | {'yes' if r['cols'] else 'no'} | {fmt(r['max_abs'])} | "
                 f"{'yes' if r['text_equal'] else 'no'} | {'yes' if r['sha_orig'] == r['sha_new'] else 'no'} |")
    cov_o, cov_n = ORIG / "coverage.md", new_dir / "coverage.md"
    so, sn = sections(cov_o), sections(cov_n)
    same = {h: so[h] == sn.get(h) for h in so}
    L += ["", "## coverage.md (T4 and T5 rewrite their sections in the copy)", "",
          f"- original `{sha(cov_o)}`", f"- re-run   `{sha(cov_n)}`", f"- bytes identical: {'yes' if sha(cov_o) == sha(cov_n) else 'no'}",
          f"- sections: {len(so)} original / {len(sn)} re-run; sections with identical text: {sum(same.values())} of {len(so)}"
          + ("" if all(same.values()) else "; differing: " + ", ".join(h for h, v in same.items() if not v)),
          f"- section order identical: {'yes' if list(so) == list(sn) else 'no (original: ' + ', '.join(h.split()[1] for h in so) + '; re-run: ' + ', '.join(h.split()[1] for h in sn) + ')'}", ""]
    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    for r in jr:
        print(f"{r['file']}: num={r['n_num']} other={r['n_other']} max_abs={fmt(r['max_abs'])} max_rel={fmt(r['max_rel'])} over_tol={len(r['over'])} "
              f"problems={len(r['problems'])} bytes_identical={r['sha_orig'] == r['sha_new']}")
    for r in cr:
        print(f"{r['file']}: rows={r['rows']} max_abs={fmt(r['max_abs'])} text_equal={r['text_equal']} bytes_identical={r['sha_orig'] == r['sha_new']}")
    print("coverage.md identical:", sha(cov_o) == sha(cov_n))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
