from __future__ import annotations

import logging
import re
from typing import Any, Dict

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_URL
from .api import channel_option_value, is_easymesh_agent
from .admin import require_admin

_LOGGER = logging.getLogger(__name__)


def _get_geoip_data(web_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(web_data, dict):
        return {}
    security = web_data.get("security", {})
    if isinstance(security, dict):
        geoip = security.get("geoip")
        if isinstance(geoip, dict):
            return geoip
    geoip = web_data.get("geoip")
    return geoip if isinstance(geoip, dict) else {}


def _policy_to_option(enable: Any, policy: Any) -> str | None:
    if not bool(enable):
        return "Off"

    value = str(policy or "").lower()
    mapping = {
        "off": "Off",
        "drop": "Country Block",
        "accept": "Country Allow",
    }
    return mapping.get(value)


def _option_to_policy(option: str) -> tuple[bool, str]:
    mapping = {
        "Off": (False, "off"),
        "Country Block": (True, "drop"),
        "Country Allow": (True, "accept"),
    }
    if option not in mapping:
        raise HomeAssistantError("Invalid GeoIP policy")
    return mapping[option]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    web_data = (coordinator.data or {}).get("web", {})
    agent_mode = is_easymesh_agent(web_data)
    entities = [] if agent_mode else [IPTimeGeoIPSelect(coordinator, entry)]

    if agent_mode:
        registry = er.async_get(hass)
        entity_id = registry.async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_geoip_policy")
        if entity_id:
            registry.async_remove(entity_id)
    
    if coordinator.api._beta_ui:
        # LED 설정이 지원되는 모델일 경우에만 생성
        if web_data.get("led_config") is not None:
            entities.append(IPTimeNightLEDSelect(coordinator, entry))
            
        # 자동 재부팅 설정이 지원되는 모델일 경우에만 생성
        if web_data.get("reboot_timer") is not None:
            entities.append(IPTimeRebootDaySelect(coordinator, entry))
            
        # 무선 채널 제어 셀렉터 동적 생성
        wireless = web_data.get("wireless", {})
        bands = wireless.get("band", [])
        if isinstance(bands, list):
            for b in bands:
                band_id = b.get("band")
                if band_id:
                    entities.append(IPTimeWifiChannelSelect(coordinator, entry, band_id))

            

        
    async_add_entities(entities)


# 요약: GeoIP 정책을 3단계 select로 노출한다.
# 연결 파일: api.py, coordinator.py, sensor.py
class IPTimeGeoIPSelect(CoordinatorEntity, SelectEntity):
    """GeoIP policy selector."""

    _attr_options = ["Off", "Country Block", "Country Allow"]

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_geoip_policy"
        self._attr_name = f"GeoIP Policy ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:earth"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def current_option(self) -> str | None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        geoip = _get_geoip_data(web_data)
        return _policy_to_option(geoip.get("enable"), geoip.get("policy"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        geoip = _get_geoip_data(web_data)
        return {
            "enable": geoip.get("enable"),
            "policy": geoip.get("policy"),
            "drop_list": geoip.get("drop_list"),
            "accept_list": geoip.get("accept_list"),
        }

    # Summary: Require an admin to apply GeoIP policy while preserving country lists.
    # Related files: admin.py, api.py, coordinator.py.
    @require_admin
    async def async_select_option(self, option: str) -> None:
        enable, policy = _option_to_policy(option)
        if policy == "off":
            await self.coordinator.api.async_set_web_geoip_policy("off")
            await self.coordinator.api.async_set_web_geoip_enable(False)
        else:
            await self.coordinator.api.async_set_web_geoip_enable(enable)
            await self.coordinator.api.async_set_web_geoip_policy(policy)
        await self.coordinator.async_request_refresh()

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


# 요약: 나이트 LED 모드 설정 셀렉터 (연결될 파일: api.py)
class IPTimeNightLEDSelect(CoordinatorEntity, SelectEntity):
    """Night LED Mode selector."""

    _attr_options = ["Disabled", "Always Off", "Time Scheduled"]

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_night_led"
        self._attr_name = f"Night LED Mode ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:led-off"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def current_option(self) -> str | None:
        config = (self.coordinator.data or {}).get("web", {}).get("led_config")
        if not isinstance(config, dict):
            return None
        return {"on": "Disabled", "off": "Always Off", "schedule": "Time Scheduled"}.get(config.get("mode"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        config = (self.coordinator.data or {}).get("web", {}).get("led_config")
        config = config if isinstance(config, dict) else {}
        attributes = {"mode": config.get("mode")}
        for field, prefix in (("on", "start"), ("off", "end")):
            hour = config.get(field)
            if type(hour) is not int or not 0 <= hour <= 23:
                hour = None
            attributes[f"{prefix}_time"] = f"{hour:02d}:00" if hour is not None else None
            attributes[f"{prefix}_hour"] = hour
            attributes[f"{prefix}_minutes"] = hour * 60 if hour is not None else None
        return attributes

    async def async_select_option(self, option: str) -> None:
        # Summary: Send only the selected mode; the API freshly reads retained times.
        # Related files: api.py, tests/test_settings.py.
        mapping = {"Disabled": "on", "Always Off": "off", "Time Scheduled": "schedule"}
        if option not in mapping:
            raise HomeAssistantError("Invalid Night LED mode")
        await self.coordinator.api.async_set_web_led_config(mapping[option])
        await self.coordinator.async_request_refresh()

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


# 요약: 자동 재시작 요일을 셀렉트로 제어한다. (연결 파일: api.py)
class IPTimeRebootDaySelect(CoordinatorEntity, SelectEntity):
    """Auto Reboot Day selector."""

    _attr_options = ["Everyday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_reboot_day"
        self._attr_name = f"Auto Reboot Day ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:calendar-week"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def current_option(self) -> str | None:
        timer = (self.coordinator.data or {}).get("web", {}).get("reboot_timer")
        days = timer.get("days") if isinstance(timer, dict) else None
        if not isinstance(days, list) or not days or any(not isinstance(day, str) for day in days):
            return None
        labels = {
            "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday",
            "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
        }
        normalized = {day.lower() for day in days}
        if normalized == set(labels):
            return "Everyday"
        if len(normalized) == 1:
            return labels.get(next(iter(normalized)))
        return None

    # Summary: Require an admin before changing the reboot schedule.
    # Related files: admin.py, api.py.
    @require_admin
    async def async_select_option(self, option: str) -> None:
        day_map = {
            "Everyday": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            "Monday": ["Mon"], "Tuesday": ["Tue"], "Wednesday": ["Wed"],
            "Thursday": ["Thu"], "Friday": ["Fri"], "Saturday": ["Sat"], "Sunday": ["Sun"],
        }
        if option not in day_map:
            raise HomeAssistantError("Invalid reboot day")
        await self.coordinator.api.async_set_web_reboot_timer(None, days=day_map[option])
        await self.coordinator.async_request_refresh()

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


# 요약: 무선 채널 제어 셀렉터 (연결될 파일: api.py)
class IPTimeWifiChannelSelect(CoordinatorEntity, SelectEntity):
    """Wi-Fi Channel selector."""

    def __init__(self, coordinator, entry, band: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._band = band
        self._attr_unique_id = f"{entry.entry_id}_wifi_channel_{band}"
        
        # 대역 친화적 명칭 정규화
        band_label = {
            "2g": "2.4GHz",
            "5g": "5GHz",
            "5g-2": "5GHz-2",
            "6g": "6GHz",
            "6g-2": "6GHz-2",
            "mlo": "MLO",
        }.get(str(band).lower(), str(band).upper())

        self._attr_name = f"Wi-Fi Channel {band_label} ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:wifi-cog"
        self._attr_entity_category = EntityCategory.CONFIG
        self._cached_options = ["auto"]
        self._last_options_update = 0.0

    @property
    def current_option(self) -> str | None:
        """현재 설정된 채널 반환."""
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        wireless = web_data.get("wireless", {})
        bands = wireless.get("band", [])
        if isinstance(bands, list):
            for b in bands:
                if str(b.get("band")).lower() == str(self._band).lower():
                    ch = b.get("channel")
                    return channel_option_value(ch)
        return "auto"

    @property
    def options(self) -> list[str]:
        """사용 가능한 채널 목록 반환 (API 부하 최소화를 위한 1시간 캐싱)."""
        import time
        now = time.time()
        
        # 1시간(3600초) 마다 또는 최초 진입 시 채널 목록을 공유기 API에서 새로 가져옴
        if not self._cached_options or len(self._cached_options) <= 1 or (now - self._last_options_update) > 3600.0:
            self.hass.async_create_task(self._async_update_options())
            
        return self._cached_options

    async def _async_update_options(self) -> None:
        """비동기식으로 채널 목록을 수집하여 캐시 갱신."""
        import time
        try:
            channels = await self.coordinator.api.async_get_wireless_channel_list(self._band)
            if channels and len(channels) > 0:
                self._cached_options = channels
                self._last_options_update = time.time()
                self.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug(f"Failed to update channel list for band {self._band}: {err}")

    # Summary: Require an admin before changing the wireless channel.
    # Related files: admin.py, api.py.
    @require_admin
    async def async_select_option(self, option: str) -> None:
        """사용자가 채널 선택 시 공유기 채널 변경 실행."""
        channel_to_set = option.split(" ")[0] if option != "auto" else "auto"
        success = await self.coordinator.api.async_set_wireless_channel(self._band, channel_to_set)
        if success:
            await self.coordinator.async_request_refresh()

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
