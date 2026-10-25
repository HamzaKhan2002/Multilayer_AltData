# multilayer-altdata

A research scaffold for a multilayer alternative-data system: sources, engineering per data type, regimes, fusion, risk, and a validation discipline that never changes. The scaffold is asset-class independent; the first idea developed in it is energy inventories before the weekly EIA report.

**No strategy backtest is run or claimed here.** What the repository contains is (1) the toolkit, (2) five **pre-registered** checks on free public data (v1), each frozen before its first run, plus a second pre-registration (v2) with an audit, a Sentinel-2 roof-shadow pilot (B-S) and an exploratory price diagnostic (B0), and (3) the documents that turn six ideas into conditional PnL figures from explicit assumptions.

## Results of the five pre-registered checks

Pre-registration: `prereg/tests_v1.json`, SHA-256 `66bec92f8383607c1777e3d69c23aa8abd25efa1f90bead18fc9f22615f1cbbe`. Each test was run once. Every verdict is reported, including the ones that do not support the hypothesis.

| Test | Question | Result | Verdict |
|---|---|---|---|
| T1 WTI | Are EIA report days more volatile? | ratio 1.10, 95% interval 1.03 to 1.19, 743 report days | supported |
| T1 gas | same | ratio 1.09, 95% interval 1.01 to 1.18, 740 report days | supported (Holm-adjusted one-sided p = 0.052) |
| T2 WTI | Does the inventory surprise move the report-day return against its sign? | -17.0 bp per sd, Newey-West t = -1.26, 743 weeks | not supported |
| T2 gas | same | -8.9 bp per sd, t = -0.65, 479 weeks | not supported |
| T3 | Do cloudier weeks give larger release-day moves? (exploratory) | one-sided t = 0.88, 430 weeks | inconclusive at daily resolution |
| T4 | More forecast wind and solar, lower German day-ahead price? | -15.9 EUR/MWh per +10 points of share, t = -16.4, 2,555 days | supported |
| T5 | Colder days, larger net EU storage withdrawals? | +645 GWh/d per heating degree day, t = 37.5, 1,664 winter days | supported |

Full table, with the adjusted p-values: `results/verdicts.md`. Deviations and implementation choices, written before each affected statistic: `results/deviations.md`. Data-integrity checks: `results/coverage.md`.

Satellite and registry findings (no statistic is tested on them): on 286 Sentinel-2 scenes covering the Cushing window, 47% are at least 60% cloudy; on the clear pass, mapped tanks are 2.9 times brighter than their surroundings; the Sentinel-1 backscatter inside the mapped tanks is 12.5 dB above the rest of the window; the OpenStreetMap registry holds 333 tanks, median diameter 60 m, about 6 pixels at 10 m.

## Second pre-registration (v2, 24-25 October 2026)

Pre-registration: `prereg/tests_v2.json`, SHA-256 `acfe66efb2878adf811e5b58aea99ff14048199728a9d76cc1045c67da67d84f`, frozen 2026-10-25 01:21 and recorded in `results/v2/prereg_v2.sha256`. The v1 record above is unchanged. The audit of 24 October came first. Every verdict is reported, including the inconclusive ones and the blocked first run of B0.

