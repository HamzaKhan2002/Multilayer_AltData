"""Roof depth of an external floating-roof tank from the shadow of its own wall, at 10 m pixel scale (prereg/tests_v2.json, BS1).

Pure numpy, no I/O. Conventions: metres; x east, y north; sun azimuth phi clockwise from north, elevation theta; u = (sin phi, cos phi)
points toward the sun. A roof at depth d below the rim shifts the rim's shadow by s = d / tan(theta): a roof point q (relative to the
tank centre, |q| <= R) is lit iff |q + s u| <= R and in shadow otherwise (the crescent next to the sun-side wall).
Image convention (UTM rasters): row index grows southward, the centre of pixel (row, col) is x = x0 + (col + .5) pix and
y = y0 - (row + .5) pix, where (x0, y0) is the top-left corner of the window.
"""
from __future__ import annotations

import math

import numpy as np

PIX = 10.0                               # pixel size, m
NSUB = 10                                # sub-points per axis of one pixel: a 1 m sub-grid
D_GRID = np.arange(0.0, 20.0 + 1e-9, 0.5)  # roof depths below the rim, m
MIN_PIXELS = 8                           # fewer interior pixels: no estimate
MIN_INSIDE = 0.9                         # interior pixel: at least 90% of its sub-points inside the disk
CONTRAST_K = 3.0                         # d_hat > 0 needs a - b >= CONTRAST_K * sigma_hat
WIDE_M = 6.0                             # profile interval wider than this: kept, flagged low precision
RANK_TOL = 1e-6                          # (u, v) nearly collinear below this share: the split of a and b is not identified


def sun_unit(az_deg: float) -> np.ndarray:
    """Horizontal unit vector (east, north) pointing toward the sun; azimuth clockwise from north."""
    a = math.radians(az_deg)
    return np.array([math.sin(a), math.cos(a)])


def subgrid_offsets(pix: float = PIX, nsub: int = NSUB) -> tuple[np.ndarray, np.ndarray]:
    """(dx, dy) of the nsub x nsub sub-points of one pixel, relative to the pixel centre, flattened."""
    o = (np.arange(nsub) + 0.5) * pix / nsub - pix / 2
    ox, oy = np.meshgrid(o, o)
    return ox.ravel(), oy.ravel()


