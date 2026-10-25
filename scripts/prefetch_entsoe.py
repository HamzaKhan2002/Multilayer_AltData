"""Prefetch the ENTSO-E series used by T4 in parallel (cache in data/entsoe/, atomic writes). Downloads only; no statistic.

Usage: python scripts/prefetch_entsoe.py 2025 2024 2023 ...      (years, default: 2025 2024 2023 2022 2021)
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from altdata import entsoe_client as ec  # noqa: E402


def job(fn, year):
    t0 = time.time()
    try:
        fn(year)
        return f"{fn.__name__} {year} ok in {time.time() - t0:.0f}s"
    except Exception as e:  # noqa: BLE001
        return f"{fn.__name__} {year} FAILED: {str(e)[:200]}"


def main() -> None:
    years = [int(a) for a in sys.argv[1:]] or [2025, 2024, 2023, 2022, 2021]
    tasks = [(fn, y) for y in years for fn in (ec.day_ahead_prices, ec.wind_solar_forecast, ec.load_forecast)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for fut in [pool.submit(job, fn, y) for fn, y in tasks]:
            print(fut.result(), flush=True)


if __name__ == "__main__":
    main()
