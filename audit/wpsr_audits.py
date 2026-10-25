"""Audits of the EIA WPSR archive: rule calendar vs archive release dates, first-release vs latest vintages, release times.

Usage: python audit/wpsr_audits.py
Inputs: audit/eia_release_registry.csv and results/v2/eia_first_release.csv (from scripts/eia_wpsr_archive.py), cached EIA xls in data/eia/,
the schedule page (downloaded once into data/eia_wpsr_archive/, 0.5 s spacing like the archive scraper).
Outputs: audit/calendar_audit.csv|md, audit/vintage_audit.csv|md, audit/eia_release_times.csv. No return or price statistic is computed.
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata import eia  # noqa: E402
from altdata.calendars import release_date  # noqa: E402
from eia_wpsr_archive import CACHE, SITE, Fetcher  # noqa: E402

AUDIT = ROOT / "audit"
PERIODS = [("2010-01-01..2024-04-05", "2010-01-01", "2024-04-05"), ("2024-04-06..2026-10-24", "2024-04-06", "2026-10-24")]
T1_SAMPLE = (pd.Timestamp("2010-01-04"), pd.Timestamp("2024-04-05"))
TOL = 0.5
SERIES = {"cushing": ("pet", "W_EPC0_SAX_YCUOK_MBBL"), "us_comm_crude": ("pet", "WCESTUS1"), "gasoline": None, "distillate": None}
LONG_DATE = re.compile(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$")


def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def day(x) -> str:
    return "" if pd.isna(x) else pd.Timestamp(x).strftime("%Y-%m-%d %a")


def calendar_audit(reg: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    arch = reg.drop_duplicates("week_ending_friday").set_index("week_ending_friday")
    first_week = reg["week_ending_friday"].min()
    rows = []
    for label, lo, hi in PERIODS:
        for F in pd.date_range(lo, hi, freq="W-FRI"):
            rule, shifted = release_date(F, "wednesday")
            a = arch["release_date"].get(F, pd.NaT)
            if pd.isna(a):
                status = "no_archive_release"
                note = f"before the first archived week ending {first_week.date()}" if F < first_week else "release not yet published on 2026-10-24"
            else:
                status = "match" if a == rule else "mismatch"
                note = arch["note"].get(F, "")
                note = "" if pd.isna(note) else note
            rows.append({"period": label, "week_ending_friday": F, "rule_release_date": rule, "rule_holiday_shift": shifted, "archive_release_date": a,
                         "diff_days_archive_minus_rule": (a - rule).days if pd.notna(a) else np.nan, "status": status, "note": note})
    cal = pd.DataFrame(rows)
    L = ["# Calendar audit: rule calendar of T1/T2 vs EIA archive release dates", "",
         "Rule: `altdata.calendars.release_date(F, \"wednesday\")` for every week-ending Friday F (F+5, or F+6 if a US federal holiday falls between F+3 and F+5). "
         "Archive date: release date of the archived report whose data week ends on F (`audit/eia_release_registry.csv`). Full table: `audit/calendar_audit.csv`.", "",
         f"The archive holds {len(reg)} releases, the first for the week ending {reg['week_ending_friday'].min().date()} (released {reg['release_date'].min().date()}); "
         f"the last for the week ending {reg['week_ending_friday'].max().date()} (released {reg['release_date'].max().date()}).", "",
         "| period | weeks (Fridays) | with archive release | rule == archive | rule != archive | no archive release |", "|---|---|---|---|---|---|"]
    for label, g in cal.groupby("period", sort=False):
        L.append(f"| {label} | {len(g)} | {(g['status'] != 'no_archive_release').sum()} | {(g['status'] == 'match').sum()} | {(g['status'] == 'mismatch').sum()} | "
                 f"{(g['status'] == 'no_archive_release').sum()} |")
    in_sample = cal[(cal["rule_release_date"] >= T1_SAMPLE[0]) & (cal["rule_release_date"] <= T1_SAMPLE[1])]
    L += ["", f"Weeks whose rule release date lies in the T1/T2 sample ({T1_SAMPLE[0].date()}..{T1_SAMPLE[1].date()}): {len(in_sample)}; with archive release: "
          f"{(in_sample['status'] != 'no_archive_release').sum()}; rule != archive: {(in_sample['status'] == 'mismatch').sum()}.", ""]
    have = cal[cal["status"] != "no_archive_release"].copy()
    have["archive_weekday"] = have["archive_release_date"].dt.day_name()
    have["rule_applied_holiday_shift"] = have["rule_holiday_shift"]
    ct = pd.crosstab(have["rule_applied_holiday_shift"], have["archive_weekday"]).reset_index()
    L += ["Archive release weekday by whether the rule applied the holiday shift (weeks with an archive release):", "", md(ct), ""]
    L += ["## Weeks without an archive release", ""]
    for label, g in cal[cal["status"] == "no_archive_release"].groupby("period", sort=False):
        L.append(f"- {label}: {len(g)} weeks, {g['week_ending_friday'].min().date()} to {g['week_ending_friday'].max().date()} ({g['note'].iloc[0]})")
    L += ["", "## Mismatches (rule date != archive date)", ""]
    mm = cal[cal["status"] == "mismatch"]
    if len(mm):
        t = pd.DataFrame({"period": mm["period"], "week ending (Friday)": mm["week_ending_friday"].map(day), "rule date": mm["rule_release_date"].map(day),
                          "archive date": mm["archive_release_date"].map(day), "archive - rule (days)": mm["diff_days_archive_minus_rule"].astype(int),
                          "rule applied holiday shift": mm["rule_holiday_shift"], "note": mm["note"]})
        L.append(md(t))
    else:
        L.append("none")
    return cal, L + [""]


def runs(d: pd.DataFrame) -> pd.DataFrame:
    g = d.dropna(subset=["diff_first_minus_latest_kbbl"]).reset_index(drop=True)
    key = (g["diff_first_minus_latest_kbbl"] != g["diff_first_minus_latest_kbbl"].shift()).cumsum()
    out = g.groupby(key).agg(first_week=("week_ending", "min"), last_week=("week_ending", "max"), weeks=("week_ending", "size"), difference=("diff_first_minus_latest_kbbl", "first"))
    out["first_week"], out["last_week"] = out["first_week"].dt.strftime("%Y-%m-%d"), out["last_week"].dt.strftime("%Y-%m-%d")
    return out.reset_index(drop=True)


def vintage_audit(fr: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    fr = fr.sort_values("week_ending").drop_duplicates("week_ending").set_index("week_ending")
    rows, L = [], []
    stats, by_year, run_tbl = [], {}, {}
    for name, latest_id in SERIES.items():
        cur, prior = fr[f"{name}_kbbl"].astype(float), fr[f"{name}_prior_kbbl"].astype(float)
        latest = eia.load(latest_id[0], latest_id[1], "w").reindex(fr.index) if latest_id else pd.Series(np.nan, index=fr.index)
        nxt_prior = pd.Series(prior.to_numpy(), index=prior.index - pd.Timedelta(days=7)).reindex(fr.index)
        nxt_date = pd.Series(fr["release_date"].to_numpy(), index=fr.index - pd.Timedelta(days=7)).reindex(fr.index)
        d = pd.DataFrame({"series": name, "week_ending": fr.index, "release_date": fr["release_date"].to_numpy(), "first_release_kbbl": cur.to_numpy(),
                          "latest_vintage_kbbl": latest.to_numpy(), "next_release_date": nxt_date.to_numpy(), "prior_in_next_release_kbbl": nxt_prior.to_numpy()})
        d["diff_first_minus_latest_kbbl"] = d["first_release_kbbl"] - d["latest_vintage_kbbl"]
        d["rev_next_minus_first_kbbl"] = d["prior_in_next_release_kbbl"] - d["first_release_kbbl"]
        rows.append(d)
        a, r = d["diff_first_minus_latest_kbbl"].dropna(), d["rev_next_minus_first_kbbl"].dropna()
        over = d.loc[a.index[a.abs() > TOL], "week_ending"]
        if latest_id:
            run_tbl[name] = runs(d)
            g = d.dropna(subset=["diff_first_minus_latest_kbbl"])
            by_year[name] = (g.assign(year=g["week_ending"].dt.year, over=g["diff_first_minus_latest_kbbl"].abs() > TOL).groupby("year")
                              .agg(weeks=("over", "size"), weeks_over_0_5=("over", "sum"), min_diff=("diff_first_minus_latest_kbbl", "min"),
                                   max_diff=("diff_first_minus_latest_kbbl", "max")).reset_index())
        stats.append({"series": name, "weeks first-vs-latest": len(a), "weeks abs diff > 0.5": int((a.abs() > TOL).sum()), "max abs diff (kbbl)": a.abs().max() if len(a) else np.nan,
                      "first week over": over.min().date() if len(over) else "", "last week over": over.max().date() if len(over) else "",
                      "release pairs (prior vs first)": len(r), "pairs abs rev > 0.5": int((r.abs() > TOL).sum()), "max abs rev (kbbl)": r.abs().max() if len(r) else np.nan})
    v = pd.concat(rows, ignore_index=True)
    v["abs_diff_gt_0_5"] = v["diff_first_minus_latest_kbbl"].abs() > TOL
    v["abs_rev_gt_0_5"] = v["rev_next_minus_first_kbbl"].abs() > TOL
    L = ["# Vintage audit: first release vs latest vintage (thousand barrels)", "",
         f"First release = value printed for the current week in csv/table4.csv of the release that first covers that week ({len(fr)} releases, week ending {fr.index.min().date()} to "
         f"{fr.index.max().date()}). Table 4 prints million barrels with three decimals, so values are exact to 1 kbbl. Latest vintage = cached EIA history files "
         f"`W_EPC0_SAX_YCUOK_MBBLw.xls` (Cushing) and `WCESTUS1w.xls` (US commercial crude, excluding SPR), loaded with `altdata.eia.load`; gasoline and distillate have no cached "
         f"latest series, so only the release-to-release check applies. Release-to-release check = `prior` value printed in release t+1 minus the first-release value of release t. "
         f"Threshold: |difference| > {TOL} kbbl. Full table: `audit/vintage_audit.csv`.", "", md(pd.DataFrame(stats).round(3)), ""]
    for name, tbl in by_year.items():
        L += [f"## {name}: first release minus latest vintage by year (kbbl)", "", md(tbl), ""]
    for name, tbl in run_tbl.items():
        L += [f"## {name}: runs of consecutive weeks with the same first-minus-latest difference", "",
              md(tbl) if len(tbl) <= 40 else f"{len(tbl)} runs (the difference changes from week to week); see the CSV.", ""]
    for label, col, flag, prefix in (("First release vs latest vintage", "diff_first_minus_latest_kbbl", "abs_diff_gt_0_5", "latest_vintage_kbbl"),
                                     ("Release t+1 `prior` vs release t first value", "rev_next_minus_first_kbbl", "abs_rev_gt_0_5", "prior_in_next_release_kbbl")):
        L += [f"## {label}: weeks with |difference| > {TOL} kbbl", ""]
        for name in SERIES:
            if flag == "abs_diff_gt_0_5" and SERIES[name] is None:
                L += [f"- {name}: no cached latest series", ""]
                continue
            g = v[(v["series"] == name) & v[flag]].copy()
            if not len(g):
                L += [f"- {name}: none", ""]
                continue
            g = g.reindex(g[col].abs().sort_values(ascending=False).index)
            shown = g.head(60)
            t = pd.DataFrame({"week ending": shown["week_ending"].dt.strftime("%Y-%m-%d"), "release": pd.to_datetime(shown["release_date"]).dt.strftime("%Y-%m-%d"),
                              "first release": shown["first_release_kbbl"].astype("Int64"), prefix: shown[prefix].round(0).astype("Int64"), "difference": shown[col].round(0).astype("Int64")})
            L += [f"### {name}: {len(g)} weeks" + (f" (60 largest shown, all in the CSV)" if len(g) > 60 else ""), "", md(t), ""]
    return v, L


def schedule_table(fetcher: Fetcher, reg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = fetcher.get(SITE + "schedule.php", CACHE / "schedule.php.html")
    if raw is None:
        raise SystemExit("schedule page not available")
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", raw.decode("utf-8", "replace"), flags=re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
        if len(cells) == 5 and LONG_DATE.match(cells[0]):
            rows.append({"week_ending": pd.to_datetime(cells[0], format="%B %d, %Y"), "release_date": pd.to_datetime(cells[1], format="%B %d, %Y"), "weekday": cells[2],
                         "release_time_et": cells[3], "holiday": cells[4], "source": "schedule.php"})
    sched = pd.DataFrame(rows)
    arch = reg.drop_duplicates("week_ending_friday").set_index("week_ending_friday")
    sched["archive_release_date"] = sched["week_ending"].map(arch["release_date"])
    sched["archive_matches_schedule"] = np.where(sched["archive_release_date"].isna(), "", (sched["archive_release_date"] == sched["release_date"]).astype(str))
    other = reg[(reg["weekday"] != "Wednesday") & ~reg["week_ending_friday"].isin(sched["week_ending"])]
    old = pd.DataFrame({"week_ending": other["week_ending_friday"], "release_date": other["release_date"], "weekday": other["weekday"], "release_time_et": "",
                        "holiday": "", "source": "archive (weekday only; time not published)", "archive_release_date": other["release_date"], "archive_matches_schedule": ""})
    return sched, pd.concat([sched, old], ignore_index=True).sort_values("release_date")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    reg = pd.read_csv(AUDIT / "eia_release_registry.csv", parse_dates=["release_date", "week_ending_friday"])
    fr = pd.read_csv(ROOT / "results" / "v2" / "eia_first_release.csv", parse_dates=["release_date", "week_ending"])

    cal, cal_md = calendar_audit(reg)
    sched, times = schedule_table(Fetcher(), reg)
    cal_md += ["## Release times", "",
               "The schedule page (`schedule.php`) states a standard release at 10:30 a.m. eastern time on Wednesday and lists exceptions only for the data weeks ending "
               f"{sched['week_ending'].min().date()} to {sched['week_ending'].max().date()} ({len(sched)} rows; no links to earlier years). Archived report pages state the release date "
               "but no time. Release times before 2025 are therefore not available; for earlier years `audit/eia_release_times.csv` lists the non-Wednesday releases (weekday known, time blank).", "",
               md(sched.assign(week_ending=sched["week_ending"].dt.strftime("%Y-%m-%d"), release_date=sched["release_date"].dt.strftime("%Y-%m-%d"),
                               archive_release_date=sched["archive_release_date"].dt.strftime("%Y-%m-%d").fillna(""))
                  [["week_ending", "release_date", "weekday", "release_time_et", "holiday", "archive_release_date", "archive_matches_schedule"]]), ""]
    cal.to_csv(AUDIT / "calendar_audit.csv", index=False, date_format="%Y-%m-%d")
    (AUDIT / "calendar_audit.md").write_text("\n".join(cal_md), encoding="utf-8", newline="\n")
    times.to_csv(AUDIT / "eia_release_times.csv", index=False, date_format="%Y-%m-%d")

    vint, vint_md = vintage_audit(fr)
    vint.to_csv(AUDIT / "vintage_audit.csv", index=False, date_format="%Y-%m-%d")
    (AUDIT / "vintage_audit.md").write_text("\n".join(vint_md), encoding="utf-8", newline="\n")

    for label, g in cal.groupby("period", sort=False):
        print(f"{label}: weeks={len(g)} archive={(g['status'] != 'no_archive_release').sum()} match={(g['status'] == 'match').sum()} mismatch={(g['status'] == 'mismatch').sum()} "
              f"no_archive={(g['status'] == 'no_archive_release').sum()}")
    print("schedule rows:", len(sched), "| times csv rows:", len(times), "| schedule vs archive:", sched["archive_matches_schedule"].value_counts().to_dict())
    print(vint_md[4])
    print("wrote audit/calendar_audit.csv|md, vintage_audit.csv|md, eia_release_times.csv")


if __name__ == "__main__":
    main()
