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

            # 4. 외부 인터넷(WAN) 연결 상태 변화 감지 및 HA 알림 생성
            # 요약: WAN 물리 포트 케이블 단절/연결 및 WAN IP 해제/복구를 실시간 감지하여 즉각적인 지속 알림을 생성한다.
            # 연결될 파일: api.py, sensor.py, binary_sensor.py
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
                    
                    # 케이스 A: WAN 물리적 포트 링크 상태 단절/복구 감지
                    if old_linked and not new_linked:
                        _LOGGER.warning("WAN 외부 인터넷 포트 케이블 연결 해제 감지 - 알림 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "WAN 외부 포트 연결 끊김",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 WAN 포트 외부 인터넷 케이블이 분리되었거나 모뎀 연결이 끊겼습니다. 물리적 회선 상태를 확인해 주세요.",
                                "notification_id": "iptime_wan_port_disconnect"
                            }
                        )
                    elif not old_linked and new_linked:
                        _LOGGER.info("WAN 외부 인터넷 포트 케이블 재연결 감지 - 알림 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "WAN 외부 포트 연결 복구",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 WAN 포트 외부 인터넷 케이블 연결이 성공적으로 복구되었습니다.",
                                "notification_id": "iptime_wan_port_connect"
                            }
                        )
                    
                    # 케이스 B: WAN 인터넷 IP 할당 해제/복구 감지 (실질적 인터넷 망 상태) 및 IP 변경 감지
                    if old_ip_valid and not new_ip_valid:
                        _LOGGER.warning("WAN 인터넷 IP 할당 해제 감지 - 알림 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "인터넷 연결 끊김 경고",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})가 공인 IP를 할당받지 못하여 외부 인터넷 통신이 단절되었습니다. 통신사 모뎀 장비를 확인해 주세요.",
                                "notification_id": "iptime_wan_ip_disconnect"
                            }
                        )
                    elif not old_ip_valid and new_ip_valid:
                        _LOGGER.info("WAN 인터넷 IP 할당 복구 감지 - 알림 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "인터넷 연결 복구",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})가 외부 인터넷 공인 IP(**{new_ip}**)를 성공적으로 할당받아 인터넷 연결이 복구되었습니다.",
                                "notification_id": "iptime_wan_ip_connect"
                            }
                        )
                    elif old_ip_valid and new_ip_valid and old_ip != new_ip:
                        _LOGGER.info("WAN 공인 IP 주소 변경 감지 - 알림 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "외부 공인 IP 주소 변경 안내",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 외부 인터넷 공인 IP 주소가 변경되었습니다.\n\n* **이전 IP 주소:** `{old_ip}`\n* **변경된 IP 주소:** `{new_ip}`",
                                "notification_id": "iptime_wan_ip_change"
                            }
                        )

                    # 5. 핵심 보안 및 제어 기능 실시간 변경 감시 알림 시스템 구축 (연결될 파일: api.py, select.py, switch.py)
                    # 요약: GeoIP 차단 해제, 포트포워딩 개방/차단, 와이파이 단절, 원격 관리 차단/개방 및 CSRF 취약점 해제를 정밀 감지하여 HA 실시간 경보 생성.
                    old_geoip_enable = old_web.get("geoip", {}).get("enable", False) if isinstance(old_web, dict) else False
                    new_geoip_enable = new_web.get("geoip", {}).get("enable", False) if isinstance(new_web, dict) else False
                    
                    old_pf_enable = old_web.get("portforward_config", {}).get("enable", False) if isinstance(old_web, dict) else False
                    new_pf_enable = new_web.get("portforward_config", {}).get("enable", False) if isinstance(new_web, dict) else False
                    
                    old_bss_list = old_web.get("wireless", {}).get("bss", []) if isinstance(old_web, dict) else []
                    new_bss_list = new_web.get("wireless", {}).get("bss", []) if isinstance(new_web, dict) else []

                    def get_acl_flag(web_data) -> bool:
                        if not isinstance(web_data, dict): return False
                        acl = web_data.get("acl", [])
                        if not isinstance(acl, list): return False
                        for entry in acl:
                            if entry.get("ntag") == "wan1":
                                return bool(entry.get("open", {}).get("flag", False))
                        return False

                    old_acl_flag = get_acl_flag(old_web)
                    new_acl_flag = get_acl_flag(new_web)

                    old_csrf = old_web.get("security_dos", {}).get("csrf", {}).get("run", False) if isinstance(old_web, dict) else False
                    new_csrf = new_web.get("security_dos", {}).get("csrf", {}).get("run", False) if isinstance(new_web, dict) else False

                    # A. GeoIP 해외망 차단 꺼짐 감지 경고
                    if old_geoip_enable and not new_geoip_enable:
                        _LOGGER.warning("GeoIP 국가 차단 기능 비활성화 감지 - 경고 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "GeoIP 기능 비활성화 경고",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 GeoIP 해외 IP 차단 보안 기능이 꺼졌습니다. 의도한 변경이 아니라면 해외발 무작위 침입 공격에 노출될 수 있으므로 설정을 확인하세요.",
                                "notification_id": "iptime_security_geoip_off"
                            }
                        )

                    # B. 포트포워딩 켜짐/꺼짐 감지 안내
                    if not old_pf_enable and new_pf_enable:
                        _LOGGER.info("포트포워딩 기능 활성화 감지 - 알림 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "포트포워딩 활성화 안내",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 포트포워딩 기능이 켜졌습니다(On). 설정된 개방 규칙에 따라 특정 로컬 포트가 외부 인터넷망에 공개됩니다.",
                                "notification_id": "iptime_portforward_on"
                            }
                        )
                    elif old_pf_enable and not new_pf_enable:
                        _LOGGER.info("포트포워딩 기능 비활성화 감지 - 알림 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "포트포워딩 비활성화 안내",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 포트포워딩 기능이 완전히 꺼졌습니다(Off). 모든 외부망 개방 규칙이 일시적으로 완전 차단됩니다.",
                                "notification_id": "iptime_portforward_off"
                            }
                        )

                    # C. Wi-Fi 무선 네트워크 꺼짐 감지 알림
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
                                    band = {"2g": "2.4GHz", "5g": "5GHz", "6g": "6GHz"}.get(band_key, band_key.upper())
                                    _LOGGER.warning(f"Wi-Fi SSID {ssid} ({band}) 비활성화 감지 - 알림 생성")
                                    await self.hass.services.async_call(
                                        "persistent_notification",
                                        "create",
                                        {
                                            "title": f"Wi-Fi 무선망 꺼짐 경고 ({ssid})",
                                            "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 무선 네트워크 **{ssid}** ({band} 대역)이 비활성화되었습니다. 해당 대역에 매핑된 무선 IoT 스마트 장치들의 연결이 모두 차단될 수 있습니다.",
                                            "notification_id": f"iptime_wifi_off_{bss_id.replace('.', '_')}"
                                        }
                                    )

                    # D. Access List (원격 웹 관리) 포트 차단 및 개방 감지 알림
                    if not old_acl_flag and new_acl_flag:
                        _LOGGER.warning("외부 원격 관리 기능(Access List) 활성화 감지 - 경고 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "원격 웹 관리(Access List) 활성화 경고",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 외부 원격 웹 관리(Access List) 접속 포트가 공개 및 활성화되었습니다. 외부 해킹 공격에 직접 노출될 수 있으므로 공유기 관리자 계정의 비밀번호를 강력하게 유지하십시오.",
                                "notification_id": "iptime_acl_on"
                            }
                        )
                    elif old_acl_flag and not new_acl_flag:
                        _LOGGER.info("외부 원격 관리 기능(Access List) 비활성화 감지 - 알림 생성")
                        await self.hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "원격 웹 관리(Access List) 차단 완료",
                                "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 외부 원격 웹 관리 접속 포트가 안전하게 전면 폐쇄 및 차단되었습니다. 외부의 비정상적 해킹 침입 시도로부터 공유기가 안전하게 격리됩니다.",
                                "notification_id": "iptime_acl_off"
                            }
                        )

                    # E. [고도화 보안 조건] 원격 관리가 활성화되어 있을 때 CSRF 보호 해제/복구 감지
                    if new_acl_flag:
                        if old_csrf and not new_csrf:
                            _LOGGER.error("원격 관리 상태 하에서 CSRF 보안 기능 차단 감지 - 고위험 보안 알림 생성")
                            await self.hass.services.async_call(
                                "persistent_notification",
                                "create",
                                {
                                    "title": "🔴 CSRF 방어 해제 경고 (원격 관리 활성화 상태)",
                                    "message": f"**[심각한 보안 취약성 위험]** ipTIME 공유기({self.entry.data.get(CONF_URL)})의 외부 원격 관리 접속망이 활성화되어 있는 취약 상태에서 **웹 CSRF 위조 공격 방어 옵션(CSRF Protection)이 차단(Off)** 되었습니다. 외부의 우회적인 악성 피싱 브라우저 해킹 기법에 취약하게 노출되므로, 즉시 CSRF 설정을 다시 활성화(On)하십시오.",
                                    "notification_id": "iptime_csrf_disabled_danger"
                                }
                            )
                        elif not old_csrf and new_csrf:
                            _LOGGER.info("원격 관리 상태 하에서 CSRF 보안 기능 복구 감지 - 알림 생성")
                            await self.hass.services.async_call(
                                "persistent_notification",
                                "create",
                                {
                                    "title": "CSRF 피싱 방어 보안 활성화",
                                    "message": f"ipTIME 공유기({self.entry.data.get(CONF_URL)})의 웹 CSRF 위조 공격 방어 옵션이 활성화되었습니다. 원격 웹 관리 포트가 개방되어 있는 상태 하에서도 외부 악성 침입에 대한 이중 보안 장벽이 유지됩니다.",
                                    "notification_id": "iptime_csrf_security_on"
                                }
                            )
                except Exception as ex:
                    _LOGGER.error(f"WAN 연결 상태 변화 판단 중 오류 발생: {ex}")

            return combined_data
        except Exception as err:
            raise UpdateFailed(f"공유기에서 데이터를 가져오는 중 오류 발생: {err}") from err
