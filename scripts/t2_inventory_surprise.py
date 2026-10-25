"""T2 (pre-registered): direction of the inventory surprise on the release day.

H: the unexpected part of the weekly inventory change moves the front contract in the opposite direction on the release day.
The expectation M0 is an expanding-window OLS of the weekly change on two lags and Fourier terms of the week of the year,
using only weeks before the forecast week. Run once on the full period (prereg common.run_once).

Usage: python scripts/t2_inventory_surprise.py
Outputs: results/T2.json, results/T2.log (figures: scripts/fig_tests.py)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from altdata.markets import MARKETS, PERIOD, build  # noqa: E402
from altdata.paths import RESULTS, assert_prereg_frozen  # noqa: E402
from altdata.runlog import RunLog, trial_log  # noqa: E402
from altdata.stats import ols_hac, one_sided_p_from_t  # noqa: E402

MIN_TRAIN = 260
LAGS = 4
UNITS = {"WTI": "thousand barrels", "NG": "Bcf"}


def surprises(stocks: pd.Series, k: int, min_train: int = MIN_TRAIN) -> pd.Series:
    """s_t = D_t - forecast_t, with the forecast fitted on weeks strictly before t (expanding window)."""
    F = stocks.index
    D = stocks.diff()
    D[pd.Series(F, index=F).diff() != pd.Timedelta(days=7)] = np.nan
    X = pd.DataFrame({"const": 1.0, "d1": D.shift(1), "d2": D.shift(2)}, index=F)
    doy = F.dayofyear.to_numpy()
    for j in range(1, k + 1):
        X[f"sin{j}"] = np.sin(2 * np.pi * j * doy / 365.25)
        X[f"cos{j}"] = np.cos(2 * np.pi * j * doy / 365.25)
    Xv, yv = X.to_numpy(float), D.to_numpy(float)
    ok = np.isfinite(Xv).all(axis=1) & np.isfinite(yv)
    fc = np.full(len(F), np.nan)
    for t in range(len(F)):
        train = np.flatnonzero(ok[:t])
        if len(train) < min_train or not np.isfinite(Xv[t]).all():
            continue
        beta = np.linalg.lstsq(Xv[train], yv[train], rcond=None)[0]
        fc[t] = Xv[t] @ beta
    return pd.Series(yv - fc, index=F, name="s")


def main() -> None:
    log = RunLog("T2")
    sha = assert_prereg_frozen()
    log("prereg hash", sha)
    out = {"id": "T2", "prereg_sha256": sha, "markets": {}}
    frames = {}
    for n in MARKETS:
        m = build(n)
        s = surprises(m.stocks, m.seas_k)
        rel = m.releases[m.releases["is_trading_day"]].set_index("week_end")["release"]
        df = pd.DataFrame({"s": s, "R": rel}).dropna()
        df = df[(df["R"] >= m.start) & (df["R"] <= PERIOD[1])]
        df["r"] = m.returns["r"].reindex(df["R"]).to_numpy()
        df = df.dropna(subset=["r"])
        sd = float(df["s"].std(ddof=1))
        df["z"] = df["s"] / sd
        reg = ols_hac(df["r"].to_numpy(), df["z"].to_numpy(), LAGS)
        t = reg["t"][0]
        nz = (df["s"] != 0) & (df["r"] != 0)
        q = pd.qcut(df["z"], 5, labels=False)
        quint = [{"quintile": int(i + 1), "n": int((q == i).sum()), "mean_r_bp": float(1e4 * df.loc[q == i, "r"].mean()),
                  "se_bp": float(1e4 * df.loc[q == i, "r"].std(ddof=1) / np.sqrt((q == i).sum()))} for i in range(5)]
        rho = stats.spearmanr(df["z"], df["r"])
        res = {"units": UNITS[n], "first_release": str(df["R"].min().date()), "last_release": str(df["R"].max().date()),
               "n": reg["n"], "sd_surprise": sd, "slope_b_per_sd": reg["b"][0], "se": reg["se"][0], "t_nw4": t, "r2": reg["r2"],
               "p_one_sided_normal": one_sided_p_from_t(t, "neg"), "spearman": float(rho.statistic), "spearman_p": float(rho.pvalue),
               "sign_hit_rate": float((np.sign(df.loc[nz, "r"]) == -np.sign(df.loc[nz, "s"])).mean()), "n_sign": int(nz.sum()),
               "quintiles": quint, "verdict": "SUPPORTED" if t <= -2.0 else "NOT SUPPORTED"}
        out["markets"][n] = res
        frames[n] = df
        log(n, "n", res["n"], "from", res["first_release"], "b(bp per sd)", round(1e4 * res["slope_b_per_sd"], 1), "t", round(t, 2),
            "spearman", round(res["spearman"], 3), "hit", round(res["sign_hit_rate"], 3), "->", res["verdict"])
    (RESULTS / "T2.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    verdict = "; ".join(f"{n}: {out['markets'][n]['verdict']}" for n in MARKETS)
    secs = log.close()
    trial_log("T2", "scripts/t2_inventory_surprise.py", sha, verdict, secs)


if __name__ == "__main__":
    main()
