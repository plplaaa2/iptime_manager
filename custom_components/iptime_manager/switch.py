from __future__ import annotations

import re
from typing import Any, Dict, List

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_URL


def _entity_key_part(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def _web_wireless_bss_list(web_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    wireless = web_data.get("wireless", {}) if isinstance(web_data, dict) else {}
    result: List[Dict[str, Any]] = []
    for bss in wireless.get("bss", []) or []:
        if isinstance(bss, dict) and bss.get("bss"):
            result.append(bss)
    return result


def _web_wireless_bss_map(web_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(bss.get("bss")): bss for bss in _web_wireless_bss_list(web_data) if bss.get("bss")}


def _web_wireless_band_list(web_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    wireless = web_data.get("wireless", {}) if isinstance(web_data, dict) else {}
    result: List[Dict[str, Any]] = []
    for band in wireless.get("band", []) or []:
        if isinstance(band, dict) and band.get("band"):
            result.append(band)
    if result:
        return result

    seen: set[str] = set()
    for bss in _web_wireless_bss_list(web_data):
        band_key = _web_wireless_bss_band_key(bss)
        if band_key in seen:
            continue
        seen.add(band_key)
        result.append({"band": band_key, "enable": bss.get("enable"), "separated": bss.get("separated"), "bss": [bss.get("bss")] if bss.get("bss") else []})
    return result


def _web_wireless_band_map(web_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(band.get("band")).lower(): band for band in _web_wireless_band_list(web_data) if band.get("band")}


def _web_wireless_band_active(band_info: Dict[str, Any]) -> bool:
    if not isinstance(band_info, dict):
        return False
    if band_info.get("activated") is not None:
        return bool(band_info.get("activated"))
    if band_info.get("enable") is not None:
        return bool(band_info.get("enable"))
    if band_info.get("configured") is not None:
        return bool(band_info.get("configured"))
    return False


def _web_wireless_band_label(band: Any) -> str:
    band_key = str(band or "").lower()
    mapping = {
        "2g": "2.4G",
        "5g": "5G",
        "5g-2": "5G-2",
        "6g": "6G",
        "6g-2": "6G-2",
        "mlo": "MLO",
    }
    return mapping.get(band_key, str(band or "Unknown"))


def _web_wireless_bss_band_key(bss_info: Dict[str, Any]) -> str:
    raw_band = bss_info.get("band")
    if isinstance(raw_band, str) and raw_band.strip():
        return raw_band.strip().lower()
    bss_id = str(bss_info.get("bss") or "").strip().lower()
    if "." in bss_id:
        return bss_id.split(".", 1)[0]
    return bss_id or "unknown"


def _web_wireless_security_label(authenc: Any) -> str:
    value = str(authenc or "").lower()
    mapping = {
        "open": "No Encrypt",
        "none": "No Encrypt",
        "wep": "WEP",
        "shared_wep": "Shared-WEP",
        "auto_wep": "Auto-WEP",
        "wpa_psk": "WPAPSK-AES",
        "wpa2psk_aes": "WPA2PSK-AES",
        "wpa2psk_tkip_aes": "WPA2PSK-TKIP/AES",
        "wpapsk_wpa2psk_aes": "WPAPSK/WPA2PSK-AES",
        "wpa3sae_aes": "WPA3SAE-AES",
        "wpa3sae_wpa2psk_aes": "WPA3SAE/WPA2PSK-AES",
        "wpa2_aes": "WPA2-AES",
        "wpa3_aes": "WPA3-AES",
    }
    return mapping.get(value, str(authenc or "Unknown"))


def _get_web_security_block(web_data: Dict[str, Any], key: str) -> Dict[str, Any]:
    security = web_data.get("security", {}) if isinstance(web_data, dict) else {}
    block = security.get(key, {}) if isinstance(security, dict) else {}
    return block if isinstance(block, dict) else {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    web_data = (coordinator.data or {}).get("web", {})
    entities = []

    # 밴드 단위가 아닌 개별 BSS(SSID) 단위로 스위치 생성
    for bss in _web_wireless_bss_list(web_data):
        bss_id = str(bss.get("bss"))
        if bss_id:
            entities.append(IPTimeWifiSwitch(coordinator, entry, bss_id))

    if coordinator.api._beta_ui:
        # 원격 관리 설정(Access List) 지원 모델인 경우에만 생성
        if web_data.get("acl") is not None:
            entities.append(IPTimeAccessListSwitch(coordinator, entry))
        
        # 보안 제어 설정이 지원되는 모델인 경우에만 생성
        if web_data.get("security_dos") is not None:
            security_items = [
                ("csrf", "CSRF Prevention", "mdi:shield-lock"),
                ("arp_virus", "ARP Virus Protection", "mdi:shield-bug"),
                ("syn_flood", "SYN Flood Protection", "mdi:shield-alert"),
                ("smurf", "Smurf Protection", "mdi:shield-remove"),
                ("ip_source_routing", "IP Source Routing Block", "mdi:router-network"),
                ("ip_spoofing", "IP Spoofing Protection", "mdi:incognito"),
                ("inbound_ping", "Block Inbound Ping", "mdi:network-lock"),
                ("outbound_ping", "Block Outbound Ping", "mdi:network-lock"),
            ]
            for key, name, icon in security_items:
                entities.append(IPTimeSecuritySwitch(coordinator, entry, key, name, icon))

        # UPnP 설정이 지원되는 모델인 경우에만 생성
        if web_data.get("upnp_config") is not None:
            entities.append(IPTimeUPnPSwitch(coordinator, entry))
            
        # 자동 재부팅 설정이 지원되는 모델인 경우에만 생성
        if web_data.get("reboot_timer") is not None:
            entities.append(IPTimeAutoRebootSwitch(coordinator, entry))
            
        # 인터넷 연결 유지 설정이 지원되는 모델인 경우에만 생성
        if web_data.get("nat_config") is not None:
            entities.append(IPTimeKeepConnectSwitch(coordinator, entry))
            
        # WAN포트 끊김 시 재연결 설정이 지원되는 모델인 경우에만 생성
        if web_data.get("wan_heartbeat") is not None:
            entities.append(IPTimeWanReconnectSwitch(coordinator, entry))

        # 와이어가드 서버 설정이 수집되는 하드웨어 모델인 경우에만 스위치 생성 (예외 처리)
        if web_data.get("wg_server") is not None:
            entities.append(IPTimeWireGuardServerSwitch(coordinator, entry))

        # 포트포워드 설정이 지원되는 모델인 경우에만 생성
        if web_data.get("portforward_config") is not None:
            entities.append(IPTimePortForwardSwitch(coordinator, entry))

        # UPnP 릴레이 설정이 지원되는 모델인 경우에만 생성
        if web_data.get("upnp_relay") is not None:
            entities.append(IPTimeUPnPRelaySwitch(coordinator, entry))

    async_add_entities(entities)


class IPTimeWifiSwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME wireless BSS (SSID) on/off switch."""

    def __init__(self, coordinator, entry, bss_id: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._bss_id = bss_id
        self._attr_unique_id = f"{entry.entry_id}_wifi_bss_{_entity_key_part(bss_id)}"
        self._attr_icon = "mdi:wifi"

        web_data = coordinator.data.get("web", {}) if coordinator.data else {}
        bss_info = _web_wireless_bss_map(web_data).get(self._bss_id, {})
        ssid = bss_info.get("ssid") or self._bss_id
        band_key = _web_wireless_bss_band_key(bss_info)
        band_label = _web_wireless_band_label(band_key)
        
        self._attr_name = f"WiFi {band_label} - {ssid} ({entry.data.get(CONF_URL)})"

    @property
    def is_on(self) -> bool:
        """Return true if the BSS is enabled."""
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        bss_info = _web_wireless_bss_map(web_data).get(self._bss_id, {})
        return bool(bss_info.get("enable"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes for the BSS."""
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        bss_info = _web_wireless_bss_map(web_data).get(self._bss_id, {})
        band_key = _web_wireless_bss_band_key(bss_info)
        return {
            "bss_id": self._bss_id,
            "ssid": bss_info.get("ssid"),
            "band": _web_wireless_band_label(band_key),
            "hide": bss_info.get("hide"),
            "security": _web_wireless_security_label(bss_info.get("authenc")),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the wireless BSS."""
        await self.coordinator.api.async_set_web_wireless_bss_enable(
            self._bss_id,
            True,
        )
        await self.coordinator.async_request_refresh()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the wireless BSS."""
        await self.coordinator.api.async_set_web_wireless_bss_enable(
            self._bss_id,
            False,
        )
        await self.coordinator.async_request_refresh()
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


class IPTimeGeoIPSwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME GeoIP protection switch."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_security_geoip"
        self._attr_name = f"GeoIP ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:web"

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        geoip = _get_web_security_block(web_data, "geoip")
        return bool(geoip.get("enable"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        geoip = _get_web_security_block(web_data, "geoip")
        return {
            "enable": geoip.get("enable"),
            "policy": geoip.get("policy"),
            "drop_list": geoip.get("drop_list"),
            "accept_list": geoip.get("accept_list"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_geoip_enable(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_geoip_enable(False)
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


class IPTimeAccessListSwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME access list / WAN ACL switch."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_security_accesslist"
        self._attr_name = f"Access List ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:shield-key"

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        acl = web_data.get("acl", [])
        for entry in acl:
            if entry.get("ntag") == "wan1":
                return bool(entry.get("open", {}).get("flag"))
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        acl = web_data.get("acl", [])
        wan1 = {}
        for entry in acl:
            if entry.get("ntag") == "wan1":
                wan1 = entry
                break
        return {
            "port": wan1.get("open", {}).get("port"),
            "filter_enabled": wan1.get("filter", {}).get("flag"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_accesslist_enable(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_accesslist_enable(False)
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


class IPTimeSecuritySwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME DoS/Security setting switch."""

    def __init__(self, coordinator, entry, key: str, name: str, icon: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_security_{key}"
        self._attr_name = f"{name} ({entry.data.get(CONF_URL)})"
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        security = web_data.get("security_dos", {})
        
        if self._key == "csrf":
            return bool(security.get("csrf", {}).get("run"))
        if self._key == "arp_virus":
            return bool(security.get("arp_virus", {}).get("run"))
            
        return bool(security.get(self._key))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_security_switch(self._key, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_security_switch(self._key, False)
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


# 요약: UPnP 설정을 스위치로 제어한다. (연결 파일: api.py)
class IPTimeUPnPSwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME UPnP setting switch."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_sysmisc_upnp"
        self._attr_name = f"UPnP ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:router-wireless"

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        return bool(web_data.get("upnp_config", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_upnp_enable(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_upnp_enable(False)
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


# 요약: 공유기 자동 재시작 설정을 스위치로 제어한다. (연결 파일: api.py)
class IPTimeAutoRebootSwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME Auto Reboot setting switch."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_sysmisc_auto_reboot"
        self._attr_name = f"Auto Reboot ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:calendar-clock"

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        timer = web_data.get("reboot_timer", {})
        return bool(timer.get("run", False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        timer = web_data.get("reboot_timer", {})
        return {
            "reboot_hour": timer.get("hour", 4),
            "reboot_minute": timer.get("min", 0),
            "reboot_days": timer.get("days", ["Fri"]),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        timer = web_data.get("reboot_timer", {})
        hour = timer.get("hour", 4)
        min_time = timer.get("min", 0)
        days = timer.get("days", ["Fri"])
        await self.coordinator.api.async_set_web_reboot_timer(True, hour, min_time, days)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        timer = web_data.get("reboot_timer", {})
        hour = timer.get("hour", 4)
        min_time = timer.get("min", 0)
        days = timer.get("days", ["Fri"])
        await self.coordinator.api.async_set_web_reboot_timer(False, hour, min_time, days)
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


# 요약: 인터넷 연결 유지 설정을 스위치로 제어한다. (연결 파일: api.py)
class IPTimeKeepConnectSwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME Keep Internet Connection switch."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_sysmisc_keep_connection"
        self._attr_name = f"Keep Connection ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:link-variant"

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        return bool(web_data.get("nat_config", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_nat_config(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_nat_config(False)
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


# 요약: WAN포트 끊김 시 재연결 설정을 스위치로 제어한다. (연결 파일: api.py)
class IPTimeWanReconnectSwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME Reconnect on WAN disconnect switch."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_sysmisc_wan_reconnect"
        self._attr_name = f"WAN Reconnect ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:connection"

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        heartbeat = web_data.get("wan_heartbeat", {})
        return bool(heartbeat.get("run", False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        heartbeat = web_data.get("wan_heartbeat", {})
        return {
            "detect_interval_seconds": heartbeat.get("interval", 3),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        heartbeat = web_data.get("wan_heartbeat", {})
        interval = heartbeat.get("interval", 3)
        await self.coordinator.api.async_set_web_wan_heartbeat(True, interval)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        heartbeat = web_data.get("wan_heartbeat", {})
        interval = heartbeat.get("interval", 3)
        await self.coordinator.api.async_set_web_wan_heartbeat(False, interval)
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


# 요약: WireGuard 서버의 실행 스위치를 제공한다. (연결 파일: api.py)
class IPTimeWireGuardServerSwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME WireGuard Server Toggle Switch."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_wg_server_run"
        self._attr_name = f"WireGuard Server ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:shield-key"

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        wg_server = web_data.get("wg_server", {})
        return wg_server.get("run") is True or wg_server.get("enable") is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        wg_server = web_data.get("wg_server", {})
        return {
            "ip": wg_server.get("ip", "10.0.21.1"),
            "subnet": wg_server.get("subnet", "24"),
            "port": wg_server.get("port", 53344),
            "nat": wg_server.get("nat", True),
            "pubkey": wg_server.get("pubkey"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_wg_server_run(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_wg_server_run(False)
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


# 요약: 포트포워딩 기능의 활성화 여부를 스위치로 제어한다. (연결 파일: api.py)
class IPTimePortForwardSwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME Port Forwarding toggle switch."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_nat_portforward"
        self._attr_name = f"Port Forwarding ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:router-wireless-settings"

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        pf = web_data.get("portforward_config", {})
        if not isinstance(pf, dict):
            return False
        return bool(pf.get("enable", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_portforward_enable(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_portforward_enable(False)
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


# 요약: UPnP 포트포워드 릴레이 활성화 여부를 스위치로 제어한다. (연결 파일: api.py)
class IPTimeUPnPRelaySwitch(CoordinatorEntity, SwitchEntity):
    """ipTIME UPnP Port-forwarding Relay toggle switch."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_nat_upnp_relay"
        self._attr_name = f"UPnP Relay ({entry.data.get(CONF_URL)})"
        self._attr_icon = "mdi:folder-swap"

    @property
    def is_on(self) -> bool:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        return bool(web_data.get("upnp_relay", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_upnp_relay_enable(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_web_upnp_relay_enable(False)
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
