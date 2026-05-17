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
    # 요약: 링크 속도 및 듀플렉스 상태 문자열을 파싱한다.
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


def _web_wan_link_value(web_data: Dict[str, Any], port_info: Dict[str, Any]) -> Any:
    # 요약: WAN 물리 포트의 실제 연결 속도 링크 값을 조회한다.
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
    # 요약: ipTIME 유선 포트(LAN/WAN) 연결 상태 이진 센서를 설정한다.
    # 연결될 파일: coordinator.py, binary_sensor.py
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data if coordinator.data else {}
    entities = []

    # Web API 기반 물리 유선 포트 센서만 생성 (무선 Wi-Fi는 스위치 엔티티로 통합 관리하므로 생성 제외)
    web_data = data.get("web", {})
    web_ports = web_data.get("ports", [])

    if web_ports:
        for port_info in web_ports:
            port_type = str(port_info.get("type", "port")).lower()
            port_num = port_info.get("port")
            if port_num is not None:
                entities.append(IPTimeInterfaceBinarySensor(coordinator, entry, f"{port_type}:{port_num}", port_info=port_info))

    async_add_entities(entities)


class IPTimeInterfaceBinarySensor(CoordinatorEntity, BinarySensorEntity):
    # 요약: ipTIME 공유기 물리 유선 포트(LAN/WAN)의 실시간 연결 상태 및 속도를 제공하는 이진 센서.
    # 연결될 파일: coordinator.py, binary_sensor.py, switch.py

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

        port_type = str(self._port_info.get("type", "port")).upper()
        port_num = self._port_info.get("port")
        self._attr_name = f"{_display_port_name(port_type, port_num)} Status ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_{_normalize_port_key(port_type, port_num)}_status"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def _get_current_info(self) -> Dict[str, Any] | None:
        # 요약: 코디네이터의 실시간 수집 데이터에서 이 포트의 최신 정보를 찾아 반환한다.
        if not self.coordinator.data:
            return None

        web_data = self.coordinator.data.get("web", {})
        if ":" in self._iface_name:
            parts = self._iface_name.split(":", 1)
            port_type = parts[0]
            try:
                port_num = int(parts[1])
            except ValueError:
                port_num = parts[1]
            
            ports = web_data.get("ports", [])
            return next(
                (p for p in ports if str(p.get("type", "")).lower() == port_type and p.get("port") == port_num), 
                None
            )
        
        return None

    @property
    def is_on(self) -> bool:
        # 요약: 물리 유선 포트가 활성화(케이블 연결됨) 상태인지 판단한다.
        info = self._get_current_info()
        if not info:
            return False

        if ":" in self._iface_name:
            port_type = str(info.get("type", "")).lower()
            link_value = info.get("link")
            if port_type == "wan":
                link_value = _web_wan_link_value(self.coordinator.data.get("web", {}), info)
            is_on, _, _, _ = _parse_link_metrics(link_value)
            return is_on

        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # 요약: 물리 포트의 세부 링크 속도(Gbps/Mbps) 및 듀플렉스 정보를 속성 값으로 제공한다.
        info = self._get_current_info()
        if not info:
            return {}

        if ":" in self._iface_name:
            link_value = info.get("link")
            port_type = str(info.get("type", "")).lower()
            if port_type == "wan":
                link_value = _web_wan_link_value(self.coordinator.data.get("web", {}), info)

            is_on, link_speed, _, speed = _parse_link_metrics(link_value)
            return {
                "interface_name": _display_port_name(info.get("type"), info.get("port")),
                "link_speed": link_speed,
                "status_code": speed if is_on else 0,
            }

        return {}

    @property
    def icon(self) -> str:
        # 요약: 유선 포트 연결 여부에 따른 이더넷 아이콘 매핑.
        port_type = str(self._port_info.get("type", "")).lower()
        if port_type in ("lan", "wan"):
            return "mdi:ethernet" if self.is_on else "mdi:ethernet-off"

        if self.is_on:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def device_info(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        model = web_data.get("model", "ipTIME Router")
        
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM Networks",
            "model": model,
        }
