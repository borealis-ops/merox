"""Classify Meraki organization configurationChanges events."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Meraki hardware serials look like Q2XX-XXXX-XXXX (and similar).
_SERIAL_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})\b", re.IGNORECASE)
_DEVICE_PATH_RE = re.compile(
    r"/devices/([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})(?:/|$|\?)",
    re.IGNORECASE,
)
_ORG_PATH_RE = re.compile(r"/organizations/[^/]+(?:/|$|\?)", re.IGNORECASE)
_NETWORK_PATH_RE = re.compile(r"/networks/[^/]+(?:/|$|\?)", re.IGNORECASE)


@dataclass
class ChangePlan:
    """Coarse scopes to refresh after a changelog scan."""

    refresh_org: bool = False
    network_ids: set[str] = field(default_factory=set)
    device_serials: set[str] = field(default_factory=set)
    device_network_hint: dict[str, str] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not self.refresh_org and not self.network_ids and not self.device_serials


def extract_serial(event: dict[str, Any]) -> str | None:
    label = str(event.get("label") or "")
    match = _DEVICE_PATH_RE.search(label)
    if match:
        return match.group(1).upper()

    blob = " ".join(
        str(event.get(key) or "")
        for key in ("label", "page", "oldValue", "newValue")
    )
    match = _SERIAL_RE.search(blob)
    if match:
        return match.group(1).upper()
    return None


def classify_event(event: dict[str, Any]) -> tuple[str, str | None]:
    """
    Return ``('org', None)``, ``('network', network_id)``, or ``('device', serial)``.

    Coarse rules:
    - device path / serial in the event → device
    - no networkId (or org API path without network) → org
    - otherwise → network
    """
    serial = extract_serial(event)
    if serial:
        return "device", serial

    network_id = event.get("networkId")
    network_id_s = str(network_id).strip() if network_id else ""
    label = str(event.get("label") or "")

    if not network_id_s:
        return "org", None

    # API change that targets the organization resource even if networkId is present.
    if _ORG_PATH_RE.search(label) and not _NETWORK_PATH_RE.search(label) and not _DEVICE_PATH_RE.search(label):
        return "org", None

    return "network", network_id_s


def plan_from_changes(events: list[dict[str, Any]]) -> ChangePlan:
    plan = ChangePlan()
    for event in events:
        kind, key = classify_event(event)
        if kind == "org":
            plan.refresh_org = True
        elif kind == "network" and key:
            plan.network_ids.add(key)
        elif kind == "device" and key:
            plan.device_serials.add(key)
            net = event.get("networkId")
            if net:
                plan.device_network_hint[key] = str(net)
    return plan
