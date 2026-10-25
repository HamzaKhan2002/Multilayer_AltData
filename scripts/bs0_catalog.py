"""BS0 (prereg/tests_v2.json): Sentinel-2 and Sentinel-1 catalogues over the Cushing window, collection choice, processing latency.

Steps: (1) Earth Search, full pagination, collections sentinel-2-l2a and sentinel-2-c1-l2a, 2018-12-01..2026-10-24; keep items whose
footprint contains the window; (2) choose the collection from the catalogue only (more distinct acquisition dates), de-duplicate by
(date, platform, relative orbit); (3) Planetary Computer sentinel-1-rtc, same window and dates; (4) publication latency of recent
Sentinel-2 L2A products of tile T14SQE from the Copernicus Data Space OData catalogue.
The availability matrix needs tank-level clear flags and is computed by scripts/bs1_analysis.py after the extraction.

Usage: python scripts/bs0_catalog.py
Outputs: results/v2/BS0/s2_catalog.csv, s1_catalog.csv, latency.json, catalog_summary.json, s2_items_both_collections.csv.gz
"""
import json
import re
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
from shapely.geometry import box, shape  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from altdata import sentinel  # noqa: E402
from altdata import v2common as V  # noqa: E402
from altdata.tankshadow import solar_position  # noqa: E402

COLLECTIONS = ("sentinel-2-l2a", "sentinel-2-c1-l2a")
ODATA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
LAT_C, LON_C = (V.WINDOW[1] + V.WINDOW[3]) / 2, (V.WINDOW[0] + V.WINDOW[2]) / 2


def s2_rows(items, collection: str) -> pd.DataFrame:
    win = box(*V.WINDOW)
    rows = []
    for it in items:
        p = it.properties
        poly = shape(it.geometry)
        contains = bool(poly.contains(win))
        m = re.search(r"_R(\d{3})_", p.get("s2:product_uri") or "")
        rel = int(m.group(1)) if m else p.get("sat:relative_orbit")
        az, el, src = p.get("view:sun_azimuth"), p.get("view:sun_elevation"), "stac"
        if az is None or el is None:
            el, az = solar_position(LAT_C, LON_C, it.datetime)
            src = "noaa"
        code = p.get("proj:epsg") or str(p.get("proj:code", "")).replace("EPSG:", "")
        rows.append({
            "item_id": it.id, "collection": collection, "datetime_utc": it.datetime.isoformat(), "date": it.datetime.date().isoformat(),
            "platform": p.get("platform"), "rel_orbit": rel if rel is not None else -1, "proc_baseline": p.get("s2:processing_baseline"),
            "sun_elev": el, "sun_az": az, "sun_source": src, "view_incidence": p.get("view:incidence_angle"),
            "view_azimuth": p.get("view:azimuth"), "cloud_cover": p.get("eo:cloud_cover"), "tile": p.get("grid:code"),
            "epsg": int(code) if str(code).isdigit() else -1, "contains_window": contains,
            "margin_deg": float(poly.boundary.distance(win)) if contains else 0.0, "product_uri": p.get("s2:product_uri"),
            "red_href": it.assets["red"].href if "red" in it.assets else None, "scl_href": it.assets["scl"].href if "scl" in it.assets else None})
    return pd.DataFrame(rows)


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """One item per (date, platform, relative orbit): prefer EPSG:32614, then the tile with the window farthest from the footprint
    edge, then the newest processing baseline, then the highest item id (latest reprocessing)."""
    d = df[df["contains_window"]].copy()
    key = ["date", "platform", "rel_orbit"]
    d["zone14"] = d["epsg"] == 32614
    d["n_candidates"] = d.groupby(key)["item_id"].transform("size")
    d = d.sort_values(key + ["zone14", "margin_deg", "proc_baseline", "item_id"], ascending=[True, True, True, False, False, False, False])
    return d.drop_duplicates(key, keep="first").sort_values("datetime_utc").reset_index(drop=True)


