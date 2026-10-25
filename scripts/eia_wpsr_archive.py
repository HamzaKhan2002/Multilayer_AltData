"""EIA Weekly Petroleum Status Report archive: release-date registry and first-release stock vintages.

Downloads the archive index and, for every release, the report page and csv/table4.csv into data/eia_wpsr_archive/
(0.5 s between requests, retries, files already cached are not fetched again). Table 4 prints stocks in million barrels with
three decimals; values are converted to thousand barrels. Week ending and release date are read from the report page,
then from the table header; the week ending is inferred only if neither is available.

Usage: python scripts/eia_wpsr_archive.py [--no-download] [--limit N]
Outputs: audit/eia_release_registry.csv, results/v2/eia_first_release.csv, data/eia_wpsr_archive/manifest.csv
Delete data/eia_wpsr_archive/archive/index.html to refresh the list of releases.
"""
import argparse
import csv
import datetime as dt
import hashlib
import html
import io
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "eia_wpsr_archive"
SITE = "https://www.eia.gov/petroleum/supply/weekly/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PAUSE = 0.5
HIDDEN = [("2011", "2011_07_27", "wpsr_2011_07_27.html")]  # not linked from the index; the 39 Wednesdays probed before it (2010-10-27..2011-07-20) returned 404
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LONG_DATE = r"([A-Z][a-z]+) (\d{1,2}), (\d{4})"
SHORT_DATE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\s*$")
LABELS = {"cushing": "cushing", "us_comm_crude": "commercial (excluding spr)", "gasoline": "total motor gasoline", "distillate": "distillate fuel oil"}


