"""Persisted sync watermarks for incremental changelog mode."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def state_path(tree: Path) -> Path:
    return tree / ".merox" / "state.json"


def load_state(tree: Path) -> dict[str, Any]:
    path = state_path(tree)
    if not path.is_file():
        return {"orgs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"orgs": {}}
    if not isinstance(data, dict):
        return {"orgs": {}}
    orgs = data.get("orgs")
    if not isinstance(orgs, dict):
        data["orgs"] = {}
    return data


def save_state(tree: Path, state: dict[str, Any]) -> None:
    path = state_path(tree)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
