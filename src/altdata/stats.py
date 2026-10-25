"""Statistics used by the pre-registered tests: HAC regressions, week-block bootstrap, multiplicity adjustment."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

SEED = 20261023
DRAWS = 5000
CHUNK = 500


def ols_hac(y: np.ndarray, x: np.ndarray, lags: int) -> dict:
    """OLS of y on [1, x] with Newey-West (Bartlett) standard errors; x may be a matrix. Returns the slope(s) on x."""
    X = sm.add_constant(np.asarray(x, float), has_constant="add")
    res = sm.OLS(np.asarray(y, float), X).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {"n": int(res.nobs), "const": float(res.params[0]), "b": res.params[1:].tolist(), "se": res.bse[1:].tolist(),
            "t": res.tvalues[1:].tolist(), "r2": float(res.rsquared)}


def week_block_ratio(abs_r: pd.Series, is_event: pd.Series, draws: int = DRAWS, seed: int = SEED) -> dict:
    """mean|r| on event days / mean|r| on the other days, with a week-block bootstrap (Monday-Sunday blocks).

    Returns the point ratio, the percentile 95% interval and the one-sided p = P(ratio* <= 1) with the (k+1)/(B+1) rule.
    """
    d = pd.DataFrame({"a": abs_r, "e": is_event.reindex(abs_r.index).astype(bool)}).dropna()
    wk = d.index.to_period("W-SUN")
    g = d.assign(ae=d["a"] * d["e"], an=d["a"] * ~d["e"], ne=d["e"].astype(int), nn=(~d["e"]).astype(int)).groupby(wk)
    sums = g[["ae", "an", "ne", "nn"]].sum().to_numpy(float)
    W = len(sums)
    point = (sums[:, 0].sum() / sums[:, 2].sum()) / (sums[:, 1].sum() / sums[:, 3].sum())
    rng = np.random.default_rng(seed)
    s = np.empty((draws, 4))
    for i in range(0, draws, CHUNK):
        j = min(i + CHUNK, draws)
        s[i:j] = sums[rng.integers(0, W, size=(j - i, W))].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = (s[:, 0] / s[:, 2]) / (s[:, 1] / s[:, 3])
    ratio = ratio[np.isfinite(ratio)]
    lo, hi = np.percentile(ratio, [2.5, 97.5])
    p = (int((ratio <= 1.0).sum()) + 1) / (len(ratio) + 1)
    return {"ratio": float(point), "ci95": [float(lo), float(hi)], "p_one_sided": float(p), "n_event": int(sums[:, 2].sum()),
            "n_other": int(sums[:, 3].sum()), "mean_abs_event": float(sums[:, 0].sum() / sums[:, 2].sum()),
            "mean_abs_other": float(sums[:, 1].sum() / sums[:, 3].sum()), "weeks": int(W), "draws": int(len(ratio))}


def holm(p: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values."""
    items = sorted(p.items(), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, v) in enumerate(items):
        run = max(run, min(1.0, (m - i) * v))
        out[k] = run
    return out


def one_sided_p_from_t(t: float, direction: str) -> float:
    """Normal-approximation one-sided p for the predicted sign ('neg' or 'pos')."""
    return float(stats.norm.cdf(t) if direction == "neg" else stats.norm.sf(t))
