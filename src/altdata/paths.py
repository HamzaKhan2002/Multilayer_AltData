"""Project paths and the guard on the frozen pre-registration."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
PREREG = ROOT / "prereg" / "tests_v1.json"
PREREG_SHA256 = "66bec92f8383607c1777e3d69c23aa8abd25efa1f90bead18fc9f22615f1cbbe"

for _p in (DATA, RESULTS, FIGURES):
    _p.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_prereg_frozen() -> str:
    """Return the pre-registration hash, or stop if the file differs from the frozen version."""
    h = sha256_file(PREREG)
    if h != PREREG_SHA256:
        raise RuntimeError("prereg/tests_v1.json differs from the frozen version; log the change in results/deviations.md")
    return h