def counts(df: pd.DataFrame) -> dict:
    c = df[df["contains_window"]]
    acq = c.drop_duplicates(["date", "platform", "rel_orbit"])
    return {"n_items_intersecting": int(len(df)), "n_items_containing_window": int(len(c)), "n_distinct_dates": int(c["date"].nunique()),
            "n_acquisitions_date_platform_orbit": int(len(acq)), "first_date": c["date"].min() if len(c) else None,
            "last_date": c["date"].max() if len(c) else None,
            "acquisitions_per_year": {str(k): int(v) for k, v in acq.groupby(acq["date"].str[:4]).size().items()},
            "platforms": {str(k): int(v) for k, v in acq["platform"].value_counts().items()},
            "tiles_among_containing_items": {str(k): int(v) for k, v in c["tile"].value_counts().items()}}


def s1_catalog() -> tuple[pd.DataFrame, dict]:
    items = sentinel.search_s1_rtc_all(V.WINDOW, V.CAT_START, V.CAT_END)
    win = box(*V.WINDOW)
    rows = []
    for it in items:
        p = it.properties
        rows.append({"item_id": it.id, "datetime_utc": it.datetime.isoformat(), "date": it.datetime.date().isoformat(),
                     "platform": str(p.get("platform")).lower(), "orbit_state": p.get("sat:orbit_state"), "rel_orbit": p.get("sat:relative_orbit"),
                     "geom": shape(it.geometry), "contains": shape(it.geometry).contains(win)})
    df = pd.DataFrame(rows)
    if df.empty:
        return df, {"n_items_intersecting": 0}
    g = []
    for (date, plat, rel, state), sub in df.groupby(["date", "platform", "rel_orbit", "orbit_state"], dropna=False):
        g.append({"datetime_utc": sub["datetime_utc"].min(), "date": date, "platform": plat, "orbit_state": state, "rel_orbit": rel,
                  "n_items": int(len(sub)), "covers_window": bool(unary_union(list(sub["geom"])).contains(win))})
    out = pd.DataFrame(g).sort_values("datetime_utc").reset_index(drop=True)
    cov = out[out["covers_window"]]
    summ = {"n_items_intersecting": int(len(df)), "n_acquisitions_date_platform_orbit": int(len(out)),
            "n_acquisitions_covering_window": int(len(cov)), "n_distinct_dates_covering_window": int(cov["date"].nunique()),
            "first_date": cov["date"].min() if len(cov) else None, "last_date": cov["date"].max() if len(cov) else None,
            "acquisitions_per_year": {str(k): int(v) for k, v in cov.groupby(cov["date"].str[:4]).size().items()},
            "platforms": {str(k): int(v) for k, v in cov["platform"].value_counts().items()},
            "orbit_states": {str(k): int(v) for k, v in cov["orbit_state"].value_counts().items()}}
    return out, summ


def latency(tile: str = "T14SQE", start: str = "2026-01-01", end: str = "2026-10-20") -> dict:
    """Hours from the start of sensing to the publication time of Sentinel-2 L2A products of one tile (Copernicus Data Space OData)."""
    flt = (f"Collection/Name eq 'SENTINEL-2' and contains(Name,'{tile}') and contains(Name,'MSIL2A') "
           f"and ContentDate/Start gt {start}T00:00:00.000Z and ContentDate/Start lt {end}T00:00:00.000Z")
    recs, skip = [], 0
    while True:
        for k in range(4):
            try:
                r = requests.get(ODATA, params={"$filter": flt, "$orderby": "ContentDate/Start asc", "$top": 1000, "$skip": skip}, timeout=90)
                r.raise_for_status()
                break
            except requests.RequestException:
                if k == 3:
                    raise
                time.sleep(5 * (k + 1))
        page = r.json().get("value", [])
        recs += page
        if len(page) < 1000:
            break
        skip += 1000
    df = pd.DataFrame([{"name": x["Name"], "sensing_start": x["ContentDate"]["Start"], "published": x["PublicationDate"]} for x in recs])
    out = {"source": ODATA, "filter": flt, "tile": tile, "sensing_start_range": [start, end], "n_products": int(len(df))}
    if df.empty:
        return out
    h = ((pd.to_datetime(df["published"], utc=True) - pd.to_datetime(df["sensing_start"], utc=True)).dt.total_seconds() / 3600).to_numpy()
    df["latency_h"] = h
    out.update({"latency_hours": {"median": float(np.median(h)), "p90": float(np.percentile(h, 90)), "max": float(h.max()),
                                  "min": float(h.min()), "share_le_24h": float((h <= 24).mean()), "share_le_48h": float((h <= 48).mean())},
                "definition": "PublicationDate - ContentDate.Start of each MSIL2A product of the tile",
                "products": [{"name": a, "sensing_start": b, "published": c, "latency_h": round(float(d), 3)}
                             for a, b, c, d in zip(df["name"], df["sensing_start"], df["published"], h)]})
    return out


