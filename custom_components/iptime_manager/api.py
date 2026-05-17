from __future__ import annotations

import logging
import asyncio
import time
import re
import html
import aiohttp
from typing import Any, Dict, List, Optional, Final
from json import loads
from datetime import timedelta
from .const import *

# 요약: ipTIME 공유기와의 통신(Web CGI) 담당 API 클래스
# 연결될 파일: const.py, coordinator.py

_LOGGER = logging.getLogger(__name__)


def _normalize_model_name(raw_model: Any) -> str:
    text = str(raw_model or "").strip()
    if not text:
        return "ipTIME Router"

    text = re.sub(r"\s+", " ", text)
    if text.lower().startswith("iptime"):
        remainder = text[6:].strip().upper()
        return f"ipTIME {remainder}".strip() if remainder else "ipTIME Router"
    return f"ipTIME {text.upper()}"


def _extract_table_rows(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL)


def _extract_table_cells(row_html: str) -> List[str]:
    if not row_html:
        return []
    cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)
    return [html.unescape(re.sub(r"<[^>]+>", "", cell)).strip() for cell in cells]

class IPTimeAPI:
    """ipTIME 공유기 API (누락 함수 복구 버전)"""
    
    def __init__(self, hass, url: str, user_id: str, user_pw: str) -> None:
        self._hass = hass
        self._user_id = user_id
        self._user_pw = user_pw
        self._ismobile = False
        self._ismesh = False
        self._beta_ui = False
        self.result: Dict[str, Any] = {}
        self.web_result: Dict[str, Any] = {}
        self._latest_firmware_version: Any = None
        self._url = url if "http" in url else "http://" + url
        if self._url.endswith("/"):
            self._url = self._url[:-1]
            
        self._host = self._url.split("//")[-1].split(":")[0]
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"{self._url}/",
            "Origin": self._url,
            "Connection": "keep-alive"
        }
        self.efm_session_id: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def _async_get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # HA 공용 세션 대신 전용 독립 세션 생성 (세션 기반 공유기 대응)
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=TIME_OUT),
                headers=self.headers
            )
        return self._session

    async def _async_request(self, method: str, url: str, **kwargs) -> str:
        try:
            session = await self._async_get_session()
            headers = kwargs.get("headers", self.headers.copy())
            if self.efm_session_id:
                headers["Cookie"] = f"efm_session_id={self.efm_session_id}"
            
            kwargs["headers"] = headers
            async with session.request(method, url, **kwargs) as response:
                return await response.text()
        except Exception as err:
            _LOGGER.debug(f"요청 실패 ({url}): {err}")
            return ""

    async def _async_service_json(self, method: str, params: Any = None) -> Dict[str, Any]:
        """beta UI JSON-RPC 호출."""
        url = f"{self._url}{BETA_SERVICE_URN}"
        payload: Dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params

        headers = self.headers.copy()
        if self.efm_session_id:
            headers["Cookie"] = f"efm_session_id={self.efm_session_id}"

        try:
            session = await self._async_get_session()
            async with session.post(url, json=payload, headers=headers) as response:
                try:
                    return await response.json()
                except Exception:
                    text = await response.text()
                    try:
                        return loads(text)
                    except Exception:
                        return {}
        except Exception as err:
            _LOGGER.debug(f"서비스 호출 실패 ({method}): {err}")
            return {}

    async def async_update(self) -> bool:
        """데이터 업데이트 메인 로직 (안정화)."""
        # 1. 세션이 없으면 로그인 시도
        if not self.efm_session_id:
            if await self.verify_beta_ui():
                self._beta_ui = True
                if not await self.login_beta_ui(): 
                    _LOGGER.debug("베타 UI 로그인 실패")
                    return False
                await self.beta_ui_check_mesh()
            else:
                await self.verify_mobile()
                if self._ismobile:
                    if not await self.m_login(): return False
                    await self.m_check_mesh()
                else:
                    if not await self.login(): return False
                    await self.check_mesh()

        # 2. 데이터 수집
        if self._beta_ui:
            await asyncio.sleep(1)
            self.result = await self.beta_ui_wlan_check()
            await self.session_update_beta_ui()
        elif self._ismobile:
            self.result = await self.m_wlan_check()
        else:
            self.result = await self.wlan_check()
        
        if len(self.result) > 1:
            first_mac = next(iter(self.result.keys())) if self.result else "None"
            _LOGGER.info(f"ipTIME Web 데이터 수집 성공: 기기 {len(self.result)-1}대 감지 (최초 MAC: {first_mac})")
        else:
            _LOGGER.warning("ipTIME Web 데이터 수집 실패: 로그인 세션은 확보했으나 기기 목록이 비어있습니다.")
        
        # 3. 세션 만료 체크
        if self.result.get("session") is False:
            _LOGGER.debug("세션 만료 감지, 다음 주기에서 재로그인 시도")
            self.efm_session_id = None
            return False
            
        return True

    async def async_get_web_data(self) -> bool:
        """웹 UI에서 노출되는 시스템/포트 정보를 수집한다."""
        self.web_result = {}

        if not self._beta_ui:
            return False

        try:
            firmware = await self._async_service_json("firmware/info")
            if firmware.get("result"):
                self.web_result["firmware"] = firmware["result"]

            firmware_block = self.web_result.setdefault("firmware", {})
            now = time.time()
            latest_cached = (
                self._latest_firmware_version is not None
                and (now - self._latest_firmware_checked_at) < 86400
            )
            if latest_cached:
                firmware_block["latest_version"] = self._latest_firmware_version
                if self._latest_firmware_raw is not None:
                    firmware_block["latest_raw"] = self._latest_firmware_raw
            else:
                firmware_latest = await self._async_service_json("firmware/version/latest")
                if firmware_latest.get("result") is not None:
                    latest_result = firmware_latest.get("result")
                    if isinstance(latest_result, dict):
                        latest_version = (
                            latest_result.get("version")
                            or latest_result.get("latest")
                            or latest_result.get("value")
                            or latest_result.get("result")
                            or latest_result.get("ok")
                        )
                        self._latest_firmware_raw = latest_result
                    else:
                        latest_version = latest_result
                        self._latest_firmware_raw = None

                    if latest_version is not None:
                        self._latest_firmware_version = latest_version
                        self._latest_firmware_checked_at = now
                        firmware_block["latest_version"] = latest_version
                        if self._latest_firmware_raw is not None:
                            firmware_block["latest_raw"] = self._latest_firmware_raw

            lan = await self._async_service_json("network/interface/lan/info")
            if lan.get("result"):
                self.web_result["lan"] = lan["result"]

            wan = await self._async_service_json("network/interface/wan1/info")
            if wan.get("result"):
                self.web_result["wan"] = wan["result"]

            dns = await self._async_service_json("network/dns/info")
            if dns.get("result"):
                self.web_result["dns"] = dns["result"]

            ports = await self._async_service_json("port/link/status")
            if ports.get("result"):
                self.web_result["ports"] = ports["result"]

            wireless_info = await self._async_service_json("wireless/info")
            wireless_band = await self._async_service_json("wireless/band/info")
            wireless_bss = await self._async_service_json("wireless/bss/show")
            wireless_client = await self._async_service_json("wireless/client/show")
            if wireless_info.get("result") or wireless_band.get("result") or wireless_bss.get("result"):
                self.web_result["wireless"] = {
                    "info": wireless_info.get("result", []),
                    "band": wireless_band.get("result", []),
                    "bss": wireless_bss.get("result", []),
                    "client": wireless_client.get("result", []),
                }

            geoip = await self._async_service_json("geoip/get")
            if geoip.get("result"):
                self.web_result.setdefault("security", {})["geoip"] = geoip["result"]
                self.web_result["geoip"] = geoip["result"]

            geoip_pcount = await self._async_service_json("geoip/blocked/pcount")
            if geoip_pcount.get("result") is not None:
                blocked_result = geoip_pcount.get("result")
                blocked_count = None
                if isinstance(blocked_result, dict):
                    if "total" in blocked_result and blocked_result["total"] is not None:
                        blocked_count = blocked_result["total"]
                    elif "count" in blocked_result and blocked_result["count"] is not None:
                        blocked_count = blocked_result["count"]
                    elif "list" in blocked_result and isinstance(blocked_result["list"], list):
                        blocked_count = len(blocked_result["list"])
                elif isinstance(blocked_result, list):
                    blocked_count = len(blocked_result)
                elif isinstance(blocked_result, (int, float)):
                    blocked_count = int(blocked_result)
                if blocked_count is not None:
                    self.web_result["geoip_blocked_pcount"] = blocked_count

            accesslist = await self._async_service_json("acl/config")
            if accesslist.get("result"):
                self.web_result.setdefault("security", {})["accesslist"] = accesslist["result"]
                self.web_result["acl"] = accesslist["result"]

            dos_config = await self._async_service_json("dos/config")
            if dos_config.get("result"):
                self.web_result["security_dos"] = dos_config["result"]

            # sysmisc 설정 정보 수집 (연결될 파일: switch.py, select.py, button.py)
            led_config = await self._async_service_json("led/config")
            if led_config.get("result") is not None:
                self.web_result["led_config"] = led_config["result"]

            upnp_config = await self._async_service_json("upnp/config")
            if upnp_config.get("result") is not None:
                self.web_result["upnp_config"] = upnp_config["result"]

            reboot_timer = await self._async_service_json("reboot/timer")
            if reboot_timer.get("result") is not None:
                self.web_result["reboot_timer"] = reboot_timer["result"]

            nat_config = await self._async_service_json("nat/config")
            if nat_config.get("result") is not None:
                self.web_result["nat_config"] = nat_config["result"]

            wan_heartbeat = await self._async_service_json("wan/heartbeat")
            if wan_heartbeat.get("result") is not None:
                self.web_result["wan_heartbeat"] = wan_heartbeat["result"]

            # IPTV 설정 정보 수집 (연결될 파일: select.py)
            iptv_config = await self._async_service_json("iptv/config")
            if iptv_config.get("result") is not None:
                self.web_result["iptv_config"] = iptv_config["result"]

            # 나이트 LED 설정 정보 수집 (연결될 파일: select.py)
            led_config = await self._async_service_json("led/config")
            if led_config.get("result") is not None:
                self.web_result["led_config"] = led_config["result"]

            # WireGuard 서버 정보 수집 (연결될 파일: switch.py)
            wg_server = await self._async_service_json("wg/server/show")
            if wg_server.get("result") is not None:
                self.web_result["wg_server"] = wg_server["result"]

            product_html = await self._async_request("GET", f"{self._url}/ui/port_setup")
            product_match = re.search(r'PRODUCT:\s*"([^"]+)"', product_html)
            self.web_result["model"] = _normalize_model_name(product_match.group(1) if product_match else None)

            uptime = None
            for candidate in (self.web_result.get("wan", {}), self.web_result.get("lan", {})):
                if isinstance(candidate, dict) and candidate.get("connected_period") is not None:
                    uptime = candidate.get("connected_period")
                    break
            self.web_result["uptime"] = uptime
            return True
        except Exception as err:
            _LOGGER.debug(f"웹 데이터 수집 실패: {err}")
            return False

    async def async_set_web_wireless_bss_enable(self, bss: str, enable: bool) -> bool:
        """Toggle a wireless BSS using the beta UI."""
        if not self._beta_ui:
            return False

        response = await self._async_service_json(
            "wireless/bss/set",
            {"bss": bss, "enable": bool(enable), "commit": True},
        )
        if response.get("error"):
            _LOGGER.warning(f"무선 BSS 제어 실패: {response.get('error')}")
            return False
        return bool(response)

    async def async_set_web_wireless_band_enable(self, band: str, enable: bool, separated: Any = None, bss: Any = None) -> bool:
        """Toggle a wireless band using the beta UI (최적화 버전)."""
        if not self._beta_ui:
            return False

        # 단순 On/Off 시에는 separated와 bss를 보내지 않는 것이 안전함 (전체 재시작 방지)
        params: Dict[str, Any] = {"band": band, "enable": bool(enable), "commit": True}
        if separated is not None and str(separated).lower() != "none":
            params["separated"] = separated
        if bss is not None and str(bss).lower() != "none":
            params["bss"] = bss

        _LOGGER.debug(f"무선 band 제어 요청: {params}")
        response = await self._async_service_json("wireless/band/set", params)
        if response.get("error"):
            _LOGGER.warning(f"무선 band 제어 실패: {response.get('error')}")
            return False
        return bool(response)

    async def async_set_web_geoip_enable(self, enable: bool) -> bool:
        if not self._beta_ui:
            return False

        response = await self._async_service_json("geoip/enable", enable)
        if response.get("error"):
            _LOGGER.warning(f"GeoIP 제어 실패: {response.get('error')}")
            return False
        return bool(response)

    async def async_set_web_geoip_policy(self, policy: str) -> bool:
        if not self._beta_ui:
            return False

        response = await self._async_service_json("geoip/policy/set", {"policy": policy})
        if response.get("error"):
            _LOGGER.warning(f"GeoIP policy 제어 실패: {response.get('error')}")
            return False
        return bool(response)

    async def async_set_web_accesslist_enable(self, enable: bool) -> bool:
        if not self._beta_ui:
            return False

        # wan1 항목 찾기
        wan1 = None
        if "acl" in self.web_result:
            for entry in self.web_result["acl"]:
                if entry.get("ntag") == "wan1":
                    wan1 = entry
                    break
        
        if wan1:
            port = wan1.get("open", {}).get("port", 80)
            params = {"ntag": "wan1", "open": {"flag": bool(enable), "port": port}}
            response = await self._async_service_json("acl/config", params)
            return not response.get("error")
        return False

    async def async_set_security_switch(self, key: str, value: bool) -> bool:
        """보안 스위치 설정 변경 (dos/config 기반)"""
        if not self._beta_ui:
            return False

        if key in ["syn_flood", "smurf", "ip_source_routing", "ip_spoofing", "inbound_ping", "outbound_ping"]:
            params = {key: bool(value)}
            response = await self._async_service_json("dos/config", params)
            return not response.get("error")
        
        if key == "csrf":
            params = {"csrf": {"run": bool(value)}}
            response = await self._async_service_json("dos/config", params)
            return not response.get("error")
            
        if key == "arp_virus":
            pps = 5
            if "security_dos" in self.web_result and "arp_virus" in self.web_result["security_dos"]:
                pps = self.web_result["security_dos"]["arp_virus"].get("pps", 5)
            params = {"arp_virus": {"run": bool(value), "pps": pps}}
            response = await self._async_service_json("dos/config", params)
            return not response.get("error")

        return False

    async def async_set_web_led_config(self, mode: str, on_time: int = 1320, off_time: int = 480) -> bool:
        # 나이트 LED 모드 설정 (연결될 파일: select.py)
        if not self._beta_ui:
            return False
        params: Dict[str, Any] = {"mode": mode}
        if mode == "interval":
            params["on"] = int(on_time)
            params["off"] = int(off_time)
        response = await self._async_service_json("led/config", params)
        return not response.get("error")

    async def async_set_web_upnp_enable(self, enable: bool) -> bool:
        # UPnP 설정 (연결될 파일: switch.py)
        if not self._beta_ui:
            return False
        response = await self._async_service_json("upnp/config", bool(enable))
        return not response.get("error")

    async def async_set_web_reboot_timer(self, run: bool, hour: int = 4, min_time: int = 0, days: List[str] = ["Fri"]) -> bool:
        # 자동 재시작 설정 (연결될 파일: switch.py)
        if not self._beta_ui:
            return False
        params = {
            "run": bool(run),
            "hour": int(hour),
            "min": int(min_time),
            "days": days
        }
        response = await self._async_service_json("reboot/timer", params)
        return not response.get("error")

    async def async_set_web_nat_config(self, enable: bool) -> bool:
        # 인터넷 연결 유지 설정 (연결될 파일: switch.py)
        if not self._beta_ui:
            return False
        response = await self._async_service_json("nat/config", bool(enable))
        return not response.get("error")

    async def async_set_web_wan_heartbeat(self, run: bool, interval: int = 3) -> bool:
        # WAN포트 끊김 시 재연결 설정 (연결될 파일: switch.py)
        if not self._beta_ui:
            return False
        params = {
            "run": bool(run),
            "interval": int(interval)
        }
        response = await self._async_service_json("wan/heartbeat", params)
        return not response.get("error")

    async def login(self) -> bool:
        """로그인 시도 (구형 및 신형 주소 모두 대응)"""
        for urn in [LOGIN_NEW_URN, LOGIN_URN]:
            url = f"{self._url}{urn}"
            data = {"username": self._user_id, "passwd": self._user_pw}
            if urn == LOGIN_NEW_URN:
                data = {"tmenu": "main", "smenu": "main", "username": self._user_id, "passwd": self._user_pw}
                
            try:
                session = await self._async_get_session()
                async with session.post(url, data=data, allow_redirects=True) as response:
                    text = await response.text()
                    # 세션 ID(16자리 문자열) 추출
                    ids = re.findall(re.compile(r"\w{16}"), text)
                    if ids:
                        self.efm_session_id = ids[0]
                        _LOGGER.debug(f"로그인 성공 (URL: {urn}, Session: {self.efm_session_id})")
                        return True
            except Exception as err:
                _LOGGER.debug(f"로그인 시도 실패 ({urn}): {err}")
        return False

    async def m_login(self) -> bool:
        url = f"{self._url}{M_LOGIN_URN}"
        data = {"username": self._user_id, "passwd": self._user_pw}
        try:
            session = await self._async_get_session()
            async with session.post(url, data=data) as response:
                text = await response.text()
                ids = re.findall(re.compile(r"\w{16}"), text)
                if ids:
                    self.efm_session_id = ids[0]
                    return True
        except Exception: pass
        return False

    async def session_update_beta_ui(self) -> None:
        """베타 UI 세션 업데이트 (연장)"""
        url = f"{self._url}{BETA_SERVICE_URN}"
        data = {"method":"session/update"}
        headers = self.headers.copy()
        if self.efm_session_id:
            headers["Cookie"] = f"efm_session_id={self.efm_session_id}"
            
        try:
            session = await self._async_get_session()
            async with session.post(url, json=data, headers=headers) as response:
                await response.text()
        except Exception: pass

    async def login_beta_ui(self) -> bool:
        """베타 UI 로그인 및 세션 쿠키 추출 (최종 강화 버전)."""
        url = f"{self._url}{BETA_SERVICE_URN}"
        data = {"method":"session/login", "params":{"id": self._user_id, "pw": self._user_pw}}
        
        # 세션 초기화 (깨끗한 상태에서 로그인 시도)
        if self._session:
            await self._session.close()
            self._session = None
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            "Origin": self._url,
            "Referer": f"{self._url}/",
            "Connection": "keep-alive"
        }
        
        try:
            session = await self._async_get_session()
            async with session.post(url, json=data, headers=headers) as response:
                res_json = await response.json()
                _LOGGER.debug(f"베타 UI 로그인 응답: {res_json}")
                
                if res_json and res_json.get('result') == "done":
                    # 쿠키 추출
                    session_id = response.cookies.get('efm_session_id')
                    if session_id:
                        self.efm_session_id = session_id.value
                        _LOGGER.debug(f"베타 UI 세션 아이디 확보: {self.efm_session_id}")
                    else:
                        _LOGGER.debug("쿠키가 없으나 결과가 done이므로 계속 진행")
                        # 쿠키가 없어도 일단 진행 (이후 요청에서 401 뜨면 그때 세션 파기)
                    
                    return True
                else:
                    _LOGGER.warning(f"베타 UI 로그인 거부됨: {res_json}")
        except Exception as err:
            _LOGGER.warning(f"베타 UI 로그인 예외 발생: {err}")
        return False

    async def verify_beta_ui(self) -> bool:
        """베타 UI 여부 판별 (파일 존재 여부 기반)."""
        urn = BETA_UI_URN if BETA_UI_URN.startswith("/") else f"/{BETA_UI_URN}"
        url = f"{self._url}{urn}flutter_bootstrap.js"
        try:
            session = await self._async_get_session()
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    _LOGGER.debug("베타 UI(Flutter) 기기 확인됨")
                    return True
        except Exception: pass
        return False

    async def verify_mobile(self) -> bool:
        text = await self._async_request("GET", f"{self._url}{HOSTINFO_URN}")
        self._ismobile = "iux" in text if text else False
        return True

    async def check_mesh(self) -> bool:
        text = await self._async_request("GET", f"{self._url}{MESH_URN}")
        mode_match = re.search(r'<input\b[^>]*id=["\']mode_none["\'][^>]*>', text or "", flags=re.IGNORECASE | re.DOTALL)
        self._ismesh = bool(mode_match and "checked" not in mode_match.group(0).lower())
        return self._ismesh

    async def m_check_mesh(self) -> bool:
        text = await self._async_request("GET", f"{self._url}{M_MESH_URN}")
        try:
            res_json = loads(text)
            self._ismesh = "easymesh" in res_json
            return self._ismesh
        except Exception: return False

    async def beta_ui_check_mesh(self) -> bool:
        url = f"{self._url}{BETA_SERVICE_URN}"
        data = {"method":"easymesh/info"}
        headers = self.headers.copy()
        if self.efm_session_id:
            headers["Cookie"] = f"efm_session_id={self.efm_session_id}"
            
        try:
            session = await self._async_get_session()
            async with session.post(url, json=data, headers=headers) as response:
                res_json = await response.json()
                if res_json and res_json.get('result'):
                    self._ismesh = res_json['result'].get('active', False)
        except Exception: pass
        return self._ismesh

    async def wlan_check(self) -> Dict:
        result_dict = {"session": True}
        for band, urn in [("2.4GHz", WLAN_2G_URN), ("5GHz", WLAN_5G_URN)]:
            text = await self._async_request("GET", self._url + urn)
            result_dict.update(self.device_parsing(_extract_table_rows(text), band))
        if self._ismesh: result_dict.update(await self.get_mesh_station())
        return result_dict

    async def m_wlan_check(self) -> Dict:
        result_dict = {"session": True}
        for band, urn in [("2.4GHz", M_WLAN_2G_URN), ("5GHz", M_WLAN_5G_URN)]:
            text = await self._async_request("GET", self._url + urn)
            try: result_dict.update(self.json_parsing(loads(text), band))
            except Exception: continue
        if self._ismesh: result_dict.update(await self.get_mesh_station())
        return result_dict

    async def beta_ui_wlan_check(self) -> Dict:
        """베타 UI 기기 목록 조회 (수동 쿠키 주입)."""
        url = f"{self._url}{BETA_SERVICE_URN}"
        data = {"method":"network/interface/lan/stations"}
        headers = self.headers.copy()
        if self.efm_session_id:
            headers["Cookie"] = f"efm_session_id={self.efm_session_id}"
            
        try:
            session = await self._async_get_session()
            async with session.post(url, json=data, headers=headers) as response:
                res_json = await response.json()
                if res_json and res_json.get('result'):
                    res = self.beta_ui_device_parsing(res_json['result'])
                    if self._ismesh: res.update(await self.get_mesh_station())
                    res["session"] = True
                    return res
        except Exception as err:
            _LOGGER.debug(f"베타 UI 기기 조회 실패: {err}")
        return {"session": False}

    def beta_ui_device_parsing(self, response_json: List) -> Dict:
        """베타 UI(Flutter 기반) 전용 기기 목록 파싱 (계층 구조 대응)."""
        result_dict = {}
        for device in response_json:
            mac = device.get("mac", "").strip().replace(":", "").replace("-", "").lower()
            if not mac: continue
            
            info = device.get("info", {})
            conn = device.get("connection", {})
            wireless = conn.get("wireless", {})
            
            # 정보 추출 (계층형 구조 대응)
            ip = info.get("ip", "N/A")
            name = info.get("name", "N/A")
            band = wireless.get("bss", conn.get("type", "Unknown"))
            stay_time_sec = wireless.get("duration", 0)
            rssi = wireless.get("rssi")
            
            result_dict[mac] = {
                "ip": ip,
                "name": name,
                "band": band,
                "stay_time": f"{stay_time_sec}초",
                "rssi": rssi,
                "state": "home"
            }
        return result_dict

    def device_parsing(self, response_list: List, band: str) -> Dict:
        result_dict = {}
        for device in response_list:
            if isinstance(device, str):
                tds = _extract_table_cells(device)
            else:
                tds = []
                try:
                    for td in device.find_all("td"):
                        tds.append(html.unescape(td.get_text(" ", strip=True)))
                except Exception:
                    tds = []
            if len(tds) == 4:
                mac = tds[0].strip().replace(":", "").replace("-", "").lower()
                ip_match = re.search(r"\d{1,3}(?:\.\d{1,3}){3}", tds[3])
                result_dict[mac] = {"ip": ip_match.group() if ip_match else "N/A", "band": band, "stay_time": tds[2].strip(), "state": "home"}
        return result_dict

    def json_parsing(self, response_json: Dict, band: str) -> Dict:
        result_dict = {}
        for device in response_json.get("stalist", []):
            if "mac" in device:
                mac = device["mac"].strip().replace(":", "").replace("-", "").lower()
                result_dict[mac] = {"ip": device.get("ipaddr", "N/A"), "band": band,
                    "stay_time": f"{device.get('day')}일 {device.get('hour')}시간 {device.get('min')}분 {device.get('sec')}초", "state": "home"}
        return result_dict

    async def get_mesh_station(self) -> Dict:
        text = await self._async_request("GET", f"{self._url}{MESH_STATION_URN}")
        res = {}
        try:
            stations = loads(text).get("station", [])
            for s in stations:
                if s.get("connection") not in ["Unknown", "WIRED"]:
                    mac = s["mac"].strip().replace(":", "").replace("-", "").lower()
                    td = timedelta(seconds=s.get("timestamp", 0) - s.get("connected_ts", 0))
                    res[mac] = {
                        "ip": s.get("ip", "N/A"), "band": s.get("mode", "Unknown"),
                        "stay_time": f"{td.days}일 {td.seconds//3600}시간 {(td.seconds//60)%60}분 {td.seconds%60}초",
                        "rssi": s.get("rssi"), "state": "home" if s.get("rssi", 0) >= RSS_LIMIT else "not_home"
                    }
        except Exception: pass
        return res

    async def async_close(self) -> None:
        if self._session:
            await self._session.close()

    async def async_reboot(self) -> bool:
        """공유기 재부팅 (Web CGI 및 JSON-RPC)."""
        if self._beta_ui:
            try:
                response = await self._async_service_json("reboot/now")
                if not response.get("error"):
                    _LOGGER.info("공유기 재부팅 명령 전송 (JSON-RPC)")
                    return True
            except Exception as err:
                _LOGGER.debug(f"JSON-RPC 재부팅 시도 실패: {err}")

        url = f"{self._url}/sess-bin/timepro.cgi?tmenu=sysconf&smenu=reboot&act=reboot"
        try:
            await self._async_request("GET", url)
            _LOGGER.info("공유기 재부팅 명령 전송 (Web CGI)")
            return True
        except Exception as err: 
            _LOGGER.debug(f"Web CGI 재부팅 시도 실패: {err}")
            return False

    async def async_set_web_iptv_config(self, mode: str, port: int | None = None) -> bool:
        """IPTV 설정을 변경한다. (연결될 파일: select.py)"""
        params: Dict[str, Any] = {"mode": mode}
        if port is not None:
            params["port"] = port

        try:
            response = await self._async_service_json("iptv/config", params)
            if not response.get("error"):
                _LOGGER.info(f"IPTV 설정 변경 완료: {mode}")
                return True
        except Exception as err:
            _LOGGER.warning(f"IPTV 설정 변경 실패: {err}")
        return False

    async def async_set_web_wg_server_run(self, run: bool) -> bool:
        """WireGuard 서버 실행 상태를 변경한다. (연결될 파일: switch.py)"""
        wg_config = self.web_result.get("wg_server", {})
        if not isinstance(wg_config, dict):
            wg_config = {}

        # 펌웨어 유효성 검사(Validation) 통과를 위해, 오직 필수 5가지 스펙 필드(run, ip, subnet, port, nat)만 정제하여 전송 (pubkey 등 메타데이터 제외)
        params = {
            "run": bool(run),
            "ip": wg_config.get("ip", "10.0.21.1"),
            "subnet": wg_config.get("subnet", "24"),
            "port": int(wg_config.get("port", 53344)),
            "nat": bool(wg_config.get("nat", True))
        }

        try:
            response = await self._async_service_json("wg/server/set", params)
            if not response.get("error"):
                _LOGGER.info(f"WireGuard 서버 실행 상태 변경 완료: {run}")
                return True
            else:
                _LOGGER.warning(f"WireGuard 서버 실행 상태 변경 중 API 오류: {response.get('error')}")
        except Exception as err:
            _LOGGER.warning(f"WireGuard 서버 실행 상태 변경 실패: {err}")
        return False

    async def async_set_web_led_config(self, mode: str, on_time: int, off_time: int) -> bool:
        """나이트 LED 설정을 변경한다. (연결될 파일: select.py)"""
        params = {
            "mode": mode,
            "on": on_time,
            "off": off_time
        }

        try:
            response = await self._async_service_json("led/config", params)
            if not response.get("error"):
                _LOGGER.info(f"나이트 LED 설정 변경 완료: mode={mode}, on={on_time}, off={off_time}")
                return True
            else:
                _LOGGER.warning(f"나이트 LED 설정 변경 중 API 오류: {response.get('error')}")
        except Exception as err:
            _LOGGER.warning(f"나이트 LED 설정 변경 실패: {err}")
        return False