def shadow_mask(qx, qy, R: float, d: float, az_deg: float, elev_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """(inside, shadow) booleans for roof points (qx, qy) relative to the tank centre. shadow implies inside."""
    qx, qy = np.asarray(qx, float), np.asarray(qy, float)
    inside = qx * qx + qy * qy <= R * R
    s = d / math.tan(math.radians(max(elev_deg, 1.0)))
    u = sun_unit(az_deg)
    shadow = inside & ((qx + s * u[0]) ** 2 + (qy + s * u[1]) ** 2 > R * R)
    return inside, shadow


def block(cx: float, cy: float, rad: float, x0: float, y0: float, shape: tuple[int, int], pix: float = PIX):
    """Pixels whose squares can touch the disk (cx, cy, rad) in an image with top-left corner (x0, y0), clipped to the image.

    Returns flat arrays rows, cols and the pixel-centre offsets qx, qy from (cx, cy), in metres.
    """
    h, w = shape
    c_lo = max(int(math.floor((cx - rad - x0) / pix)), 0)
    c_hi = min(int(math.floor((cx + rad - x0) / pix)), w - 1)
    r_lo = max(int(math.floor((y0 - (cy + rad)) / pix)), 0)
    r_hi = min(int(math.floor((y0 - (cy - rad)) / pix)), h - 1)
    if c_hi < c_lo or r_hi < r_lo:
        e = np.zeros(0)
        return e.astype(int), e.astype(int), e, e
    rows, cols = np.meshgrid(np.arange(r_lo, r_hi + 1), np.arange(c_lo, c_hi + 1), indexing="ij")
    rows, cols = rows.ravel(), cols.ravel()
    return rows, cols, x0 + (cols + 0.5) * pix - cx, y0 - (rows + 0.5) * pix - cy


def pixel_design(qx, qy, R: float, az_deg: float, elev_deg: float, d_grid=D_GRID, pix: float = PIX, nsub: int = NSUB,
                 min_inside: float = MIN_INSIDE):
    """Interior pixels and their shadowed share for every depth of the grid.

    qx, qy: centres of the candidate pixels relative to the tank centre. Returns (keep, F): keep is the boolean mask of candidates with
    at least min_inside of their sub-points inside the disk; F[k, j] = (sub-points inside the disk and in shadow at depth d_grid[j]) / nsub^2
    for the k-th kept pixel. Computed with |q + s u|^2 = |q|^2 + 2 s (q . u) + s^2 for all depths at once.
    """
    qx, qy = np.asarray(qx, float), np.asarray(qy, float)
    ox, oy = subgrid_offsets(pix, nsub)
    X = qx[:, None] + ox[None, :]
    Y = qy[:, None] + oy[None, :]
    r2 = X * X + Y * Y
    inside = r2 <= R * R
    need = int(math.ceil(min_inside * nsub * nsub - 1e-9))
    keep = inside.sum(axis=1) >= need
    d_grid = np.asarray(d_grid, float)
    if not keep.any():
        return keep, np.zeros((0, d_grid.size))
    X, Y, r2, inside = X[keep], Y[keep], r2[keep], inside[keep]
    u = sun_unit(az_deg)
    s = d_grid / math.tan(math.radians(max(elev_deg, 1.0)))
    cross = X * u[0] + Y * u[1]
    r2s = r2[:, :, None] + 2.0 * cross[:, :, None] * s[None, None, :] + (s * s)[None, None, :]
    F = (inside[:, :, None] & (r2s > R * R)).sum(axis=1) / float(nsub * nsub)
    return keep, F


def profile(x, F):
    """Least squares of x = a (1 - F) + b F with b <= a, separately for each depth (column of F).

    If the unconstrained solution has b > a, or the design cannot separate a from b (all F equal), the constant fit a = b = mean(x) is used.
    Returns rss (per depth), a, b (per depth) and the residual sum of squares of the constant fit.
    """
    x = np.asarray(x, float)
    m = float(x.mean())
    xc = x - m                      # a and b shift by the same constant, so centring changes nothing but the conditioning
    u = 1.0 - F
    Suu = np.einsum("ij,ij->j", u, u)
    Svv = np.einsum("ij,ij->j", F, F)
    Suv = np.einsum("ij,ij->j", u, F)
    Sux, Svx = u.T @ xc, F.T @ xc
    det = Suu * Svv - Suv * Suv
    ok = det > RANK_TOL * Suu * Svv
    den = np.where(ok, det, 1.0)
    a = (Svv * Sux - Suv * Svx) / den
    b = (Suu * Svx - Suv * Sux) / den
    rss_const = float(xc @ xc)
    use = ok & (b <= a)
    rss = np.where(use, np.clip(rss_const - a * Sux - b * Svx, 0.0, rss_const), rss_const)
    return rss, np.where(use, a, 0.0) + m, np.where(use, b, 0.0) + m, rss_const


def classify(d_hat: float, lo: float, hi: float, a: float, b: float, sigma: float, wide_m: float = WIDE_M, k: float = CONTRAST_K) -> str:
    """Abstention and flag rules of the pre-registration, applied to a fitted tank (at least MIN_PIXELS interior pixels, clear)."""
    if d_hat > 0 and (a - b) < k * sigma:
        return "no_contrast"
    if d_hat <= 0:
        return "full_or_fixed"
    if hi - lo > wide_m:
        return "wide_interval"
    return "ok"


def fit(x, F, d_grid=D_GRID, min_pixels: int = MIN_PIXELS) -> dict:
    """Depth estimate of one tank on one date.

    x: values of the n interior pixels; F: their shadowed shares (n x depths). d_hat minimises the residual sum of squares over the grid;
    exact ties (identical shadow columns on the 1 m sub-grid, or a plateau when a single pixel carries the shadow) are resolved by the
    midpoint of the first run of tied depths, and "no depth beats the constant fit" gives d_hat = 0. sigma2 = RSS_min / (n - 3); the 68%
    interval is the hull of {d: RSS(d) - RSS_min <= sigma2}.
    Returns a dict with d_hat, lo, hi, a, b, sigma, n, rss, rss_const, ratio (= rss / rss_const), status and the profile.
    """
    x = np.asarray(x, float)
    n = int(x.size)
    out = {"n": n, "d_hat": np.nan, "lo": np.nan, "hi": np.nan, "a": np.nan, "b": np.nan, "sigma": np.nan, "rss": np.nan,
           "rss_const": np.nan, "ratio": np.nan, "status": "few_pixels", "profile": None}
    if n < min_pixels:
        return out
    d_grid = np.asarray(d_grid, float)
    rss, a, b, rss_const = profile(x, F)
    rmin = float(rss.min())
    tol = 1e-9 * rss_const + 1e-12
    if rss_const - rmin <= tol:                      # no depth explains more than a constant
        d_hat, j = float(d_grid[0]), 0
    else:
        tied = np.flatnonzero(rss <= rmin + tol)
        breaks = np.flatnonzero(np.diff(tied) != 1)
        run = tied[: breaks[0] + 1] if breaks.size else tied
        d_hat = float(d_grid[run].mean())
        j = int(run[int(np.argmin(np.abs(d_grid[run] - d_hat)))])
    sigma2 = rmin / (n - 3)
    inset = np.flatnonzero(rss - rmin <= sigma2 + tol)
    lo, hi, sigma = float(d_grid[inset[0]]), float(d_grid[inset[-1]]), math.sqrt(sigma2)
    out.update(d_hat=d_hat, lo=lo, hi=hi, a=float(a[j]), b=float(b[j]), sigma=sigma, rss=rmin, rss_const=rss_const,
               ratio=rmin / rss_const if rss_const > 0 else np.nan, profile=rss)
    out["status"] = classify(d_hat, lo, hi, out["a"], out["b"], sigma)
    return out


def render(qx, qy, R: float, d: float, az_deg: float, elev_deg: float, a: float, b: float, ground: float | None = None,
           offset=(0.0, 0.0), sigma: float = 0.0, rng=None, pix: float = PIX, nsub: int = NSUB) -> np.ndarray:
    """Pixel values of a synthetic tank: lit roof a, shadow b, outside the disk `ground` (default b).

    qx, qy: pixel centres relative to the nominal tank centre; the tank is really centred at `offset` from it (misregistration).
    Each pixel is the mean of an nsub x nsub sub-grid; N(0, sigma) noise is added if sigma > 0.
    """
    qx, qy = np.asarray(qx, float), np.asarray(qy, float)
    ox, oy = subgrid_offsets(pix, nsub)
    X = qx[:, None] + ox[None, :] - offset[0]
    Y = qy[:, None] + oy[None, :] - offset[1]
    inside, shadow = shadow_mask(X, Y, R, d, az_deg, elev_deg)
    g = b if ground is None else ground
    x = np.where(inside, np.where(shadow, b, a), g).mean(axis=1)
    if sigma > 0:
        x = x + (rng or np.random.default_rng()).normal(0.0, sigma, size=x.shape)
    return x


def coverage_image(cx, cy, R, shape: tuple[int, int], x0: float, y0: float, pix: float = PIX, nsub: int = NSUB) -> np.ndarray:
    """Share of each pixel covered by the union (sum, capped at 1) of the disks (cx, cy, R), on an image with top-left corner (x0, y0)."""
    img = np.zeros(shape)
    ox, oy = subgrid_offsets(pix, nsub)
    for xc, yc, r in zip(np.asarray(cx, float), np.asarray(cy, float), np.asarray(R, float)):
        rows, cols, qx, qy = block(xc, yc, r, x0, y0, shape, pix)
        if rows.size:
            X, Y = qx[:, None] + ox[None, :], qy[:, None] + oy[None, :]
            img[rows, cols] += ((X * X + Y * Y) <= r * r).mean(axis=1)
    return np.minimum(img, 1.0)


def register(img, S, search: int = 2, pix: float = PIX) -> dict:
    """Translation that best aligns the synthetic disk image S with the observed image.

    Integer shifts of S by (di rows, dj columns) in [-search, search] are scored by the Pearson correlation with the observed image over
    the same central pixels, then each axis is refined by a parabola through the peak and its two neighbours. A displaced S moves
    south by di and east by dj, so the disks appear at registry + (shift_x_m, shift_y_m) with x east, y north. edge is True if the integer
    peak lies on the search border (that axis is then not refined).
    """
    img, S = np.asarray(img, float), np.asarray(S, float)
    h, w = img.shape
    m = search
    a = img[m:h - m, m:w - m]
    a = a - a.mean()
    na = math.sqrt(float((a * a).sum()))
    C = np.full((2 * m + 1, 2 * m + 1), np.nan)
    for di in range(-m, m + 1):
        for dj in range(-m, m + 1):
            s = S[m - di:h - m - di, m - dj:w - m - dj]
            s = s - s.mean()
            nb = math.sqrt(float((s * s).sum()))
            if na > 0 and nb > 0:
                C[di + m, dj + m] = float((a * s).sum()) / (na * nb)
    if np.isnan(C).all():
        return {"shift_x_m": 0.0, "shift_y_m": 0.0, "edge": True, "corr": float("nan"), "corr0": float("nan")}
    i, j = np.unravel_index(np.nanargmax(C), C.shape)

    def refine(y0, y1, y2):
        den = y0 - 2 * y1 + y2
        return 0.0 if not (den < 0) else 0.5 * (y0 - y2) / den

    di_sub = (i - m) + (refine(C[i - 1, j], C[i, j], C[i + 1, j]) if 0 < i < 2 * m else 0.0)
    dj_sub = (j - m) + (refine(C[i, j - 1], C[i, j], C[i, j + 1]) if 0 < j < 2 * m else 0.0)
    return {"shift_x_m": float(dj_sub * pix), "shift_y_m": float(-di_sub * pix), "edge": bool(i in (0, 2 * m) or j in (0, 2 * m)),
            "corr": float(C[i, j]), "corr0": float(C[m, m])}


def touches(bad, cx: float, cy: float, rad: float, x0: float, y0: float, pix: float = PIX) -> bool:
    """True if any True pixel of the boolean image `bad` has its square intersecting the disk (cx, cy, rad)."""
    rows, cols, qx, qy = block(cx, cy, rad, x0, y0, bad.shape, pix)
    if rows.size == 0:
        return False
    dx = np.maximum(np.abs(qx) - pix / 2, 0.0)
    dy = np.maximum(np.abs(qy) - pix / 2, 0.0)
    near = dx * dx + dy * dy <= rad * rad
    return bool(bad[rows[near], cols[near]].any())


def solar_position(lat: float, lon: float, when) -> tuple[float, float]:
    """NOAA low-precision solar position (about 0.3 deg): (elevation, azimuth clockwise from north), in degrees, for a UTC datetime."""
    import datetime as dt

    t = when.astimezone(dt.timezone.utc) if getattr(when, "tzinfo", None) else when
    hour = t.hour + t.minute / 60 + (t.second + t.microsecond / 1e6) / 3600
    g = 2 * math.pi / 365 * (t.timetuple().tm_yday - 1 + (hour - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dec = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
           - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    ha = math.radians((hour * 60 + eqt + 4 * lon) / 4 - 180)     # hour angle, positive after solar noon
    la = math.radians(lat)
    east = -math.cos(dec) * math.sin(ha)
    north = math.sin(dec) * math.cos(la) - math.cos(dec) * math.sin(la) * math.cos(ha)
    up = math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha)
    return math.degrees(math.asin(max(-1.0, min(1.0, up)))), math.degrees(math.atan2(east, north)) % 360
