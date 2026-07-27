"""Load and write merox YAML configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INTERVAL = 3600
DEFAULT_FULL_SYNC_EVERY_HOURS = 168


@dataclass
class GitOutput:
    repo: Path
    user: str = "merox"
    email: str = "merox@localhost"


@dataclass
class MeroxConfig:
    interval: int = DEFAULT_INTERVAL
    api_key: str | None = None
    organizations: list[str] = field(default_factory=list)
    network_tags: list[str] = field(default_factory=list)
    incremental: bool = True
    full_sync_every_hours: int = DEFAULT_FULL_SYNC_EVERY_HOURS
    output: GitOutput = field(default_factory=lambda: GitOutput(repo=Path("./configs")))
    path: Path | None = None

    def resolve_api_key(self) -> str:
        key = (os.environ.get("MERAKI_DASHBOARD_API_KEY") or self.api_key or "").strip()
        if not key:
            raise SystemExit(
                "No Meraki API key found. Set MERAKI_DASHBOARD_API_KEY or api_key in config."
            )
        return key


def default_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "merox"
    return Path.home() / ".config" / "merox"


def default_config_path() -> Path:
    return default_config_dir() / "config.yml"


def example_config(repo: Path | None = None) -> dict[str, Any]:
    return {
        "interval": DEFAULT_INTERVAL,
        "api_key": None,
        "organizations": [],
        "network_tags": [],
        "incremental": True,
        "full_sync_every_hours": DEFAULT_FULL_SYNC_EVERY_HOURS,
        "output": {
            "git": {
                "repo": str(repo or (Path.home() / "merox-configs")),
                "user": "merox",
                "email": "merox@localhost",
            }
        },
    }


def load_config(path: Path | None = None) -> MeroxConfig:
    config_path = path or default_config_path()
    if not config_path.is_file():
        raise SystemExit(f"Config not found: {config_path}\nRun `merox init` first.")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    git_raw = (raw.get("output") or {}).get("git") or {}
    repo = Path(git_raw.get("repo") or "./configs").expanduser()

    return MeroxConfig(
        interval=int(raw.get("interval") or DEFAULT_INTERVAL),
        api_key=(raw.get("api_key") or None),
        organizations=[str(x) for x in (raw.get("organizations") or [])],
        network_tags=[str(x) for x in (raw.get("network_tags") or [])],
        incremental=bool(raw["incremental"]) if "incremental" in raw else True,
        full_sync_every_hours=int(
            raw.get("full_sync_every_hours") or DEFAULT_FULL_SYNC_EVERY_HOURS
        ),
        output=GitOutput(
            repo=repo,
            user=str(git_raw.get("user") or "merox"),
            email=str(git_raw.get("email") or "merox@localhost"),
        ),
        path=config_path,
    )


def write_example_config(path: Path, repo: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(example_config(repo), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
