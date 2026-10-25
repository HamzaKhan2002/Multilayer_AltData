"""Secret loading. Values are returned to the caller and are never printed, logged or written."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Development inside the CV repository only: the parent .env uses "label: value" lines.
_PARENT_LABELS = {
    "AGSI_API_KEY": "AGSI+ API KEY",
    "ENTSOE_API_TOKEN": "ENTSO-E Restful API Token",
}


def _read_key_value(path: Path, name: str) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name and value.strip():
            return value.strip().strip("'\"")
    return None


def _read_labelled(path: Path, label: str) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip().lower() == label.lower() and value.strip():
            return value.strip()
    return None


def get_secret(name: str) -> str:
    """Environment variable, then multilayer-altdata/.env (KEY=VALUE), then the parent .env (label: value)."""
    value = os.environ.get(name) or _read_key_value(ROOT / ".env", name)
    if not value and name in _PARENT_LABELS:
        value = _read_labelled(ROOT.parent / ".env", _PARENT_LABELS[name])
    if not value:
        raise KeyError(f"secret {name} is not set (see .env.example)")
    return value


def mask(text: str, *names: str) -> str:
    """Replace any secret value found in text, so exceptions and URLs can be shown safely."""
    for n in names:
        try:
            v = get_secret(n)
        except KeyError:
            continue
        text = text.replace(v, "***")
    return text