| Test | Question and rule | Result | Verdict |
|---|---|---|---|
| Audit | Can the v1 record be reproduced, and are its release calendar and data vintages right? Descriptive: no return or price statistic is computed. | T1-T5 re-run from the archived code in a scratch copy: identical outputs (`audit/repro_T1_T5.md`). The zip snapshot equals the folder except two new scripts (`audit/snapshot_diff.md`). EIA report archive: 796 releases since 2011 (`audit/eia_release_registry.csv`). The v1 rule calendar misdated 14 of 660 weeks in 2011-2024, mostly +1 day in holiday weeks (`audit/calendar_audit.md`). Cushing first-published values equal the latest values in all 795 weeks (no revision); US commercial crude differs in 272 weeks of 2011-2016 (`audit/vintage_audit.md`). Cushing AR(2) baseline reproduced: out-of-sample R2 0.307 on 521 forecasts, RMSE 1.20 Mb against 1.44 for a constant mean, sign hit 0.674; on first-published values R2 0.324 on 517 forecasts; the +-1.2 Mb band holds about 74% of the errors (`results/v2/baseline_cushing/metrics.json`). | reproduced |
| T1c WTI | T1 for WTI recomputed with the EIA archive release dates (12 report days moved in the sample). Same statistic and rule as T1. | ratio 1.108, 95% interval 1.028 to 1.192 (`results/v2/T1c.json`) | supported |
| T2c WTI | T2 for WTI recomputed with the archive release dates. Same statistic and rule as T2. | -17.9 bp per sd, Newey-West t = -1.32 (`results/v2/T2c.json`) | not supported |
| BS0 | What imagery exists over Cushing, and how often is a usable pass available before the weekly figure? Descriptive: no verdict. | 603 Sentinel-2 L2A acquisitions, 2018-12 to 2026-10, all on one relative orbit (R112), via Element 84 Earth Search. Sentinel-1 RTC via Microsoft Planetary Computer: 310 acquisitions, all ascending, about 55 a year in 2019-2021 and 28-31 a year since 2022 (about 12 days). A usable pass within +-2 days of the Friday and before the Tuesday API cut-off (24 h latency assumed): Sentinel-2 39% of 410 weeks, 14% with sun elevation <= 45 deg; Sentinel-1 44%. Sentinel-2 L2A publication latency (Copernicus Data Space catalogue, 149 products in 2026): median 6.0 h, p90 8.6 h, max 12.8 h (`results/v2/BS0/`). | descriptive |
| BS1 | Can a shadow model read the roof depth of floating-roof tanks from 10 m Sentinel-2 pixels, and how repeatable is it? Descriptive: no verdict. | 441 acquisitions x 234 tanks of diameter >= 40 m (from the 333-tank OpenStreetMap registry); an estimate for 60% of tank-dates, a third lost to clouds. Same-pass pairs (two satellites 27 s apart, 4 winter dates, sun 31-36 deg): 828 pairs, 91% within 1 m, 78% within 0.5 m. Simulated RMSE by sun elevation: 2.3 m (25-35 deg) to 7.2 m (above 65 deg). Nominal 68% intervals cover only 33-57% (too narrow). Registration: median absolute shift 1.2 m (x) and 2.4 m (y), 7% of acquisitions flagged (`results/v2/BS1/`). | descriptive: repeatable per tank, intervals too narrow |
| BS2 | Does the weekly change of the hub proxy (roof-depth changes converted to volume and summed over the tanks) track the first-published Cushing change? SIGNAL if the lower 95% bound of r > 0; NO SIGNAL if the upper bound < 0.20; else INCONCLUSIVE. | Primary low-sun sample: r = 0.16, 95% interval -0.32 to 0.57, 19 weeks. All seasons: r = 0.13 (-0.14 to 0.38), 57 weeks. Nowcast test not evaluable (fewer than 20 earlier valid weeks) (`results/v2/BS2/bs2.json`). | inconclusive |
| B0, first run | How do first-published inventory surprises move WTI at the 10:30 ET print? Ex post diagnostic, not a strategy. Clock check first: the 10:30 minute must be the largest one-minute move of 10:00-10:59 on at least 70% of release days. | 10:30 is the largest minute on 44% of 464 days, below 70%. No price difference and no regression computed (`results/v2/B0/`). | blocked |
| B0-AM1 (amended) | Same question; the clock check is replaced by the year-wise gate of AM-B0-1. Detected if the 95% interval of the Cushing coefficient lies below 0. | 447 releases 2013-2023. WTI change from 10:30:00 to 10:36:00 (HistData minute bid bars) on first-published surprises (AR(2) recursive forecast errors), HC1. Cushing -3.1 cents per barrel per Mb, 95% interval -6.6 to +0.4. US crude ex-Cushing -2.6 (-3.4 to -1.8, t -6.2); gasoline -3.6; distillate -3.1; R2 0.21; sd of the move 39 cents (`results/v2/B0_amended/b0.json`). | not detected (exploratory) |

**AM-B0-1.** The first B0 run stopped at its written clock check. The mean profile of the one-minute moves peaks at 10:30, but the rule asked for the single largest minute of the hour, and volatility stays high for several minutes after the print. Before any outcome statistic was computed, the check was replaced by a year-wise gate: for each calendar year, the mean absolute one-minute change over 10:15-10:45 must peak at 10:30 and exceed 3 times its 10:15-10:29 mean. 2026 failed the gate and is excluded. The blocked run stays on record in `results/v2/B0/`; the amended run is in `results/v2/B0_amended/` and is reported as exploratory.

Not run: A (replication of Alturki and Kurov; the published tables were not accessed) and B2-B3 (they need intraday quotes for two contracts and an admissible weekly variable).

Deviations, implementation choices and the amendment, each written before the statistic it affects: `results/v2/deviations_v2.md`. Every v2 run, with the pre-registration hash: `results/v2/trial_log_v2.csv` (ids BS1, BS0+BS1, BS2, FIG, T1c, T2c, B0, B0-AM1). BS0 to BS2 are the B-S pilot of idea I1 and B0 prices the print; the gates are in `docs/IDEAS.md`.

