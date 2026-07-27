"""Fetch Meraki Dashboard configs into a working tree."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import meraki

from merox.config import MeroxConfig
from merox.endpoints import (
    DEVICE_ENDPOINTS,
    NETWORK_ENDPOINTS,
    ORG_ENDPOINTS,
    device_family,
)
from merox.normalize import slugify, write_json

log = logging.getLogger("merox")


def _call(dashboard: Any, scope: str, operation: str, *args: Any, **kwargs: Any) -> Any:
    api = getattr(dashboard, scope)
    method = getattr(api, operation)
    return method(*args, **kwargs)


def _safe_call(dashboard: Any, scope: str, operation: str, *args: Any, **kwargs: Any) -> Any | None:
    try:
        return _call(dashboard, scope, operation, *args, **kwargs)
    except meraki.APIError as exc:
        # 400/404 are common for product-inapplicable endpoints.
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


def backup_once(cfg: MeroxConfig, tree: Path) -> dict[str, int]:
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

    stats = {"organizations": 0, "networks": 0, "devices": 0, "files": 0}
    orgs_root = tree / "orgs"
    # Replace previous snapshot so deleted networks disappear from Git.
    if orgs_root.exists():
        for child in orgs_root.iterdir():
            if child.is_dir():
                _rm_tree(child)

    organizations = dashboard.organizations.getOrganizations()
    for org in organizations:
        if not _org_matches(org, cfg.organizations):
            continue
        org_id = str(org["id"])
        org_slug = slugify(str(org.get("name") or org_id), fallback=org_id)
        org_dir = orgs_root / org_slug
        stats["organizations"] += 1
        log.info("Backing up organization %s (%s)", org.get("name"), org_id)

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

        networks = _safe_call(
            dashboard, "organizations", "getOrganizationNetworks", org_id, total_pages="all"
        ) or []
        networks = _filter_networks(networks, cfg.network_tags)

        devices = _safe_call(
            dashboard, "organizations", "getOrganizationDevices", org_id, total_pages="all"
        ) or []
        devices_by_net: dict[str, list[dict]] = {}
        for device in devices:
            net_id = str(device.get("networkId") or "")
            devices_by_net.setdefault(net_id, []).append(device)

        for network in networks:
            net_id = str(network["id"])
            net_slug = slugify(str(network.get("name") or net_id), fallback=net_id)
            net_dir = org_dir / "networks" / net_slug
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

            for device in devices_by_net.get(net_id, []):
                serial = str(device.get("serial") or "").strip()
                if not serial:
                    continue
                model = str(device.get("model") or "")
                family = device_family(model)
                name = str(device.get("name") or serial)
                dev_slug = slugify(f"{name}_{serial}", fallback=serial)
                dev_dir = net_dir / "devices" / dev_slug
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

    return stats


def _rm_tree(path: Path) -> None:
    if path.is_file():
        path.unlink()
        return
    for child in path.iterdir():
        _rm_tree(child)
    path.rmdir()
