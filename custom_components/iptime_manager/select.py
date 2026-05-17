from __future__ import annotations

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
            
        # IPTV 설정이 지원되는 모델일 경우에만 생성
        if web_data.get("iptv_config") is not None:
            entities.append(IPTimeIPTVSelect(coordinator, entry))
        
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

    @property
    def current_option(self) -> str | None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        led_config = web_data.get("led_config", {})
        mode = led_config.get("mode", "off")

        mapping = {
            "off": "Disabled",
            "on": "Always Off",
            "interval": "Time Scheduled"
        }
        return mapping.get(mode, "Disabled")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        led_config = web_data.get("led_config", {})
        on_time = led_config.get("on", 1320)
        off_time = led_config.get("off", 480)

        # 분 단위를 HH:MM 형식으로 변환
        on_hour, on_min = divmod(on_time, 60)
        off_hour, off_min = divmod(off_time, 60)

        return {
            "mode": led_config.get("mode", "off"),
            "start_time": f"{on_hour:02d}:{on_min:02d}",
            "end_time": f"{off_hour:02d}:{off_min:02d}",
            "start_minutes": on_time,
            "end_minutes": off_time,
        }

    async def async_select_option(self, option: str) -> None:
        mapping = {
            "Disabled": "off",
            "Always Off": "on",
            "Time Scheduled": "interval"
        }
        mode = mapping.get(option, "off")

        # 기존 시간 값을 유지하거나 기본값(22:00 ~ 08:00)을 사용
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        led_config = web_data.get("led_config", {})
        on_time = led_config.get("on", 1320)
        off_time = led_config.get("off", 480)

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

    @property
    def current_option(self) -> str | None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        timer = web_data.get("reboot_timer", {})
        days = timer.get("days", ["Fri"])

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

        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        timer = web_data.get("reboot_timer", {})
        run = timer.get("run", False)
        hour = timer.get("hour", 4)
        min_time = timer.get("min", 0)

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


# 요약: IPTV 셀렉트 엔티티로 제어한다. (연결 파일: api.py)
class IPTimeIPTVSelect(CoordinatorEntity, SelectEntity):
    """ipTIME IPTV configuration selector."""

    _attr_options = [
        "Disabled",
        "Private IP (IGMP Proxy) - SKB, LGU+",
        "Public IP (LAN Port) - KT",
        "Public IP (MACVLAN) - KT",
        "Public IP (LAN Port) - SCS",
        "Private IP (All Ports) - SCS"
    ]

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_iptv_mode"
        self._attr_name = f"IPTV Mode ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:television-box"

    @property
    def current_option(self) -> str | None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        iptv = web_data.get("iptv_config", {})
        
        # iptv가 딕셔너리가 아닌 문자열 등으로 들어올 경우 대비 예외 처리
        if not isinstance(iptv, dict):
            mode = str(iptv)
        else:
            mode = iptv.get("mode", "off")

        mapping = {
            "off": "Disabled",
            "private": "Private IP (IGMP Proxy) - SKB, LGU+",
            "public": "Public IP (LAN Port) - KT",
            "macvlan": "Public IP (MACVLAN) - KT",
            "scs": "Public IP (LAN Port) - SCS",
            "scsp": "Private IP (All Ports) - SCS"
        }
        return mapping.get(mode, "Disabled")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        iptv = web_data.get("iptv_config", {})
        
        if not isinstance(iptv, dict):
            iptv = {"mode": str(iptv)}

        return {
            "raw_mode": iptv.get("mode", "off"),
            "designated_port": iptv.get("port"),
        }

    async def async_select_option(self, option: str) -> None:
        mapping = {
            "Disabled": "off",
            "Private IP (IGMP Proxy) - SKB, LGU+": "private",
            "Public IP (LAN Port) - KT": "public",
            "Public IP (MACVLAN) - KT": "macvlan",
            "Public IP (LAN Port) - SCS": "scs",
            "Private IP (All Ports) - SCS": "scsp"
        }
        mode = mapping.get(option, "off")

        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        iptv = web_data.get("iptv_config", {})
        
        if not isinstance(iptv, dict):
            port = None
        else:
            port = iptv.get("port")

        await self.coordinator.api.async_set_web_iptv_config(mode, port)
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
