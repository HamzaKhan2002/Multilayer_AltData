"""BS1 extraction (prereg/tests_v2.json): B04 + SCL windows of every Sentinel-2 acquisition, registration, roof-depth fit of every tank.

For each acquisition of results/v2/BS0/s2_catalog.csv with scene cloud cover <= 90%: read the red (B04, 10 m) and scene-classification
(SCL) windows of the Cushing window grown by 40 m, cache them in data/s2_tanks/<acq_id>.npz (resumable), estimate one translation against a
synthetic image of all registry disks (+-2 pixels, then parabola), and fit the roof depth of every tank with diameter >= 40 m
(src/altdata/tankshadow.py). Output: results/v2/BS1/fits.csv.gz (one row per acquisition x tank), acq_summary.csv, extract_status.json.

Usage: python scripts/bs1_extract.py            full run (resumable; fits are re-computed only if the model code changed)
       python scripts/bs1_extract.py --sanity   geometry check on 3 cached winter acquisitions: physical sun direction vs mirrored
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pyproj import Transformer  # noqa: E402

from altdata import sentinel  # noqa: E402
from altdata import tankshadow as ts  # noqa: E402
from altdata import v2common as V  # noqa: E402

PIPELINE = "bs1-v1"            # bump if the registration / clear-flag / abstention logic of this script changes
WORKERS = 5
VERSION = hashlib.sha256(Path(ts.__file__).read_bytes() + PIPELINE.encode()).hexdigest()[:10]
COLS = ["acq_id", "datetime_utc", "platform", "rel_orbit", "sun_elev", "sun_az", "shift_x_m", "shift_y_m", "shift_flag", "osm_id",
        "diameter_m", "clear", "n_pix", "d_hat", "d_lo", "d_hi", "a", "b", "sigma", "status", "rss_const_ratio"]
_PROJ, _SYN = {}, {}


def log(*parts) -> None:
    print(dt.datetime.now().strftime("%H:%M:%S"), *parts, flush=True)


def cache_file(acq_id: str) -> Path:
    return V.CACHE / f"{acq_id}.npz"


def fetch(r) -> str:
    """Download and cache the B04 + SCL window of one acquisition (atomic write); returns cached / downloaded."""
    p = cache_file(r.acq_id)
    if p.exists():
        return "cached"
    out = sentinel.read_s2_window(r.red_href, r.scl_href, V.WINDOW, pad_m=V.PAD_M)
    if out is None:
        raise RuntimeError("window not inside the raster")
    tmp = p.with_name(p.stem + ".part.npz")
    np.savez_compressed(tmp, red=out["red"], scl=out["scl"], transform=np.array(out["transform"]), crs=np.array(out["crs"]))
    os.replace(tmp, p)
    return "downloaded"


def load_cached(acq_id: str):
    with np.load(cache_file(acq_id), allow_pickle=False) as z:
        red, scl, tr, crs = z["red"], z["scl"], tuple(float(v) for v in z["transform"]), str(z["crs"])
    return red, scl, tr, crs


def project(crs: str, lon, lat):
    if crs not in _PROJ:
        _PROJ[crs] = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    return _PROJ[crs].transform(lon, lat)


def synthetic(reg: pd.DataFrame, X, Y, tr, shape):
    key = (tr, shape)
    if key not in _SYN:
        _SYN.clear()
        _SYN[key] = ts.coverage_image(X, Y, reg["R"].to_numpy(), shape, tr[2], tr[5])
    return _SYN[key]


def fit_acq(r, reg: pd.DataFrame, red, scl, tr, crs: str, mirror: bool = False):
    """Registration and per-tank fits of one acquisition. mirror=True flips the sun direction (geometry check only)."""
    if abs(tr[0] - 10.0) > 1e-6 or abs(tr[4] + 10.0) > 1e-6 or tr[1] != 0 or tr[3] != 0:
        raise ValueError(f"expected a north-up 10 m grid, got {tr}")
    x0, y0 = tr[2], tr[5]
    X, Y = project(crs, reg["lon"].to_numpy(), reg["lat"].to_numpy())
    S = synthetic(reg, X, Y, tr, red.shape)
    rg = ts.register(red.astype(float), S)
    sx, sy = rg["shift_x_m"], rg["shift_y_m"]
    bad = np.isin(scl, V.BAD_SCL)
    az = float(r.sun_az) + (180.0 if mirror else 0.0)
    base = {"acq_id": r.acq_id, "datetime_utc": r.datetime_utc, "platform": r.platform, "rel_orbit": r.rel_orbit,
            "sun_elev": float(r.sun_elev), "sun_az": float(r.sun_az), "shift_x_m": sx, "shift_y_m": sy, "shift_flag": rg["edge"]}
    rows, n_nodata = [], 0
    for k in np.flatnonzero(reg["big"].to_numpy()):
        R = float(reg["R"].iloc[k])
        cx, cy = float(X[k]) + sx, float(Y[k]) + sy
        clear = not ts.touches(bad, cx, cy, R + V.CLEAR_BUFFER_M, x0, y0)
        ri, ci, qx, qy = ts.block(cx, cy, R, x0, y0, red.shape)
        keep, F = ts.pixel_design(qx, qy, R, az, float(r.sun_elev))
        xv = red[ri[keep], ci[keep]].astype(float)
        nodata = bool((xv <= 0).any())
        n_nodata += nodata
        rec = {"osm_id": reg["osm_id"].iloc[k], "diameter_m": float(reg["diameter_m"].iloc[k]), "clear": bool(clear), "n_pix": int(xv.size),
               "d_hat": np.nan, "d_lo": np.nan, "d_hi": np.nan, "a": np.nan, "b": np.nan, "sigma": np.nan, "status": "few_pixels",
               "rss_const_ratio": np.nan}
        if xv.size >= ts.MIN_PIXELS and not nodata:
            if not clear:
                rec["status"] = "cloudy"
            else:
                f = ts.fit(xv, F)
                rec.update(d_hat=f["d_hat"], d_lo=f["lo"], d_hi=f["hi"], a=f["a"], b=f["b"], sigma=f["sigma"], status=f["status"],
                           rss_const_ratio=f["ratio"])
        rows.append({**base, **rec})
    df = pd.DataFrame(rows)[COLS].round({"shift_x_m": 3, "shift_y_m": 3, "d_hat": 3, "d_lo": 2, "d_hi": 2, "a": 2, "b": 2, "sigma": 3,
                                          "rss_const_ratio": 5, "sun_elev": 4, "sun_az": 4})
    area = np.pi * (df["diameter_m"] / 2) ** 2
    summ = {"acq_id": r.acq_id, "datetime_utc": r.datetime_utc, "platform": r.platform, "rel_orbit": int(r.rel_orbit),
            "sun_elev": float(r.sun_elev), "sun_az": float(r.sun_az), "cloud_cover": float(r.cloud_cover), "shift_x_m": round(sx, 3),
            "shift_y_m": round(sy, 3), "shift_flag": bool(rg["edge"]), "reg_corr": round(rg["corr"], 5), "reg_corr0": round(rg["corr0"], 5),
            "n_big": int(len(df)), "n_clear": int(df["clear"].sum()), "clear_area_share": float(area[df["clear"]].sum() / area.sum()),
            "n_fitted": int(df["status"].isin(V.KEPT + ("no_contrast",)).sum()), "n_nodata_tanks": int(n_nodata)}
    return df, summ


def process(r, reg: pd.DataFrame, parts: Path) -> None:
    red, scl, tr, crs = load_cached(r.acq_id)
    df, summ = fit_acq(r, reg, red, scl, tr, crs)
    tmp = parts / f"{r.acq_id}.part.csv.gz"
    df.to_csv(tmp, index=False)
    (parts / f"{r.acq_id}.json").write_text(json.dumps(summ), encoding="utf-8")
    os.replace(tmp, parts / f"{r.acq_id}.csv.gz")


def consolidate(cat: pd.DataFrame, parts: Path, out: Path) -> tuple[int, pd.DataFrame | None]:
    frames, sums = [], []
    for aid in cat["acq_id"]:
        f = parts / f"{aid}.csv.gz"
        if f.exists() and (parts / f"{aid}.json").exists():
            frames.append(pd.read_csv(f))
            sums.append(json.loads((parts / f"{aid}.json").read_text(encoding="utf-8")))
    if not frames:
        return 0, None
    fits = pd.concat(frames, ignore_index=True).sort_values(["datetime_utc", "osm_id"])
    out.mkdir(parents=True, exist_ok=True)
    fits.to_csv(out / "fits.csv.gz", index=False)
    pd.DataFrame(sums).sort_values("datetime_utc").to_csv(out / "acq_summary.csv", index=False)
    return len(frames), fits


def run(cat: pd.DataFrame, reg: pd.DataFrame, workers: int, sha: str) -> int:
    parts = V.CACHE / f"fits_{VERSION}"
    parts.mkdir(parents=True, exist_ok=True)
    todo = [r for r in cat.itertuples() if not (parts / f"{r.acq_id}.csv.gz").exists()]
    log(f"model version {VERSION}; {len(cat)} acquisitions with scene cloud <= {V.SCENE_CLOUD_MAX:.0f}%; {len(cat) - len(todo)} already fitted; "
        f"{sum(cache_file(r.acq_id).exists() for r in todo)} of the {len(todo)} to do already cached; {workers} download workers")
    t0, done, fails = time.time(), 0, {}

    def progress(final=False):
        el = (time.time() - t0) / 60
        rate = done / el if el > 0 else 0.0
        eta = (len(todo) - done) / rate if rate > 0 else float("nan")
        log(f"{done}/{len(todo)} acquisitions ({done / max(len(todo), 1):.0%}) | failed {len(fails)} | elapsed {el:.1f} min | "
            f"{rate:.1f} acq/min | ETA {eta:.1f} min" + (" | pass finished" if final else ""))

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch, r): r for r in todo}
        for fu in cf.as_completed(futs):
            r = futs[fu]
            try:
                fu.result()
                process(r, reg, parts)
            except Exception as e:  # noqa: BLE001  (recorded; the acquisition is retried once below and in the next run)
                fails[r.acq_id] = f"{type(e).__name__}: {str(e)[:300]}"
            done += 1
            if done % 10 == 0 or done == len(todo):
                progress(done == len(todo))
    for r in [x for x in todo if x.acq_id in fails]:               # one more attempt, sequentially, after a pause
        time.sleep(10)
        try:
            fetch(r)
            process(r, reg, parts)
            fails.pop(r.acq_id)
            log(f"retry succeeded: {r.acq_id}")
        except Exception as e:  # noqa: BLE001
            fails[r.acq_id] = f"{type(e).__name__}: {str(e)[:300]}"
            log(f"retry failed: {r.acq_id} {fails[r.acq_id]}")
    n_ok, _ = consolidate(cat, parts, V.BS1)
    pd.DataFrame([{"acq_id": k, "error": v} for k, v in fails.items()], columns=["acq_id", "error"]).to_csv(V.BS1 / "extract_failures.csv", index=False)
    status = {"model_version": VERSION, "prereg_v2_sha256": sha, "n_expected": int(len(cat)), "n_fitted": int(n_ok), "n_failed": int(len(fails)),
              "failed": sorted(fails), "finished_at": dt.datetime.now().isoformat(timespec="seconds"), "seconds": round(time.time() - t0, 1)}
    (V.BS1 / "extract_status.json").write_text(json.dumps(status, indent=1), encoding="utf-8")
    log(f"consolidated {n_ok}/{len(cat)} acquisitions -> results/v2/BS1/fits.csv.gz; failed {len(fails)}")
    return len(fails)


def sanity(cat: pd.DataFrame, reg: pd.DataFrame) -> int:
    """Geometry check on 3 cached winter acquisitions (sun elevation < 35 deg, lowest scene cloud cover, recent ESA processing)."""
    pool = cat[(cat["sun_elev"] < 35) & (cat["date"] >= "2023-11-01")].sort_values(["cloud_cover", "datetime_utc"])
    pick = list(pool.head(3).itertuples())
    lat_c, lon_c = (V.WINDOW[1] + V.WINDOW[3]) / 2, (V.WINDOW[0] + V.WINDOW[2]) / 2
    out, ratios = {"acquisitions": []}, {"phys": [], "mirror": []}
    san = V.CACHE / "sanity"
    san.mkdir(parents=True, exist_ok=True)
    for r in pick:
        log(f"{r.acq_id}: sun elev {r.sun_elev:.1f} az {r.sun_az:.1f} scene cloud {r.cloud_cover:.2f}% ({fetch(r)})")
        red, scl, tr, crs = load_cached(r.acq_id)
        phys, summ = fit_acq(r, reg, red, scl, tr, crs, mirror=False)
        mirr, _ = fit_acq(r, reg, red, scl, tr, crs, mirror=True)
        phys.to_csv(san / f"{r.acq_id}.csv.gz", index=False)
        (san / f"{r.acq_id}.json").write_text(json.dumps(summ), encoding="utf-8")
        fitted = phys["status"].isin(V.KEPT + ("no_contrast",)).to_numpy()
        rp, rm = phys["rss_const_ratio"].to_numpy()[fitted], mirr["rss_const_ratio"].to_numpy()[fitted]
        el_n, az_n = ts.solar_position(lat_c, lon_c, dt.datetime.fromisoformat(r.datetime_utc))
        ratios["phys"].append(rp)
        ratios["mirror"].append(rm)
        rec = {"acq_id": r.acq_id, "n_tanks_fitted": int(fitted.sum()), "median_ratio_physical": float(np.median(rp)),
               "median_ratio_mirrored": float(np.median(rm)), "share_physical_lower": float(np.mean(rp < rm)),
               "shift_x_m": summ["shift_x_m"], "shift_y_m": summ["shift_y_m"], "shift_flag": summ["shift_flag"], "reg_corr": summ["reg_corr"],
               "reg_corr_at_zero_shift": summ["reg_corr0"], "sun_stac": [round(float(r.sun_elev), 2), round(float(r.sun_az), 2)],
               "sun_noaa": [round(el_n, 2), round(az_n, 2)]}
        out["acquisitions"].append(rec)
        log(json.dumps(rec))
    P, M = np.concatenate(ratios["phys"]), np.concatenate(ratios["mirror"])
    out.update(n_tank_fits=int(P.size), median_ratio_physical=float(np.median(P)), median_ratio_mirrored=float(np.median(M)),
               share_physical_lower=float(np.mean(P < M)), passed=bool(np.median(P) < np.median(M)))
    (V.BS1 / "geometry_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    log(f"POOLED over {P.size} tank fits: median RSS ratio physical {np.median(P):.4f} vs mirrored {np.median(M):.4f}; "
        f"physical lower in {np.mean(P < M):.1%} of tanks; check {'PASSED' if out['passed'] else 'FAILED'}")
    return 0 if out["passed"] else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sanity", action="store_true")
    ap.add_argument("--workers", type=int, default=WORKERS)
    args = ap.parse_args()
    V.ensure_dirs()
    sha = V.assert_prereg_v2_frozen()
    cat = pd.read_csv(V.BS0 / "s2_catalog.csv")
    cat = cat[cat["cloud_cover"] <= V.SCENE_CLOUD_MAX].sort_values("datetime_utc").reset_index(drop=True)
    reg = V.registry()
    log(f"prereg_v2 sha256 {sha}; {int(reg['big'].sum())} tanks with diameter >= {V.MIN_DIAM:.0f} m of {len(reg)}")
    if args.sanity:
        return sanity(cat, reg)
    return 1 if run(cat, reg, args.workers, sha) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
