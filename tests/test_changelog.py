from __future__ import annotations

from merox.changelog import classify_event, plan_from_changes


def test_classify_org_api_change():
    kind, key = classify_event(
        {
            "ts": "2018-02-11T00:00:00.090210Z",
            "networkId": None,
            "label": "PUT /api/v1/organizations/2930418",
            "page": "via API",
        }
    )
    assert kind == "org"
    assert key is None


def test_classify_network_change():
    kind, key = classify_event(
        {
            "networkId": "N_24329156",
            "networkName": "Main Office",
            "label": "Firewall rules",
            "page": "Security appliance",
        }
    )
    assert kind == "network"
    assert key == "N_24329156"


def test_classify_device_from_api_path():
    kind, key = classify_event(
        {
            "networkId": "N_24329156",
            "label": "PUT /api/v1/devices/Q2XX-XXXX-XXXX/switch/ports",
            "page": "via API",
        }
    )
    assert kind == "device"
    assert key == "Q2XX-XXXX-XXXX"


def test_plan_aggregates_scopes():
    plan = plan_from_changes(
        [
            {"networkId": None, "label": "PUT /api/v1/organizations/1"},
            {"networkId": "N_1", "label": "SSID rename"},
            {
                "networkId": "N_1",
                "label": "PUT /api/v1/devices/Q2AB-CDEF-GHIJ/managementInterface",
            },
            {"networkId": "N_2", "label": "VLAN add"},
        ]
    )
    assert plan.refresh_org is True
    assert plan.network_ids == {"N_1", "N_2"}
    assert plan.device_serials == {"Q2AB-CDEF-GHIJ"}
    assert plan.device_network_hint["Q2AB-CDEF-GHIJ"] == "N_1"
