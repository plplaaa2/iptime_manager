from datetime import timedelta
from typing import Any, Dict, Optional
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import *
from .api import IPTimeAPI

# \uc694\uc57d: Web \ubc0f SNMP \ub370\uc774\ud130\ub9bc \ud1b5\ud569\ud558\uc5ec \uc5d4\ud2f0\ud2f0\uc5d0 \uc81c\uacf5\ud558\ub294 \uc911\uc559 \ucf54\ub514\ub124\uc774\ud130
# \uc5f0\uacb0\ub420 \ud30c\uc77c: api.py, const.py, __init__.py, sensor.py, device_tracker.py

_LOGGER = logging.getLogger(__name__)

class IPTimeDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """ipTIME API \ub370\uc774\ud130\ub9bc \uad00\ub9ac\ud558\ub294 \uc911\uc559 \ucf54\ub514\ub124\uc774\ud130."""

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
            
            # 2. SNMP 정보 (설정된 경우에만 수집)
            use_snmp = self.entry.options.get(CONF_USE_SNMP, self.entry.data.get(CONF_USE_SNMP, False))
            if use_snmp:
                _LOGGER.info("ipTIME SNMP 데이터 수집 시작...")
                await self.api.async_get_snmp_data(
                    version=self.entry.options.get(CONF_SNMP_VERSION, self.entry.data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)),
                    community=self.entry.options.get(CONF_SNMP_COMMUNITY, self.entry.data.get(CONF_SNMP_COMMUNITY, DEFAULT_SNMP_COMMUNITY)),
                    username=self.entry.options.get(CONF_SNMP_USER, self.entry.data.get(CONF_SNMP_USER, "")),
                    auth_key=self.entry.options.get(CONF_SNMP_AUTH_KEY, self.entry.data.get(CONF_SNMP_AUTH_KEY, "")),
                    priv_key=self.entry.options.get(CONF_SNMP_PRIV_KEY, self.entry.data.get(CONF_SNMP_PRIV_KEY, "")),
                    auth_protocol=self.entry.options.get(CONF_SNMP_AUTH_PROTOCOL, self.entry.data.get(CONF_SNMP_AUTH_PROTOCOL, DEFAULT_SNMP_AUTH_PROTOCOL)),
                    priv_protocol=self.entry.options.get(CONF_SNMP_PRIV_PROTOCOL, self.entry.data.get(CONF_SNMP_PRIV_PROTOCOL, DEFAULT_SNMP_PRIV_PROTOCOL)),
                    port=self.entry.options.get(CONF_SNMP_PORT, self.entry.data.get(CONF_SNMP_PORT, DEFAULT_SNMP_PORT)),
                )
            else:
                _LOGGER.debug("SNMP 사용이 비활성화되어 수집을 건너뜁니다.")
            
            if not success:
                _LOGGER.info("\uacf5\uc720\uae30 Web \ub370\uc774\ud130 \uc218\uc9d1\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4. (\uc778\uc99d \ub610\ub294 \ud1b5\uc2e0 \uc624\ub958)")
            
            # 3. 데이터 통합 (Web + SNMP)
            combined_data = {
                "devices": self.api.result,
                "snmp": self.api.snmp_result
            }
            return combined_data
        except Exception as err:
            raise UpdateFailed(f"\uacf5\uc720\uae30\uc5d0\uc11c \ub370\uc774\ud130\ub9bc \uac00\uc838\uc624\ub294 \uc911 \uc624\ub958 \ubc1c\uc0dd: {err}") from err