from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

try:
    from homeassistant.components.ssdp import SsdpServiceInfo
except ImportError:
    # 최신 버전이나 환경에 따라 임포트 경로가 다를 수 있으므로 예외 처리
    SsdpServiceInfo = Any

from .const import *
from .api import IPTimeAPI

_LOGGER = logging.getLogger(__name__)

def _format_mac(mac: str) -> str:
    """소문자/기호 없는 MAC 주소를 대문자 및 콜론(:)이 포함된 표준 형태로 포맷팅한다."""
    clean = mac.replace(":", "").replace("-", "").upper()
    if len(clean) == 12:
        return ":".join(clean[i:i+2] for i in range(0, 12, 2))
    return clean

class IPTimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ipTIME Manager 설정 흐름."""
    
    VERSION = 1

    def __init__(self) -> None:
        self.temp_config: Dict[str, Any] = {}
        self.selected_macs: List[str] = []
        self.device_map: Dict[str, str] = {}

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> FlowResult:
        """SSDP 자동 탐지 처리."""
        # 객체와 딕셔너리 형태 모두 대응
        upnp = getattr(discovery_info, "upnp", {}) or {}
        url = upnp.get("presentationURL")
        
        if not url:
            from urllib.parse import urlparse
            loc = getattr(discovery_info, "ssdp_location", None) or getattr(discovery_info, "location", None)
            if loc:
                p = urlparse(loc)
                url = f"{p.scheme}://{p.netloc}"
        
        if url:
            self.temp_config[CONF_URL] = url
            # 중복 체크
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            return await self.async_step_user()
            
        return self.async_abort(reason="cannot_connect")

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """사용자 입력 처리 (1단계)."""
        if user_input is not None:
            self.temp_config = user_input
            # URL 기반 Unique ID 설정
            await self.async_set_unique_id(user_input[CONF_URL])
            self._abort_if_unique_id_configured()
            return await self.async_step_select_devices()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=self.temp_config.get(CONF_URL, "")): str,
                vol.Required(CONF_ID): str,
                vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                vol.Optional(CONF_CONSIDER_HOME, default=DEFAULT_CONSIDER_HOME): int,
            })
        )

    async def async_step_select_devices(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """추적 대상 기기 선택 (2단계)."""
        errors: dict[str, str] = {}
        api = IPTimeAPI(self.hass, self.temp_config[CONF_URL], self.temp_config[CONF_ID], self.temp_config[CONF_PASSWORD])
        
        try:
            # 리팩토링된 비동기 API 호출
            if not await api.verify_mobile():
                errors["base"] = "cannot_connect"
            elif not await api.async_update():
                errors["base"] = "invalid_auth"
        except Exception as err:
            _LOGGER.error("공유기 접속 중 오류: %s", err)
            errors["base"] = "unknown"
        finally:
            await api.async_close()

        if not errors:
            options = {mac: f"{info.get('ip', 'N/A')} ({_format_mac(mac)})" for mac, info in api.result.items() if mac != "session" and isinstance(info, dict)}
            if not options:
                errors["base"] = "no_devices_found"
            elif user_input is not None:
                self.selected_macs = user_input[CONF_TARGET]
                return await self.async_step_name_devices()
            
            return self.async_show_form(
                step_id="select_devices", 
                data_schema=vol.Schema({vol.Required(CONF_TARGET): cv.multi_select(options)}),
                errors=errors
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=self.temp_config.get(CONF_URL)): str,
                vol.Required(CONF_ID, default=self.temp_config.get(CONF_ID)): str,
                vol.Required(CONF_PASSWORD, default=self.temp_config.get(CONF_PASSWORD)): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                vol.Optional(CONF_CONSIDER_HOME, default=self.temp_config.get(CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME)): int,
            }),
            errors=errors
        )

    async def async_step_name_devices(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """기기 이름 설정 (3단계)."""
        if user_input is not None:
            self.device_map[self.selected_macs.pop(0)] = user_input[CONF_NAME]
            if self.selected_macs:
                return await self.async_step_name_devices()
            return self.async_create_entry(
                title=f"ipTIME ({self.temp_config[CONF_URL]})", 
                data={**self.temp_config, "devices": self.device_map}
            )

        next_mac = self.selected_macs[0]
        return self.async_show_form(
            step_id="name_devices", 
            data_schema=vol.Schema({vol.Required(CONF_NAME, default=f"iptime_{next_mac}"): str}), 
            description_placeholders={"mac_address": next_mac}
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> IPTimeOptionsFlowHandler:
        return IPTimeOptionsFlowHandler(config_entry)

class IPTimeOptionsFlowHandler(config_entries.OptionsFlow):
    """옵션 관리 흐름."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry
        self.new_macs: List[str] = []
        self.device_map = dict(config_entry.data.get("devices", {}))
        self.temp_options: Dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """옵션 초기화 단계."""
        if user_input is not None:
            selected = user_input.get(CONF_TARGET, [])
            self.new_macs = [mac for mac in selected if mac not in self.device_map]
            # device_map은 파괴하지 않고 보존하며, temp_options에 targets를 안전하게 분리 저장
            self.temp_options = {
                CONF_CONSIDER_HOME: user_input[CONF_CONSIDER_HOME],
                CONF_TARGET: selected,
            }
            
            if user_input.get("add_manual"):
                return await self.async_step_add_manual()
            if self.new_macs:
                return await self.async_step_name_new_devices()
            return self._save_config()

        options: dict[str, str] = {}
        coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        if coordinator and coordinator.data:
            devices = coordinator.data.get("devices", {})
            for mac, info in devices.items():
                if mac != "session" and isinstance(info, dict):
                    options[mac] = f"{info.get('ip', 'N/A')} ({_format_mac(mac)})"
        
        for mac, name in self.device_map.items():
            if mac not in options:
                options[mac] = f"{name} (오프라인 - {_format_mac(mac)})"
            
        current_timeout = self._config_entry.options.get(
            CONF_CONSIDER_HOME, 
            self._config_entry.data.get(CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME)
        )

        current_targets = self._config_entry.options.get(
            CONF_TARGET,
            list(self.device_map.keys())
        )

        return self.async_show_form(
            step_id="init", 
            data_schema=vol.Schema({
                vol.Optional(CONF_TARGET, default=current_targets): cv.multi_select(options),
                vol.Required(CONF_CONSIDER_HOME, default=current_timeout): int,
                vol.Optional("add_manual", default=False): bool,
            })
        )

    async def async_step_add_manual(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """수동으로 MAC 주소 추가."""
        if user_input is not None:
            mac = user_input[CONF_MAC].replace(":", "").replace("-", "").lower()
            if mac:
                self.new_macs.append(mac)
                return await self.async_step_name_new_devices()

        return self.async_show_form(
            step_id="add_manual",
            data_schema=vol.Schema({
                vol.Required(CONF_MAC): str,
            })
        )

    async def async_step_name_new_devices(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """새로 발견된 기기 이름 설정."""
        if user_input is not None:
            self.device_map[self.new_macs.pop(0)] = user_input[CONF_NAME]
            if self.new_macs:
                return await self.async_step_name_new_devices()
            return self._save_config()

        next_mac = self.new_macs[0]
        return self.async_show_form(
            step_id="name_new_devices", 
            data_schema=vol.Schema({vol.Required(CONF_NAME, default=f"iptime_{next_mac}"): str}), 
            description_placeholders={"mac_address": next_mac}
        )

    def _save_config(self) -> FlowResult:
        """최종 설정 저장."""
        new_data = dict(self._config_entry.data)
        new_data["devices"] = self.device_map
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data, options=self.temp_options)
        return self.async_create_entry(title="", data={})