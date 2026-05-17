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
                except Exception as ex:
                    _LOGGER.error(f"WAN 연결 상태 변화 판단 중 오류 발생: {ex}")

            return combined_data
        except Exception as err:
            raise UpdateFailed(f"공유기에서 데이터를 가져오는 중 오류 발생: {err}") from err
