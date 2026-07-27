"""Deterministic JSON helpers for stable Git diffs."""

from __future__ import annotations

import json
import re
from typing import Any


_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slugify(value: str, fallback: str = "unnamed") -> str:
    text = (value or "").strip()
    if not text:
        return fallback
    text = _UNSAFE.sub("_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("._")
    return text or fallback


def normalize(data: Any) -> Any:
    """Recursively sort dict keys and leave lists in API order."""
    if isinstance(data, dict):
        return {key: normalize(data[key]) for key in sorted(data)}
    if isinstance(data, list):
        return [normalize(item) for item in data]
    return data


def dumps(data: Any) -> str:
    return json.dumps(normalize(data), indent=2, ensure_ascii=False) + "\n"


def write_json(path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(data), encoding="utf-8")
