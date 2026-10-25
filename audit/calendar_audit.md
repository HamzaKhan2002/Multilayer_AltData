# Calendar audit: rule calendar of T1/T2 vs EIA archive release dates

Rule: `altdata.calendars.release_date(F, "wednesday")` for every week-ending Friday F (F+5, or F+6 if a US federal holiday falls between F+3 and F+5). Archive date: release date of the archived report whose data week ends on F (`audit/eia_release_registry.csv`). Full table: `audit/calendar_audit.csv`.

The archive holds 796 releases, the first for the week ending 2011-07-22 (released 2011-07-27); the last for the week ending 2026-10-16 (released 2026-10-21).

| period | weeks (Fridays) | with archive release | rule == archive | rule != archive | no archive release |
|---|---|---|---|---|---|
| 2010-01-01..2024-04-05 | 745 | 661 | 647 | 14 | 84 |
| 2024-04-06..2026-10-24 | 133 | 131 | 128 | 3 | 2 |

Weeks whose rule release date lies in the T1/T2 sample (2010-01-04..2024-04-05): 744; with archive release: 660; rule != archive: 14.

Archive release weekday by whether the rule applied the holiday shift (weeks with an archive release):

| rule_applied_holiday_shift   |   Friday |   Monday |   Sunday |   Thursday |   Wednesday |
|:-----------------------------|---------:|---------:|---------:|-----------:|------------:|
| False                        |        0 |        1 |        1 |          2 |         673 |
| True                         |       10 |        1 |        0 |        103 |           1 |

## Weeks without an archive release

- 2010-01-01..2024-04-05: 84 weeks, 2010-01-01 to 2017-02-17 (before the first archived week ending 2011-07-22)
- 2024-04-06..2026-10-24: 2 weeks, 2026-10-02 to 2026-10-23 (release not yet published on 2026-10-24)

## Mismatches (rule date != archive date)

| period                 | week ending (Friday)   | rule date      | archive date   |   archive - rule (days) | rule applied holiday shift   | note                                             |
|:-----------------------|:-----------------------|:---------------|:---------------|------------------------:|:-----------------------------|:-------------------------------------------------|
| 2010-01-01..2024-04-05 | 2012-10-26 Fri         | 2012-10-31 Wed | 2012-11-01 Thu |                       1 | False                        |                                                  |
| 2010-01-01..2024-04-05 | 2012-12-21 Fri         | 2012-12-27 Thu | 2012-12-28 Fri |                       1 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2012-12-28 Fri         | 2013-01-03 Thu | 2013-01-04 Fri |                       1 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2013-10-11 Fri         | 2013-10-17 Thu | 2013-10-21 Mon |                       4 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2013-12-20 Fri         | 2013-12-26 Thu | 2013-12-27 Fri |                       1 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2013-12-27 Fri         | 2014-01-02 Thu | 2014-01-03 Fri |                       1 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2018-11-30 Fri         | 2018-12-05 Wed | 2018-12-06 Thu |                       1 | False                        |                                                  |
| 2010-01-01..2024-04-05 | 2018-12-21 Fri         | 2018-12-27 Thu | 2018-12-28 Fri |                       1 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2018-12-28 Fri         | 2019-01-03 Thu | 2019-01-04 Fri |                       1 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2019-12-20 Fri         | 2019-12-26 Thu | 2019-12-27 Fri |                       1 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2019-12-27 Fri         | 2020-01-02 Thu | 2020-01-03 Fri |                       1 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2021-01-15 Fri         | 2021-01-21 Thu | 2021-01-22 Fri |                       1 | True                         |                                                  |
| 2010-01-01..2024-04-05 | 2022-06-17 Fri         | 2022-06-23 Thu | 2022-06-29 Wed |                       6 | True                         | data-only folder, released with a later report   |
| 2010-01-01..2024-04-05 | 2023-11-03 Fri         | 2023-11-08 Wed | 2023-11-15 Wed |                       7 | False                        | data-only folder, released with a later report   |
| 2024-04-06..2026-10-24 | 2024-12-20 Fri         | 2024-12-26 Thu | 2024-12-27 Fri |                       1 | True                         |                                                  |
| 2024-04-06..2026-10-24 | 2025-12-19 Fri         | 2025-12-24 Wed | 2025-12-29 Mon |                       5 | False                        |                                                  |
| 2024-04-06..2026-10-24 | 2026-06-19 Fri         | 2026-06-24 Wed | 2026-06-14 Sun |                     -10 | False                        | page release date 2026-06-14 differs from folder |

## Release times

The schedule page (`schedule.php`) states a standard release at 10:30 a.m. eastern time on Wednesday and lists exceptions only for the data weeks ending 2024-12-27 to 2026-11-06 (14 rows; no links to earlier years). Archived report pages state the release date but no time. Release times before 2025 are therefore not available; for earlier years `audit/eia_release_times.csv` lists the non-Wednesday releases (weekday known, time blank).

| week_ending   | release_date   | weekday   | release_time_et   | holiday                                   | archive_release_date   | archive_matches_schedule   |
|:--------------|:---------------|:----------|:------------------|:------------------------------------------|:-----------------------|:---------------------------|
| 2024-12-27    | 2025-01-02     | Thursday  | 11:00 a.m.        | New Year's Day                            | 2025-01-02             | True                       |
| 2025-01-17    | 2025-01-23     | Thursday  | 12:00 p.m.        | Martin Luther King Jr. Day / Inauguration | 2025-01-23             | True                       |
| 2025-02-14    | 2025-02-20     | Thursday  | 12:00 p.m.        | President's Day                           | 2025-02-20             | True                       |
| 2025-05-23    | 2025-05-29     | Thursday  | 12:00 p.m.        | Memorial Day                              | 2025-05-29             | True                       |
| 2025-08-29    | 2025-09-04     | Thursday  | 12:00 p.m.        | Labor Day                                 | 2025-09-04             | True                       |
| 2025-10-10    | 2025-10-16     | Thursday  | 12:00 p.m.        | Columbus Day                              | 2025-10-16             | True                       |
| 2025-11-07    | 2025-11-13     | Thursday  | 12:00 p.m.        | Veterans Day                              | 2025-11-13             | True                       |
| 2025-12-19    | 2025-12-29     | Monday    | 5:00 p.m.         | Christmas                                 | 2025-12-29             | True                       |
| 2026-01-16    | 2026-01-22     | Thursday  | 12:00 p.m.        | Martin Luther King Jr. Day                | 2026-01-22             | True                       |
| 2026-02-13    | 2026-02-19     | Thursday  | 12:00 p.m.        | President's Day                           | 2026-02-19             | True                       |
| 2026-05-22    | 2026-05-28     | Thursday  | 12:00 p.m.        | Memorial Day                              | 2026-05-28             | True                       |
| 2026-09-04    | 2026-09-10     | Thursday  | 12:00 p.m.        | Labor Day                                 | 2026-09-10             | True                       |
| 2026-10-09    | 2026-10-15     | Thursday  | 12:00 p.m.        | Columbus Day                              | 2026-10-15             | True                       |
| 2026-11-06    | 2026-11-12     | Thursday  | 12:00 p.m.        | Veterans Day                              |                        |                            |
