"""Sentinel-2 L2A through the Element 84 Earth Search STAC (anonymous) with windowed reads of cloud-optimised GeoTIFFs.

Attribution: Contains modified Copernicus Sentinel data [year of the scene].
"""
from __future__ import annotations

import time

import numpy as np
import rasterio
from pystac_client import Client
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
GDAL_ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff", "GDAL_HTTP_MAX_RETRY": "4",
            "GDAL_HTTP_RETRY_DELAY": "2"}
SCL_CLOUD = (3, 8, 9, 10)  # cloud shadow, cloud medium / high probability, thin cirrus


def search(bbox, start: str, end: str, collection: str = "sentinel-2-l2a", min_cloud=None, max_cloud=None, limit: int = 400):
    """STAC items intersecting bbox (lon_min, lat_min, lon_max, lat_max) between two dates, filtered on scene-level cloud cover."""
    query = {}
    if min_cloud is not None:
        query.setdefault("eo:cloud_cover", {})["gte"] = min_cloud
    if max_cloud is not None:
        query.setdefault("eo:cloud_cover", {})["lte"] = max_cloud
    client = Client.open(EARTH_SEARCH)
    res = client.search(collections=[collection], bbox=list(bbox), datetime=f"{start}/{end}", query=query or None, max_items=limit)
    return sorted(res.items(), key=lambda it: it.datetime)


def read_window(href: str, bbox, retries: int = 3):
    """Read the window covering bbox (WGS84) from a COG. Returns (array bands x h x w, transform, crs), or None if the
    dataset does not fully contain the window."""
    for attempt in range(retries):
        try:
            env = {k: v for k, v in GDAL_ENV.items() if not (k == "CPL_VSIL_CURL_ALLOWED_EXTENSIONS" and "?" in href)}
            with rasterio.Env(**env), rasterio.open(href) as ds:
                b = transform_bounds("EPSG:4326", ds.crs, *bbox)
                win = from_bounds(*b, transform=ds.transform).round_offsets().round_lengths()
                full = Window(0, 0, ds.width, ds.height)
                if win.col_off < 0 or win.row_off < 0 or win.col_off + win.width > full.width or win.row_off + win.height > full.height:
                    return None
                return ds.read(window=win), ds.window_transform(win), ds.crs
        except rasterio.errors.RasterioIOError:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def local_cloud_fraction(item, bbox) -> float | None:
    """Share of the window classified as cloud, cloud shadow or cirrus in the scene classification (SCL, 20 m)."""
    out = read_window(item.assets["scl"].href, bbox)
    if out is None:
        return None
    scl = out[0][0]
    valid = scl != 0
    return float(np.isin(scl, SCL_CLOUD)[valid].mean()) if valid.any() else None


def true_colour(item, bbox):
    """8-bit RGB image (h x w x 3) of the window from the visual (TCI, 10 m) asset, plus the affine transform."""
    out = read_window(item.assets["visual"].href, bbox)
    if out is None:
        return None
    arr, transform, crs = out
    return np.moveaxis(arr[:3], 0, -1), transform, crs


PLANETARY = "https://planetarycomputer.microsoft.com/api/stac/v1"


def search_s1_rtc(bbox, start: str, end: str):
    """Sentinel-1 radiometrically terrain-corrected scenes (10 m, VV and VH) from Microsoft Planetary Computer, signed anonymously."""
    import planetary_computer as pc

    client = Client.open(PLANETARY, modifier=pc.sign_inplace)
    res = client.search(collections=["sentinel-1-rtc"], bbox=list(bbox), datetime=f"{start}/{end}", max_items=100)
    return sorted(res.items(), key=lambda it: it.datetime)


def backscatter_db(item, bbox, pol: str = "vv"):
    """Backscatter in dB (gamma-nought, linear power converted with 10 log10) for the window; non-positive values become NaN."""
    out = read_window(item.assets[pol].href, bbox)
    if out is None:
        return None
    arr, transform, crs = out
    x = arr[0].astype("float32")
    x[x <= 0] = np.nan
    return 10 * np.log10(x), transform, crs


# ---- additions for the pre-registered BS tests (prereg/tests_v2.json): full pagination and aligned B04 + SCL windows ----

def _retry(fn, tries: int = 4, wait: float = 3.0):
    for k in range(tries):
        try:
            return fn()
        except Exception:  # noqa: BLE001  (network / API hiccups; the last error is re-raised)
            if k == tries - 1:
                raise
            time.sleep(wait * (k + 1))


