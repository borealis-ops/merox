"""Fetch Meraki Dashboard configs into a working tree."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import meraki

from merox.changelog import ChangePlan, plan_from_changes
from merox.config import MeroxConfig
from merox.endpoints import (
    DEVICE_ENDPOINTS,
    NETWORK_ENDPOINTS,
    ORG_ENDPOINTS,
    device_family,
)
from merox.normalize import slugify, write_json
from merox.state import load_state, parse_ts, save_state, utc_now_iso

log = logging.getLogger("merox")


def _call(dashboard: Any, scope: str, operation: str, *args: Any, **kwargs: Any) -> Any:
    api = getattr(dashboard, scope)
    method = getattr(api, operation)
    return method(*args, **kwargs)


def _safe_call(dashboard: Any, scope: str, operation: str, *args: Any, **kwargs: Any) -> Any | None:
    try:
        return _call(dashboard, scope, operation, *args, **kwargs)
    except meraki.APIError as exc:
        if getattr(exc, "status", None) in {400, 403, 404}:
            log.debug("%s skipped (%s): %s", operation, exc.status, exc)
            return None
        log.warning("%s failed: %s", operation, exc)
        return None
    except Exception as exc:  # noqa: BLE001 — keep a full run going
        log.warning("%s failed: %s", operation, exc)
        return None


def _filter_networks(networks: list[dict], tags: list[str]) -> list[dict]:
    if not tags:
        return networks
    wanted = set(tags)
    return [n for n in networks if wanted.intersection(set(n.get("tags") or []))]


def _org_matches(org: dict, selectors: list[str]) -> bool:
    if not selectors:
        return True
    org_id = str(org.get("id") or "")
    name = str(org.get("name") or "")
    return org_id in selectors or name in selectors


def _rm_tree(path: Path) -> None:
    if not path.exists():
        return
    if path.is_file():
        path.unlink()
        return
    for child in path.iterdir():
        _rm_tree(child)
    path.rmdir()


def _write_org_endpoints(
    dashboard: Any,
    org: dict,
    org_dir: Path,
    stats: dict[str, int],
) -> None:
    org_id = str(org["id"])
    for file_stem, scope, operation in ORG_ENDPOINTS:
        if operation == "getOrganization":
            data = org
        elif operation in {
            "getOrganizationNetworks",
            "getOrganizationDevices",
            "getOrganizationInventoryDevices",
        }:
            data = _safe_call(dashboard, scope, operation, org_id, total_pages="all")
        else:
            data = _safe_call(dashboard, scope, operation, org_id)
        if data is None:
            continue
        write_json(org_dir / f"{file_stem}.json", data)
        stats["files"] += 1


def _write_network(
    dashboard: Any,
    network: dict,
    org_dir: Path,
    stats: dict[str, int],
) -> Path:
    net_id = str(network["id"])
    net_slug = slugify(str(network.get("name") or net_id), fallback=net_id)
    net_dir = org_dir / "networks" / net_slug
    # Drop previous files for this network folder so removed endpoints disappear.
    if net_dir.exists():
        for child in list(net_dir.iterdir()):
            if child.is_file():
                child.unlink()
    write_json(net_dir / "network.json", network)
    stats["files"] += 1
    stats["networks"] += 1

    products = set(network.get("productTypes") or [])
    for file_stem, scope, operation, product_filter in NETWORK_ENDPOINTS:
        if product_filter is not None and not products.intersection(product_filter):
            continue
        data = _safe_call(dashboard, scope, operation, net_id)
        if data is None:
            continue
        write_json(net_dir / f"{file_stem}.json", data)
        stats["files"] += 1
    return net_dir


def _write_device(
    dashboard: Any,
    device: dict,
    net_dir: Path,
    stats: dict[str, int],
) -> None:
    serial = str(device.get("serial") or "").strip()
    if not serial:
        return
    model = str(device.get("model") or "")
    family = device_family(model)
    name = str(device.get("name") or serial)
    dev_slug = slugify(f"{name}_{serial}", fallback=serial)
    dev_dir = net_dir / "devices" / dev_slug
    if dev_dir.exists():
        _rm_tree(dev_dir)
    write_json(dev_dir / "device.json", device)
    stats["files"] += 1
    stats["devices"] += 1

    for file_stem, scope, operation, want_family in DEVICE_ENDPOINTS:
        if want_family != "*" and want_family != family:
            continue
        data = _safe_call(dashboard, scope, operation, serial)
        if data is None:
            continue
        write_json(dev_dir / f"{file_stem}.json", data)
        stats["files"] += 1


def _backup_org_full(
    dashboard: Any,
    org: dict,
    org_dir: Path,
    network_tags: list[str],
    stats: dict[str, int],
) -> None:
    if org_dir.exists():
        _rm_tree(org_dir)
    org_dir.mkdir(parents=True, exist_ok=True)
    stats["organizations"] += 1
    log.info("Full backup: organization %s (%s)", org.get("name"), org["id"])
    _write_org_endpoints(dashboard, org, org_dir, stats)

    org_id = str(org["id"])
    networks = _safe_call(
        dashboard, "organizations", "getOrganizationNetworks", org_id, total_pages="all"
    ) or []
    networks = _filter_networks(networks, network_tags)
    devices = _safe_call(
        dashboard, "organizations", "getOrganizationDevices", org_id, total_pages="all"
    ) or []
    devices_by_net: dict[str, list[dict]] = {}
    for device in devices:
        net_id = str(device.get("networkId") or "")
        devices_by_net.setdefault(net_id, []).append(device)

    for network in networks:
        net_dir = _write_network(dashboard, network, org_dir, stats)
        for device in devices_by_net.get(str(network["id"]), []):
            _write_device(dashboard, device, net_dir, stats)


def _fetch_changes(
    dashboard: Any,
    org_id: str,
    t0: str,
    t1: str,
) -> list[dict[str, Any]]:
    data = _safe_call(
        dashboard,
        "organizations",
        "getOrganizationConfigurationChanges",
        org_id,
        t0=t0,
        t1=t1,
        total_pages="all",
    )
    if not data:
        return []
    return list(data)


def _needs_full_sync(
    org_state: dict[str, Any],
    cfg: MeroxConfig,
    force_full: bool,
) -> bool:
    if force_full or not cfg.incremental:
        return True
    last = parse_ts(org_state.get("last_sync_ts"))
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - last
    return age >= timedelta(hours=max(1, cfg.full_sync_every_hours))


def _backup_org_incremental(
    dashboard: Any,
    org: dict,
    org_dir: Path,
    network_tags: list[str],
    plan: ChangePlan,
    stats: dict[str, int],
) -> None:
    org_id = str(org["id"])
    org_dir.mkdir(parents=True, exist_ok=True)
    stats["organizations"] += 1
    log.info(
        "Incremental backup: %s (org=%s networks=%s devices=%s)",
        org.get("name"),
        plan.refresh_org,
        len(plan.network_ids),
        len(plan.device_serials),
    )

    if plan.refresh_org:
        _write_org_endpoints(dashboard, org, org_dir, stats)

    # Inventory helps resolve network/device paths and keeps lists current.
    need_inventory = bool(plan.network_ids or plan.device_serials)
    networks: list[dict] = []
    devices: list[dict] = []
    if need_inventory or plan.refresh_org:
        networks = _safe_call(
            dashboard, "organizations", "getOrganizationNetworks", org_id, total_pages="all"
        ) or []
        devices = _safe_call(
            dashboard, "organizations", "getOrganizationDevices", org_id, total_pages="all"
        ) or []
        if need_inventory and not plan.refresh_org:
            write_json(org_dir / "networks.json", networks)
            write_json(org_dir / "devices.json", devices)
            stats["files"] += 2

    networks = _filter_networks(networks, network_tags)
    networks_by_id = {str(n["id"]): n for n in networks}
    devices_by_serial = {
        str(d.get("serial") or "").upper(): d
        for d in devices
        if d.get("serial")
    }

    for net_id in sorted(plan.network_ids):
        network = networks_by_id.get(net_id)
        if not network:
            log.warning("Changelog network %s not in inventory; skipping", net_id)
            continue
        # Coarse: network change refreshes network-wide settings only (not every device).
        _write_network(dashboard, network, org_dir, stats)
    for serial in sorted(plan.device_serials):
        device = devices_by_serial.get(serial.upper())
        if not device:
            # Fall back to a direct device GET if inventory lagged.
            device = _safe_call(dashboard, "devices", "getDevice", serial)
        if not device:
            log.warning("Changelog device %s not found; skipping", serial)
            continue
        net_id = str(
            device.get("networkId")
            or plan.device_network_hint.get(serial)
            or plan.device_network_hint.get(serial.upper())
            or ""
        )
        network = networks_by_id.get(net_id)
        if not network:
            network = _safe_call(dashboard, "networks", "getNetwork", net_id) if net_id else None
        if not network:
            log.warning("No network for device %s; skipping", serial)
            continue
        net_slug = slugify(str(network.get("name") or net_id), fallback=net_id)
        net_dir = org_dir / "networks" / net_slug
        net_dir.mkdir(parents=True, exist_ok=True)
        _write_device(dashboard, device, net_dir, stats)


def backup_once(
    cfg: MeroxConfig,
    tree: Path,
    *,
    force_full: bool = False,
) -> dict[str, int]:
    """Pull configs and write JSON under ``tree``. Returns run stats."""
    api_key = cfg.resolve_api_key()
    dashboard = meraki.DashboardAPI(
        api_key,
        suppress_logging=True,
        print_console=False,
        retry_4xx_error=False,
        maximum_retries=5,
        wait_on_rate_limit=True,
    )

    stats = {
        "organizations": 0,
        "networks": 0,
        "devices": 0,
        "files": 0,
        "skipped": 0,
        "full": 0,
        "incremental": 0,
    }
    run_started = utc_now_iso()
    state = load_state(tree)
    orgs_state: dict[str, Any] = state.setdefault("orgs", {})
    orgs_root = tree / "orgs"
    orgs_root.mkdir(parents=True, exist_ok=True)

    organizations = dashboard.organizations.getOrganizations()
    for org in organizations:
        if not _org_matches(org, cfg.organizations):
            continue
        org_id = str(org["id"])
        org_slug = slugify(str(org.get("name") or org_id), fallback=org_id)
        org_dir = orgs_root / org_slug
        org_state = orgs_state.get(org_id) or {}

        if _needs_full_sync(org_state, cfg, force_full):
            _backup_org_full(dashboard, org, org_dir, cfg.network_tags, stats)
            stats["full"] += 1
        else:
            t0 = str(org_state.get("last_sync_ts"))
            changes = _fetch_changes(dashboard, org_id, t0=t0, t1=run_started)
            plan = plan_from_changes(changes)
            if plan.empty:
                log.info("No changelog activity for %s since %s; skipping", org.get("name"), t0)
                stats["skipped"] += 1
            else:
                _backup_org_incremental(
                    dashboard, org, org_dir, cfg.network_tags, plan, stats
                )
                stats["incremental"] += 1

        orgs_state[org_id] = {
            "last_sync_ts": run_started,
            "slug": org_slug,
            "name": org.get("name"),
        }

    save_state(tree, state)
    return stats