## Repository layout

```
prereg/tests_v1.json     the five tests, frozen before any statistic was computed
prereg/tests_v2.json     second pre-registration (T1c, T2c, BS0 to BS2, B0), frozen 2026-10-25
src/altdata/             toolkit: EIA files, trading calendars, statistics, Sentinel-1/-2, OpenStreetMap,
                         ENTSO-E, GIE AGSI+, Open-Meteo, plotting, run log, secrets handling
  tankshadow.py          roof-shadow model of floating-roof tanks (v2)
  histdata.py            HistData minute loader (v2)
  v2common.py            shared paths, guards and helpers of the v2 tests
scripts/                 coverage audit, T1 to T5, T1c, T2c, BS0 to BS2, B0, EIA archive, Cushing
                         baseline, PnL grid, tank registry, figures
audit/                   re-runs of T1-T5, EIA release calendar, first-published vintages, snapshot diff
results/                 result JSON files, verdicts, deviations, coverage, trial log, PnL grid (v1)
results/v2/              v2 results, logs, trial log, deviations
figures/                 every chart and satellite figure (PNG and SVG)
docs/                    architecture, ideas, PnL method, six-month plan, data sources
docs/spec/               Research and Technical Specification (HTML source and PDF)
tests/                   synthetic-data checks of the statistical code and the v2 modules
data/                    raw downloads and caches (not committed; rebuilt by the scripts)
```

## Reproduce

Python 3.11. Tested with the versions in `requirements.txt`.

```
pip install -r requirements.txt
cp .env.example .env        # then fill in your own ENTSO-E token and AGSI+ key (both free)
python -m pytest tests

python scripts/coverage_audit.py
python scripts/t1_release_volatility.py
python scripts/t2_inventory_surprise.py
python scripts/t3_cloud_cover.py
python scripts/prefetch_entsoe.py 2025 2024 2023 2022 2021 2020 2019
python scripts/t4_merit_order.py
python scripts/t5_gas_storage_hdd.py
python scripts/verdicts.py
python scripts/pnl_grid.py --v1
python scripts/fig_tests.py
```

The satellite figures (`fig_sentinel_cushing.py`, `fig_sentinel1_cushing.py`, `fig_tank_registry.py`, after `tank_registry.py`) read public imagery through STAC and the Overpass API, and need a network connection. Downloads are cached in `data/`.

### v2 (second pre-registration)

The v2 scripts reuse the EIA files cached in `data/eia/` by the v1 scripts, and `t1c_t2c_calendar.py` checks itself against `results/T1.json` and `results/T2.json`. From the repository root:

```
python scripts/eia_wpsr_archive.py            # EIA report archive, first-published values
python audit/wpsr_audits.py                   # calendar and vintage audits
python audit/compare_repro.py --new <scratch results folder>
python audit/snapshot_diff.py                 # folder against multilayer-altdata.zip
python scripts/baseline_cushing_ar2.py        # Cushing AR(2) baseline
python scripts/t1c_t2c_calendar.py --calendar rule      # built-in check against T1 and T2
python scripts/t1c_t2c_calendar.py --calendar archive   # T1c and T2c
python scripts/bs0_catalog.py                 # Sentinel catalogues, publication latency
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bs_run_all.ps1
python scripts/b0_transmission.py             # first run: stops at the clock check
python scripts/b0_transmission.py --amended   # amendment AM-B0-1
python scripts/fig_b0.py
python scripts/pnl_grid.py                    # v2 grid
python scripts/pnl_grid.py --v1               # v1 grid
```

- `eia_wpsr_archive.py` downloads the report archive (network; pages cached in `data/eia_wpsr_archive/`) and writes `audit/eia_release_registry.csv` and `results/v2/eia_first_release.csv`. `wpsr_audits.py` writes the calendar and vintage audits in `audit/`.
- `compare_repro.py --new` takes the `results/` folder of a scratch copy of the repository in which T1 to T5 were re-run, and writes `audit/repro_T1_T5.md`. `snapshot_diff.py` compares the folder with `multilayer-altdata.zip`, which must sit next to it, and writes `audit/snapshot_diff.md`.
- `baseline_cushing_ar2.py` writes `results/v2/baseline_cushing/`. It reads the first-version weekly CSV from `../deliverables/analysis/eia_cushing_weekly.csv` unless `--v1-csv PATH` is given.
- `t1c_t2c_calendar.py --calendar rule` is a check: the WTI blocks computed with the rule calendar must reproduce `results/T1.json` and `results/T2.json`. `--calendar archive` repeats it, then runs T1c and T2c.
- `bs0_catalog.py` writes the Sentinel catalogues and the latency check in `results/v2/BS0/`. `bs_run_all.ps1` then runs `bs1_extract`, `bs1_analysis`, `bs2_aggregate` and `fig_bs`; set `ALTDATA_PYTHON` to your interpreter.
- B0 needs the HistData WTIUSD M1 zips (`DAT_ASCII_WTIUSD_M1_<year or yyyymm>.zip`), downloaded by you from HistData.com into the folder named by the environment variable `ALTDATA_HISTDATA_DIR`. HistData files are not redistributed. The first command is the run as pre-registered; `--amended` applies AM-B0-1 and writes `results/v2/B0_amended/`; `fig_b0.py` draws from the amended result when it exists.
- `pnl_grid.py` writes `results/v2/pnl_grid_v2.csv`; `--v1` reproduces `results/pnl_grid.csv` byte for byte.