class Fetcher:
    def __init__(self, offline: bool = False):
        CACHE.mkdir(parents=True, exist_ok=True)
        self.offline, self.last, self.n_requests = offline, 0.0, 0
        self.session = requests.Session()
        self.session.headers.update(UA)
        self.manifest = CACHE / "manifest.csv"
        if self.manifest.exists():
            m = pd.read_csv(self.manifest)
            self.not_found = set(m.loc[m["status"] == 404, "url"])
        else:
            self.not_found = set()
            self.manifest.write_text("url,status,bytes,sha256,fetched_utc\n", encoding="utf-8")

    def _log(self, url: str, status: int, body: bytes) -> None:
        with open(self.manifest, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([url, status, len(body), hashlib.sha256(body).hexdigest(), dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")])

    def get(self, url: str, path: Path) -> bytes | None:
        """Cached body; None when the server answers 404 (or offline and not cached)."""
        if path.exists():
            return path.read_bytes()
        if self.offline or url in self.not_found:
            return None
        err = "unknown"
        for attempt in range(1, 5):
            time.sleep(max(0.0, PAUSE - (time.monotonic() - self.last)))
            try:
                r = self.session.get(url, timeout=60)
            except requests.RequestException as e:
                err = type(e).__name__
            else:
                self.n_requests += 1
                if r.status_code == 200 and r.content:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(r.content)
                    self._log(url, 200, r.content)
                    self.last = time.monotonic()
                    return r.content
                if r.status_code == 404:
                    self.not_found.add(url)
                    self._log(url, 404, b"")
                    self.last = time.monotonic()
                    return None
                err = f"HTTP {r.status_code}"
            self.last = time.monotonic()
            time.sleep(3 * attempt)
        raise RuntimeError(f"{url}: {err} after 4 attempts")


@dataclass(frozen=True)
class Release:
    year: str
    folder: str
    page: str
    in_index: bool

    @property
    def base(self) -> str:
        return f"archive/{self.year}/{self.folder}/"

    @property
    def page_url(self) -> str:
        return SITE + self.base + self.page

    @property
    def table_url(self) -> str:
        return SITE + self.base + "csv/table4.csv"

    @property
    def page_path(self) -> Path:
        return CACHE / self.base / self.page

    @property
    def table_path(self) -> Path:
        return CACHE / self.base / "csv" / "table4.csv"


def list_releases(index_html: bytes) -> list[Release]:
    found = re.findall(r'href="/petroleum/supply/weekly/archive/(\d{4})/([^/"]+)/(wpsr_[^"/]+\.(?:php|html))"', index_html.decode("utf-8", "replace"))
    rel = {(y, f, p): Release(y, f, p, True) for y, f, p in found}
    for y, f, p in HIDDEN:
        rel.setdefault((y, f, p), Release(y, f, p, False))
    return sorted(rel.values(), key=lambda r: r.folder)


def long_date(m: re.Match) -> dt.date:
    return dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()


def parse_page(raw: bytes | None) -> dict:
    out = {"week_ending": None, "release_date": None}
    if raw is None:
        return out
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw.decode("utf-8", "replace"), flags=re.S | re.I)
    t = re.sub(r"[\s\xa0]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    we = re.search(r"Data for week ending " + LONG_DATE, t)
    rd = re.search(r"Release Date: " + LONG_DATE, t) or re.search(r"Released: " + LONG_DATE, t)
    out["week_ending"] = long_date(we) if we else None
    out["release_date"] = long_date(rd) if rd else None
    return out


def short_date(s: str) -> dt.date | None:
    m = SHORT_DATE.match(s)
    if not m:
        return None
    y = int(m.group(3))
    return dt.date(y + 2000 if y < 100 else y, int(m.group(1)), int(m.group(2)))


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip().lower()


def to_kbbl(s: str) -> float:
    """Table 4 prints million barrels ('1,578.731'); returns thousand barrels or NaN for '--', blanks and replacement characters."""
    try:
        return float(round(float(s.replace(",", "").strip()) * 1000))
    except ValueError:
        return np.nan


def parse_table4(raw: bytes | None) -> dict | None:
    """Current and prior week dates from the header and the four stock rows (kbbl), or None if the file is not a table."""
    if raw is None or raw.lstrip()[:1] == b"<":
        return None
    rows = list(csv.reader(io.StringIO(raw.decode("cp1252", "replace"))))
    head = next((r for r in rows if len(r) >= 3 and short_date(r[1]) and short_date(r[2])), None)
    if head is None:
        return {"layout": "no date header", "ncols": len(rows[0]) if rows else 0}
    out = {"week_ending": short_date(head[1]), "prior_week_ending": short_date(head[2]), "ncols": len(head), "stub": head[0].strip(), "labels": {}}
    for r in rows:
        if len(r) < 3:
            continue
        for key, label in LABELS.items():
            if norm(r[0]) == label and key not in out["labels"]:
                out["labels"][key] = (to_kbbl(r[1]), to_kbbl(r[2]))
    return out


def infer_friday(release: dt.date) -> dt.date:
    k = (release.weekday() - 4) % 7
    return release - dt.timedelta(days=k if k >= 3 else k + 7)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    f = Fetcher(offline=args.no_download)
    index = f.get(SITE + "archive/", CACHE / "archive" / "index.html")
    if index is None:
        raise SystemExit("archive index is not cached")
    releases = list_releases(index)[: args.limit]
    print(f"{len(releases)} releases ({sum(not r.in_index for r in releases)} not linked from the index): {releases[0].folder} -> {releases[-1].folder}", flush=True)

    t0, rows, firsts, notes = time.time(), [], [], {"page_missing": 0, "table4_missing": 0, "table4_not_table": 0, "table4_no_header": 0}
    layouts, label_miss = {}, {k: 0 for k in LABELS}
    for i, rel in enumerate(releases, 1):
        page, tab = f.get(rel.page_url, rel.page_path), f.get(rel.table_url, rel.table_path)
        if i % 25 == 0 or i == len(releases):
            print(f"{i}/{len(releases)} {rel.folder} requests={f.n_requests} elapsed={time.time() - t0:.0f}s", flush=True)
        p, t4 = parse_page(page), parse_table4(tab)
        notes["page_missing"] += page is None
        notes["table4_missing"] += tab is None
        notes["table4_not_table"] += tab is not None and t4 is None
        notes["table4_no_header"] += t4 is not None and "labels" not in t4
        folder_date = dt.datetime.strptime(rel.folder[:10], "%Y_%m_%d").date()
        flags = []
        release = p["release_date"] or folder_date
        if p["release_date"] is None:
            flags.append("release date from folder name")
        elif not rel.folder.endswith("_data") and p["release_date"] != folder_date:
            flags.append(f"page release date {p['release_date']} differs from folder")
        if rel.folder.endswith("_data"):
            flags.append("data-only folder, released with a later report")
        we_t4 = t4.get("week_ending") if t4 else None
        if p["week_ending"] and we_t4 and p["week_ending"] != we_t4:
            flags.append(f"week ending differs: page {p['week_ending']} table4 {we_t4}")
        week, source = p["week_ending"], "page"
        if week is None:
            week, source = (we_t4, "table4") if we_t4 else (infer_friday(release), "inferred")
        if week.weekday() != 4:
            flags.append(f"week ending is a {WEEKDAYS[week.weekday()]}")
        rows.append({"release_date": release.isoformat(), "weekday": WEEKDAYS[release.weekday()], "week_ending_friday": week.isoformat(), "inferred": source == "inferred",
                     "source_url": rel.page_url, "week_ending_source": source, "in_index": rel.in_index, "note": "; ".join(flags)})
        if t4 and "labels" in t4:
            layouts[(t4["ncols"], t4["stub"])] = layouts.get((t4["ncols"], t4["stub"]), 0) + 1
            rec = {"release_date": release.isoformat(), "week_ending": (we_t4 or week).isoformat()}
            for key in LABELS:
                cur, prior = t4["labels"].get(key, (np.nan, np.nan))
                label_miss[key] += key not in t4["labels"]
                rec[f"{key}_kbbl"], rec[f"{key}_prior_kbbl"] = cur, prior
            rec["source_url"] = rel.table_url
            firsts.append(rec)

    reg = pd.DataFrame(rows).sort_values(["release_date", "week_ending_friday"])
    (ROOT / "audit").mkdir(exist_ok=True)
    reg.to_csv(ROOT / "audit" / "eia_release_registry.csv", index=False)
    cols = ["release_date", "week_ending", "cushing_kbbl", "cushing_prior_kbbl", "us_comm_crude_kbbl", "us_comm_crude_prior_kbbl", "gasoline_kbbl", "gasoline_prior_kbbl",
            "distillate_kbbl", "distillate_prior_kbbl", "source_url"]
    fr = pd.DataFrame(firsts)[cols].sort_values("week_ending")
    for c in cols[2:-1]:
        fr[c] = fr[c].round().astype("Int64")
    out = ROOT / "results" / "v2"
    out.mkdir(parents=True, exist_ok=True)
    fr.to_csv(out / "eia_first_release.csv", index=False)

    print(f"requests this run: {f.n_requests}; elapsed {time.time() - t0:.0f}s")
    print("registry rows:", len(reg), "| release_date", reg["release_date"].min(), "->", reg["release_date"].max(), "| inferred:", int(reg["inferred"].sum()),
          "| week ending source:", reg["week_ending_source"].value_counts().to_dict())
    print("weekday of release:", reg["weekday"].value_counts().to_dict())
    print("rows with notes:", int((reg["note"] != "").sum()))
    for n in reg.loc[reg["note"] != "", ["release_date", "note"]].itertuples(index=False):
        print("  ", n.release_date, n.note)
    print("table4 problems:", notes, "| layouts (ncols, stub):", layouts, "| label misses:", label_miss)
    print("first-release rows:", len(fr), "| first week", fr["week_ending"].min(), "| first release", fr["release_date"].min())


if __name__ == "__main__":
    main()
