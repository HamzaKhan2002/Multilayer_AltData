# Coverage audit (run before any test statistic)

Pre-registration hash: `66bec92f8383607c1777e3d69c23aa8abd25efa1f90bead18fc9f22615f1cbbe`. Test period: 2010-01-04 to 2024-04-05.

## 1. Series and file versions

| file                       | series                                     | sha256                                                           |   rows |   missing_values | first      | last       |
|:---------------------------|:-------------------------------------------|:-----------------------------------------------------------------|-------:|-----------------:|:-----------|:-----------|
| RCLC1d.xls                 | WTI C1 (RCLC1d)                            | 85364c1f20f27b2b56cb5c9af4819f5cd80a297bac2800e9be317a918aa45f38 |  10183 |                0 | 1983-04-04 | 2024-04-05 |
| RCLC2d.xls                 | WTI C2 (RCLC2d)                            | d9cb3e20b9ff4878961b1cdbe64052dcbb6b24f8574a0425b6247bbb555afbc8 |   9594 |                0 | 1985-01-02 | 2024-04-05 |
| RNGC1d.xls                 | NG C1 (RNGC1d)                             | 9d9c003e4220e448978e76ffe6aaed438a7732b16638eb33193c0b52902b184c |   7496 |                0 | 1994-01-13 | 2024-04-05 |
| RNGC2d.xls                 | NG C2 (RNGC2d)                             | 35b4fd8cd144d7ebfb2270fb141848be9a31bc47ed20f637ef93cb044b9bb180 |   7500 |                0 | 1994-01-12 | 2024-04-05 |
| WCESTUS1w.xls              | US crude stocks (WCESTUS1w)                | 1d558024381f37816f256db83a37cbf56078d9894edda2dcb20bbf455f49bfd5 |   2299 |                0 | 1982-08-20 | 2026-10-16 |
| W_EPC0_SAX_YCUOK_MBBLw.xls | Cushing stocks (W_EPC0_SAX_YCUOK_MBBLw)    | ec4ed594fb58d743797558941f4ed797fdcfcae341faa60c916b3b963d8a3abc |   1092 |                0 | 2004-04-16 | 2026-10-16 |
| NW2_EPG0_SWO_R48_BCFw.xls  | US gas storage L48 (NW2_EPG0_SWO_R48_BCFw) | b17ad48542d5f3128c1c5611090a70bcd292c3e3b2be975d70a34f1fb4ddb698 |    876 |                0 | 2010-01-01 | 2026-10-09 |

## 2. Observations by year (non-missing values)

|   year |   WTI C1 |   WTI C2 |   NG C1 |   NG C2 |   US crude stocks |   Cushing stocks |   US gas storage L48 |
|-------:|---------:|---------:|--------:|--------:|------------------:|-----------------:|---------------------:|
|   2008 |      253 |      253 |     253 |     253 |                52 |               52 |                    0 |
|   2009 |      252 |      252 |     251 |     252 |                52 |               52 |                    0 |
|   2010 |      252 |      252 |     252 |     251 |                53 |               53 |                   53 |
|   2011 |      250 |      252 |     248 |     251 |                52 |               52 |                   52 |
|   2012 |      252 |      252 |     252 |     252 |                52 |               52 |                   52 |
|   2013 |      252 |      252 |     252 |     252 |                52 |               52 |                   52 |
|   2014 |      252 |      252 |     252 |     252 |                52 |               52 |                   52 |
|   2015 |      250 |      250 |     249 |     249 |                52 |               52 |                   52 |
|   2016 |      248 |      248 |     247 |     247 |                53 |               53 |                   53 |
|   2017 |      248 |      248 |     248 |     248 |                52 |               52 |                   52 |
|   2018 |      261 |      261 |     261 |     261 |                52 |               52 |                   52 |
|   2019 |      253 |      253 |     260 |     260 |                52 |               52 |                   52 |
|   2020 |      252 |      252 |     252 |     252 |                52 |               52 |                   52 |
|   2021 |      251 |      251 |     250 |     250 |                53 |               53 |                   53 |
|   2022 |      251 |      251 |     251 |     251 |                52 |               52 |                   52 |
|   2023 |      250 |      250 |     250 |     250 |                52 |               52 |                   52 |
|   2024 |       66 |       66 |      66 |      66 |                52 |               52 |                   52 |
|   2025 |        0 |        0 |       0 |       0 |                52 |               52 |                   52 |
|   2026 |        0 |        0 |       0 |       0 |                42 |               42 |                   41 |

