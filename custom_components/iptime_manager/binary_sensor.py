from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_URL, CONF_USE_SNMP

# 요약: ipTIME 공유기의 WAN 및 포트 연결 상태를 제공하는 이진 센서 플랫폼
# 연결될 파일: const.py, coordinator.py, __init__.py, api.py

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """이진 센서 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # SNMP가 비활성화된 경우 등록 건너뜀
    use_snmp = entry.options.get(CONF_USE_SNMP, entry.data.get(CONF_USE_SNMP, False))
    if not use_snmp:
        _LOGGER.debug("SNMP 비활성화 상태이므로 포트 상태 이진 센서를 생성하지 않습니다.")
        return
        
    entities = []

    # SNMP 데이터에서 인터페이스 정보를 가져와 이진 센서 생성
    data = coordinator.data if coordinator.data else {}
    snmp_data = data.get("snmp", {})
    ifaces = snmp_data.get("interfaces", {})

    for iface_name in ifaces:
        # WAN 포트는 별도의 DeviceClass 부여를 고려하여 처리 가능
        entities.append(IPTimeInterfaceBinarySensor(coordinator, entry, iface_name))

    async_add_entities(entities)

class IPTimeInterfaceBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """인터페이스 연결 상태 이진 센서 (WAN/LAN)."""

    def __init__(self, coordinator, entry, iface_name: str) -> None:
        super().__init__(coordinator)
        self._iface_name = iface_name
        self._entry = entry
        
        # WiFi 인터페이스인 경우 주파수 대역 정보를 찾아 이름에 포함
        snmp_data = self.coordinator.data.get("snmp", {})
        wifi_list = snmp_data.get("wifi", {})
        band_tag = ""
        display_name = iface_name
        
        for w_idx, w_info in wifi_list.items():
            if w_info.get("ssid") == iface_name:
                mode_map_short = {0: "2.4G", 1: "5G", 2: "5G-2", 3: "6G", 4: "6G-2", 8: "MLO"}
                band_tag = f"WiFi {mode_map_short.get(w_info.get('mode'), 'Unknown')} "
                # SSID가 이름에 포함되지 않게 요청하셨으므로 display_name에서 SSID 제외 가능
                display_name = ""
                break
        
        self._attr_name = f"ipTIME {band_tag}{display_name} Status ({entry.data.get(CONF_URL)})".replace("  ", " ")
        self._attr_unique_id = f"{entry.entry_id}_{iface_name}_status"
        self._attr_device_class = None # 켜짐/꺼짐으로 표시되도록 설정

    @property
    def is_on(self) -> bool:
        """와이파이는 활성화 상태(enable)를, 유선은 연결 상태(status)를 기준으로 판별."""
        snmp_data = self.coordinator.data.get("snmp", {})
        ifaces = snmp_data.get("interfaces", {})
        wifi_list = snmp_data.get("wifi", {})
        
        # 1. WiFi 리스트에서 먼저 검색 (무선 전용 상태)
        is_wifi = False
        for w_idx, w_info in wifi_list.items():
            if w_info.get("ssid") == self._iface_name:
                is_wifi = True
                return w_info.get("enable", 0) == 1
        
        # 2. 유선 포트 테이블에서 검색
        info = ifaces.get(self._iface_name)
        if info is not None:
            # LAN/WAN이 아닌데 WiFi 리스트에도 없었다면 꺼진 WiFi로 간주
            if not is_wifi and "LAN" not in self._iface_name and "WAN" not in self._iface_name:
                return False
                
            status_code = info.get("status", 0)
            return status_code >= 1
            
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """추가 속성으로 상세 상태(속도 등) 제공."""
        snmp_data = self.coordinator.data.get("snmp", {})
        ifaces = snmp_data.get("interfaces", {})
        info = ifaces.get(self._iface_name, {})
        status_code = info.get("status", 0)
        
        # 상태 코드 해석 (MIB 기반)
        status_map = {
            0: "Down", 1: "Up", 10: "10Mbps", 100: "100Mbps", 
            500: "500Mbps", 1000: "1Gbps", 2500: "2.5Gbps", 
            5000: "5Gbps", 10000: "10Gbps"
        }
        
        return {
            "interface_name": self._iface_name,
            "link_speed": status_map.get(status_code, "Unknown"),
            "status_code": status_code
        }

    @property
    def icon(self) -> str:
        """연결 상태에 따른 아이콘 변경."""
        if self.is_on:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def device_info(self) -> dict[str, Any]:
        snmp_data = self.coordinator.data.get("snmp", {}) if self.coordinator.data else {}
        model = snmp_data.get("model", "ipTIME Router")
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
        }
