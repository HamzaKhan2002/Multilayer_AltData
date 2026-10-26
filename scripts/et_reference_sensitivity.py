"""Post hoc sensitivity of BS0 and BS2 to the time zone of the Friday stock reference (no new test, no stored result touched).

The EIA survey instructions (Forms EIA-800, EIA-803, EIA-804) put the stock reference at 7 a.m. Eastern Time on Friday; the frozen
protocol (prereg/tests_v2.json) used 07:00 America/Chicago. The BS0 availability and the BS2 hub test are recomputed with both
references in scratch folders, and the differences are written to results/v3/et_reference_sensitivity.json.

    python scripts/et_reference_sensitivity.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

from altdata import v2common as V  # noqa: E402
import bs1_analysis as B1  # noqa: E402
import bs2_aggregate as B2  # noqa: E402

OUT = ROOT / "results" / "v3" / "et_reference_sensitivity.json"
_CT = V.ref_time_utc


def _ref_et(friday) -> pd.Timestamp:
    d = pd.Timestamp(friday)
    return pd.Timestamp(d.year, d.month, d.day, 7, tz="America/New_York").tz_convert("UTC")


def main() -> None:
    fits, summ, cat = V.read_fits(), V.read_acq_summary(), V.read_s2_catalog()
    s1 = pd.read_csv(V.BS0 / "s1_catalog.csv")
    eia = V.eia_weekly()
    sha = V.assert_prereg_v2_frozen()
    out: dict[str, dict] = {}
    selected: dict[str, list] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn in (("ct_frozen_protocol", _CT), ("et_eia_instructions", _ref_et)):
            V.ref_time_utc = fn
            d = Path(tmp) / name
            d.mkdir(parents=True, exist_ok=True)
            av = B1.availability(cat, summ, s1, eia.index, d)
            res = B2.run(fits, summ, eia, d / "bs2", sha)
            sel = B2.select_weekly(summ, B2.analysis_weeks(eia))
            selected[name] = sel["acq_id"].fillna("").tolist()
            out[name] = {
                "bs0_share_of_weeks": av["share_of_weeks"],
                "n_weeks": av["n_weeks"],
                "bs2_primary": {k: res["primary"][k] for k in ("n", "r", "fisher_ci95", "verdict")},
                "bs2_all_season": {k: res["secondary"]["all_season"][k] for k in ("n", "r", "fisher_ci95")},
                "n_weeks_with_selected_acquisition": res["n_weeks_with_selected_acquisition"],
                "n_weeks_with_dV": res["n_weeks_with_dV"],
            }
    V.ref_time_utc = _CT
    a, b = (selected[k] for k in ("ct_frozen_protocol", "et_eia_instructions"))
    ct, et = out["ct_frozen_protocol"], out["et_eia_instructions"]
    result = {
        "id": "ET_reference_sensitivity",
        "scope": "post hoc documentation check; not a pre-registered test; stored BS0/BS2 results are unchanged",
        "prereg_v2_sha256": sha,
        "reason": "EIA-800/803/804 instructions: stocks as of 7 a.m. Eastern Time Friday; the frozen protocol used 07:00 America/Chicago",
        "weeks_with_a_different_selected_acquisition": sum(1 for x, y in zip(a, b) if x != y),
        "identical_bs0": ct["bs0_share_of_weeks"] == et["bs0_share_of_weeks"],
        "identical_bs2_primary": ct["bs2_primary"] == et["bs2_primary"],
        "identical_bs2_all_season": ct["bs2_all_season"] == et["bs2_all_season"],
        **out,
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("weeks_with_a_different_selected_acquisition", "identical_bs0", "identical_bs2_primary", "identical_bs2_all_season")}))


if __name__ == "__main__":
    main()
