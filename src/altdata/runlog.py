"""Run logging: timestamped log files in results/ and an append-only trial log."""
from __future__ import annotations

import csv
import datetime as dt
import time
from pathlib import Path

from .paths import RESULTS


class RunLog:
    def __init__(self, name: str):
        self.name = name
        self.t0 = time.time()
        self.path = RESULTS / f"{name}.log"
        self._f = open(self.path, "w", encoding="utf-8")
        self(f"start {name}")

    def __call__(self, *parts) -> None:
        line = f"{dt.datetime.now().isoformat(timespec='seconds')} " + " ".join(str(p) for p in parts)
        print(line, flush=True)
        self._f.write(line + "\n")
        self._f.flush()

    def close(self) -> float:
        elapsed = time.time() - self.t0
        self(f"done in {elapsed:.1f}s")
        self._f.close()
        return elapsed


def append_coverage(heading: str, body: str) -> None:
    """Add (or replace) a '## heading' section at the end of results/coverage.md."""
    path = RESULTS / "coverage.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# Coverage audit\n"
    marker = f"## {heading}"
    if marker in text:
        head, _, rest = text.partition(marker)
        nxt = rest.find("\n## ")
        text = head.rstrip() + "\n" + (rest[nxt + 1:] if nxt >= 0 else "")
    path.write_text(text.rstrip() + f"\n\n{marker}\n\n{body.strip()}\n", encoding="utf-8")


def trial_log(test_id: str, script: str, prereg_sha256: str, verdict: str, seconds: float, note: str = "") -> None:
    path = RESULTS / "trial_log.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["id", "timestamp", "script", "prereg_sha256", "verdict", "seconds", "note"])
        w.writerow([test_id, dt.datetime.now().isoformat(timespec="seconds"), script, prereg_sha256, verdict, f"{seconds:.1f}", note])
