from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation, UnitOfTime, UnitOfDataRate
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_URL, CONF_USE_SNMP

# 요약: ipTIME 공유기의 시스템 정보 및 트래픽 정보를 제공하는 센서 플랫폼
# 연결될 파일: const.py, coordinator.py, __init__.py

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
    "lan_mac": SensorEntityDescription(
        key="lan_mac",
        name="LAN MAC",
        icon="mdi:lan",
    ),
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """센서 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # SNMP가 비활성화된 경우 센서 등록 건너뜀
    use_snmp = entry.options.get(CONF_USE_SNMP, entry.data.get(CONF_USE_SNMP, False))
    if not use_snmp:
        _LOGGER.debug("SNMP 비활성화 상태이므로 SNMP 관련 센서를 생성하지 않습니다.")
        return

    # 기본 시스템 센서 추가
    for key in SENSOR_TYPES:
        entities.append(IPTimeSystemSensor(coordinator, entry, SENSOR_TYPES[key]))

    # WIFI 채널 센서 추가 (데이터가 있을 때만)
    snmp_data = coordinator.data.get("snmp", {}) if coordinator.data else {}
    if snmp_data.get("wifi"):
        for idx, info in snmp_data["wifi"].items():
            if info.get("ssid"):
                entities.append(IPTimeWifiSensor(coordinator, entry, idx, info["ssid"]))

    async_add_entities(entities)

class IPTimeSystemSensor(CoordinatorEntity, SensorEntity):
    """공유기 시스템 정보 센서 (Uptime, Model, Version)."""

    def __init__(self, coordinator, entry, description: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_name = f"ipTIME {description.name} ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """코디네이터 통합 데이터에서 시스템 정보 추출."""
        if not self.coordinator.data:
            return None
        snmp_data = self.coordinator.data.get("snmp", {})
        val = snmp_data.get(self.entity_description.key)
        _LOGGER.debug(f"ipTIME 센서 [{self.entity_description.key}] 업데이트 시도: {val}")
        if self.entity_description.key == "uptime" and val:
            return val / 100
        return val

    @property
    def device_info(self) -> dict[str, Any]:
        snmp_data = self.coordinator.data.get("snmp", {}) if self.coordinator.data else {}
        model = snmp_data.get("model", "ipTIME Router")
        version = snmp_data.get("version", "Unknown")
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM Networks",
            "model": model,
            "sw_version": version,
        }


class IPTimeWifiSensor(CoordinatorEntity, SensorEntity):
    """와이파이(WIFI) 상태 및 채널 센서."""

    def __init__(self, coordinator, entry, idx: str, ssid: str) -> None:
        super().__init__(coordinator)
        self._idx = idx
        self._entry = entry
        
        # 주파수 대역 정보를 가져와 이름에 포함
        snmp_data = self.coordinator.data.get("snmp", {})
        info = snmp_data.get("wifi", {}).get(idx, {})
        mode_map_short = {0: "2.4G", 1: "5G", 2: "5G-2", 3: "6G", 4: "6G-2", 8: "MLO"}
        band_tag = mode_map_short.get(info.get("mode"), "Unknown")
        
        self._attr_name = f"ipTIME WiFi {band_tag} ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_wifi_{idx}"
        self._attr_icon = "mdi:wifi"

    @property
    def native_value(self) -> Any:
        """상태값을 [대역] SSID 형식으로 제공."""
        snmp_data = self.coordinator.data.get("snmp", {})
        wifi = snmp_data.get("wifi", {})
        info = wifi.get(self._idx, {})
        
        mode_map_short = {0: "2.4G", 1: "5G", 2: "5G-2", 3: "6G", 4: "6G-2", 8: "MLO"}
        band_tag = mode_map_short.get(info.get("mode"), "Unknown")
        ssid = info.get("ssid", "Unknown")
        
        return f"[{band_tag}] {ssid}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """WiFi 상세 정보(채널, 보안 등)를 추가 속성으로 제공."""
        snmp_data = self.coordinator.data.get("snmp", {})
        wifi = snmp_data.get("wifi", {})
        info = wifi.get(self._idx, {})
        
        mode_map = {0: "2.4GHz", 1: "5GHz", 2: "5GHz-2", 3: "6GHz", 4: "6GHz-2", 8: "MLO"}
        security_map = {
            0: "No Encrypt", 1: "WPA2PSK-AES", 2: "WPAPSK/WPA2PSK-AES", 3: "WPAPSK-AES",
            4: "WPA3SAE-AES", 5: "WPA3SAE/WPA2PSK-AES", 6: "WPA2PSK-TKIP/AES",
            12: "Auto-WEP", 13: "Open-WEP", 14: "Shared-WEP", 15: "WPA2-AES", 18: "WPA3-AES"
        }
        protocol_map = {1: "WiFi 1 (b)", 2: "WiFi 2 (g)", 4: "WiFi 4 (n)", 8: "WiFi 5 (ac)", 16: "WiFi 6 (ax)", 32: "WiFi 7 (be)"}
        
        return {
            "channel": info.get("channel"),
            "band": mode_map.get(info.get("mode"), "Unknown"),
            "protocol": protocol_map.get(info.get("protocol"), "Unknown"),
            "security": security_map.get(info.get("security"), "Unknown"),
            "broadcast": "Enabled" if info.get("broadcast") == 1 else "Disabled",
            "index": self._idx,
            "raw_ssid": info.get("ssid")
        }

    @property
    def device_info(self) -> dict[str, Any]:
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}
