"""Export docs/spec/spec.html to an A4 PDF with headless Edge or Chrome (same engine as the deck).

Usage: python docs/spec/export_spec.py [--commit HASH]
    --commit HASH   replace the COMMIT_HASH placeholder in a temporary copy of the HTML (the source keeps the placeholder
                    only until the hash is written into it; if the source already holds a hash, nothing is replaced)
Output: docs/spec/Borel_I1_Research_Technical_Specification.pdf
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "spec.html"
PDF = HERE / "Borel_I1_Research_Technical_Specification.pdf"
CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def browser() -> str:
    for c in CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("msedge", "chrome", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit("Edge or Chrome not found")


def main() -> None:
    html = SRC
    tmp = None
    if "--commit" in sys.argv:
        commit = sys.argv[sys.argv.index("--commit") + 1]
        text = SRC.read_text(encoding="utf-8")
        if "COMMIT_HASH" in text:
            tmp = HERE / "_spec_export.html"
            tmp.write_text(text.replace("COMMIT_HASH", commit), encoding="utf-8")
            html = tmp
    try:
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=20000",
                        f"--print-to-pdf={PDF}", html.as_uri()], check=True, capture_output=True, timeout=180)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
    print(f"wrote {PDF.relative_to(HERE.parents[1]).as_posix()} ({PDF.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