def main() -> None:
    V.ensure_dirs()
    sha = V.assert_prereg_v2_frozen()
    t0 = time.time()
    print(f"prereg_v2 sha256 {sha}", flush=True)
    both, per = [], {}
    for col in COLLECTIONS:
        t1 = time.time()
        items = sentinel.search_all(V.WINDOW, V.CAT_START, V.CAT_END, col)
        df = s2_rows(items, col)
        per[col] = counts(df)
        both.append(df)
        print(f"{col}: {len(items)} items intersect, {per[col]['n_items_containing_window']} contain the window, "
              f"{per[col]['n_distinct_dates']} distinct dates, {per[col]['n_acquisitions_date_platform_orbit']} acquisitions ({time.time() - t1:.0f}s)", flush=True)
    allitems = pd.concat(both, ignore_index=True)
    ranked = sorted(COLLECTIONS, key=lambda c: (per[c]["n_distinct_dates"], per[c]["n_acquisitions_date_platform_orbit"]), reverse=True)
    chosen = ranked[0]
    rule = "more distinct acquisition dates among items containing the window (tie: more (date, platform, orbit) acquisitions)"
    cat = dedupe(allitems[allitems["collection"] == chosen])
    cat = cat.rename(columns={"item_id": "acq_id"})
    cols = ["acq_id", "collection", "datetime_utc", "date", "platform", "rel_orbit", "proc_baseline", "sun_elev", "sun_az", "sun_source",
            "view_incidence", "view_azimuth", "cloud_cover", "tile", "epsg", "n_candidates", "red_href", "scl_href", "product_uri"]
    cat[cols].to_csv(V.BS0 / "s2_catalog.csv", index=False)
    chosen_keys = set(cat["acq_id"])
    allitems.assign(selected=allitems["item_id"].isin(chosen_keys)).drop(columns=["red_href", "scl_href"]).to_csv(
        V.BS0 / "s2_items_both_collections.csv.gz", index=False)
    print(f"chosen {chosen}: {len(cat)} acquisitions after de-duplication; sun angles from {cat['sun_source'].value_counts().to_dict()}", flush=True)

    s1, s1_summ = s1_catalog()
    s1.to_csv(V.BS0 / "s1_catalog.csv", index=False)
    print(f"Sentinel-1 RTC: {s1_summ}", flush=True)

    lat = latency()
    (V.BS0 / "latency.json").write_text(json.dumps(lat, indent=1), encoding="utf-8")
    print("latency:", {k: v for k, v in lat.items() if k in ("n_products", "latency_hours")}, flush=True)

    summary = {"prereg_v2_sha256": sha, "window_wgs84": V.WINDOW, "period": [V.CAT_START, V.CAT_END], "collections": per,
               "chosen_collection": chosen, "choice_rule": rule, "ranking": ranked,
               "s2_acquisitions_after_dedup": int(len(cat)), "s2_acquisitions_cloud_le_90": int((cat["cloud_cover"] <= V.SCENE_CLOUD_MAX).sum()),
               "s2_tiles_selected": {str(k): int(v) for k, v in cat["tile"].value_counts().items()},
               "s2_sun_angle_source": {str(k): int(v) for k, v in cat["sun_source"].value_counts().items()},
               "sentinel1": s1_summ, "latency_hours": lat.get("latency_hours"), "latency_n_products": lat.get("n_products"),
               "tie_break_after_zone14": "window farthest from the item footprint edge, then newest processing baseline, then highest item id",
               "seconds": round(time.time() - t0, 1)}
    (V.BS0 / "catalog_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(f"done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