## 3. Gaps longer than 5 business days (daily series, whole history)

**WTI C1 (RCLC1d)**: 0 gap(s)

_none_

Non-positive prices in WTI C1 (RCLC1d): 1 (2020-04-20=-37.63)

**WTI C2 (RCLC2d)**: 0 gap(s)

_none_

Non-positive prices in WTI C2 (RCLC2d): 0 (none)

**NG C1 (RNGC1d)**: 0 gap(s)

_none_

Non-positive prices in NG C1 (RNGC1d): 0 (none)

**NG C2 (RNGC2d)**: 0 gap(s)

_none_

Non-positive prices in NG C2 (RNGC2d): 0 (none)

## 4. Weekly series: weekday and spacing

- **US crude stocks (WCESTUS1w)**: 2299 weeks, 100.0% dated on a Friday, 4 spacing(s) different from 7 days (28d, 14d, 14d, 14d)

- **Cushing stocks (W_EPC0_SAX_YCUOK_MBBLw)**: 1092 weeks, 100.0% dated on a Friday, 36 spacing(s) different from 7 days (21d, 14d, 14d, 14d, 28d, 14d, 42d, 21d)

- **US gas storage L48 (NW2_EPG0_SWO_R48_BCFw)**: 876 weeks, 100.0% dated on a Friday, 0 spacing(s) different from 7 days


## 5. Release-calendar alignment (rules from the pre-registration)

**WTI**: 744 release weeks in the period; weekdays: {'Wednesday': 636, 'Thursday': 108}

|   year |   weeks |   shifted_by_holiday |   not_a_trading_day |
|-------:|--------:|---------------------:|--------------------:|
|   2010 |      52 |                    6 |                   0 |
|   2011 |      52 |                    7 |                   0 |
|   2012 |      52 |                    9 |                   0 |
|   2013 |      52 |                    8 |                   0 |
|   2014 |      53 |                    7 |                   0 |
|   2015 |      52 |                    6 |                   0 |
|   2016 |      52 |                    7 |                   1 |
|   2017 |      52 |                    8 |                   0 |
|   2018 |      52 |                    9 |                   0 |
|   2019 |      52 |                    8 |                   0 |
|   2020 |      53 |                    7 |                   0 |
|   2021 |      52 |                    6 |                   0 |
|   2022 |      52 |                    8 |                   0 |
|   2023 |      52 |                    9 |                   0 |
|   2024 |      14 |                    3 |                   0 |

**NG**: 744 release weeks in the period; weekdays: {'Thursday': 724, 'Wednesday': 20}

|   year |   weeks |   shifted_by_holiday |   not_a_trading_day |
|-------:|--------:|---------------------:|--------------------:|
|   2010 |      52 |                    2 |                   0 |
|   2011 |      52 |                    1 |                   1 |
|   2012 |      52 |                    1 |                   0 |
|   2013 |      52 |                    2 |                   0 |
|   2014 |      53 |                    3 |                   1 |
|   2015 |      52 |                    1 |                   0 |
|   2016 |      52 |                    1 |                   2 |
|   2017 |      52 |                    1 |                   0 |
|   2018 |      52 |                    1 |                   0 |
|   2019 |      52 |                    2 |                   0 |
|   2020 |      53 |                    1 |                   0 |
|   2021 |      52 |                    2 |                   0 |
|   2022 |      52 |                    1 |                   0 |
|   2023 |      52 |                    1 |                   0 |
|   2024 |      14 |                    0 |                   0 |

