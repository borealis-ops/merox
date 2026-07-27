"""Command-line interface for merox."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from merox import __version__
from merox.config import (
    default_config_path,
    load_config,
    write_example_config,
)
from merox.fetch import backup_once
from merox.git_out import commit_if_changed, working_tree_root


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_init(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser() if args.config else default_config_path()
    repo = Path(args.repo).expanduser() if args.repo else (Path.home() / "merox-configs")

    if config_path.exists() and not args.force:
        print(f"Config already exists: {config_path}", file=sys.stderr)
        print("Pass --force to overwrite.", file=sys.stderr)
        return 1

    write_example_config(config_path, repo=repo)
    cfg = load_config(config_path)
    working_tree_root(cfg.output)
    print(f"Wrote {config_path}")
    print(f"Git repo: {cfg.output.repo}")
    print("Set MERAKI_DASHBOARD_API_KEY (recommended) or api_key in the config, then run:")
    print("  merox run")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser() if args.config else None
    cfg = load_config(config_path)
    tree = working_tree_root(cfg.output)
    log = logging.getLogger("merox")
    force_full = bool(getattr(args, "full", False))
    mode = "full" if force_full or not cfg.incremental else "incremental"
    log.info("Writing backup into %s (%s)", tree, mode)
    stats = backup_once(cfg, tree, force_full=force_full)
    message = (
        f"merox: {stats['organizations']} orgs, "
        f"{stats['networks']} networks, {stats['devices']} devices "
        f"(full={stats['full']} incr={stats['incremental']} skip={stats['skipped']})"
    )
    committed = commit_if_changed(cfg.output, message)
    if committed:
        log.info("Committed: %s", message)
    else:
        log.info("No configuration changes detected")
    log.info(
        "Wrote %s files (%s orgs / %s networks / %s devices; full=%s incr=%s skip=%s)",
        stats["files"],
        stats["organizations"],
        stats["networks"],
        stats["devices"],
        stats["full"],
        stats["incremental"],
        stats["skipped"],
    )
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser() if args.config else None
    cfg = load_config(config_path)
    log = logging.getLogger("merox")
    interval = max(60, int(args.interval or cfg.interval))
    log.info("Daemon mode; interval=%ss", interval)
    while True:
        try:
            cmd_run(args)
        except SystemExit as exc:
            if exc.code not in (0, None):
                log.error("Run failed with exit %s; will retry", exc.code)
        except Exception:  # noqa: BLE001
            log.exception("Run failed; will retry after interval")
        time.sleep(interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="merox",
        description="Oxidized-like Meraki Dashboard configuration backup to Git",
    )
    parser.add_argument("--version", action="version", version=f"merox {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "-c",
        "--config",
        help="Path to config.yml (default: ~/.config/merox/config.yml)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser(
        "init", parents=[shared], help="Create config and Git backup repo"
    )
    init_p.add_argument("--repo", help="Path for the Git working tree")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing config")
    init_p.set_defaults(func=cmd_init)

    run_p = sub.add_parser("run", parents=[shared], help="Run one backup cycle")
    run_p.add_argument(
        "--full",
        action="store_true",
        help="Force a full org/network/device pull (ignore changelog)",
    )
    run_p.set_defaults(func=cmd_run)

    daemon_p = sub.add_parser(
        "daemon", parents=[shared], help="Run backup cycles on an interval"
    )
    daemon_p.add_argument(
        "--interval",
        type=int,
        help="Seconds between runs (default: config interval)",
    )
    daemon_p.set_defaults(func=cmd_daemon)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
