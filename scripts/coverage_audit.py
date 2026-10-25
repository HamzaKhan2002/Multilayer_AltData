"""Coverage audit of every EIA series, run before any test statistic (prereg: common.coverage_audit_first).

Writes results/coverage.md and results/data_versions.json: rows by year, gaps longer than 5 business days, non-positive
prices, weekday check of the weekly series, release-calendar alignment, the pre-registered NG sample start, and an
integrity check of the contract-expiry rules. No return or inventory statistic is computed here.

Usage: python scripts/coverage_audit.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata import eia  # noqa: E402
from altdata.calendars import release_table, roll_diagnostic  # noqa: E402
from altdata.markets import MARKETS, PERIOD, business_day_gaps, ng_sample_start  # noqa: E402
from altdata.paths import RESULTS, assert_prereg_frozen, sha256_file  # noqa: E402
from altdata.runlog import RunLog, trial_log  # noqa: E402

SERIES = [
    ("WTI C1 (RCLC1d)", "pet", "RCLC1", "d"), ("WTI C2 (RCLC2d)", "pet", "RCLC2", "d"),
    ("NG C1 (RNGC1d)", "ng", "RNGC1", "d"), ("NG C2 (RNGC2d)", "ng", "RNGC2", "d"),
    ("US crude stocks (WCESTUS1w)", "pet", "WCESTUS1", "w"),
    ("Cushing stocks (W_EPC0_SAX_YCUOK_MBBLw)", "pet", "W_EPC0_SAX_YCUOK_MBBL", "w"),
    ("US gas storage L48 (NW2_EPG0_SWO_R48_BCFw)", "ng", "NW2_EPG0_SWO_R48_BCF", "w"),
]


def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False) if len(df) else "_none_"


def main() -> None:
    log = RunLog("coverage_audit")
    sha = assert_prereg_frozen()
    log("prereg hash", sha)
    raw, versions, parts = {}, {}, []
    for label, area, sid, freq in SERIES:
        s = eia.load(area, sid, freq, dropna=False)
        raw[sid + freq] = s
        p = eia.path(sid, freq)
        versions[p.name] = {"series": label, "sha256": sha256_file(p), "rows": int(len(s)), "missing_values": int(s.isna().sum()),
                            "first": str(s.index.min().date()), "last": str(s.dropna().index.max().date())}
        log(label, versions[p.name]["rows"], "rows", versions[p.name]["first"], "->", versions[p.name]["last"])
    (RESULTS / "data_versions.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")

    parts.append("# Coverage audit (run before any test statistic)\n")
    parts.append(f"Pre-registration hash: `{sha}`. Test period: {PERIOD[0].date()} to {PERIOD[1].date()}.\n")
    parts.append("## 1. Series and file versions\n")
    parts.append(md(pd.DataFrame([{"file": k, **v} for k, v in versions.items()])) + "\n")

    years = list(range(2008, 2027))
    table = pd.DataFrame({"year": years})
    for label, _, sid, freq in SERIES:
        s = raw[sid + freq].dropna()
        table[label.split(" (")[0]] = [int((s.index.year == y).sum()) for y in years]
    parts.append("## 2. Observations by year (non-missing values)\n")
    parts.append(md(table) + "\n")

    parts.append("## 3. Gaps longer than 5 business days (daily series, whole history)\n")
    for label, _, sid, freq in SERIES:
        if freq != "d":
            continue
        s = raw[sid + freq].dropna()
        gaps = business_day_gaps(s.index)
        gtab = pd.DataFrame([{"after": a.date(), "next_obs": b.date(), "missing_weekdays": m, "in_period": (b >= PERIOD[0]) and (a <= PERIOD[1])}
                             for a, b, m in gaps])
        parts.append(f"**{label}**: {len(gaps)} gap(s)\n\n{md(gtab)}\n")
        neg = s[s <= 0]
        parts.append(f"Non-positive prices in {label}: {len(neg)} ({', '.join(str(d.date()) + '=' + str(v) for d, v in neg.items()) or 'none'})\n")

    parts.append("## 4. Weekly series: weekday and spacing\n")
    for label, _, sid, freq in SERIES:
        if freq != "w":
            continue
        s = raw[sid + freq].dropna()
        fri = float((s.index.dayofweek == 4).mean())
        step = pd.Series(s.index[1:] - s.index[:-1])
        off = step[step != pd.Timedelta(days=7)]
        parts.append(f"- **{label}**: {len(s)} weeks, {fri:.1%} dated on a Friday, {len(off)} spacing(s) different from 7 days"
                     f"{' (' + ', '.join(str(x.days) + 'd' for x in off.head(8)) + ')' if len(off) else ''}\n")

    parts.append("\n## 5. Release-calendar alignment (rules from the pre-registration)\n")
    for name, cfg in MARKETS.items():
        c1 = raw[cfg["c1"] + "d"].dropna()
        stocks = raw[cfg["stock"] + "w"].dropna()
        rt = release_table(stocks.index, cfg["release"], c1.index)
        rt = rt[(rt["release"] >= PERIOD[0]) & (rt["release"] <= PERIOD[1])]
        rt["weekday"] = rt["release"].dt.day_name()
        by_year = rt.groupby(rt["release"].dt.year).agg(weeks=("release", "size"), shifted_by_holiday=("shifted", "sum"),
                                                          not_a_trading_day=("is_trading_day", lambda x: int((~x).sum()))).reset_index()
        parts.append(f"**{name}**: {len(rt)} release weeks in the period; weekdays: "
                     f"{dict(rt['weekday'].value_counts())}\n\n{md(by_year.rename(columns={'release': 'year'}))}\n")

    parts.append("## 6. Pre-registered NG sample start\n")
    ng = MARKETS["NG"]
    start = ng_sample_start(raw[ng["c1"] + "d"], raw[ng["c2"] + "d"])
    parts.append(f"Rule: if RNGC1 or RNGC2 has a gap longer than 5 business days inside the period, the sample starts on the first trading "
                 f"day after the last such gap. **NG sample start: {start.date()}.**\n")
    parts.append("WTI has no sample rule in the pre-registration; its sample starts on the period start unless the gap tables above show a gap inside the period.\n")
    log("NG sample start", start.date())

    parts.append("## 7. Integrity check of the contract-expiry rules (no return statistic)\n")
    parts.append("Share of roll days, by offset from the rule's day, where C1 today is closer to yesterday's C2 than to yesterday's C1 "
                 "(2009-12-01 to 2024-04-05). Offset 0 should dominate.\n")
    for name, cfg in MARKETS.items():
        c1 = raw[cfg["c1"] + "d"].dropna()
        c2 = raw[cfg["c2"] + "d"].dropna()
        sl = slice(pd.Timestamp("2009-12-01"), PERIOD[1])
        diag = roll_diagnostic(c1.loc[sl], c2.loc[sl], cfg["rule"])
        parts.append(f"- **{name}** ({cfg['rule']} rule): " + ", ".join(f"offset {o:+d}: {v}" for o, v in diag.items()) + "\n")
        log(name, "roll diagnostic", diag)

    (RESULTS / "coverage.md").write_text("\n".join(parts), encoding="utf-8")
    secs = log.close()
    trial_log("COVERAGE", "scripts/coverage_audit.py", sha, "n/a", secs, "no statistic computed")


if __name__ == "__main__":
    main()
