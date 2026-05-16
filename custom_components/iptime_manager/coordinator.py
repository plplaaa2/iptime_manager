from datetime import timedelta
from typing import Any, Dict, Optional
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import *
from .api import IPTimeAPI

# 요약: Web 및 SNMP 데이터를 통합하여 엔티티에 제공하는 중앙 코디네이터
# 연결될 파일: api.py, const.py, __init__.py, sensor.py, device_tracker.py

_LOGGER = logging.getLogger(__name__)

class IPTimeDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """ipTIME API 데이터를 관리하는 중앙 코디네이터."""

    def __init__(self, hass: HomeAssistant, api: IPTimeAPI, entry: ConfigEntry) -> None:
        self.api = api
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data.get(CONF_URL)}",
            update_interval=timedelta(seconds=DEFAULT_INTERVAL),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """주기적으로 API를 호출하여 최신 데이터를 가져옵니다."""
        try:
            # 1. 기기 추적 정보 (웹 파싱)
            success = await self.api.async_update()
            
            # 2. Web 데이터 수집 (기본/필수)
            await self.api.async_get_web_data()


            if not success:
                _LOGGER.warning("공유기 Web 데이터 수집에 실패했습니다. (인증 또는 통신 오류)")
            
            # 3. 데이터 통합 (Web + SNMP)
            combined_data = {
                "devices": self.api.result,
                "web": self.api.web_result,
            }
            return combined_data
        except Exception as err:
            raise UpdateFailed(f"공유기에서 데이터를 가져오는 중 오류 발생: {err}") from err
