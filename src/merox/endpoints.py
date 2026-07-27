"""Curated Meraki Dashboard GET operations for config backup.

Inspired by Cisco Meraki's official backup_configs endpoint list:
https://github.com/meraki/automation-scripts/tree/master/backup_configs
"""

from __future__ import annotations

# (file_stem, sdk_scope, operation, product filter or None)
# product filter: None = always; set of productTypes; or "device:<family>"

ORG_ENDPOINTS: list[tuple[str, str, str]] = [
    ("organization", "organizations", "getOrganization"),
    ("networks", "organizations", "getOrganizationNetworks"),
    ("config_templates", "organizations", "getOrganizationConfigTemplates"),
    ("devices", "organizations", "getOrganizationDevices"),
    ("inventory_devices", "organizations", "getOrganizationInventoryDevices"),
    ("admins", "organizations", "getOrganizationAdmins"),
    ("snmp", "organizations", "getOrganizationSnmp"),
    ("login_security", "organizations", "getOrganizationLoginSecurity"),
    ("saml", "organizations", "getOrganizationSaml"),
    ("saml_idps", "organizations", "getOrganizationSamlIdps"),
    ("saml_roles", "organizations", "getOrganizationSamlRoles"),
    ("licenses_overview", "organizations", "getOrganizationLicensesOverview"),
    ("appliance_vpn_third_party_peers", "appliance", "getOrganizationApplianceVpnThirdPartyVPNPeers"),
    ("appliance_vpn_firewall_rules", "appliance", "getOrganizationApplianceVpnVpnFirewallRules"),
]

NETWORK_ENDPOINTS: list[tuple[str, str, str, frozenset[str] | None]] = [
    ("settings", "networks", "getNetworkSettings", None),
    ("snmp", "networks", "getNetworkSnmp", None),
    ("syslog_servers", "networks", "getNetworkSyslogServers", None),
    ("traffic_analysis", "networks", "getNetworkTrafficAnalysis", None),
    ("alerts_settings", "networks", "getNetworkAlertsSettings", None),
    ("firmware_upgrades", "networks", "getNetworkFirmwareUpgrades", None),
    ("group_policies", "networks", "getNetworkGroupPolicies", frozenset({"appliance", "wireless"})),
    ("webhooks_http_servers", "networks", "getNetworkWebhooksHttpServers", None),
    ("appliance_vlans", "appliance", "getNetworkApplianceVlans", frozenset({"appliance"})),
    ("appliance_vlans_settings", "appliance", "getNetworkApplianceVlansSettings", frozenset({"appliance"})),
    ("appliance_single_lan", "appliance", "getNetworkApplianceSingleLan", frozenset({"appliance"})),
    ("appliance_ports", "appliance", "getNetworkAppliancePorts", frozenset({"appliance"})),
    ("appliance_static_routes", "appliance", "getNetworkApplianceStaticRoutes", frozenset({"appliance"})),
    ("appliance_firewall_l3", "appliance", "getNetworkApplianceFirewallL3FirewallRules", frozenset({"appliance"})),
    ("appliance_firewall_l7", "appliance", "getNetworkApplianceFirewallL7FirewallRules", frozenset({"appliance"})),
    ("appliance_firewall_inbound", "appliance", "getNetworkApplianceFirewallInboundFirewallRules", frozenset({"appliance"})),
    ("appliance_port_forwarding", "appliance", "getNetworkApplianceFirewallPortForwardingRules", frozenset({"appliance"})),
    ("appliance_content_filtering", "appliance", "getNetworkApplianceContentFiltering", frozenset({"appliance"})),
    ("appliance_security_intrusion", "appliance", "getNetworkApplianceSecurityIntrusion", frozenset({"appliance"})),
    ("appliance_security_malware", "appliance", "getNetworkApplianceSecurityMalware", frozenset({"appliance"})),
    ("appliance_traffic_shaping", "appliance", "getNetworkApplianceTrafficShaping", frozenset({"appliance"})),
    ("appliance_uplink_bandwidth", "appliance", "getNetworkApplianceTrafficShapingUplinkBandwidth", frozenset({"appliance"})),
    ("appliance_site_to_site_vpn", "appliance", "getNetworkApplianceVpnSiteToSiteVpn", frozenset({"appliance"})),
    ("appliance_warm_spare", "appliance", "getNetworkApplianceWarmSpare", frozenset({"appliance"})),
    ("switch_acl", "switch", "getNetworkSwitchAccessControlLists", frozenset({"switch"})),
    ("switch_settings", "switch", "getNetworkSwitchSettings", frozenset({"switch"})),
    ("switch_mtu", "switch", "getNetworkSwitchMtu", frozenset({"switch"})),
    ("switch_stp", "switch", "getNetworkSwitchStp", frozenset({"switch"})),
    ("switch_qos_rules", "switch", "getNetworkSwitchQosRules", frozenset({"switch"})),
    ("switch_storm_control", "switch", "getNetworkSwitchStormControl", frozenset({"switch"})),
    ("switch_dscp_to_cos", "switch", "getNetworkSwitchDscpToCosMappings", frozenset({"switch"})),
    ("wireless_ssids", "wireless", "getNetworkWirelessSsids", frozenset({"wireless"})),
    ("wireless_settings", "wireless", "getNetworkWirelessSettings", frozenset({"wireless"})),
    ("wireless_rf_profiles", "wireless", "getNetworkWirelessRfProfiles", frozenset({"wireless"})),
    ("wireless_bluetooth", "wireless", "getNetworkWirelessBluetoothSettings", frozenset({"wireless"})),
]

DEVICE_ENDPOINTS: list[tuple[str, str, str, str]] = [
    # file_stem, scope, operation, model_prefix family
    ("management_interface", "devices", "getDeviceManagementInterface", "*"),
    ("switch_ports", "switch", "getDeviceSwitchPorts", "MS"),
    ("switch_warm_spare", "switch", "getDeviceSwitchWarmSpare", "MS"),
    ("wireless_radio_settings", "wireless", "getDeviceWirelessRadioSettings", "MR"),
    ("camera_quality_retention", "camera", "getDeviceCameraQualityAndRetention", "MV"),
    ("camera_video_settings", "camera", "getDeviceCameraVideoSettings", "MV"),
    ("cellular_lan", "cellularGateway", "getDeviceCellularGatewayLan", "MG"),
    ("cellular_port_forwarding", "cellularGateway", "getDeviceCellularGatewayPortForwardingRules", "MG"),
]


def device_family(model: str) -> str:
    model = (model or "").upper()
    if model.startswith("MR") or model.startswith("CW"):
        return "MR"
    if model.startswith("MS"):
        return "MS"
    if model.startswith("MV"):
        return "MV"
    if model.startswith("MG"):
        return "MG"
    if model.startswith(("MX", "Z3", "Z4", "Z1", "VM")):
        return "MX"
    return model[:2] if len(model) >= 2 else "*"
