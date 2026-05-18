from datetime import timedelta
from typing import Any, Dict, Optional
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.translation import async_get_translations
from .const import *
from .api import IPTimeAPI

# 요약: Web 및 SNMP 데이터를 통합하여 엔티티에 제공하는 중앙 코디네이터
# 연결된 파일: api.py, const.py, __init__.py, sensor.py, device_tracker.py

_LOGGER = logging.getLogger(__name__)

class IPTimeDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """ipTIME API 데이터를 관리하는 중앙 코디네이터"""

    def __init__(self, hass: HomeAssistant, api: IPTimeAPI, entry: ConfigEntry) -> None:
        self.api = api
        self.entry = entry
        self._last_web_update = 0.0
        
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data.get(CONF_URL)}",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """주기적으로 API를 호출하여 최신 데이터를 가져옵니다."""
        try:
            # 1. 기기 추적 정보 (하프싱킹)
            rssi_limit = self.entry.options.get(
                CONF_RSSI_LIMIT,
                self.entry.data.get(CONF_RSSI_LIMIT, DEFAULT_RSSI_LIMIT)
            )
            success = await self.api.async_update(rssi_limit=rssi_limit)
            
            # 2. Web 데이터 수집 (기본/필수) - 재실 주기 단축 시 공유기 부하 예방을 위한 5초 격리/독립
            # 다만 스위치 제어 등의 강제 갱신(caching_time 리셋) 시에는 즉시 동기화합니다.
            import time
            now = time.time()
            if now - self._last_web_update >= 5.0 or getattr(self.api, "_last_caching_time", 300.0) == 0.0:
                await self.api.async_get_web_data()
                self._last_web_update = now

            if not success:
                _LOGGER.warning("Failed to collect web data from the router (Auth or communication error)")
            
            # 3. 데이터 통합 (Web + SNMP)
            import copy
            combined_data = {
                "devices": copy.deepcopy(self.api.result),
                "web": copy.deepcopy(self.api.web_result),
            }

            # 4. 외부 인터넷(WAN) 연결 상태 변화 감지 및 HA 알림 생성
            if self.data:
                try:
                    old_web = self.data.get("web", {})
                    new_web = self.api.web_result
                    
                    old_wan = old_web.get("wan", {}) if isinstance(old_web, dict) else {}
                    new_wan = new_web.get("wan", {}) if isinstance(new_web, dict) else {}
                    
                    old_ip = old_wan.get("ip") if isinstance(old_wan, dict) else None
                    new_ip = new_wan.get("ip") if isinstance(new_wan, dict) else None
                    
                    old_ip_valid = old_ip and old_ip not in ("0.0.0.0", "", "null")
                    new_ip_valid = new_ip and new_ip not in ("0.0.0.0", "", "null")
                    
                    # WAN 물리 포트 링크 감지 보조 함수
                    def is_wan_linked(web_data: Dict[str, Any]) -> bool:
                        if not isinstance(web_data, dict):
                            return False
                        ports = web_data.get("ports", [])
                        wan_port = next((p for p in ports if str(p.get("type", "")).lower() == "wan"), {})
                        link = wan_port.get("link")
                        if link in (None, "", "null", "0", 0):
                            wan_info = web_data.get("wan", {})
                            if isinstance(wan_info, dict):
                                for key in ("wan_speed", "link", "speed"):
                                    value = wan_info.get(key)
                                    if value not in (None, "", "null", "0", 0):
                                        return True
                            return False
                        return True
                    
                    old_linked = is_wan_linked(old_web)
                    new_linked = is_wan_linked(new_web)
                    
                    # 로벨/로케일 감지 및 번역 파일 동적 로드
                    lang = "ko" if str(self.hass.config.language or "en").startswith("ko") else "en"
                    try:
                        translations = await async_get_translations(
                            self.hass,
                            lang,
                            "config",
                            integrations={DOMAIN}
                        )
                    except Exception as trans_err:
                        _LOGGER.warning(f"Failed to load translations: {trans_err}")
                        translations = {}

                    def get_notify_string(key: str, default: str) -> str:
                        full_key = f"component.{DOMAIN}.config.notifications.{key}"
                        return translations.get(full_key, default)

                    def get_security_detail(sec_key: str, field: str, default: str) -> str:
                        full_key = f"component.{DOMAIN}.config.notifications.security_{sec_key}_off.{field}"
                        return translations.get(full_key, default)

                    # 케이스 A: WAN 물리적 포트 링크 상태 단절/복구 감지
                    if old_linked and not new_linked:
                        _LOGGER.warning("WAN external internet port link disconnected - creating notification")
                        title = get_notify_string("wan_port_disconnect.title", "WAN External Port Disconnected")
                        message = get_notify_string(
                            "wan_port_disconnect.message",
                            "The WAN port external Internet cable of the ipTIME router ({url}) is unplugged or the modem connection is lost."
                        ).format(url=self.entry.data.get(CONF_URL))

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_wan_port_disconnect"
                            }
                        )
                    elif not old_linked and new_linked:
                        _LOGGER.info("WAN external internet port link reconnected - creating notification")
                        title = get_notify_string("wan_port_connect.title", "WAN External Port Connected")
                        message = get_notify_string(
                            "wan_port_connect.message",
                            "The WAN port external Internet cable of the ipTIME router ({url}) has been successfully reconnected."
                        ).format(url=self.entry.data.get(CONF_URL))

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_wan_port_connect"
                            }
                        )
                    
                    # 케이스 B: WAN 인터넷 IP 할당 해제/복구 감지 (실질적 인터넷 망 상태) 및 IP 변경 감지
                    if old_ip_valid and not new_ip_valid:
                        _LOGGER.warning("WAN Internet IP deallocated - creating notification")
                        title = get_notify_string("wan_ip_disconnect.title", "Internet Connection Lost Warning")
                        message = get_notify_string(
                            "wan_ip_disconnect.message",
                            "The ipTIME router ({url}) failed to obtain a public IP, and external Internet communication has been disconnected."
                        ).format(url=self.entry.data.get(CONF_URL))

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_wan_ip_disconnect"
                            }
                        )
                    elif not old_ip_valid and new_ip_valid:
                        _LOGGER.info("WAN Internet IP restored - creating notification")
                        title = get_notify_string("wan_ip_connect.title", "Internet Connection Restored")
                        message = get_notify_string(
                            "wan_ip_connect.message",
                            "The ipTIME router ({url}) has successfully obtained the public IP (**{ip}**) and the Internet connection is restored."
                        ).format(url=self.entry.data.get(CONF_URL), ip=new_ip)

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_wan_ip_connect"
                            }
                        )
                    elif old_ip_valid and new_ip_valid and old_ip != new_ip:
                        _LOGGER.info("WAN public IP address changed - creating notification")
                        title = get_notify_string("wan_ip_change.title", "Public IP Address Changed")
                        message = get_notify_string(
                            "wan_ip_change.message",
                            "The public IP address of the ipTIME router ({url}) has changed.\n\n* **Previous IP Address:** `{old_ip}`\n* **New IP Address:** `{new_ip}`"
                        ).format(url=self.entry.data.get(CONF_URL), old_ip=old_ip, new_ip=new_ip)

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_wan_ip_change"
                            }
                        )

                    # 5. 핵심 보안 및 제어 기능 실시간 변경 감시 알림 시스템 구축
                    old_geoip_enable = old_web.get("geoip", {}).get("enable", False) if isinstance(old_web, dict) else False
                    new_geoip_enable = new_web.get("geoip", {}).get("enable", False) if isinstance(new_web, dict) else False

                    # A. GeoIP 해외망 차단 꺼짐 감지 경고
                    if old_geoip_enable and not new_geoip_enable:
                        _LOGGER.warning("GeoIP overseas block feature disabled - creating warning")
                        title = get_notify_string("geoip_off.title", "GeoIP Feature Disabled Warning")
                        message = get_notify_string(
                            "geoip_off.message",
                            "The GeoIP foreign IP blocking security feature of the ipTIME router ({url}) is turned off."
                        ).format(url=self.entry.data.get(CONF_URL))

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_security_geoip_off"
                            }
                        )

                    # B. 포트포워딩(Port Forwarding) 활성화 및 비활성화 감지 알림
                    def get_pf_flag(web_data: Dict[str, Any]) -> bool:
                        if not isinstance(web_data, dict):
                            return False
                        pf_config = web_data.get("portforward_config", {}) or {}
                        if isinstance(pf_config, dict):
                            return bool(pf_config.get("run"))
                        return False

                    old_pf_enable = get_pf_flag(old_web)
                    new_pf_enable = get_pf_flag(new_web)

                    if not old_pf_enable and new_pf_enable:
                        _LOGGER.info("Port forwarding feature enabled - creating notification")
                        title = get_notify_string("portforward_on.title", "Port Forwarding Enabled")
                        message = get_notify_string(
                            "portforward_on.message",
                            "The Port Forwarding feature of the ipTIME router ({url}) has been turned On."
                        ).format(url=self.entry.data.get(CONF_URL))

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_portforward_on"
                            }
                        )
                    elif old_pf_enable and not new_pf_enable:
                        _LOGGER.info("Port forwarding feature disabled - creating notification")
                        title = get_notify_string("portforward_off.title", "Port Forwarding Disabled")
                        message = get_notify_string(
                            "portforward_off.message",
                            "The Port Forwarding feature of the ipTIME router ({url}) has been turned Off."
                        ).format(url=self.entry.data.get(CONF_URL))

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_portforward_off"
                            }
                        )

                    # C. Wi-Fi 무선 네트워크 꺼짐 감지 알림
                    old_wireless = old_web.get("wireless", {}) if isinstance(old_web, dict) else {}
                    new_wireless = new_web.get("wireless", {}) if isinstance(new_web, dict) else {}
                    old_bss_list = old_wireless.get("bss", []) if isinstance(old_wireless, dict) else []
                    new_bss_list = new_wireless.get("bss", []) if isinstance(new_wireless, dict) else []

                    if isinstance(old_bss_list, list) and isinstance(new_bss_list, list):
                        old_bss_map = {b.get("bss"): b for b in old_bss_list if isinstance(b, dict) and b.get("bss")}
                        new_bss_map = {b.get("bss"): b for b in new_bss_list if isinstance(b, dict) and b.get("bss")}
                        for bss_id, old_b in old_bss_map.items():
                            new_b = new_bss_map.get(bss_id)
                            if new_b:
                                old_active = bool(old_b.get("enable"))
                                new_active = bool(new_b.get("enable"))
                                if old_active and not new_active:
                                    ssid = old_b.get("ssid", bss_id)
                                    
                                    band_key = str(old_b.get("band") or "").strip().lower()
                                    if not band_key and "." in str(bss_id):
                                        band_key = str(bss_id).split(".", 1)[0]
                                    
                                    band_label = {
                                        "2g": "2.4G",
                                        "5g": "5G",
                                        "5g-2": "5G-2",
                                        "6g": "6G",
                                        "6g-2": "6G-2",
                                        "mlo": "MLO",
                                    }.get(band_key, band_key or "Unknown")

                                    _LOGGER.warning(f"Wi-Fi BSS disabled - SSID: {ssid}")
                                    title = get_notify_string("wifi_off.title", "Wi-Fi Network Off Warning ({ssid})").format(ssid=ssid)
                                    message = get_notify_string(
                                        "wifi_off.message",
                                        "The wireless network **{ssid}** ({band} band) of the ipTIME router ({url}) has been disabled."
                                    ).format(url=self.entry.data.get(CONF_URL), ssid=ssid, band=band_label)

                                    await self.hass.services.async_call(
                                        "persistent_notification",
                                        "create",
                                        {
                                            "title": title,
                                            "message": message,
                                            "notification_id": f"iptime_wifi_off_{bss_id}"
                                        }
                                    )

                    # D. Access List (원격 웹 관리) 포트 차단 및 개방 감지 알림
                    def get_acl_flag(web_data: Dict[str, Any]) -> bool:
                        if not isinstance(web_data, dict):
                            return False
                        acl = web_data.get("acl", []) or []
                        for entry in acl:
                            if isinstance(entry, dict) and entry.get("ntag") == "wan1":
                                return bool(entry.get("open", {}).get("flag"))
                        return False

                    old_acl_flag = get_acl_flag(old_web)
                    new_acl_flag = get_acl_flag(new_web)

                    if not old_acl_flag and new_acl_flag:
                        _LOGGER.warning("Remote WAN management (Access List) enabled - creating warning")
                        title = get_notify_string("acl_on.title", "Remote Web Management (Access List) Enabled Warning")
                        message = get_notify_string(
                            "acl_on.message",
                            "The external remote web management (Access List) access port of the ipTIME router ({url}) is now open and active."
                        ).format(url=self.entry.data.get(CONF_URL))

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_acl_on"
                            }
                        )
                    elif old_acl_flag and not new_acl_flag:
                        _LOGGER.info("Remote WAN management (Access List) disabled - creating notification")
                        title = get_notify_string("acl_off.title", "Remote Web Management (Access List) Closed")
                        message = get_notify_string(
                            "acl_off.message",
                            "The external remote web management access port of the ipTIME router ({url}) has been securely closed and blocked."
                        ).format(url=self.entry.data.get(CONF_URL))

                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": title,
                                "message": message,
                                "notification_id": "iptime_acl_off"
                            }
                        )

                    # E. [고도화 보안 조건] 원격 관리가 활성화되어 있을 때 CSRF 보호 해제/복구 감지
                    def get_csrf_flag(web_data: Dict[str, Any]) -> bool:
                        if not isinstance(web_data, dict):
                            return False
                        security = web_data.get("security_dos", {}) or {}
                        if isinstance(security, dict):
                            return bool(security.get("csrf", {}).get("run"))
                        return False

                    old_csrf = get_csrf_flag(old_web)
                    new_csrf = get_csrf_flag(new_web)

                    if new_acl_flag:
                        if old_csrf and not new_csrf:
                            _LOGGER.error("CSRF protection disabled while remote WAN management is active - creating critical alert")
                            title = get_notify_string("csrf_disabled_danger.title", "🔴 CSRF Prevention Disabled Warning (Remote Management Active)")
                            message = get_notify_string(
                                "csrf_disabled_danger.message",
                                "**[CRITICAL SECURITY RISK]** While remote web management is active on the ipTIME router ({url}), the **CSRF Prevention option has been turned Off**."
                            ).format(url=self.entry.data.get(CONF_URL))

                            await self.hass.services.async_call(
                                "persistent_notification",
                                "create",
                                {
                                    "title": title,
                                    "message": message,
                                    "notification_id": "iptime_csrf_disabled_danger"
                                }
                            )
                        elif not old_csrf and new_csrf:
                            _LOGGER.info("CSRF protection restored while remote WAN management is active - creating notification")
                            title = get_notify_string("csrf_security_on.title", "CSRF Phishing Defense Enabled")
                            message = get_notify_string(
                                "csrf_security_on.message",
                                "The web CSRF cross-site request forgery defense option of the ipTIME router ({url}) is now active."
                            ).format(url=self.entry.data.get(CONF_URL))

                            await self.hass.services.async_call(
                                "persistent_notification",
                                "create",
                                {
                                    "title": title,
                                    "message": message,
                                    "notification_id": "iptime_csrf_security_on"
                                }
                            )

                    # F. 개별 DoS/보안 제어 옵션 비활성화 감지 및 설명 알림
                    old_sec = old_web.get("security_dos", {}) if isinstance(old_web, dict) else {}
                    new_sec = new_web.get("security_dos", {}) if isinstance(new_web, dict) else {}

                    if old_sec and new_sec:
                        def get_sec_value(sec_dict, key) -> bool:
                            if not isinstance(sec_dict, dict):
                                return False
                            if key == "csrf":
                                return bool(sec_dict.get("csrf", {}).get("run", False))
                            if key == "arp_virus":
                                return bool(sec_dict.get("arp_virus", {}).get("run", False))
                            return bool(sec_dict.get(key, False))

                        security_details = {
                            "csrf": {
                                "name": get_security_detail("csrf", "name", "CSRF Prevention"),
                                "description": get_security_detail("csrf", "description", "Blocks cross-site request forgery attacks."),
                                "danger": get_security_detail("csrf", "danger", "Visiting forged websites can lead to settings theft."),
                                "notification_id": "iptime_security_csrf_off"
                            },
                            "arp_virus": {
                                "name": get_security_detail("arp_virus", "name", "ARP Virus Protection"),
                                "description": get_security_detail("arp_virus", "description", "Detects and blocks ARP Spoofing."),
                                "danger": get_security_detail("arp_virus", "danger", "Important packets could be easily intercepted."),
                                "notification_id": "iptime_security_arp_virus_off"
                            },
                            "syn_flood": {
                                "name": get_security_detail("syn_flood", "name", "SYN Flood Protection"),
                                "description": get_security_detail("syn_flood", "description", "Defends against TCP SYN Floods."),
                                "danger": get_security_detail("syn_flood", "danger", "Traffic floods can overload the router processor."),
                                "notification_id": "iptime_security_syn_flood_off"
                            },
                            "smurf": {
                                "name": get_security_detail("smurf", "name", "Smurf DDoS Protection"),
                                "description": get_security_detail("smurf", "description", "Prevents Smurf Distributed Denial of Service attacks."),
                                "danger": get_security_detail("smurf", "danger", "Compromised local devices can crash the router."),
                                "notification_id": "iptime_security_smurf_off"
                            },
                            "ip_source_routing": {
                                "name": get_security_detail("ip_source_routing", "name", "IP Source Routing Block"),
                                "description": get_security_detail("ip_source_routing", "description", "Prevents packets from specifying routes."),
                                "danger": get_security_detail("ip_source_routing", "danger", "Attackers can bypass security firewalls."),
                                "notification_id": "iptime_security_ip_source_routing_off"
                            },
                            "ip_spoofing": {
                                "name": get_security_detail("ip_spoofing", "name", "IP Spoofing Protection"),
                                "description": get_security_detail("ip_spoofing", "description", "Rejects faked source IP packets."),
                                "danger": get_security_detail("ip_spoofing", "danger", "Hackers can spoof local trusted IP addresses."),
                                "notification_id": "iptime_security_ip_spoofing_off"
                            },
                            "inbound_ping": {
                                "name": get_security_detail("inbound_ping", "name", "Block Inbound Ping"),
                                "description": get_security_detail("inbound_ping", "description", "Blocks external ICMP Ping requests."),
                                "danger": get_security_detail("inbound_ping", "danger", "Active presence online is exposed to hackers."),
                                "notification_id": "iptime_security_inbound_ping_off"
                            },
                            "outbound_ping": {
                                "name": get_security_detail("outbound_ping", "name", "Block Outbound Ping"),
                                "description": get_security_detail("outbound_ping", "description", "Restricts outbound ICMP Ping packets."),
                                "danger": get_security_detail("outbound_ping", "danger", "Malicious local code can contact external command servers."),
                                "notification_id": "iptime_security_outbound_ping_off"
                            }
                        }

                        for key, info in security_details.items():
                            if key == "csrf" and new_acl_flag:
                                continue

                            old_val = get_sec_value(old_sec, key)
                            new_val = get_sec_value(new_sec, key)

                            if old_val and not new_val:
                                _LOGGER.warning(f"Security feature disabled: {info['name']} - creating warning notification")

                                title = get_notify_string("security_disabled_title", "⚠️ Security Feature Disabled Warning: {name}").format(name=info['name'])
                                message = get_notify_string(
                                    "security_disabled_message",
                                    "The security option **{name}** of the ipTIME router ({url}) has been turned Off."
                                ).format(
                                    url=self.entry.data.get(CONF_URL),
                                    name=info['name'],
                                    description=info['description'],
                                    danger=info['danger']
                                )

                                await self.hass.services.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "title": title,
                                        "message": message,
                                        "notification_id": info["notification_id"]
                                    }
                                )

                    # G. 물리 유선 포트(LAN/WAN) 실시간 링크 연결 상태(Up/Down) 변화 감지 및 커스텀 이벤트 버스 방출
                    old_ports = old_web.get("ports", []) if isinstance(old_web, dict) else []
                    new_ports = new_web.get("ports", []) if isinstance(new_web, dict) else []

                    if isinstance(old_ports, list) and isinstance(new_ports, list):
                        def get_link_state(port_info: Dict[str, Any], web_data: Dict[str, Any]) -> tuple[bool, str]:
                            link_val = port_info.get("link")
                            p_type = str(port_info.get("type", "")).lower()
                            if p_type == "wan" and link_val in (None, "", "null"):
                                wan_info = web_data.get("wan", {}) if isinstance(web_data, dict) else {}
                                for key in ("wan_speed", "link", "speed"):
                                    val = wan_info.get(key)
                                    if val not in (None, "", "null"):
                                        link_val = val
                                        break
                            
                            if link_val in (None, "", "null", "0", 0, "down", "Down"):
                                return False, "Down"
                            
                            link_str = str(link_val)
                            import re
                            match = re.match(r"^(\d+)([fh]?)$", link_str)
                            if match:
                                speed = int(match.group(1))
                                label = f"{speed // 1000}Gbps" if speed >= 1000 else f"{speed}Mbps"
                                return True, label
                            return True, link_str

                        old_port_map = {f"{str(p.get('type')).lower()}:{p.get('port')}": p for p in old_ports if isinstance(p, dict) and p.get("port") is not None}
                        new_port_map = {f"{str(p.get('type')).lower()}:{p.get('port')}": p for p in new_ports if isinstance(p, dict) and p.get("port") is not None}

                        for p_key, old_p in old_port_map.items():
                            new_p = new_port_map.get(p_key)
                            if new_p:
                                old_up, old_speed = get_link_state(old_p, old_web)
                                new_up, new_speed = get_link_state(new_p, new_web)
                                
                                p_type = str(old_p.get("type", "port")).lower()
                                p_num = old_p.get("port")
                                disp_name = "WAN" if p_type == "wan" else f"LAN {p_num}"
                                
                                # 케이스 G-1: 포트가 새로 연결됨 (Link Up)
                                if not old_up and new_up:
                                    _LOGGER.info(f"Physical LAN Port Link Connected: {disp_name} at {new_speed}")
                                    self.hass.bus.async_fire(
                                        "iptime_manager_port_connected",
                                        {
                                            "port_type": p_type,
                                            "port_num": p_num,
                                            "display_name": disp_name,
                                            "link_speed": new_speed,
                                            "url": self.entry.data.get(CONF_URL)
                                        }
                                    )
                                # 케이스 G-2: 포트 연결이 끊김 (Link Down)
                                elif old_up and not new_up:
                                    _LOGGER.warning(f"Physical LAN Port Link Disconnected: {disp_name}")
                                    self.hass.bus.async_fire(
                                        "iptime_manager_port_disconnected",
                                        {
                                            "port_type": p_type,
                                            "port_num": p_num,
                                            "display_name": disp_name,
                                            "link_speed": "Down",
                                            "url": self.entry.data.get(CONF_URL)
                                        }
                                    )
                except Exception as ex:
                    _LOGGER.error(f"Error checking WAN link status change: {ex}")

            return combined_data
        except Exception as err:
            raise UpdateFailed(f"Error fetching data from router: {err}") from err
