from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME

# 요약: ipTIME 공유기 연결 기기 목록을 바탕으로 재실 상태를 관리하는 플랫폼
# 연결될 파일: const.py, coordinator.py, __init__.py

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """기기 추적기 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_map = entry.data.get("devices", {})
    
    _LOGGER.debug("ipTIME Device Tracker 설정 시작: %s 기기 등록됨", len(device_map))
    
    entities = [
        IPTimeDeviceEntity(coordinator, entry, mac, name)
        for mac, name in device_map.items()
    ]
    async_add_entities(entities)

class IPTimeDeviceEntity(CoordinatorEntity, ScannerEntity):
    """ipTIME 연결 기기 엔티티."""

    def __init__(self, coordinator, entry, mac: str, name: str) -> None:
        super().__init__(coordinator)
        # 매칭용 MAC: 모든 기호 제거 후 소문자
        self._mac = mac.replace(":", "").replace("-", "").lower()
        self._attr_name = name
        # 고유 ID는 기존 호환성을 위해 원본 MAC 사용
        self._attr_unique_id = f"{entry.entry_id}_{mac}"
        self._entry = entry
        self._last_seen: Any = None
        _LOGGER.debug("[%s] 엔티티 초기화 완료 (매칭 MAC: %s)", name, self._mac)

    @property
    def is_connected(self) -> bool:
        """연결 상태 확인."""
        if not self.coordinator.data:
            return False
            
        # 코디네이터 통합 데이터에서 기기 목록 추출
        devices = self.coordinator.data.get("devices", {})
        device = devices.get(self._mac)
        
        # 만약 못 찾았다면, 데이터 내의 키들을 다시 한 번 표준화해서 비교 시도
        if not device:
            for k, v in devices.items():
                if isinstance(v, dict) and k.replace(":", "").replace("-", "").lower() == self._mac:
                    device = v
                    break
        
        is_now_home = device is not None and device.get("state") == "home"
        _LOGGER.error(f"ipTIME 트래커 [{self._attr_name}] 매칭 시도 (MAC: {self._mac}): {'성공' if device else '실패'}")
        
        if is_now_home:
            self._last_seen = dt_util.utcnow()
            return True
            
        if self._last_seen is None:
            return False
            
        timeout = self._entry.options.get(
            CONF_CONSIDER_HOME, 
            self._entry.data.get(CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME)
        )
        
        return (dt_util.utcnow() - self._last_seen).total_seconds() < timeout

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def mac_address(self) -> str:
        return self._mac

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """추가 속성 제공."""
        # 통합 데이터에서 해당 MAC의 정보 추출
        devices = self.coordinator.data.get("devices", {}) if self.coordinator.data else {}
        device = devices.get(self._mac)
        
        if not isinstance(device, dict):
            device = {}
            
        return {
            "ip": device.get("ip"),
            "band": device.get("band"),
            "stay_time": device.get("stay_time"),
            "rssi": device.get("rssi"),
            "last_seen": self._last_seen.isoformat() if self._last_seen else None
        }

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
        }