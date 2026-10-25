# Reproduction of T1-T5 in a scratch copy

Original outputs: `multilayer-altdata/results/` (not modified). Re-run: `C:\Users\Hamza\AppData\Local\Temp\mla_repro` (copy of src, scripts, prereg, data, results; T*.json, T*.log, T*_*.csv and trial_log.csv deleted in the copy before the run). Scripts run in the order T1, T2, T3, T4, T5 on the cached data in `data/`; no download was attempted and all five exited with code 0.

## Environment

- Python 3.11.9 (CPython, Windows-10-10.0.26200-SP0)
- numpy 1.26.4, pandas 2.3.2, scipy 1.13.0, statsmodels 0.14.5

## Re-run log (copy's trial_log.csv)

| id | timestamp | seconds | verdict |
|---|---|---|---|
| T1 | 2026-10-24T15:43:36 | 1.9 | WTI: SUPPORTED; NG: SUPPORTED |
| T2 | 2026-10-24T15:43:40 | 1.3 | WTI: NOT SUPPORTED; NG: NOT SUPPORTED |
| T3 | 2026-10-24T15:43:43 | 1.0 | INCONCLUSIVE AT DAILY RESOLUTION |
| T4 | 2026-10-24T15:43:54 | 3.6 | SUPPORTED |
| T5 | 2026-10-24T15:43:56 | 0.2 | SUPPORTED |

## JSON outputs (relative tolerance 1e-09)

| file | numeric fields | other fields | max abs diff | max rel diff | fields with rel diff > 1e-9 | structural/string mismatches | bytes identical |
|---|---|---|---|---|---|---|---|
| T1.json | 82 | 10 | 0 | 0 | 0 | 0 | yes |
| T2.json | 62 | 10 | 0 | 0 | 0 | 0 | yes |
| T3.json | 30 | 6 | 0 | 0 | 0 | 0 | yes |
| T4.json | 29 | 6 | 0 | 0 | 0 | 0 | yes |
| T5.json | 7 | 5 | 0 | 0 | 0 | 0 | yes |

SHA-256 (original / re-run):

- T1.json: `35b8d1ec24d5c93653c51a7237f6a00a5e5b4cce21e8326728e9183f36d79e7c` / `35b8d1ec24d5c93653c51a7237f6a00a5e5b4cce21e8326728e9183f36d79e7c`
- T2.json: `e80b219e4be025c8d7397c9c9f2ab322f28cc669c3b75b27eb20ad0bd8aa4895` / `e80b219e4be025c8d7397c9c9f2ab322f28cc669c3b75b27eb20ad0bd8aa4895`
- T3.json: `88fe3f5ea4cb08cd76c317557198e3128ff053930607bf7944feb5adf063e6b1` / `88fe3f5ea4cb08cd76c317557198e3128ff053930607bf7944feb5adf063e6b1`
- T4.json: `bcd9fb6d3ba8f03ef4b8907a124749ef0df5e6d2fc3154585616c44eb59f28a6` / `bcd9fb6d3ba8f03ef4b8907a124749ef0df5e6d2fc3154585616c44eb59f28a6`
- T5.json: `29e7058d406ed4e0cfd9b7d2d3d51334c330f465f228a8c5d375718653b53e78` / `29e7058d406ed4e0cfd9b7d2d3d51334c330f465f228a8c5d375718653b53e78`

## CSV outputs

| file | rows (orig / re-run) | same columns | max abs diff (numeric columns) | non-numeric columns equal | bytes identical |
|---|---|---|---|---|---|
| T3_weeks.csv | 430 / 430 | yes | 0 | yes | yes |
| T4_daily.csv | 2555 / 2555 | yes | 0 | yes | yes |
| T5_daily.csv | 1664 / 1664 | yes | 0 | yes | yes |
| T5_fill.csv | 4018 / 4018 | yes | 0 | yes | yes |

## coverage.md (T4 and T5 rewrite their sections in the copy)

- original `31fa2ae97086b8b6b501ad20633137b694102deaab707b9e7220abf8401196e0`
- re-run   `95ace40fda25c71837529bc8e6a1f043b29f9c24cf991893bcf17ba1a833c3aa`
- bytes identical: no
- sections: 9 original / 9 re-run; sections with identical text: 9 of 9
- section order identical: no (original: 1., 2., 3., 4., 5., 6., 7., 9., 8.; re-run: 1., 2., 3., 4., 5., 6., 7., 8., 9.)
