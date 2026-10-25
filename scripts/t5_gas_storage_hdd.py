"""T5 (pre-registered): EU gas storage withdrawals and temperature.

H: cold days drive EU storage withdrawals: net withdrawal rises with heating degree days (November to March gas days, 2015-2025).
Definitions: prereg/tests_v1.json and results/deviations.md. Run once on the full period (prereg common.run_once).

Usage: python scripts/t5_gas_storage_hdd.py
Outputs: results/T5.json, results/T5_daily.csv, results/T5_fill.csv, results/T5.log, a section appended to results/coverage.md
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata import agsi, openmeteo  # noqa: E402
from altdata.paths import RESULTS, assert_prereg_frozen  # noqa: E402
from altdata.runlog import RunLog, append_coverage, trial_log  # noqa: E402
from altdata.stats import ols_hac  # noqa: E402

START, END = "2015-01-01", "2025-12-31"
CITIES = {"Berlin": (52.52, 13.405), "Paris": (48.857, 2.352), "Milan": (45.464, 9.19), "Amsterdam": (52.37, 4.895),
          "Vienna": (48.208, 16.373), "Warsaw": (52.23, 21.012)}
BASE_TEMP = 15.5
LAGS = 7


def main() -> None:
    log = RunLog("T5")
    sha = assert_prereg_frozen()
    log("prereg hash", sha)
    gas = agsi.eu_storage(START, END)
    log("AGSI+ EU aggregate", len(gas), "gas days", gas.index.min().date(), "->", gas.index.max().date())
    temps = pd.concat({c: openmeteo.daily_mean_temperature(la, lo, START, END) for c, (la, lo) in CITIES.items()}, axis=1)
    log("Open-Meteo", temps.shape, "city-days; missing", int(temps.isna().sum().sum()))

    d = pd.DataFrame({"inj": gas["injection"], "wd": gas["withdrawal"], "fill": gas["full"]}).join(temps.mean(axis=1, skipna=False).rename("T"), how="left")
    d["NW"] = d["wd"] - d["inj"]
    d["HDD"] = (BASE_TEMP - d["T"]).clip(lower=0)
    d["gas_year"] = np.where(d.index.month >= 10, d.index.year, d.index.year - 1)
    winter = d[d.index.month.isin([11, 12, 1, 2, 3])]
    used = winter.dropna(subset=["NW", "HDD"])

    full_index = pd.date_range(START, END, freq="D")
    by_gy = pd.DataFrame({"winter days in sample": winter.groupby("gas_year").size(), "days used": used.groupby("gas_year").size(),
                          "mean NW (GWh/d)": used.groupby("gas_year")["NW"].mean().round(0), "mean HDD": used.groupby("gas_year")["HDD"].mean().round(2)}).fillna(0)
    body = (f"AGSI+ aggregate type=eu: {len(gas)} gas days in {START}..{END} ({len(full_index)} calendar days). Units: GWh/d for injection "
            f"(median {gas['injection'].median():.0f}) and withdrawal (median {gas['withdrawal'].median():.0f}); fill level in % "
            f"(min {gas['full'].min():.1f}, max {gas['full'].max():.1f}). Temperatures: Open-Meteo daily mean at 2 m, Europe/Berlin day, six cities, "
            f"{int(temps.isna().sum().sum())} missing city-days. Rule: gas days 1 November to 31 March; a day with a missing value is dropped.\n\n"
            + by_gy.reset_index().rename(columns={"gas_year": "gas year"}).to_markdown(index=False)
            + f"\n\nDays used: {len(used)}; HDD range {used['HDD'].min():.1f} to {used['HDD'].max():.1f}.")
    append_coverage("9. T5 integrity checks (AGSI+ and Open-Meteo)", body)

    gy = pd.get_dummies(used["gas_year"].astype(str), drop_first=True).to_numpy(float)
    wk = pd.get_dummies(pd.Series(used.index.dayofweek, index=used.index), drop_first=True).to_numpy(float)
    reg = ols_hac(used["NW"].to_numpy(float), np.column_stack([used["HDD"].to_numpy(float), gy, wk]), LAGS)
    b, se, t = reg["b"][0], reg["se"][0], reg["t"][0]
    out = {"id": "T5", "prereg_sha256": sha, "period": [START, END], "n_days": int(reg["n"]), "b_gwh_per_hdd_degree": b, "se": se, "t_nw7": t,
           "mean_NW_gwh": float(used["NW"].mean()), "mean_HDD": float(used["HDD"].mean()), "sd_HDD": float(used["HDD"].std()),
           "verdict": "SUPPORTED" if t >= 5.0 else "NOT SUPPORTED"}
    (RESULTS / "T5.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    used[["NW", "HDD", "gas_year"]].to_csv(RESULTS / "T5_daily.csv")
    d[["fill", "gas_year"]].dropna().to_csv(RESULTS / "T5_fill.csv")
    log("b (GWh/d per HDD degree):", round(b, 1), "se", round(se, 1), "t", round(t, 2), "n", reg["n"], "->", out["verdict"])
    secs = log.close()
    trial_log("T5", "scripts/t5_gas_storage_hdd.py", sha, out["verdict"], secs)


if __name__ == "__main__":
    main()
