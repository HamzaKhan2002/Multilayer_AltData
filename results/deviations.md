# Deviations and implementation notes

Entries are written before the affected statistic is computed unless stated otherwise. The pre-registration (`prereg/tests_v1.json`, SHA-256 `66bec92f8383607c1777e3d69c23aa8abd25efa1f90bead18fc9f22615f1cbbe`) is unchanged.

## 2026-10-23 11:00 (+02:00), before the first run of T1 (11:02) and T2 (11:03)

No deviation from the pre-registration. Implementation choices that the pre-registration leaves open, fixed now:

1. **Non-positive prices.** WTI contract 1 settled at -37.63 on 2020-04-20, so a log return is undefined. `r` is missing on 2020-04-20 and on 2020-04-21 (the second return uses the negative price); both days are excluded from every statistic. 2020-04-22 is a roll day (the May contract expired on 2020-04-21 under the pre-registered rule) and uses ln(C1_t / C2_{t-1}).
2. **Weekly changes.** D_t = I_t - I_{t-1} only when the two Fridays are 7 days apart. The coverage audit finds no irregular spacing inside 2010-2026 for US crude stocks or L48 gas storage.
3. **Release weeks.** Weeks whose release day is not a trading day are dropped (coverage audit: WTI 1 week, NG 4 weeks in the period).
4. **NG sample.** The coverage audit finds no gap longer than 5 business days in RNGC1 or RNGC2 inside the period, so the NG sample starts on the period start, 2010-01-04.
5. **Bootstrap.** Every ratio is bootstrapped with a fresh `numpy.random.default_rng(20261023)`: 5,000 draws of calendar weeks (Monday to Sunday) with replacement, drawn in chunks of 500, percentile 95% interval, one-sided p = (number of draws <= 1 + 1) / (draws + 1).
6. **Cross placebos (T1, no prediction).** The denominator of the ratio is every trading day that is not a release day of the calendar being evaluated.
7. **T2 history.** "First forecast after 260 weeks of history" is implemented as at least 260 training weeks with complete regressors (D_t, D_{t-1}, D_{t-2}). z_t divides by the standard deviation of the surprises over the weeks of the test sample that have a release-day return.
8. **Holm adjustment.** Computed after T1 and T2 have both run, over the four primary tests, with the bootstrap p for T1 and the normal one-sided p of the Newey-West t for T2.
9. **Roll-rule integrity check.** Offset 0 has the highest share for both markets (WTI 0.56, NG 0.62; other offsets 0.33-0.48), so the pre-registered expiry rules are kept.

## 2026-10-23 11:05 (+02:00), after the T1 and T2 runs (recorded afterwards)

- **Freeze time.** The `frozen_at` field inside the pre-registration reads 10:40; the file-system timestamps of `prereg/tests_v1.json` are created 10:33:49 and last written 10:34:02. The SHA-256 was computed after that. No statistic was computed before 11:00, so the order pre-registration, coverage audit, T1, T2 holds either way. The file is not edited, to keep its hash.
- **Single runs.** T1 ran once (11:02:12, 2.3 s) and T2 ran once (11:02:58, 1.8 s). Result files: `results/T1.json` SHA-256 `35b8d1ec24d5c93653c51a7237f6a00a5e5b4cce21e8326728e9183f36d79e7c`, `results/T2.json` SHA-256 `e80b219e4be025c8d7397c9c9f2ab322f28cc669c3b75b27eb20ad0bd8aa4895`.
- **Figure code moved.** The first figure versions (labels overlapped) were drawn inside the T1 and T2 scripts. After the runs, the figure code was moved to `scripts/fig_tests.py`, which reads the result files; the computation in the two scripts is unchanged and was not re-run.

## 2026-10-23 (before the first run of T4 and T5)

Only three-day probes of the ENTSO-E and AGSI+ APIs have been made (shape and units; no statistic). Implementation choices that the pre-registration leaves open, fixed now:

1. **T4 daily series.** Prices, the day-ahead wind and solar forecast (sum of Solar, Wind Onshore and Wind Offshore at each time stamp, all three required) and the day-ahead load forecast are averaged over each Europe/Berlin delivery day, using the resolution as published (hourly, or 15 minutes where published). S_d is the ratio of the daily mean of the wind and solar forecast to the daily mean of the load forecast.
2. **T4 and T5 completeness.** A day enters a regression only if each series it uses covers at least 90% of the hours of that local day (an hour is covered if it holds at least one observation). Days that fail are dropped and counted in the coverage section.
3. **T4 regression.** OLS with month-year and weekday dummies (one dropped each) and the slope on S_d; Newey-West (Bartlett) with 7 lags. The slope is reported per 1.00 of S_d and per +10 percentage points. By-year slopes use month and weekday dummies within the year.
4. **T5.** Gas year = 1 October to 30 September; the sample is gas days from 1 November to 31 March of gas years starting 2014-10-01 to 2025-10-01 that fall inside 2015-01-01..2025-12-31. T_d is the equal-weight mean of the six city daily means (Open-Meteo, Europe/Berlin day); a day with a missing city value is dropped. NW_d = withdrawal - injection from the AGSI+ EU aggregate (type=eu, GWh/d).
5. **Coverage reporting.** The T4 and T5 integrity checks are appended to `results/coverage.md` by the test scripts themselves, in the same run as the statistic.

## 2026-10-23 (before the first run of T3; T1 and T2 results are known, no cloud-cover statistic has been computed)

1. **Cloud window.** "16:00-19:00 UTC" is read as the hourly values stamped 16, 17, 18 and 19 UTC (four per day). C_t is the mean over the 7 calendar days ending the day before the WTI release (28 values).
2. **Terciles.** Cut points are the 1/3 and 2/3 quantiles of C_t over the release weeks of the sample that have all inputs; Cloudy_t = 1 if C_t is at or above the upper cut. The top-versus-bottom ratio excludes the middle tercile.
3. **RV20.** Square root of the mean squared front-month return over the 20 trading days that end the day before the release (days without a log return are skipped); a release with fewer than 20 such days is dropped.
4. **Statistic.** OLS of the absolute release-day return on a constant, Cloudy_t and ln(RV20), Newey-West with 4 lags; one-sided t on Cloudy_t. The ratio uses the week-block bootstrap of `stats.week_block_ratio` (one release day per week).

## 2026-10-23 12:55 (+02:00), crash re-runs of T4 and T5 (no statistic had been computed in the crashed runs)

- **T5** first run (12:49) stopped on the AGSI+ download: the first response had no `data` key, so the table was empty. A later page-by-page check returned all 4,018 gas days (14 pages). `agsi.eu_storage` now raises a clear error if a page has no data, and T5 was re-run (12:52). Same code and rules.
- **T4** first run (12:36) downloaded all years, then stopped in `daily()` with `AmbiguousTimeError` at the autumn clock change (2019-10-27 02:00 local): flooring local time stamps to the hour is ambiguous. The hour key is now computed in UTC, which does not change any definition (hours covered per local day, daily means). Downloads were parallelised (`scripts/prefetch_entsoe.py`, atomic writes) to save time; the data are the same.
