"""Compare multilayer-altdata.zip with the current multilayer-altdata folder.

Usage: python audit/snapshot_diff.py
The zip is only read. It is extracted to %TEMP%\\mla_zip; data/, __pycache__/, audit/ and results/v2/ are ignored on both sides.
Writes audit/snapshot_diff.md.
"""
import datetime as dt
import difflib
import hashlib
import os
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT.parent / "multilayer-altdata.zip"
EXTRACT = Path(os.environ["TEMP"]) / "mla_zip"
OUT = ROOT / "audit" / "snapshot_diff.md"
CREATED_BY_AUDIT = {"scripts/eia_wpsr_archive.py", "scripts/baseline_cushing_ar2.py"}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def ignored(rel: PurePosixPath) -> bool:
    return rel.parts[0] in {"data", "audit"} or "__pycache__" in rel.parts or rel.parts[:2] == ("results", "v2")


def tree(base: Path) -> dict[str, Path]:
    out = {}
    for p in sorted(base.rglob("*")):
        if p.is_file():
            rel = PurePosixPath(p.relative_to(base).as_posix())
            if not ignored(rel):
                out[str(rel)] = p
    return out


def is_text(b: bytes) -> bool:
    if b"\x00" in b[:8192]:
        return False
    try:
        b.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def clip(s: str, n: int = 80) -> str:
    s = s.strip().replace("|", "\\|")
    return s if len(s) <= n else s[: n - 1] + "..."


def describe(a: bytes, b: bytes) -> str:
    """One line: what differs between the zip copy (a) and the folder copy (b)."""
    if not (is_text(a) and is_text(b)):
        return f"binary files differ ({len(a)} vs {len(b)} bytes)"
    ta, tb = a.decode("utf-8"), b.decode("utf-8")
    ea = "CRLF" if b"\r\n" in a else "LF"
    eb = "CRLF" if b"\r\n" in b else "LF"
    la, lb = ta.splitlines(), tb.splitlines()
    if la == lb:
        return f"line endings only (zip {ea}, folder {eb})" if ea != eb else "trailing newline only"
    d = [x for x in difflib.unified_diff(la, lb, lineterm="", n=0) if not x.startswith(("---", "+++", "@@"))]
    add, dele = sum(x.startswith("+") for x in d), sum(x.startswith("-") for x in d)
    first_del = next((x[1:] for x in d if x.startswith("-")), "")
    first_add = next((x[1:] for x in d if x.startswith("+")), "")
    hunks = sum(1 for x in difflib.unified_diff(la, lb, lineterm="", n=0) if x.startswith("@@"))
    eol = "" if ea == eb else f"; line endings zip {ea}, folder {eb}"
    return f"{len(la)} -> {len(lb)} lines, +{add}/-{dele} in {hunks} hunk(s); first: `{clip(first_del)}` -> `{clip(first_add)}`{eol}"


def stamp(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    zip_bytes = ZIP.read_bytes()
    zip_sha = sha(zip_bytes)
    if EXTRACT.exists():
        shutil.rmtree(EXTRACT)
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(EXTRACT)
        member_times = {i.filename.removeprefix("multilayer-altdata/"): dt.datetime(*i.date_time) for i in z.infolist() if not i.is_dir()}
        n_members = sum(not i.is_dir() for i in z.infolist())
        env_files = [i.filename for i in z.infolist() if not i.is_dir() and Path(i.filename).name.startswith(".env") and Path(i.filename).name != ".env.example"]
    zt, ft = tree(EXTRACT / "multilayer-altdata"), tree(ROOT)
    only_zip, only_dir = sorted(set(zt) - set(ft)), sorted(set(ft) - set(zt))
    both = sorted(set(zt) & set(ft))
    same, diff = [], []
    for r in both:
        a, b = zt[r].read_bytes(), ft[r].read_bytes()
        (same if a == b else diff).append((r, a, b))

    L = ["# Snapshot diff: multilayer-altdata.zip vs current folder", "",
         f"- Zip: `{ZIP.relative_to(ROOT.parent)}`, {ZIP.stat().st_size:,} bytes, modified {stamp(ZIP.stat().st_mtime)}, {n_members} files (single top-level folder `multilayer-altdata/`)",
         f"- Zip SHA-256: `{zip_sha}`",
         f"- Zip member timestamps: {min(member_times.values()):%Y-%m-%d %H:%M} to {max(member_times.values()):%Y-%m-%d %H:%M}",
         f"- `.env` files in the zip (other than `.env.example`): {', '.join(env_files) if env_files else 'none'}",
         f"- Folder: `{ROOT.name}/` (not under version control)",
         "- Ignored on both sides: `data/`, `__pycache__/`, `audit/`, `results/v2/`",
         f"- Compared files: {len(zt)} in the zip, {len(ft)} in the folder; identical SHA-256: {len(same)}; different: {len(diff)}; only in the zip: {len(only_zip)}; only in the folder: {len(only_dir)}", ""]
    L += ["## Only in the zip", ""] + ([f"- `{r}` ({zt[r].stat().st_size:,} bytes)" for r in only_zip] or ["none"]) + [""]
    L += ["## Only in the folder", ""]
    for r in only_dir:
        tag = " (created by this audit)" if r in CREATED_BY_AUDIT else ""
        L.append(f"- `{r}` ({ft[r].stat().st_size:,} bytes, modified {stamp(ft[r].stat().st_mtime)}){tag}")
    L += ([] if only_dir else ["none"]) + [""]
    L += ["## Different SHA-256", ""]
    if diff:
        L += ["| file | zip SHA-256 | folder SHA-256 | zip member time | folder mtime | difference |", "|---|---|---|---|---|---|"]
        for r, a, b in diff:
            L.append(f"| `{r}` | `{sha(a)[:12]}` | `{sha(b)[:12]}` | {member_times[r]:%Y-%m-%d %H:%M} | {stamp(ft[r].stat().st_mtime)} | {describe(a, b)} |")
    else:
        L.append("none")
    L.append("")
    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(f"zip sha256 {zip_sha}")
    print(f"zip files {len(zt)} folder files {len(ft)} identical {len(same)} different {len(diff)} only_zip {len(only_zip)} only_folder {len(only_dir)}")
    for r in only_zip:
        print("only in zip:", r)
    for r in only_dir:
        print("only in folder:", r)
    for r, a, b in diff:
        print("differs:", r, "|", describe(a, b)[:160])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
