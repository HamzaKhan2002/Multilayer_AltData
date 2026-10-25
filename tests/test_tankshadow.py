"""Checks of the tank-shadow model on synthetic tanks (no real image, no EIA value is read). Run: pytest tests/test_tankshadow.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import datetime as dt  # noqa: E402

import numpy as np  # noqa: E402

from altdata import tankshadow as ts  # noqa: E402

R, THETA, PHI = 30.0, 30.0, 155.0
CENTRES = [(0.0, 0.0), (2.5, -3.1), (-4.2, 1.7), (4.9, 4.9), (-1.3, -4.8)]   # tank centre relative to a pixel centre, m


def lattice(centre, half=6):
    k = np.arange(-half, half + 1) * ts.PIX
    gx, gy = np.meshgrid(k, k)
    return gx.ravel() - centre[0], gy.ravel() - centre[1]


def run_fit(d, centre, az=PHI, elev=THETA, nsub_truth=ts.NSUB, ground=1000.0, sigma=0.0, rng=None):
    qx, qy = lattice(centre)
    keep, F = ts.pixel_design(qx, qy, R, az, elev)
    x = ts.render(qx, qy, R, d, az, elev, 1000.0, 300.0, ground=ground, sigma=sigma, rng=rng, nsub=nsub_truth)[keep]
    return ts.fit(x, F), keep


def test_recovers_depth_noise_free_same_discretisation():
    for centre in CENTRES:
        for d in (2.0, 6.0, 10.0, 14.0):
            res, _ = run_fit(d, centre)
            j = int(np.argmin(np.abs(ts.D_GRID - d)))
            assert res["profile"][j] < 1e-6 * res["rss_const"], (centre, d)      # the true depth is a minimiser
            assert abs(res["d_hat"] - d) <= 0.5, (centre, d, res["d_hat"])
            assert res["lo"] <= d <= res["hi"]


def test_recovers_depth_with_finer_truth():
    # truth rendered on a 0.25 m sub-grid, the model uses the pre-registered 1 m sub-grid
    for centre in CENTRES:
        for d in (2.0, 6.0, 10.0, 14.0):
            res, _ = run_fit(d, centre, nsub_truth=40)
            assert abs(res["d_hat"] - d) <= 0.5, (centre, d, res["d_hat"])


def test_shadow_is_on_the_sun_side():
    # |q + s u| > R and |q| <= R imply q.u > -s/2: the crescent lies on the sun side of that line, its tips wrap to y = +s/2 at most
    g = np.arange(-29.5, 30.0, 1.0)
    gx, gy = np.meshgrid(g, g)
    for az, axis, sign in ((180.0, 1, -1), (0.0, 1, 1), (90.0, 0, 1), (270.0, 0, -1)):
        inside, shadow = ts.shadow_mask(gx, gy, R, 6.0, az, 30.0)
        assert shadow.any() and not (shadow & ~inside).any()
        coord = sign * (gx, gy)[axis][shadow]
        s = 6.0 / np.tan(np.radians(30.0))
        assert (coord > -s / 2).all(), (az, coord.min())
        assert coord.mean() > 0 and (coord > 0).mean() > 0.8, (az, coord.mean(), (coord > 0).mean())
    inside, shadow = ts.shadow_mask(gx, gy, R, 6.0, 180.0, 30.0)      # sun due south: the shadow centroid has negative y
    assert gy[shadow].mean() < 0 and np.abs(gx[shadow].mean()) < 1e-9
    # sun due south: the pixel design puts its shadow share in the south (negative y)
    qx, qy = lattice((0.0, 0.0))
    keep, F = ts.pixel_design(qx, qy, R, 180.0, 30.0)
    j = int(np.argmin(np.abs(ts.D_GRID - 6.0)))
    assert (F[:, j] * qy[keep]).sum() < 0 and abs((F[:, j] * qx[keep]).sum()) < 1e-9


def test_no_shadow_at_zero_depth():
    g = np.arange(-29.5, 30.0, 1.0)
    gx, gy = np.meshgrid(g, g)
    _, shadow = ts.shadow_mask(gx, gy, R, 0.0, PHI, THETA)
    assert not shadow.any()
    qx, qy = lattice((1.0, 2.0))
    keep, F = ts.pixel_design(qx, qy, R, PHI, THETA)
    assert np.all(F[:, 0] == 0.0)
    res, _ = run_fit(0.0, (1.0, 2.0))
    assert res["d_hat"] == 0.0 and res["status"] == "full_or_fixed"


def test_shadow_width_grows_with_depth_and_low_sun():
    g = np.arange(-29.5, 30.0, 1.0)
    gx, gy = np.meshgrid(g, g)
    areas = [ts.shadow_mask(gx, gy, R, d, PHI, THETA)[1].sum() for d in (2, 6, 10, 14)]
    assert all(b > a for a, b in zip(areas, areas[1:]))
    assert ts.shadow_mask(gx, gy, R, 6.0, PHI, 20.0)[1].sum() > ts.shadow_mask(gx, gy, R, 6.0, PHI, 50.0)[1].sum()


def test_interior_pixel_rule():
    qx, qy = lattice((0.0, 0.0))
    keep, F = ts.pixel_design(qx, qy, R, PHI, THETA)
    assert F.shape == (int(keep.sum()), ts.D_GRID.size)
    ox, oy = ts.subgrid_offsets()
    inside = ((qx[:, None] + ox) ** 2 + (qy[:, None] + oy) ** 2 <= R * R).mean(axis=1)
    assert np.array_equal(keep, inside >= 0.9 - 1e-12)


def test_reverse_contrast_is_not_fitted_as_a_shadow():
    qx, qy = lattice((1.0, -2.0))
    keep, F = ts.pixel_design(qx, qy, R, PHI, THETA)
    x = ts.render(qx, qy, R, 8.0, PHI, THETA, 300.0, 1000.0, ground=300.0)[keep]    # the "shadow" is brighter than the lit roof
    res = ts.fit(x, F)
    assert res["d_hat"] == 0.0 and res["status"] == "full_or_fixed"


def test_few_pixels_and_rules():
    res = ts.fit(np.arange(7.0), np.zeros((7, ts.D_GRID.size)))
    assert res["status"] == "few_pixels" and np.isnan(res["d_hat"])
    assert ts.classify(5.0, 4.0, 6.0, 100.0, 90.0, 10.0) == "no_contrast"      # a - b = 10 < 3 * 10
    assert ts.classify(5.0, 4.0, 6.0, 100.0, 60.0, 10.0) == "ok"
    assert ts.classify(5.0, 2.0, 9.0, 100.0, 60.0, 10.0) == "wide_interval"    # 7 m > 6 m
    assert ts.classify(0.0, 0.0, 3.0, 100.0, 100.0, 10.0) == "full_or_fixed"
    assert ts.classify(5.0, 2.0, 8.0, 100.0, 60.0, 10.0) == "ok"              # exactly 6 m is not wider than 6 m
    assert ts.classify(5.0, 1.5, 8.0, 100.0, 60.0, 10.0) == "wide_interval"
    assert ts.classify(5.0, 1.5, 8.0, 100.0, 90.0, 10.0) == "no_contrast"     # no contrast takes precedence over a wide interval


def test_noisy_fit_interval_covers_truth_most_of_the_time():
    rng = np.random.default_rng(7)
    hit = tot = 0
    for _ in range(150):
        centre = tuple(rng.uniform(-5, 5, 2))
        d = float(rng.choice([4.0, 8.0, 12.0]))
        res, _ = run_fit(d, centre, sigma=40.0, rng=rng)
        tot += 1
        hit += res["lo"] <= d <= res["hi"]
    assert hit / tot > 0.55            # nominal 68%, the 1 m model discretisation and edge pixels cost some coverage


def test_registration_recovers_translation_and_flags_edge():
    rng = np.random.default_rng(3)
    shape, x0, y0 = (120, 140), 500000.0, 4000000.0
    cx = x0 + rng.uniform(100, 1300, 25)
    cy = y0 - rng.uniform(100, 1100, 25)
    rad = rng.uniform(20, 40, 25)
    S = ts.coverage_image(cx, cy, rad, shape, x0, y0)
    for sx, sy in ((7.3, -4.1), (0.0, 0.0), (-12.0, 9.0), (13.2, 3.2)):
        img = 3000.0 * ts.coverage_image(cx + sx, cy + sy, rad, shape, x0, y0) + 500.0 + rng.normal(0, 60, shape)
        reg = ts.register(img, S)
        assert abs(reg["shift_x_m"] - sx) < 2.5 and abs(reg["shift_y_m"] - sy) < 2.5, (sx, sy, reg)
        assert not reg["edge"]
    img = 3000.0 * ts.coverage_image(cx + 30.0, cy, rad, shape, x0, y0) + rng.normal(0, 60, shape)
    assert ts.register(img, S)["edge"]


def test_touches_uses_the_disk_plus_buffer():
    bad = np.zeros((40, 40), bool)
    x0, y0 = 0.0, 400.0
    bad[20, 30] = True                          # pixel square x in [300, 310), y in (190, 200]
    cx, cy = 250.0, 195.0
    assert not ts.touches(bad, cx, cy, 30.0, x0, y0)       # nearest point is 50 m away
    assert ts.touches(bad, cx, cy, 30.0 + 20.0, x0, y0)    # disk plus 20 m buffer reaches x = 300
    assert not ts.touches(bad, cx, cy, 49.0, x0, y0)


def test_row_index_grows_southward():
    x0, y0 = 1000.0, 5000.0
    rows, cols, qx, qy = ts.block(1055.0, 4945.0, 12.0, x0, y0, (100, 100))
    k = np.flatnonzero((rows == 5) & (cols == 5))[0]       # pixel (5, 5) centre = (1055, 4945)
    assert qx[k] == 0.0 and qy[k] == 0.0
    north = np.flatnonzero((rows == 4) & (cols == 5))[0]   # one row up = 10 m to the north
    assert qy[north] == 10.0


def test_solar_position_sanity():
    # equinox, solar noon at lon 0: sun due south at elevation 90 - lat
    el, az = ts.solar_position(40.0, 0.0, dt.datetime(2025, 3, 20, 12, 5, tzinfo=dt.timezone.utc))
    assert abs(el - 50.0) < 1.5 and abs(az - 180.0) < 3.0
    # morning at 36N, winter: sun in the south-east, i.e. azimuth between 90 and 180
    el, az = ts.solar_position(35.94, -96.74, dt.datetime(2026, 1, 15, 15, 30, tzinfo=dt.timezone.utc))
    assert 0 < el < 30 and 100 < az < 170
