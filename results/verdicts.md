# Verdicts of the pre-registered tests

Pre-registration SHA-256: `66bec92f8383607c1777e3d69c23aa8abd25efa1f90bead18fc9f22615f1cbbe`. Each test was run once; see `trial_log.csv` and `deviations.md`.

| Test | Question | Result | Verdict | Holm-adjusted one-sided p |
|---|---|---|---|---|
| T1 WTI | Report days more volatile? | ratio 1.10, 95% interval 1.03 to 1.19, 743 report days | SUPPORTED | 0.017 |
| T1 NG | Report days more volatile? | ratio 1.09, 95% interval 1.01 to 1.18, 740 report days | SUPPORTED | 0.052 |
| T2 WTI | Surprise moves the price against its sign? | slope -17.0 bp per sd, Newey-West t -1.26, n 743 | NOT SUPPORTED | 0.209 |
| T2 NG | Surprise moves the price against its sign? | slope -8.9 bp per sd, Newey-West t -0.65, n 479 | NOT SUPPORTED | 0.258 |
| T3 | Cloudier weeks, larger release-day move? (exploratory) | b +0.0022, one-sided t 0.88, n 430 | INCONCLUSIVE AT DAILY RESOLUTION | not in the primary family |
| T4 | More forecast wind and solar, lower German day-ahead price? | -15.91 EUR/MWh per +10 pp, Newey-West t -16.4, n 2555 days | SUPPORTED | mechanism check |
| T5 | Colder days, larger net EU storage withdrawals? | +645 GWh/d per degree-day, Newey-West t 37.5, n 1664 days | SUPPORTED | mechanism check |