def search_all(bbox, start: str, end: str, collection: str = "sentinel-2-l2a"):
    """All STAC items intersecting bbox between two instants, following every result page (no item cap)."""
    def go():
        res = Client.open(EARTH_SEARCH).search(collections=[collection], bbox=list(bbox), datetime=f"{start}/{end}", max_items=None, limit=100)
        return sorted(res.items(), key=lambda it: it.datetime)
    return _retry(go)


def search_s1_rtc_all(bbox, start: str, end: str):
    """All Sentinel-1 RTC items of Planetary Computer intersecting bbox between two instants (signed anonymously, no item cap)."""
    import planetary_computer as pc

    def go():
        res = Client.open(PLANETARY, modifier=pc.sign_inplace).search(collections=["sentinel-1-rtc"], bbox=list(bbox),
                                                                      datetime=f"{start}/{end}", max_items=None, limit=100)
        return sorted(res.items(), key=lambda it: it.datetime)
    return _retry(go)


def pad_bbox(bbox, metres: float):
    """WGS84 bbox grown by `metres` on every side (small-extent approximation, good to a few centimetres at 6 km)."""
    lon0, lat0, lon1, lat1 = bbox
    dlat = metres / 111_320.0
    dlon = metres / (111_320.0 * np.cos(np.radians((lat0 + lat1) / 2)))
    return (lon0 - dlon, lat0 - dlat, lon1 + dlon, lat1 + dlat)


def read_s2_window(red_href: str, scl_href: str, bbox, pad_m: float = 40.0, retries: int = 4):
    """B04 (10 m) and the scene classification (SCL, 20 m, each pixel repeated 2 x 2 onto the 10 m grid) for bbox grown by pad_m metres.

    Both arrays cover exactly the same pixels. Returns {"red": uint16 (h, w), "scl": uint8 (h, w), "transform": (a, b, c, d, e, f),
    "crs": str}, or None if bbox itself (without the pad) is not fully inside the red raster; the pad is clipped at the raster edge.
    Row index increases southward: the centre of pixel (row, col) is x = c + (col + 0.5) a, y = f + (row + 0.5) e with e = -10.
    """
    for attempt in range(retries):
        try:
            with rasterio.Env(**GDAL_ENV):
                with rasterio.open(red_href) as ds:
                    b = transform_bounds("EPSG:4326", ds.crs, *bbox)
                    f0 = from_bounds(*b, transform=ds.transform)
                    if f0.col_off < 0 or f0.row_off < 0 or f0.col_off + f0.width > ds.width or f0.row_off + f0.height > ds.height:
                        return None                      # the window itself is not inside the raster
                    f = from_bounds(b[0] - pad_m, b[1] - pad_m, b[2] + pad_m, b[3] + pad_m, transform=ds.transform)
                    c0, r0 = max(int(np.floor(f.col_off)), 0), max(int(np.floor(f.row_off)), 0)          # the pad is clipped at the raster edge
                    c1, r1 = min(int(np.ceil(f.col_off + f.width)), ds.width), min(int(np.ceil(f.row_off + f.height)), ds.height)
                    win = Window(c0, r0, c1 - c0, r1 - r0)
                    red = ds.read(1, window=win)
                    tr, crs = ds.window_transform(win), ds.crs.to_string()
                h, w = red.shape
                x0, y0 = tr.c, tr.f
                with rasterio.open(scl_href) as ds2:
                    s = ds2.transform                    # 20 m grid, aligned with the 10 m grid of the tile
                    p = s.a
                    k0, q0 = int(np.floor((x0 - s.c) / p + 1e-6)), int(np.floor((s.f - y0) / p + 1e-6))
                    k1, q1 = int(np.ceil((x0 + 10 * w - s.c) / p - 1e-6)), int(np.ceil((s.f - (y0 - 10 * h)) / p - 1e-6))
                    scl20 = ds2.read(1, window=Window(k0, q0, k1 - k0, q1 - q0))
                up = np.repeat(np.repeat(scl20, 2, axis=0), 2, axis=1)
                oc, orow = int(round((x0 - (s.c + k0 * p)) / 10)), int(round(((s.f - q0 * p) - y0) / 10))
                scl = up[orow:orow + h, oc:oc + w]
                if scl.shape != red.shape:
                    raise ValueError(f"SCL window {scl.shape} does not match B04 window {red.shape}")
                return {"red": red, "scl": scl.astype(np.uint8), "transform": (tr.a, tr.b, tr.c, tr.d, tr.e, tr.f), "crs": crs}
        except (OSError, rasterio.errors.RasterioError):
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