Every test script checks the pre-registration hash first. T1c, T2c and B0 also refuse to overwrite an existing result file (single-run guard); the other test scripts overwrite their outputs. A reproduction therefore runs in a scratch copy of the repository and is compared with the archived results, as `audit/compare_repro.py` does.

## Discipline built into the code

- The pre-registration hash is checked at the start of every test script; a changed file stops the run.
- Each test runs once. Every run is appended to `results/trial_log.csv` (v1) or `results/v2/trial_log_v2.csv` (v2), and deviations are written before the statistic they affect (`results/deviations.md`, `results/v2/deviations_v2.md`).
- One amendment (AM-B0-1), dated and written before any outcome statistic; B0 is reported as exploratory and its first, blocked run stays on record.
- Availability timestamps, not event timestamps, define what is known at a decision time. In v1 the EIA release dates are rebuilt by rule, and the cases where that can be wrong are listed in `results/coverage.md`; v2 uses the release dates of the EIA report archive (`audit/calendar_audit.md`).
- Secrets are read from the environment (`.env`, git-ignored), never printed or logged; exceptions are masked.
- Every result file carries the pre-registration hash; the SHA-256 of each raw EIA file used is recorded in `results/data_versions.json`.

## Data sources and attributions

| Source | Used for | Terms |
|---|---|---|
| U.S. Energy Information Administration | NYMEX contracts 1 and 2, weekly crude stocks, Cushing, gas storage | public data |
| EIA weekly report archive | release dates and first-published stocks (Table 4) | public data |
| Copernicus Sentinel-2 and Sentinel-1 | optical and radar images | free, full and open. Contains modified Copernicus Sentinel data 2018-2026 (ESA) |
| Copernicus Data Space catalogue | Sentinel-2 L2A publication times | free access, same terms as the Sentinel data |
| OpenStreetMap | tank registry | ODbL, (c) OpenStreetMap contributors; coverage is incomplete |
| HistData.com | WTI minute bid bars (B0) | free download; the files are not redistributed |
| Open-Meteo (ERA5-based archive) | cloud cover, temperatures | CC BY 4.0, non-commercial use |
| ENTSO-E Transparency Platform | German prices, wind, solar and load forecasts | free token |
| GIE AGSI+ | EU gas storage | free key |

Details and point-in-time caveats: `docs/DATA_SOURCES.md`.

## Limits

- The checks confirm mechanisms on free data; they do not establish a tradable edge. The NYMEX contract series used end on 2024-04-05, so T1 stops there.
- T2 uses an expectation built only from the stock history. The market also has the API estimate and the consensus; the checks do not include them.
- T3 is exploratory and at daily resolution; B0 (v2) is an intraday test around the print, for the stock surprise.
- Free 10 m imagery gives coarse per-tank readings (about 6 pixels across a median tank). The v2 pilot reads roof depth from the shadow inside each tank; the documents propose aggregation by hub, Sentinel-1 phase data, and a vendor trial measured against the pilot.
- There is no gauge truth for tank depths: the pilot shows repeatability, not accuracy, and its nominal 68% intervals are too narrow.
- The hub test is inconclusive on 19 weeks, and the nowcast test could not be evaluated.
- B0 is exploratory: its validity gate was amended after the first run, and it excludes 2026. Its surprises are AR(2) forecast errors on first-published values, not consensus or API surprises.
- There is no HistData file for 2024-01 to 2026-05; its minute bars are bid-only.
- A, B2 and B3 were not run.
- Vendor claims are not reproduced.
- The PnL figures in `docs/PNL_METHOD.md`, `results/v2/pnl_grid_v2.csv` and `results/pnl_grid.csv` (v1) are illustrative: conditional orders of magnitude from explicit assumptions (N, k, B), not results.
