from __future__ import annotations

import re
from typing import Any, Dict

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_URL


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
    return mapping.get(option, (False, "off"))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    web_data = (coordinator.data or {}).get("web", {})
    entities = [IPTimeGeoIPSelect(coordinator, entry)]
    
    if coordinator.api._beta_ui:
        # LED 설정이 지원되는 모델일 경우에만 생성
        if web_data.get("led_config") is not None:
            entities.append(IPTimeNightLEDSelect(coordinator, entry))
            
        # 자동 재부팅 설정이 지원되는 모델일 경우에만 생성
        if web_data.get("reboot_timer") is not None:
            entities.append(IPTimeRebootDaySelect(coordinator, entry))
            

            

        
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

    async def async_select_option(self, option: str) -> None:
        enable, policy = _option_to_policy(option)
        if policy == "off":
            await self.coordinator.api.async_set_web_geoip_policy("off")
            await self.coordinator.api.async_set_web_geoip_enable(False)
        else:
            # 락아웃(Lockout) 방지 지능형 안전 장치: Country Allow(accept) 선택 시 한국('kr')이 누락된 경우 자동 추가
            if policy == "accept":
                web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
                geoip = _get_geoip_data(web_data)
                accept_list = geoip.get("accept_list", [])
                if not isinstance(accept_list, list):
                    accept_list = []
                
                # 'kr'이 없으면 추가 등록 시도
                if "kr" not in [str(c).lower() for c in accept_list]:
                    _LOGGER.info("GeoIP 정책을 국내 허용(Country Allow)으로 변경 시 한국('kr') 자동 등록 - 락아웃 예방")
                    try:
                        # geoip/policy/accept/add API를 호출해 'kr' 국가를 허용 리스트에 지능적으로 추가
                        await self.coordinator.api._async_service_json("geoip/policy/accept/add", "kr")
                    except Exception as err:
                        _LOGGER.warning(f"GeoIP 한국('kr') 자동 등록 실패: {err}")

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
        self._last_valid_on = None
        self._last_valid_off = None

    @property
    def current_option(self) -> str | None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        led_config = web_data.get("led_config", {})
        if not isinstance(led_config, dict):
            led_config = {}
        mode = led_config.get("mode", "on")

        # ipTIME 나이트 LED API: mode="on"이 LED가 항상 켜진 상태(Disabled), mode="off"가 LED가 항상 꺼진 상태(Always Off), mode="schedule"이 스케줄 작동(Time Scheduled)
        # 연결될 파일: api.py
        mapping = {
            "on": "Disabled",
            "off": "Always Off",
            "schedule": "Time Scheduled"
        }
        return mapping.get(mode, "Disabled")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        led_config = web_data.get("led_config", {})
        if not isinstance(led_config, dict):
            led_config = {}
            
        on = led_config.get("on")
        if on is not None:
            self._last_valid_on = on
        on_time = self._last_valid_on if self._last_valid_on is not None else 22
        
        off = led_config.get("off")
        if off is not None:
            self._last_valid_off = off
        off_time = self._last_valid_off if self._last_valid_off is not None else 8

        return {
            "mode": led_config.get("mode", "on"),
            "start_time": f"{on_time:02d}:00",
            "end_time": f"{off_time:02d}:00",
            "start_hour": on_time,
            "end_hour": off_time,
            "start_minutes": on_time * 60,
            "end_minutes": off_time * 60,
        }

    async def async_select_option(self, option: str) -> None:
        # ipTIME 나이트 LED API: Disabled -> "on" (LED 항상 켜짐), Always Off -> "off" (LED 항상 꺼짐), Time Scheduled -> "schedule" (스케줄 작동)
        # 연결될 파일: api.py
        mapping = {
            "Disabled": "on",
            "Always Off": "off",
            "Time Scheduled": "schedule"
        }
        mode = mapping.get(option, "on")

        # 기존 시간 값을 유지하거나 기본값(22:00 ~ 08:00)을 사용
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        led_config = web_data.get("led_config", {})
        if not isinstance(led_config, dict):
            led_config = {}
            
        on = led_config.get("on")
        if on is not None:
            self._last_valid_on = on
        on_time = self._last_valid_on if self._last_valid_on is not None else 22
        
        off = led_config.get("off")
        if off is not None:
            self._last_valid_off = off
        off_time = self._last_valid_off if self._last_valid_off is not None else 8

        await self.coordinator.api.async_set_web_led_config(mode, on_time, off_time)
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
        self._last_valid_hour = None
        self._last_valid_min = None
        self._last_valid_days = None

    @property
    def current_option(self) -> str | None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        timer = web_data.get("reboot_timer", {})
        
        d = timer.get("days")
        if d is not None:
            self._last_valid_days = d
        days = self._last_valid_days if self._last_valid_days is not None else ["Fri"]

        if not isinstance(days, list) or not days:
            return "Friday"

        if len(days) >= 7:
            return "Everyday"

        day_map = {
            "mon": "Monday",
            "tue": "Tuesday",
            "wed": "Wednesday",
            "thu": "Thursday",
            "fri": "Friday",
            "sat": "Saturday",
            "sun": "Sunday"
        }

        first_day = str(days[0]).lower()
        return day_map.get(first_day, "Friday")

    async def async_select_option(self, option: str) -> None:
        day_map = {
            "Everyday": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            "Monday": ["Mon"],
            "Tuesday": ["Tue"],
            "Wednesday": ["Wed"],
            "Thursday": ["Thu"],
            "Friday": ["Fri"],
            "Saturday": ["Sat"],
            "Sunday": ["Sun"]
        }
        target_days = day_map.get(option, ["Fri"])
        self._last_valid_days = target_days

        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        timer = web_data.get("reboot_timer", {})
        run = timer.get("run", False)
        
        h = timer.get("hour")
        if h is not None:
            self._last_valid_hour = h
        hour = self._last_valid_hour if self._last_valid_hour is not None else 4
        
        m = timer.get("min")
        if m is not None:
            self._last_valid_min = m
        min_time = self._last_valid_min if self._last_valid_min is not None else 0

        await self.coordinator.api.async_set_web_reboot_timer(run, hour, min_time, target_days)
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
