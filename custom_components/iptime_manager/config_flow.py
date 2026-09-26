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
from .api import IPTimeAPI, get_easymesh_role

_LOGGER = logging.getLogger(__name__)

def _is_private_mac(mac: str) -> bool:
    """사설(임의) MAC 주소인지 판단한다.
    첫 번째 바이트의 두 번째 16진수 문자가 2, 6, A, E 중 하나이면 사설 MAC 주소이다.
    """
    clean = mac.replace(":", "").replace("-", "").lower()
    if len(clean) >= 2:
        return clean[1] in ("2", "6", "a", "e")
    return False

def _format_mac(mac: str) -> str:
    """소문자/기호 없는 MAC 주소를 대문자 및 콜론(:)이 포함된 표준 형태로 포맷팅한다."""
    clean = mac.replace(":", "").replace("-", "").upper()
    if len(clean) == 12:
        return ":".join(clean[i:i+2] for i in range(0, 12, 2))
    return clean


def _default_presence_name(label: str, mac: str) -> str:
    """Return a readable default sensor name from a router inventory label."""
    label = label.removeprefix("[임의 MAC / Private MAC] ")
    return label.split(" (", 1)[0].strip() or _format_mac(mac)


def _presence_name_field(label: str, mac: str) -> str:
    """Use the selected router client label for the name field shown in the flow."""
    return label or _format_mac(mac)


def _presence_inventory(hass) -> tuple[bool, dict[str, str]]:
    """Return presence-list eligibility and known clients from all router entries."""
    coordinators = hass.data.get(DOMAIN, {})
    entries = {
        entry.entry_id: entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if not is_presence_list_entry(entry.data)
    }
    eligible = False
    options: dict[str, str] = {}

    for entry_id, entry in entries.items():
        coordinator = coordinators.get(entry_id)
        if (
            coordinator is None
            or coordinator.last_update_success is False
            or (coordinator.data or {}).get("presence_scan_success") is False
        ):
            continue

        web_data = (coordinator.data or {}).get("web", {})
        role = get_easymesh_role(web_data)
        configured_mode = entry.options.get(
            CONF_DEVICE_MODE,
            entry.data.get(CONF_DEVICE_MODE, DEFAULT_DEVICE_MODE),
        )
        if role != "agent" and (
            role in ("controller", "alone")
            or configured_mode in (DEVICE_MODE_SINGLE, DEVICE_MODE_CONTROLLER)
        ):
            eligible = True

        known_names = entry.data.get("devices", {})
        devices = (coordinator.data or {}).get("devices", {})
        for mac, info in devices.items():
            if mac == "session" or not isinstance(info, dict):
                continue
            normalized_mac = str(mac).replace(":", "").replace("-", "").lower()
            ip = info.get("ip", "N/A")
            name = known_names.get(mac) or known_names.get(normalized_mac) or info.get("name")
            formatted_mac = _format_mac(normalized_mac)
            label = f"{name} ({ip}, {formatted_mac})" if name else f"{ip} ({formatted_mac})"
            if _is_private_mac(normalized_mac):
                label = f"[임의 MAC / Private MAC] {label}"
            options[normalized_mac] = label

        # Keep previously configured clients selectable even while offline.
        for mac, name in entry.data.get("devices", {}).items():
            normalized_mac = str(mac).replace(":", "").replace("-", "").lower()
            if normalized_mac not in options:
                formatted_mac = _format_mac(normalized_mac)
                prefix = "[임의 MAC / Private MAC] " if _is_private_mac(normalized_mac) else ""
                options[normalized_mac] = f"{prefix}{name} (오프라인 - {formatted_mac})"

    return eligible, options

class IPTimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ipTIME Manager 설정 흐름."""
    
    VERSION = 1

    def __init__(self) -> None:
        self.temp_config: Dict[str, Any] = {}
        self.selected_macs: List[str] = []
        self.presence_names: dict[str, str] = {}
        self.presence_options: dict[str, str] = {}
        self.presence_index = 0

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
            return await self.async_step_router()
            
        return self.async_abort(reason="cannot_connect")

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """공유기 또는 재실 센서 목록 추가 방식을 선택한다."""
        return self.async_show_menu(step_id="user", menu_options=["router", "presence"])

    async def async_step_router(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """기존 공유기 추가 흐름."""
        if user_input is not None:
            self.temp_config = user_input
            # URL 기반 Unique ID 설정
            await self.async_set_unique_id(user_input[CONF_URL])
            self._abort_if_unique_id_configured()
            return await self.async_step_validate_router()

        return self.async_show_form(
            step_id="router",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=self.temp_config.get(CONF_URL, "")): str,
                vol.Required(CONF_ID): str,
                vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                vol.Optional(CONF_RSSI_LIMIT, default=DEFAULT_RSSI_LIMIT): int,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                vol.Required(CONF_DEVICE_MODE, default=DEFAULT_DEVICE_MODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[DEVICE_MODE_AUTO, DEVICE_MODE_SINGLE, DEVICE_MODE_CONTROLLER, DEVICE_MODE_AGENT],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            })
        )

    async def async_step_validate_router(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Validate credentials and add the router without creating per-device trackers."""
        errors: dict[str, str] = {}
        api = IPTimeAPI(self.hass, self.temp_config[CONF_URL], self.temp_config[CONF_ID], self.temp_config[CONF_PASSWORD])
        
        try:
            # 리팩토링된 비동기 API 호출
            if not await api.verify_mobile():
                errors["base"] = "cannot_connect"
            elif not await api.async_update():
                errors["base"] = "invalid_auth"
        except Exception as err:
            _LOGGER.error("Error connecting to the router: %s", err)
            errors["base"] = "unknown"
        finally:
            await api.async_close()

        if not errors:
            return self.async_create_entry(
                title=f"ipTIME ({self.temp_config[CONF_URL]})",
                data={**self.temp_config, CONF_ENTRY_TYPE: ENTRY_TYPE_ROUTER, "devices": {}},
            )

        return self.async_show_form(
            step_id="router",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=self.temp_config.get(CONF_URL)): str,
                vol.Required(CONF_ID, default=self.temp_config.get(CONF_ID)): str,
                vol.Required(CONF_PASSWORD, default=self.temp_config.get(CONF_PASSWORD)): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                vol.Optional(CONF_RSSI_LIMIT, default=self.temp_config.get(CONF_RSSI_LIMIT, DEFAULT_RSSI_LIMIT)): int,
                vol.Optional(CONF_SCAN_INTERVAL, default=self.temp_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
                vol.Required(CONF_DEVICE_MODE, default=self.temp_config.get(CONF_DEVICE_MODE, DEFAULT_DEVICE_MODE)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[DEVICE_MODE_AUTO, DEVICE_MODE_SINGLE, DEVICE_MODE_CONTROLLER, DEVICE_MODE_AGENT],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            errors=errors
        )

    def _presence_inventory(self) -> tuple[bool, dict[str, str]]:
        """Return whether presence lists are allowed and known devices from all routers."""
        return _presence_inventory(self.hass)

    async def async_step_presence(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Select devices that will each get their own presence sensor."""
        eligible, options = self._presence_inventory()
        if not eligible:
            return self.async_abort(reason="no_eligible_router")
        if any(
            is_presence_list_entry(entry.data)
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        ):
            return self.async_abort(reason="already_configured")
        if not options:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            self.selected_macs = user_input[CONF_TARGET]
            if not self.selected_macs:
                return self.async_show_form(
                    step_id="presence",
                    data_schema=vol.Schema({vol.Required(CONF_TARGET): cv.multi_select(options)}),
                    errors={"base": "no_devices_found"},
                )
            self.presence_options = options
            self.presence_names = {}
            self.presence_index = 0
            return await self.async_step_presence_device_name()

        return self.async_show_form(
            step_id="presence",
            data_schema=vol.Schema({vol.Required(CONF_TARGET): cv.multi_select(options)}),
        )

    async def async_step_presence_device_name(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Name each selected presence sensor individually."""
        mac = self.selected_macs[self.presence_index]
        field_name = _presence_name_field(self.presence_options.get(mac, ""), mac)
        if user_input is not None:
            name = str(user_input[field_name]).strip()
            if not name:
                return self.async_show_form(
                    step_id="presence_device_name",
                    data_schema=vol.Schema({vol.Required(field_name): str}),
                    errors={"base": "invalid_name"},
                )
            self.presence_names[mac] = name
            self.presence_index += 1
            if self.presence_index < len(self.selected_macs):
                return await self.async_step_presence_device_name()

            await self.async_set_unique_id("home_presence")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Home Presence",
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_PRESENCE_LIST,
                    CONF_NAME: "Home Presence",
                    CONF_TARGET: self.selected_macs,
                    "devices": {mac: self.presence_options.get(mac, mac) for mac in self.selected_macs},
                    "device_names": self.presence_names,
                    CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME,
                },
            )

        default_name = _default_presence_name(self.presence_options.get(mac, mac), mac)
        return self.async_show_form(
            step_id="presence_device_name",
            data_schema=vol.Schema({vol.Required(field_name, default=default_name): str}),
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
        self._presence_targets: list[str] = []
        self._presence_names: dict[str, str] = {}
        self._presence_options: dict[str, str] = {}
        self._presence_timeout = DEFAULT_CONSIDER_HOME
        self._presence_index = 0

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """옵션 초기화 단계."""
        if is_presence_list_entry(self._config_entry.data):
            return await self.async_step_presence_list(user_input)

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_RSSI_LIMIT: user_input[CONF_RSSI_LIMIT],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_DEVICE_MODE: user_input[CONF_DEVICE_MODE],
                },
            )

        current_rssi_limit = self._config_entry.options.get(
            CONF_RSSI_LIMIT,
            self._config_entry.data.get(CONF_RSSI_LIMIT, DEFAULT_RSSI_LIMIT)
        )

        current_scan_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        current_device_mode = self._config_entry.options.get(
            CONF_DEVICE_MODE,
            self._config_entry.data.get(CONF_DEVICE_MODE, DEFAULT_DEVICE_MODE)
        )

        return self.async_show_form(
            step_id="init", 
            data_schema=vol.Schema({
                vol.Required(CONF_RSSI_LIMIT, default=current_rssi_limit): int,
                vol.Required(CONF_SCAN_INTERVAL, default=current_scan_interval): int,
                vol.Required(CONF_DEVICE_MODE, default=current_device_mode): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[DEVICE_MODE_AUTO, DEVICE_MODE_SINGLE, DEVICE_MODE_CONTROLLER, DEVICE_MODE_AGENT],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            })
        )

    async def async_step_presence_list(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Edit selected devices and timeout for the Home Presence device."""
        _, options = _presence_inventory(self.hass)
        stored_devices = self._config_entry.options.get(
            "devices", self._config_entry.data.get("devices", {})
        )
        for mac, label in stored_devices.items():
            options.setdefault(mac, label)

        if user_input is not None:
            targets = user_input.get(CONF_TARGET, [])
            if not targets:
                return self.async_show_form(
                    step_id="presence_list",
                    data_schema=vol.Schema({
                        vol.Required(CONF_TARGET): cv.multi_select(options),
                        vol.Required(CONF_CONSIDER_HOME, default=self._config_entry.options.get(
                            CONF_CONSIDER_HOME,
                            self._config_entry.data.get(CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME),
                        )): int,
                    }),
                    errors={"base": "no_devices_found"},
                )
            self._presence_targets = targets
            self._presence_timeout = user_input[CONF_CONSIDER_HOME]
            self._presence_options = options
            old_names = self._config_entry.options.get(
                "device_names", self._config_entry.data.get("device_names", {})
            )
            self._presence_names = {
                mac: old_names[mac] for mac in targets if mac in old_names
            }
            self._presence_index = 0
            return await self.async_step_presence_device_name()

        current_targets = self._config_entry.options.get(
            CONF_TARGET, self._config_entry.data.get(CONF_TARGET, [])
        )
        return self.async_show_form(
            step_id="presence_list",
            data_schema=vol.Schema({
                vol.Required(CONF_TARGET, default=current_targets): cv.multi_select(options),
                vol.Required(CONF_CONSIDER_HOME, default=self._config_entry.options.get(
                    CONF_CONSIDER_HOME,
                    self._config_entry.data.get(CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME),
                )): int,
            }),
        )

    async def async_step_presence_device_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit each selected device's presence sensor name."""
        mac = self._presence_targets[self._presence_index]
        field_name = _presence_name_field(self._presence_options.get(mac, ""), mac)
        if user_input is not None:
            name = str(user_input[field_name]).strip()
            if not name:
                return self.async_show_form(
                    step_id="presence_device_name",
                    data_schema=vol.Schema({vol.Required(field_name): str}),
                    errors={"base": "invalid_name"},
                )
            self._presence_names[mac] = name
            self._presence_index += 1
            if self._presence_index < len(self._presence_targets):
                return await self.async_step_presence_device_name()

            return self.async_create_entry(
                title="",
                data={
                    CONF_TARGET: self._presence_targets,
                    "devices": {
                        selected_mac: self._presence_options.get(selected_mac, selected_mac)
                        for selected_mac in self._presence_targets
                    },
                    "device_names": self._presence_names,
                    CONF_CONSIDER_HOME: self._presence_timeout,
                },
            )

        default_name = self._presence_names.get(mac) or _default_presence_name(
            self._presence_options.get(mac, mac), mac
        )
        return self.async_show_form(
            step_id="presence_device_name",
            data_schema=vol.Schema({vol.Required(field_name, default=default_name): str}),
        )