## 6. Pre-registered NG sample start

Rule: if RNGC1 or RNGC2 has a gap longer than 5 business days inside the period, the sample starts on the first trading day after the last such gap. **NG sample start: 2010-01-04.**

WTI has no sample rule in the pre-registration; its sample starts on the period start unless the gap tables above show a gap inside the period.

## 7. Integrity check of the contract-expiry rules (no return statistic)

Share of roll days, by offset from the rule's day, where C1 today is closer to yesterday's C2 than to yesterday's C1 (2009-12-01 to 2024-04-05). Offset 0 should dominate.

- **WTI** (CL rule): offset -2: 0.404, offset -1: 0.48, offset +0: 0.558, offset +1: 0.448, offset +2: 0.39

- **NG** (NG rule): offset -2: 0.36, offset -1: 0.419, offset +0: 0.622, offset +1: 0.366, offset +2: 0.331

## 9. T5 integrity checks (AGSI+ and Open-Meteo)

AGSI+ aggregate type=eu: 4018 gas days in 2015-01-01..2025-12-31 (4018 calendar days). Units: GWh/d for injection (median 1774) and withdrawal (median 716); fill level in % (min 17.7, max 99.5). Temperatures: Open-Meteo daily mean at 2 m, Europe/Berlin day, six cities, 0 missing city-days. Rule: gas days 1 November to 31 March; a day with a missing value is dropped.

|   gas year |   winter days in sample |   days used |   mean NW (GWh/d) |   mean HDD |
|-----------:|------------------------:|------------:|------------------:|-----------:|
|       2014 |                      90 |          90 |              5176 |      11.5  |
|       2015 |                     152 |         152 |              3349 |      10.13 |
|       2016 |                     151 |         151 |              4727 |      11.63 |
|       2017 |                     151 |         151 |              5158 |      11.91 |
|       2018 |                     151 |         151 |              3239 |      10.48 |
|       2019 |                     152 |         152 |              3210 |       9.8  |
|       2020 |                     151 |         151 |              4820 |      11.11 |
|       2021 |                     151 |         151 |              3731 |      10.73 |
|       2022 |                     151 |         151 |              2842 |      10.34 |
|       2023 |                     152 |         152 |              2941 |       9.62 |
|       2024 |                     151 |         151 |              4507 |      10.74 |
|       2025 |                      61 |          61 |              3874 |      10.05 |

Days used: 1664; HDD range 1.1 to 22.2.

## 8. T4 integrity checks (ENTSO-E DE-LU)

Zone DE_LU (EIC 10Y1001A1001A82H), time zone Europe/Berlin. Units: prices EUR/MWh (min -500.0, max 936.3); wind and solar forecast MW (max 75145); load forecast MW (min 30739, max 78313). Rule: a day is used if prices, the wind and solar forecast and the load forecast each cover at least 90% of its hours.

|   year |   calendar days |   days used |   price obs |   wind+solar obs |   load obs |   share used |
|-------:|----------------:|------------:|------------:|-----------------:|-----------:|-------------:|
|   2019 |             365 |         365 |        8759 |            35040 |      35040 |        1     |
|   2020 |             366 |         366 |        8783 |            35136 |      35136 |        1     |
|   2021 |             365 |         365 |        8759 |            35040 |      35040 |        1     |
|   2022 |             365 |         363 |        8759 |            35040 |      34848 |        0.995 |
|   2023 |             365 |         365 |        8759 |            35036 |      35036 |        1     |
|   2024 |             366 |         366 |        8783 |            35132 |      35132 |        1     |
|   2025 |             365 |         365 |       15386 |            35036 |      35040 |        1     |
|   2026 |               0 |           0 |           1 |                0 |          0 |      nan     |

Days used: 2555 of 2557; S_d range 0.05 to 1.02.
