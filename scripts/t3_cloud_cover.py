"""T3 (pre-registered, exploratory): cloud cover over Cushing and the size of the WTI release-day move.

H: when clouds hide Cushing from optical satellites in the days before the print, more information is left for the release day, so the
absolute release-day return is larger in cloudy weeks. Never presented as evidence of a trading edge. Definitions: prereg/tests_v1.json
and results/deviations.md. Run once on the full period (prereg common.run_once).

Usage: python scripts/t3_cloud_cover.py
Outputs: results/T3.json, results/T3_weeks.csv, results/T3.log
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from altdata import openmeteo  # noqa: E402
from altdata.markets import PERIOD, build  # noqa: E402
from altdata.paths import RESULTS, assert_prereg_frozen  # noqa: E402
from altdata.runlog import RunLog, trial_log  # noqa: E402
from altdata.stats import ols_hac, one_sided_p_from_t, week_block_ratio  # noqa: E402

LAT, LON = 35.985, -96.767
START = pd.Timestamp("2016-01-01")
HOURS = (16, 17, 18, 19)
ONE = pd.Timedelta(days=1)


def main() -> None:
    log = RunLog("T3")
    sha = assert_prereg_frozen()
    log("prereg hash", sha)
    m = build("WTI")
    r = m.returns["r"]
    rel = m.releases[m.releases["is_trading_day"]]
    rel = rel[(rel["release"] >= START) & (rel["release"] <= PERIOD[1])]
    cloud = openmeteo.hourly_cloud_cover(LAT, LON, "2015-12-01", "2024-04-05")
    sel = cloud[cloud.index.hour.isin(HOURS)]
    log("cloud-cover hours", len(cloud), "selected", len(sel), "missing", int(cloud.isna().sum()))
    daily = sel.groupby(sel.index.normalize()).mean()

    rows = []
    for R in rel["release"]:
        c = daily.reindex(pd.date_range(R - 7 * ONE, R - ONE)).mean()
        prior = r.loc[: R - ONE].dropna().iloc[-20:]
        rv = float(np.sqrt((prior ** 2).mean())) if len(prior) == 20 else np.nan
        rows.append({"release": R, "C": c, "RV20": rv, "abs_r": abs(r.get(R, np.nan))})
    w = pd.DataFrame(rows).set_index("release").dropna()
    q1, q2 = w["C"].quantile([1 / 3, 2 / 3])
    w["cloudy"] = (w["C"] >= q2).astype(float)
    w["tercile"] = np.where(w["C"] >= q2, "top", np.where(w["C"] <= q1, "bottom", "middle"))
    reg = ols_hac(w["abs_r"].to_numpy(float), np.column_stack([w["cloudy"], np.log(w["RV20"])]), 4)
    b, se, t = reg["b"][0], reg["se"][0], reg["t"][0]
    tb = w[w["tercile"] != "middle"]
    ratio = week_block_ratio(tb["abs_r"], pd.Series(tb["tercile"].eq("top").to_numpy(), index=tb.index))
    terciles = {k: {"n": int((w["tercile"] == k).sum()), "mean_abs_r_bp": float(1e4 * w.loc[w["tercile"] == k, "abs_r"].mean()),
                    "se_bp": float(1e4 * w.loc[w["tercile"] == k, "abs_r"].std(ddof=1) / np.sqrt((w["tercile"] == k).sum()))}
                for k in ("bottom", "middle", "top")}
    out = {"id": "T3", "prereg_sha256": sha, "exploratory": True, "period": [str(START.date()), str(PERIOD[1].date())], "n": reg["n"],
           "cloud_hours_utc": list(HOURS), "tercile_cuts_pct": [float(q1), float(q2)], "b": b, "se": se, "t_nw4": t, "p_one_sided_normal": one_sided_p_from_t(t, "pos"),
           "ratio_top_over_bottom": ratio, "terciles": terciles,
           "verdict": "CONSISTENT" if t >= 1.65 else "INCONCLUSIVE AT DAILY RESOLUTION"}
    (RESULTS / "T3.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    w.to_csv(RESULTS / "T3_weeks.csv")
    log("n", reg["n"], "b", f"{b:.3g}", "t", round(t, 2), "ratio top/bottom", round(ratio["ratio"], 3), "ci", [round(x, 3) for x in ratio["ci95"]], "->", out["verdict"])
    secs = log.close()
    trial_log("T3", "scripts/t3_cloud_cover.py", sha, out["verdict"], secs, "exploratory")


if __name__ == "__main__":
    main()
