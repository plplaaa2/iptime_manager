"""ipTIME Manager WiFi Switch."""
from __future__ import annotations

from typing import Any
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_URL, CONF_USE_SNMP, CONF_SNMP_MODE, SNMP_MODE_RW

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """스위치 엔티티 등록."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # SNMP를 사용하고 읽기/쓰기 모드인 경우에만 WiFi 스위치 등록
    snmp_mode = entry.options.get(CONF_SNMP_MODE, entry.data.get(CONF_SNMP_MODE))
    if entry.options.get(CONF_USE_SNMP) and snmp_mode == SNMP_MODE_RW:
        snmp_data = coordinator.data.get("snmp", {})
        wifi_list = snmp_data.get("wifi", {})
        
        entities = []
        for idx, info in wifi_list.items():
            entities.append(IPTimeWifiSwitch(coordinator, entry, idx, info.get("ssid")))
            entities.append(IPTimeWifiBroadcastSwitch(coordinator, entry, idx, info.get("ssid")))
        
        async_add_entities(entities)

class IPTimeWifiSwitch(CoordinatorEntity, SwitchEntity):
    """WiFi On/Off 제어 스위치."""

    def __init__(self, coordinator, entry, idx: str, ssid: str) -> None:
        super().__init__(coordinator)
        self._idx = idx
        self._entry = entry
        
        # 이름에서 SSID 제외 규칙 적용
        snmp_data = coordinator.data.get("snmp", {})
        info = snmp_data.get("wifi", {}).get(idx, {})
        mode_map_short = {0: "2.4G", 1: "5G", 2: "5G-2", 3: "6G", 4: "6G-2", 8: "MLO"}
        band_tag = mode_map_short.get(info.get("mode"), "Unknown")
        
        self._attr_name = f"ipTIME WiFi {band_tag} Switch ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_wifi_switch_{idx}"

    @property
    def is_on(self) -> bool:
        """WiFi 활성화 상태 확인."""
        snmp_data = self.coordinator.data.get("snmp", {})
        wifi = snmp_data.get("wifi", {})
        return wifi.get(self._idx, {}).get("enable", 0) == 1

    @property
    def icon(self) -> str:
        """상태에 따른 아이콘."""
        return "mdi:wifi-check" if self.is_on else "mdi:wifi-off"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """WiFi 켜기."""
        oid = f".1.3.6.1.4.1.12874.1.4.2.1.9.{self._idx}"
        success = await self.coordinator.api.async_snmp_set(oid, 1)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """WiFi 끄기."""
        oid = f".1.3.6.1.4.1.12874.1.4.2.1.9.{self._idx}"
        success = await self.coordinator.api.async_snmp_set(oid, 0)
        if success:
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> dict[str, Any]:
        snmp_data = self.coordinator.data.get("snmp", {}) if self.coordinator.data else {}
        model = snmp_data.get("model", "ipTIME Router")
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM-Networks",
            "model": model,
        }

class IPTimeWifiBroadcastSwitch(CoordinatorEntity, SwitchEntity):
    """WiFi SSID 숨김/보임 제어 스위치."""

    def __init__(self, coordinator, entry, idx: str, ssid: str) -> None:
        super().__init__(coordinator)
        self._idx = idx
        self._entry = entry
        
        snmp_data = coordinator.data.get("snmp", {})
        info = snmp_data.get("wifi", {}).get(idx, {})
        mode_map_short = {0: "2.4G", 1: "5G", 2: "5G-2", 3: "6G", 4: "6G-2", 8: "MLO"}
        band_tag = mode_map_short.get(info.get("mode"), "Unknown")
        
        self._attr_name = f"ipTIME WiFi {band_tag} Broadcast ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_wifi_broadcast_{idx}"

    @property
    def is_on(self) -> bool:
        """SSID 브로드캐스트 상태 확인."""
        snmp_data = self.coordinator.data.get("snmp", {})
        wifi = snmp_data.get("wifi", {})
        return wifi.get(self._idx, {}).get("broadcast", 1) == 1

    @property
    def icon(self) -> str:
        """상태에 따른 아이콘 (눈 모양)."""
        return "mdi:eye" if self.is_on else "mdi:eye-off"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """SSID 보이기 (Visible)."""
        oid = f".1.3.6.1.4.1.12874.1.4.2.1.3.{self._idx}"
        success = await self.coordinator.api.async_snmp_set(oid, 1)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """SSID 숨기기 (Hidden)."""
        oid = f".1.3.6.1.4.1.12874.1.4.2.1.3.{self._idx}"
        success = await self.coordinator.api.async_snmp_set(oid, 0)
        if success:
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> dict[str, Any]:
        snmp_data = self.coordinator.data.get("snmp", {}) if self.coordinator.data else {}
        model = snmp_data.get("model", "ipTIME Router")
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM-Networks",
            "model": model,
        }
