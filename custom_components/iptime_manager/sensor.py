from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_URL

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
}


def _band_label(raw_band: Any) -> str:
    band = str(raw_band or "").lower()
    mapping = {
        "2g.1": "2.4G",
        "2.4g": "2.4G",
        "2.4ghz": "2.4G",
        "5g.1": "5G",
        "5g.2": "5G-2",
        "5ghz": "5G",
        "6g.1": "6G",
        "6g.2": "6G-2",
        "6ghz": "6G",
        "mlo": "MLO",
    }
    return mapping.get(band, raw_band or "Unknown")


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
    return None


def _web_wireless_band_label(band: Any) -> str:
    band_key = str(band or "").lower()
    mapping = {
        "2g": "2.4G",
        "5g": "5G",
        "5g-2": "5G-2",
        "6g": "6G",
        "6g-2": "6G-2",
        "mlo": "MLO",
    }
    return mapping.get(band_key, str(band or "Unknown"))


def _web_wireless_band_attr_label(band: Any) -> str:
    band_key = str(band or "").lower()
    mapping = {
        "2g": "2.4GHz",
        "5g": "5GHz",
        "5g-2": "5GHz-2",
        "6g": "6GHz",
        "6g-2": "6GHz-2",
        "mlo": "MLO",
    }
    return mapping.get(band_key, "Unknown")


def _web_wireless_security_label(authenc: Any) -> str:
    value = str(authenc or "").lower()
    mapping = {
        "open": "No Encrypt",
        "none": "No Encrypt",
        "wep": "WEP",
        "shared_wep": "Shared-WEP",
        "auto_wep": "Auto-WEP",
        "wpa_psk": "WPAPSK-AES",
        "wpa2psk_aes": "WPA2PSK-AES",
        "wpa2psk_tkip_aes": "WPA2PSK-TKIP/AES",
        "wpapsk_wpa2psk_aes": "WPAPSK/WPA2PSK-AES",
        "wpa3sae_aes": "WPA3SAE-AES",
        "wpa3sae_wpa2psk_aes": "WPA3SAE/WPA2PSK-AES",
        "wpa2_aes": "WPA2-AES",
        "wpa3_aes": "WPA3-AES",
    }
    return mapping.get(value, str(authenc or "Unknown"))


def _entity_key_part(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def _web_wireless_band_map(web_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    band_map: Dict[str, Dict[str, Any]] = {}
    wireless = web_data.get("wireless", {}) if isinstance(web_data, dict) else {}
    for band_info in wireless.get("band", []) or []:
        if isinstance(band_info, dict) and band_info.get("band"):
            band_map[str(band_info["band"]).lower()] = band_info
    return band_map


def _web_wireless_bss_band_key(bss_info: Dict[str, Any]) -> str:
    """Derive the wireless band key from BSS data."""
    raw_band = bss_info.get("band")
    if isinstance(raw_band, str) and raw_band.strip():
        return raw_band.strip().lower()
    if isinstance(raw_band, dict):
        for key in ("band", "id", "name", "label"):
            value = raw_band.get(key)
            if value:
                return str(value).strip().lower()
    if isinstance(raw_band, list):
        for item in raw_band:
            if isinstance(item, dict):
                for key in ("band", "id", "name", "label"):
                    value = item.get(key)
                    if value:
                        return str(value).strip().lower()
            elif item:
                return str(item).strip().lower()

    bss_id = str(bss_info.get("bss") or "").strip().lower()
    if "." in bss_id:
        return bss_id.split(".", 1)[0]
    return bss_id or "unknown"


def _web_wireless_bss_list(web_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    wireless = web_data.get("wireless", {}) if isinstance(web_data, dict) else {}
    result: List[Dict[str, Any]] = []
    for bss in wireless.get("bss", []) or []:
        if isinstance(bss, dict) and bss.get("bss"):
            result.append(bss)
    return result


def _web_wireless_bss_map(web_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(bss.get("bss")): bss
        for bss in _web_wireless_bss_list(web_data)
        if bss.get("bss")
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """센서 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    entities = []

    for key in SENSOR_TYPES:
        entities.append(IPTimeSystemSensor(coordinator, entry, SENSOR_TYPES[key]))

    # 2. Wi-Fi 엔티티 추가 (Web 기반)
    web_data = data.get("web", {})
    bss_list = _web_wireless_bss_list(web_data)
    
    if bss_list:
        for bss in bss_list:
            bss_key = str(bss.get("bss"))
            band_label = _web_wireless_band_label(bss.get("band"))
            entities.append(IPTimeWifiSensor(coordinator, entry, bss_key, band_label))

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


class IPTimeWifiSensor(CoordinatorEntity, SensorEntity):
    """와이파이(WIFI) 상태 및 채널 센서."""

    def __init__(self, coordinator, entry, idx: str, label: str) -> None:
        super().__init__(coordinator)
        self._idx = idx
        self._label = label
        self._entry = entry

        web_data = self.coordinator.data.get("web", {})
        bss_info = _web_wireless_bss_map(web_data).get(str(idx), {})
        ssid = bss_info.get("ssid")
        band_key = _web_wireless_bss_band_key(bss_info)
        band_tag = f"{_web_wireless_band_label(band_key)} - {ssid}" if ssid else f"{_web_wireless_band_label(band_key)} - {idx}"
        ssid_key = _entity_key_part(ssid or idx)

        self._attr_name = f"ipTIME WiFi {band_tag} ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_wifi_{band_key}_{ssid_key}"
        self._attr_icon = "mdi:wifi"

    @property
    def native_value(self) -> Any:
        """상태값을 제공한다."""
        if not self.coordinator.data:
            return None

        web_data = self.coordinator.data.get("web", {})
        bss_map = _web_wireless_bss_map(web_data)
        bss = bss_map.get(str(self._idx))
        if bss:
            ssid = bss.get("ssid") or "Disabled"
            return f"[{_web_wireless_band_label(_web_wireless_bss_band_key(bss))}] {ssid}"
        return f"[{_web_wireless_band_label(self._label)}] Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """추가 상태 정보를 제공한다."""
        if not self.coordinator.data:
            return {}

        web_data = self.coordinator.data.get("web", {})
        band_map = _web_wireless_band_map(web_data)
        bss_info = _web_wireless_bss_map(web_data).get(str(self._idx), {})
        band_key = _web_wireless_bss_band_key(bss_info)
        band_info = band_map.get(band_key, {})
        broadcast = "Disabled" if bss_info.get("hide") else "Enabled"
        return {
            "channel": band_info.get("channel"),
            "band": _web_wireless_band_attr_label(band_key),
            "protocol": "Unknown",
            "security": _web_wireless_security_label(bss_info.get("authenc")),
            "broadcast": broadcast,
            "index": self._idx,
            "raw_ssid": bss_info.get("ssid"),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}
