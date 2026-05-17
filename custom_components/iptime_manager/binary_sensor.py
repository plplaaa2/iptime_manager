from __future__ import annotations

import logging
import re
from typing import Any, Dict

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_URL

_LOGGER = logging.getLogger(__name__)


def _parse_link_metrics(link: Any) -> tuple[bool, str, str, int]:
    if link in (None, "", "null"):
        return False, "Down", "unknown", 0

    link_str = str(link)
    match = re.match(r"^(\d+)([fh]?)$", link_str)
    if not match:
        return True, link_str, "unknown", 0

    speed = int(match.group(1))
    duplex_code = match.group(2)
    duplex = {"f": "full", "h": "half"}.get(duplex_code, "unknown")

    if speed >= 1000:
        label = f"{speed // 1000}Gbps"
    else:
        label = f"{speed}Mbps"

    return True, label, duplex, speed


def _entity_key_part(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def _normalize_port_key(port_type: Any, port_num: Any) -> str:
    kind = str(port_type or "port").strip().lower()
    if not kind:
        kind = "port"

    try:
        num = int(port_num)
    except Exception:
        num = port_num

    if kind == "wan":
        return "wan_1"
    return f"{kind}_{num}"


def _display_port_name(port_type: Any, port_num: Any) -> str:
    kind = str(port_type or "port").strip().lower()
    if kind == "wan":
        return "WAN"
    if kind == "lan":
        return f"LAN {port_num}"
    return f"{str(port_type or 'Port').upper()} {port_num}"


def _web_wireless_band_key(info: Dict[str, Any]) -> str:
    """Extract band key string from info dict."""
    raw_band = info.get("band")
    if isinstance(raw_band, str) and raw_band.strip():
        return raw_band.strip().lower()
    if isinstance(raw_band, dict):
        for key in ("band", "id", "name", "label"):
            val = raw_band.get(key)
            if val:
                return str(val).strip().lower()
    
    # Fallback to 'bss' if present
    bss_id = str(info.get("bss") or "").strip().lower()
    if "." in bss_id:
        return bss_id.split(".", 1)[0]
    return bss_id or ""

def _web_wireless_band_list(web_data: Dict[str, Any]) -> list[Dict[str, Any]]:
    wireless = web_data.get("wireless", {}) if isinstance(web_data, dict) else {}
    bands = wireless.get("band", []) if isinstance(wireless, dict) else []
    result: list[Dict[str, Any]] = []
    
    seen: set[str] = set()
    if isinstance(bands, list) and bands:
        for band in bands:
            if not isinstance(band, dict): continue
            bkey = _web_wireless_band_key(band)
            if bkey and bkey not in seen:
                seen.add(bkey)
                result.append(band)
    
    if result:
        return result

    # Fallback to BSS list if band info is missing
    bss_list = wireless.get("bss", []) if isinstance(wireless, dict) else []
    if isinstance(bss_list, list):
        for bss in bss_list:
            if not isinstance(bss, dict): continue
            bkey = _web_wireless_band_key(bss)
            if bkey and bkey not in seen:
                seen.add(bkey)
                result.append({
                    "band": bkey,
                    "enable": bss.get("enable"),
                    "activated": bss.get("activated"),
                    "bss": [bss.get("bss")] if bss.get("bss") else [],
                })
    return result


def _web_wireless_band_active(band_info: Dict[str, Any]) -> bool:
    if not isinstance(band_info, dict):
        return False
    if band_info.get("activated") is not None:
        return bool(band_info.get("activated"))
    if band_info.get("enable") is not None:
        return bool(band_info.get("enable"))
    if band_info.get("configured") is not None:
        return bool(band_info.get("configured"))
    return False


def _web_wan_link_value(web_data: Dict[str, Any], port_info: Dict[str, Any]) -> Any:
    wan_info = web_data.get("wan", {}) if isinstance(web_data, dict) else {}
    if not isinstance(wan_info, dict):
        wan_info = {}

    link = port_info.get("link")
    if link not in (None, "", "null"):
        return link

    for key in ("wan_speed", "link", "speed"):
        value = wan_info.get(key)
        if value not in (None, "", "null"):
            return value
    return link


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """이진 센서 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data if coordinator.data else {}
    entities = []

    # Web API 기반 포트 및 Wi-Fi 센서 생성
    web_data = data.get("web", {})
    web_ports = web_data.get("ports", [])
    web_bands = _web_wireless_band_list(web_data)

    if web_ports or web_bands:
        for port_info in web_ports:
            port_type = str(port_info.get("type", "port")).lower()
            port_num = port_info.get("port")
            if port_num is not None:
                entities.append(IPTimeInterfaceBinarySensor(coordinator, entry, f"{port_type}:{port_num}", port_info=port_info))
        
        for band_info in web_bands:
            band_key = _web_wireless_band_key(band_info)
            if band_key:
                entities.append(IPTimeInterfaceBinarySensor(coordinator, entry, f"wifi:{band_key}", port_info=band_info))

    async_add_entities(entities)


class IPTimeInterfaceBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """인터페이스 연결 상태 이진 센서 (WAN/LAN)."""

    def __init__(
        self,
        coordinator,
        entry,
        iface_name: str,
        port_info: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._iface_name = iface_name
        self._entry = entry
        self._port_info = port_info or {}

        if self._iface_name.startswith("wifi:"):
            band_key = str(self._iface_name.split(":", 1)[1]).strip().lower()
            band_label = {
                "2g": "2.4G",
                "5g": "5G",
                "5g-2": "5G-2",
                "6g": "6G",
                "6g-2": "6G-2",
                "mlo": "MLO",
            }.get(band_key, band_key or "Unknown")
            self._attr_name = f"WiFi {band_label} Status ({entry.data.get(CONF_URL)})"
            self._attr_unique_id = f"{entry.entry_id}_wifi_{_entity_key_part(band_key)}_status"
            self._attr_device_class = None
        else:
            port_type = str(self._port_info.get("type", "port")).upper()
            port_num = self._port_info.get("port")
            self._attr_name = f"{_display_port_name(port_type, port_num)} Status ({entry.data.get(CONF_URL)})"
            self._attr_unique_id = f"{entry.entry_id}_{_normalize_port_key(port_type, port_num)}_status"
            self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """활성 상태를 판단한다 (Web 전용)."""
        if not self.coordinator.data:
            return False

        if self._iface_name.startswith("wifi:"):
            return _web_wireless_band_active(self._port_info)
        
        if ":" in self._iface_name: # "type:num" \ud615\uc2dd\uc758 Web \ud3ec\ud2b8
            port_type = str(self._port_info.get("type", "")).lower()
            link_value = self._port_info.get("link")
            if port_type == "wan":
                link_value = _web_wan_link_value(self.coordinator.data.get("web", {}), self._port_info)
            is_on, _, _, _ = _parse_link_metrics(link_value)
            return is_on

        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """추가 상태 정보를 제공한다 (Web 전용)."""
        if not self.coordinator.data:
            return {}

        if self._iface_name.startswith("wifi:"):
            band_key = str(self._iface_name.split(":", 1)[1]).strip().lower()
            band_label = {
                "2g": "2.4G", "5g": "5G", "5g-2": "5G-2", "6g": "6G", "6g-2": "6G-2", "mlo": "MLO",
            }.get(band_key, band_key or "Unknown")
            active = _web_wireless_band_active(self._port_info)
            return {
                "interface_name": f"WiFi {band_label}",
                "link_speed": "Enabled" if active else "Disabled",
                "status_code": 1 if active else 0,
            }

        if ":" in self._iface_name:
            link_value = self._port_info.get("link")
            port_type = str(self._port_info.get("type", "")).lower()
            if port_type == "wan":
                link_value = _web_wan_link_value(self.coordinator.data.get("web", {}), self._port_info)

            is_on, link_speed, _, speed = _parse_link_metrics(link_value)
            return {
                "interface_name": _display_port_name(self._port_info.get("type"), self._port_info.get("port")),
                "link_speed": link_speed,
                "status_code": speed if is_on else 0,
            }

        return {}

    @property
    def icon(self) -> str:
        """연결 상태에 따른 아이콘 변경."""
        if self._iface_name.startswith("wifi:"):
            return "mdi:router-wireless" if self.is_on else "mdi:router-wireless-off"

        port_type = str(self._port_info.get("type", "")).lower()
        if port_type in ("lan", "wan"):
            return "mdi:ethernet" if self.is_on else "mdi:ethernet-off"

        if self.is_on:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def device_info(self) -> dict[str, Any]:
        """기기 정보 제공 (Web 전용)."""
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        model = web_data.get("model", "ipTIME Router")
        
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM Networks",
            "model": model,
        }
