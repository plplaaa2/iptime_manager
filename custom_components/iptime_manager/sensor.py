from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_URL
from .api import is_easymesh_agent, is_easymesh_controller

# 요약: Web 데이터를 통합하여 시스템 정보 및 네트워크 통계를 제공하는 센서 플랫폼
# 연결될 파일: coordinator.py, const.py, api.py

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: Dict[str, SensorEntityDescription] = {
    "uptime": SensorEntityDescription(
        key="uptime",
        name="Uptime",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "model": SensorEntityDescription(
        key="model",
        name="Model",
        icon="mdi:router-wireless",
    ),
    "version": SensorEntityDescription(
        key="version",
        name="Firmware Version",
        icon="mdi:information-outline",
    ),
    "latest_version": SensorEntityDescription(
        key="latest_version",
        name="Latest Firmware Version",
        icon="mdi:update",
    ),
    "primary_dns": SensorEntityDescription(
        key="primary_dns",
        name="Primary DNS",
        icon="mdi:dns",
    ),
    "secondary_dns": SensorEntityDescription(
        key="secondary_dns",
        name="Secondary DNS",
        icon="mdi:dns-outline",
    ),
    "wan_mac": SensorEntityDescription(
        key="wan_mac",
        name="WAN MAC",
        icon="mdi:network",
    ),
    "wan_ip": SensorEntityDescription(
        key="wan_ip",
        name="WAN IP Address",
        icon="mdi:ip-network",
    ),
    "lan_mac": SensorEntityDescription(
        key="lan_mac",
        name="LAN MAC",
        icon="mdi:lan",
    ),
    # 요약: GeoIP 차단 누적 수를 웹 데이터 기본 센서로 노출한다.
    # 연결 파일: api.py, coordinator.py, select.py
    "geoip_blocked_count": SensorEntityDescription(
        key="geoip_blocked_count",
        name="GeoIP Blocked Count",
        icon="mdi:shield-alert",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "easymesh_agent_count": SensorEntityDescription(
        key="easymesh_agent_count",
        name="EasyMesh Agent Count",
        icon="mdi:access-point-network",
    ),
    # Summary: Expose the latest WireGuard peer and handshake time.
    # Related files: api.py.
    "wireguard_last_peer_name": SensorEntityDescription(
        key="wireguard_last_peer_name",
        name="WireGuard Last Peer Name",
        icon="mdi:account-network",
    ),
    "wireguard_last_handshake": SensorEntityDescription(
        key="wireguard_last_handshake",
        name="WireGuard Last Handshake",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
    ),
}


def _web_sensor_value(web_data: Dict[str, Any], key: str) -> Any:
    firmware = web_data.get("firmware", {}) if isinstance(web_data, dict) else {}
    lan = web_data.get("lan", {}) if isinstance(web_data, dict) else {}
    wan = web_data.get("wan", {}) if isinstance(web_data, dict) else {}
    dns = web_data.get("dns", []) if isinstance(web_data, dict) else []

    if key == "uptime":
        return web_data.get("uptime") if isinstance(web_data, dict) else None
    if key == "model":
        return web_data.get("model", "ipTIME Router") if isinstance(web_data, dict) else "ipTIME Router"
    if key == "version":
        return firmware.get("version")
    if key == "latest_version":
        return firmware.get("latest_version")
    if key == "primary_dns":
        return dns[0] if isinstance(dns, list) and len(dns) > 0 else None
    if key == "secondary_dns":
        return dns[1] if isinstance(dns, list) and len(dns) > 1 else None
    if key == "wan_mac":
        return wan.get("mac")
    if key == "wan_ip":
        return wan.get("ip")
    if key == "lan_mac":
        return lan.get("mac")
    if key == "geoip_blocked_count":
        return web_data.get("geoip_blocked_pcount") if isinstance(web_data, dict) else None
    if key == "easymesh_agent_count":
        mesh = web_data.get("easymesh", {}) if isinstance(web_data, dict) else {}
        agents = mesh.get("agents", {}) if isinstance(mesh, dict) else {}
        if isinstance(agents, dict):
            agents = agents.get("agent", [])
        return len(agents) if isinstance(agents, list) else 0
    # Summary: Return the latest peer metadata calculated at API collection time.
    # Related files: api.py.
    if key in ("wireguard_last_peer_name", "wireguard_last_handshake"):
        wg_server = web_data.get("wg_server", {}) if isinstance(web_data, dict) else {}
        field = "last_peer_name" if key == "wireguard_last_peer_name" else "last_handshake_at"
        return wg_server.get(field) if isinstance(wg_server, dict) else None
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """센서 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # Summary: Remove only this config entry's retired WireGuard count entity.
    # Related files: api.py, __init__.py.
    registry = er.async_get(hass)
    web_data = (coordinator.data or {}).get("web", {})
    agent_mode = is_easymesh_agent(web_data)
    controller_mode = is_easymesh_controller(web_data)
    old_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_wireguard_connected_peer_count"
    )
    if old_entity_id is not None:
        registry.async_remove(old_entity_id)

    agent_only_hidden = {
        "primary_dns",
        "secondary_dns",
        "geoip_blocked_count",
        "wireguard_last_peer_name",
        "wireguard_last_handshake",
    }
    controller_only_hidden = {"easymesh_agent_count"}
    if agent_mode:
        for key in agent_only_hidden:
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
            if entity_id:
                registry.async_remove(entity_id)

    if not controller_mode:
        for key in controller_only_hidden:
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
            if entity_id:
                registry.async_remove(entity_id)

    for key in SENSOR_TYPES:
        if (agent_mode and key in agent_only_hidden) or (not controller_mode and key in controller_only_hidden):
            continue
        entities.append(IPTimeSystemSensor(coordinator, entry, SENSOR_TYPES[key]))

    async_add_entities(entities)


class IPTimeSystemSensor(CoordinatorEntity, SensorEntity):
    """공유기 시스템 정보 센서 (Uptime, Model, Version)."""

    def __init__(self, coordinator, entry, description: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_name = f"{description.name} ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        # Summary: Place router identity and connection metadata in the device information section.
        # Related files: coordinator.py, api.py, select.py.
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        
        # MAC 관련 센서는 보안성과 대시보드 정화를 위해 초기 설치 시 기본 비활성화 처리
        if description.key in ("wan_mac", "lan_mac"):
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> Any:
        """통합 데이터에서 시스템 정보 추출 (Web 전용)."""
        if not self.coordinator.data:
            return None

        web_data = self.coordinator.data.get("web", {})
        return _web_sensor_value(web_data, self.entity_description.key)

    @property
    def device_info(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        model = web_data.get("model", "ipTIME Router")
        version = web_data.get("firmware", {}).get("version", "Unknown")

        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM Networks",
            "model": model,
            "sw_version": version,
        }
