from __future__ import annotations

import logging
import asyncio
import time
import re
import html
import aiohttp
from typing import Any, Dict, List, Optional, Final
from json import loads
from datetime import datetime, timedelta, timezone
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from ipaddress import ip_interface
from .const import *
from .dhcp import DHCPReservations
from .port_forward import PortForwardRules

# 요약: ipTIME 공유기와의 통신(Web CGI) 담당 API 클래스
# 연결될 파일: const.py, coordinator.py

_LOGGER = logging.getLogger(__name__)
MESH_STATUS_REFRESH_INTERVAL = 15.0


# Summary: Treat ambiguous responses as connection failures, not rejected credentials.
# Related files: coordinator.py, config_flow.py.
class RouterConnectionError(aiohttp.ClientError):
    """The router did not return a usable response."""


def _session_error(response: dict[str, Any]) -> bool:
    error = response.get("error")
    if not isinstance(error, dict):
        return False
    message = str(error.get("message", "")).lower()
    return any(word in message for word in ("session", "login", "auth"))


# Summary: Reject missing or malformed retained settings before constructing a write.
# Related files: select.py, switch.py, tests/test_settings.py.
def _setting_int(config: dict, key: str, minimum: int, maximum: int | None = None) -> int:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r"-?\d+", str(value)):
        raise HomeAssistantError(f"Router setting '{key}' is missing or invalid; refresh the router configuration")
    try:
        number = int(value)
    except ValueError as err:
        raise HomeAssistantError(f"Router setting '{key}' is not a usable integer") from err
    if number < minimum or (maximum is not None and number > maximum):
        raise HomeAssistantError(f"Router setting '{key}' is outside its supported range")
    return number


def _setting_bool(config: dict, key: str) -> bool:
    value = config.get(key)
    if not isinstance(value, bool):
        raise HomeAssistantError(f"Router setting '{key}' is missing or invalid; refresh the router configuration")
    return value


def _setting_days(config: dict) -> list[str]:
    value = config.get("days")
    if not isinstance(value, list) or any(
        not isinstance(day, str) or day.lower() not in ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
        for day in value
    ):
        raise HomeAssistantError("Router reboot days are missing or invalid; refresh the router configuration")
    return list(value)


# Summary: Normalize the router's EasyMesh mode for role-specific entity and API gates.
# Related files: coordinator.py, binary_sensor.py, sensor.py, select.py, switch.py, number.py.
def get_easymesh_role(web_data: Dict[str, Any]) -> str | None:
    """Return the EasyMesh role reported by the router."""
    mesh = web_data.get("easymesh", {}) if isinstance(web_data, dict) else {}
    info = mesh.get("info", {}) if isinstance(mesh, dict) else {}
    system_info = web_data.get("system_info", {}) if isinstance(web_data, dict) else {}
    system_mesh = system_info.get("easymesh", {}) if isinstance(system_info, dict) else {}
    info_active = info.get("active") if isinstance(info, dict) else None
    active = info_active if info_active is not None else (
        web_data.get("easymesh_active") if isinstance(web_data, dict) else None
    )
    if active is not None and not bool(active):
        return "alone"
    role = None
    if isinstance(info, dict):
        role = info.get("role") or info.get("current_role")
    if not role and isinstance(system_mesh, dict):
        role = system_mesh.get("role")
    return str(role).strip().lower() if role else None


def is_easymesh_agent(web_data: Dict[str, Any]) -> bool:
    return get_easymesh_role(web_data) == "agent"


def is_easymesh_controller(web_data: Dict[str, Any]) -> bool:
    if get_easymesh_role(web_data) != "controller":
        return False
    mesh = web_data.get("easymesh", {}) if isinstance(web_data, dict) else {}
    info = mesh.get("info", {}) if isinstance(mesh, dict) else {}
    active = info.get("active") if isinstance(info, dict) else None
    return active is not False


# Summary: Share EasyMesh agent normalization and liveness rules across entity platforms.
# Related files: binary_sensor.py, sensor.py.
def get_easymesh_agents(mesh_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize EasyMesh agent responses from different firmware versions."""
    if not isinstance(mesh_data, dict):
        return []
    raw_agents = mesh_data.get("agents", mesh_data.get("agent", []))
    if isinstance(raw_agents, dict):
        raw_agents = raw_agents.get("agent", raw_agents.get("list", []))
    if not isinstance(raw_agents, list):
        return []
    return [agent for agent in raw_agents if isinstance(agent, dict)]


def is_easymesh_agent_connected(agent: Dict[str, Any]) -> bool:
    """Determine agent liveness from explicit status and backhaul fields."""
    offline_values = {"0", "FALSE", "NO", "OFF", "DOWN", "MISSING", "NOT_CONNECTED", "DISCONNECTED", "OFFLINE"}
    online_values = {"1", "TRUE", "YES", "ON", "UP", "CONNECTED", "ONLINE", "ONBOARDING"}
    status = str(agent.get("status") or "").strip().upper().replace("-", "_").replace(" ", "_")
    connection = str(agent.get("connection") or "").strip().upper().replace("-", "_").replace(" ", "_")

    if status in offline_values or connection in offline_values:
        return False

    for key in ("connected", "active", "online"):
        value = agent.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in offline_values:
                return False
            if normalized in online_values:
                return True

    if connection in {"WIRED", "WIRELESS", "ETHERNET", "WIFI", "WIRELESS_BACKHAUL"}:
        return True
    return status in online_values


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

def format_channel_string(channel_str: Any) -> str:
    if channel_str in (None, "", "0", "0.0", "auto", "Auto", "AUTO"):
        return "auto"
    s = str(channel_str).lower().strip()
    if "." not in s:
        return s
    parts = s.split(".")
    if len(parts) != 2:
        return parts[0]
    try:
        x = int(parts[0])
        y = int(parts[1])
    except ValueError:
        return parts[0]
    diff = abs(x - y)
    if 1 <= x <= 14:
        return f"{x} (40MHz)" if diff == 4 else str(x)
    if x >= 36:
        if diff == 4: return f"{x} (40MHz)"
        if y in [42, 58, 106, 122, 138, 155, 171]: return f"{x} (80MHz)"
        if y in [50, 114, 163, 15, 47, 79, 111, 143, 175, 207]: return f"{x} (160MHz)"
        return f"{x} (Bonded)"
    return str(x)


# Summary: Normalize bonded channel strings to the primary channel used by the channel selector.
# Related files: select.py.
def channel_option_value(channel: Any) -> str:
    if channel is None:
        return "auto"
    value = str(channel).strip()
    if value.lower() in ("", "0", "0.0", "auto"):
        return "auto"
    match = re.fullmatch(r"(\d+)(?:\.\d+)?", value)
    if match:
        return match.group(1)
    return format_channel_string(channel)

# Summary: Select the latest peer handshake from firmware elapsed-second values.
# Related files: sensor.py.
def _latest_wireguard_handshake(peers: Any, observed_at: datetime) -> tuple:
    latest_peer = None
    latest_age = None
    for peer in peers if isinstance(peers, list) else []:
        if not isinstance(peer, dict):
            continue
        age = peer.get("last_handshake")
        if type(age) is not int or not 0 <= age <= observed_at.timestamp():
            continue
        if latest_age is None or age < latest_age:
            latest_peer, latest_age = peer, age
    if latest_peer is None:
        return None, None
    return latest_peer.get("name") or None, observed_at - timedelta(seconds=latest_age)


# Summary: Track bidirectional port activity without treating idle links as failures.
# Related files: binary_sensor.py, coordinator.py.
def _port_activity(stats: Any, ports: Any, previous: dict, now: float) -> dict:
    result = {}
    if not isinstance(stats, list) or not isinstance(ports, list):
        previous.clear()
        return result
    samples = {(p.get("type"), p.get("port")): p for p in stats if isinstance(p, dict)}
    seen = set()
    for port in ports:
        key = (port.get("type"), port.get("port"))
        seen.add(key)
        sample = samples.get(key, {})
        rx_stats, tx_stats = sample.get("rx"), sample.get("tx")
        rx = rx_stats.get("packet") if isinstance(rx_stats, dict) else None
        tx = tx_stats.get("packet") if isinstance(tx_stats, dict) else None
        linked = port.get("link") not in (None, "", "null", "0", 0, False)
        old = previous.get(key)
        valid = all(type(value) is int and value >= 0 for value in (rx, tx))
        state = {"active": False if not linked else None, "rx_packets_delta": None,
                 "tx_packets_delta": None, "activity_window_seconds": 30}
        if not valid:
            previous.pop(key, None)
        else:
            current = {"rx": rx, "tx": tx, "rx_at": None, "tx_at": None, "last_activity_at": None}
            if linked and old and rx >= old["rx"] and tx >= old["tx"]:
                drx, dtx = rx - old["rx"], tx - old["tx"]
                current["rx_at"] = now if drx else old["rx_at"]
                current["tx_at"] = now if dtx else old["tx_at"]
                state.update(rx_packets_delta=drx, tx_packets_delta=dtx)
                current["last_activity_at"] = (
                    datetime.now(timezone.utc).isoformat() if drx or dtx else old["last_activity_at"]
                )
                state["active"] = all(
                    stamp is not None and now - stamp <= 30
                    for stamp in (current["rx_at"], current["tx_at"])
                )
            previous[key] = current
            state["last_activity_at"] = current["last_activity_at"]
        result[f"{key[0]}:{key[1]}"] = state
    for key in set(previous) - seen:
        previous.pop(key)
    return result


# Summary: Exclude hubs/APs using WAN enable, NAT and optional WAN-port role.
# Related files: coordinator.py, binary_sensor.py.
def _internet_monitor_enabled(nat: Any, wan_config: Any, port_role: Any) -> bool | None:
    enabled = wan_config.get("enable") if isinstance(wan_config, dict) else None
    if nat is False or enabled is False or port_role == "lan":
        return False
    if nat is True and enabled is True:
        return True
    return None


class IPTimeAPI:
    """ipTIME 공유기 API (누락 함수 복구 버전)"""
    
    def __init__(self, hass, url: str, user_id: str, user_pw: str) -> None:
        self._hass = hass
        self._user_id = user_id
        self._user_pw = user_pw
        self._ismobile = False
        self._ismesh = False
        self._beta_ui = False
        self._last_mesh_status_check = 0.0
        self.result: Dict[str, Any] = {}
        self.web_result: Dict[str, Any] = {}
        self._dns_security_lock = asyncio.Lock()
        self._settings_lock = asyncio.Lock()
        self._latest_firmware_version: Any = None
        self._last_caching_time = 0.0
        self._cached_model = None
        self._port_samples: dict = {}
        self._login_lock = asyncio.Lock()
        self._auth_failed = False
        self._ui_detected = False
        self._retry_at = 0.0
        self._retry_delay = 0.0

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
        # Summary: Keep a per-router reservation lock across action calls.
        # Related files: dhcp.py, services.py.
        self.dhcp = DHCPReservations(self)
        # Summary: Serialize port forwarding action changes per router.
        # Related files: port_forward.py, services.py.
        self.port_forward = PortForwardRules(self)

    # Summary: Stop rejected credentials and defer network retries without blocking HA.
    # Related files: coordinator.py, config_flow.py.
    def _check_ready(self) -> None:
        if self._auth_failed:
            raise ConfigEntryAuthFailed("Router credentials were rejected; reauthenticate")
        if time.monotonic() < self._retry_at:
            raise RouterConnectionError("Waiting before retrying the router")

    def _defer_retry(self) -> None:
        now = time.monotonic()
        if now >= self._retry_at:
            self._retry_delay = min(max(15.0, self._retry_delay * 2), 300.0)
            self._retry_at = now + self._retry_delay

    def reset_retry_delay(self) -> None:
        """Reset backoff only after a complete successful collection."""
        self._retry_at = 0.0
        self._retry_delay = 0.0

    def _reject_auth(self) -> None:
        self._auth_failed = True
        self.efm_session_id = None
        raise ConfigEntryAuthFailed("Router credentials were rejected; reauthenticate")

    # Summary: Accept only explicit session cookies or named session assignments.
    # Related files: config_flow.py, coordinator.py.
    def _capture_session(self, response, text: str = "") -> bool:
        cookie = response.cookies.get("efm_session_id")
        if cookie is not None and cookie.value:
            self.efm_session_id = cookie.value
            return True
        for header in response.headers.getall("Set-Cookie", []):
            match = re.search(r"(?:^|;\s*)efm_session_id=([^;\s]+)", header)
            if match:
                self.efm_session_id = match.group(1).strip('"')
                return True
        match = re.search(
            r"""efm_session_id["']?\s*(?:=|,)\s*["']([A-Za-z0-9_-]+)["']""",
            text,
        )
        if match:
            self.efm_session_id = match.group(1)
            return True
        # Older firmware uses a single-argument setCookie session setter.
        match = re.search(r"""\bsetCookie\(\s*["']([A-Za-z0-9]{16})["']\s*\)""", text)
        if match:
            self.efm_session_id = match.group(1)
            return True
        return False

    async def _async_ensure_login(self, expired_session: str | None = None) -> None:
        async with self._login_lock:
            self._check_ready()
            if self.efm_session_id and self.efm_session_id != expired_session:
                return
            self.efm_session_id = None
            try:
                if not self._ui_detected:
                    self._beta_ui = await self.verify_beta_ui()
                    if not self._beta_ui:
                        await self.verify_mobile()
                    self._ui_detected = True
                if self._beta_ui:
                    success = await self.login_beta_ui()
                elif self._ismobile:
                    success = await self.m_login()
                else:
                    success = await self.login()
                if not success:
                    raise RouterConnectionError("Router login response was not recognized")
            except ConfigEntryAuthFailed:
                self._auth_failed = True
                self.efm_session_id = None
                raise
            except (aiohttp.ClientError, TimeoutError):
                self._defer_retry()
                raise

    async def _async_get_session(self) -> aiohttp.ClientSession:
        self._check_ready()
        if self._session is None or self._session.closed:
            # HA 공용 세션 대신 전용 독립 세션 생성 (세션 기반 공유기 대응)
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=TIME_OUT),
                headers=self.headers
            )
        return self._session

    async def _async_request(self, method: str, url: str, **kwargs) -> str:
        self._check_ready()
        try:
            session = await self._async_get_session()
            headers = kwargs.get("headers", self.headers.copy())
            if self.efm_session_id:
                headers["Cookie"] = f"efm_session_id={self.efm_session_id}"
            
            kwargs["headers"] = headers
            async with session.request(method, url, **kwargs) as response:
                if response.status in (401, 403):
                    self.efm_session_id = None
                    raise RouterConnectionError("Router session expired")
                response.raise_for_status()
                text = await response.text()
                if not text:
                    raise RouterConnectionError("Empty router response")
                login_form = re.search(
                    r'name=["\x27]?(?:username|passwd)\b', text, re.IGNORECASE
                )
                login_redirect = re.search(
                    r"""location(?:\.href\s*=|\s*=|\.(?:replace|assign)\()\s*["']"""
                    r"""[^"']*(?:/login/|login_session\.cgi|m_login\.cgi)""",
                    text, re.IGNORECASE,
                )
                if self.efm_session_id and (login_form or login_redirect):
                    self.efm_session_id = None
                    raise RouterConnectionError("Router returned a login form")
                return text
        except (aiohttp.ClientError, TimeoutError):
            self._defer_retry()
            raise

    async def _async_service_json(self, method: str, params: Any = None) -> Dict[str, Any]:
        """Retry an explicitly expired session once, without retrying empty replies."""
        self._check_ready()
        await self._async_ensure_login()
        url = f"{self._url}{BETA_SERVICE_URN}"
        payload: Dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params

        async def _execute_call():
            self._check_ready()
            headers = self.headers.copy()
            if self.efm_session_id:
                headers["Cookie"] = f"efm_session_id={self.efm_session_id}"
            
            session = await self._async_get_session()
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status in (401, 403):
                    return {"error": {"message": "session expired"}}
                response.raise_for_status()
                try:
                    result = loads(await response.text())
                except (ValueError, TypeError) as err:
                    raise RouterConnectionError("Invalid JSON response") from err
                if not isinstance(result, dict) or not result:
                    raise RouterConnectionError("Empty or invalid RPC response")
                return result

        try:
            sent_session = self.efm_session_id
            res = await _execute_call()
            if _session_error(res):
                await self._async_ensure_login(expired_session=sent_session)
                res = await _execute_call()
                if _session_error(res):
                    self._reject_auth()
            return res
        except (aiohttp.ClientError, TimeoutError):
            self._defer_retry()
            raise

    async def async_update(self, rssi_limit: int = DEFAULT_RSSI_LIMIT) -> bool:
        """데이터 업데이트 메인 로직 (안정화)."""
        await self._async_ensure_login()
        if self._beta_ui:
            await self.beta_ui_check_mesh()

        # Summary: Refresh legacy UI mesh state so disabling EasyMesh promotes an Agent to standalone.
        # Related files: coordinator.py, presence.py, config_flow.py.
        if not self._beta_ui and time.monotonic() - self._last_mesh_status_check >= MESH_STATUS_REFRESH_INTERVAL:
            if self._ismobile:
                await self.m_check_mesh()
            else:
                await self.check_mesh()
            self._last_mesh_status_check = time.monotonic()

        # 2. 데이터 수집
        if self._beta_ui:
            await asyncio.sleep(1)
            self.result = await self.beta_ui_wlan_check(rssi_limit=rssi_limit)
            await self.session_update_beta_ui()
        elif self._ismobile:
            self.result = await self.m_wlan_check(rssi_limit=rssi_limit)
        else:
            self.result = await self.wlan_check(rssi_limit=rssi_limit)
        
        if len(self.result) > 1:
            first_mac = next(iter(self.result.keys())) if self.result else "None"
            _LOGGER.info(f"ipTIME Web 데이터 수집 성공: 기기 {len(self.result)-1}대 감지 (최초 MAC: {first_mac})")
        else:
            _LOGGER.warning("ipTIME Web 데이터 수집 실패: 로그인 세션은 확보했으나 기기 목록이 비어있습니다.")
        
        # 3. 세션 만료 체크
        if self.result.get("session") is False:
            _LOGGER.debug("세션 만료 감지, 다음 주기에서 재로그인 시도")
            self.efm_session_id = None
            self._defer_retry()
            raise RouterConnectionError("Router session expired")
            
        return True

    async def async_check_internet(self) -> bool:
        """Check real external reachability independently of WAN link/IP state."""
        try:
            session = await self._async_get_session()
            async with session.get("https://connectivitycheck.gstatic.com/generate_204", timeout=3) as response:
                return response.status in (200, 204)
        except Exception:
            return False

    async def async_get_web_data(self) -> bool:
        """웹 UI에서 노출되는 시스템/포트 정보를 수집한다. (연결될 파일: coordinator.py)"""
        # 요약: 스마트 캐싱 엔진을 적용하여 실시간 데이터는 5초마다 수집하고, 정적 설정 데이터는 5분 캐시 처리한다.
        # 연결 파일: coordinator.py
        if self.web_result is None:
            self.web_result = {}

        if not self._beta_ui:
            return False

        try:
            now = time.time()
            # 5분(300초) 단위 캐싱 조건 성립 여부 판단
            use_cache = (now - self._last_caching_time) < 300.0

            # 1. 펌웨어 기본 정보 수집 (내부 24시간 캐시 지원됨)
            firmware = await self._async_service_json("firmware/info")
            if firmware.get("result"):
                self.web_result["firmware"] = firmware["result"]

            firmware_block = self.web_result.setdefault("firmware", {})
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

            # 2. 공유기 모델명 수집 (평생 캐시 처리: CGI 파싱 부하 최소화)
            if self._cached_model is not None:
                self.web_result["model"] = self._cached_model
            else:
                product_html = await self._async_request("GET", f"{self._url}/ui/port_setup")
                product_match = re.search(r'PRODUCT:\s*"([^"]+)"', product_html)
                model_name = _normalize_model_name(product_match.group(1) if product_match else None)
                self._cached_model = model_name
                self.web_result["model"] = model_name

            # Summary: Refresh DNS security switch states.
            # Related files: switch.py.
            async with self._dns_security_lock:
                for method in ("network/dns/redirect", "firewall/secure_dns"):
                    await self._async_read_dns_security(method)

            # 3. 자주 변경되지 않는 설정값 (LAN, WAN, DNS, GeoIP, ACL, DoS, UPnP, Reboot, WireGuard 등) 캐싱 처리
            if not use_cache or "lan" not in self.web_result or "wan" not in self.web_result:
                _LOGGER.debug("정적 설정 데이터 캐시 만료 또는 최초 수집: 공유기 쿼리 수행 시작")
                
                lan = await self._async_service_json("network/interface/lan/info")
                if lan.get("result"):
                    self.web_result["lan"] = lan["result"]

                wan = await self._async_service_json("network/interface/wan1/info")
                if wan.get("result"):
                    self.web_result["wan"] = wan["result"]

                dns = await self._async_service_json("network/dns/info")
                if dns.get("result"):
                    self.web_result["dns"] = dns["result"]

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

                upnp_config = await self._async_service_json("upnp/config")
                if upnp_config.get("result") is not None:
                    self.web_result["upnp_config"] = upnp_config["result"]

                portforward_config = await self._async_service_json("portforward/config")
                if portforward_config.get("result") is not None:
                    self.web_result["portforward_config"] = portforward_config["result"]

                upnp_relay = await self._async_service_json("upnp/relay")
                if upnp_relay.get("result") is not None:
                    self.web_result["upnp_relay"] = upnp_relay.get("result")

                reboot_timer = await self._async_service_json("reboot/timer")
                if reboot_timer.get("result") is not None:
                    self.web_result["reboot_timer"] = reboot_timer["result"]

                nat_config = await self._async_service_json("nat/config")
                if nat_config.get("result") is not None:
                    self.web_result["nat_config"] = nat_config["result"]

                # Summary: Read operating mode without changing router configuration.
                # Related files: coordinator.py, binary_sensor.py.
                wan_config = await self._async_service_json("network/interface/wan1/config")
                port_role = await self._async_service_json("port/role")
                mode = _internet_monitor_enabled(
                    nat_config.get("result"), wan_config.get("result"), port_role.get("result")
                )
                if mode is not None:
                    self.web_result["internet_monitor_enabled"] = mode

                self._last_caching_time = now

            # 4. 실시간 수집 데이터 (유선 포트, 무선 상태, LED, WAN 링크 상태는 매 주기마다 필수 조회)
            ports = await self._async_service_json("port/link/status")
            if ports.get("result"):
                self.web_result["ports"] = ports["result"]

            # Summary: Derive recent bidirectional traffic from read-only packet counters.
            # Related files: binary_sensor.py.
            stats = await self._async_service_json("port/stat/get")
            self.web_result["port_activity"] = _port_activity(
                stats.get("result"), ports.get("result"), self._port_samples, time.monotonic()
            )

            wg_server = await self._async_service_json("wg/server/show")
            if wg_server.get("result") is not None:
                wg_data = wg_server["result"]
                if isinstance(wg_data, dict):
                    # Firmware 16 exposes peer definitions through a separate endpoint.
                    # Related files: sensor.py, switch.py.
                    peer_response = await self._async_service_json("wg/peer/show")
                    observed_at = datetime.now(timezone.utc)
                    peers = peer_response.get("result") if isinstance(peer_response.get("result"), list) else wg_data.get("peers", wg_data.get("peer", wg_data.get("clients", [])))
                    if isinstance(peers, dict):
                        peers = list(peers.values())
                    peer_count = len(peers) if isinstance(peers, list) else 0
                    # Summary: Store the latest peer name and UTC handshake timestamp.
                    # Related files: sensor.py.
                    last_peer_name, last_handshake_at = _latest_wireguard_handshake(peers, observed_at)
                    self.web_result["wg_server"] = {
                        "run": wg_data.get("active"),
                        "ip": wg_data.get("address"),
                        "port": wg_data.get("port"),
                        "nat": wg_data.get("nat"),
                        "peer_count": peer_count,
                        "last_peer_name": last_peer_name,
                        "last_handshake_at": last_handshake_at,
                    }
                else:
                    self.web_result["wg_server"] = {}

            wireless_info = await self._async_service_json("wireless/info")
            wireless_band = await self._async_service_json("wireless/band/info")
            wireless_band_show = await self._async_service_json("wireless/band/show")
            wireless_bss = await self._async_service_json("wireless/bss/show")
            wireless_client = await self._async_service_json("wireless/client/show")

            system_info = await self._async_service_json("system/info")
            if isinstance(system_info.get("result"), dict):
                self.web_result["system_info"] = system_info["result"]
            else:
                self.web_result["system_info"] = {}

            easymesh_info = await self._async_service_json("easymesh/info")
            easymesh_config = await self._async_service_json("easymesh/config")
            easymesh_agents = await self._async_service_json("easymesh/show/agent")
            mesh_info = easymesh_info.get("result")
            if isinstance(mesh_info, dict) and "active" in mesh_info:
                self.web_result["easymesh_active"] = bool(mesh_info.get("active"))
            else:
                self.web_result["easymesh_active"] = bool(self._ismesh)
            if (
                easymesh_info.get("result") is not None
                or easymesh_config.get("result") is not None
                or easymesh_agents.get("result") is not None
            ):
                self.web_result["easymesh"] = {
                    "info": easymesh_info.get("result", {}),
                    "config": easymesh_config.get("result", {}),
                    "agents": easymesh_agents.get("result", {}),
                }
            
            # Firmware 16 separates configured values (band/show) from live state
            # (band/info); retain both while exposing the live channel to entities.
            band_show = wireless_band_show.get("result") or []
            band_info = wireless_band.get("result") or []
            info_by_band = {str(item.get("band")).lower(): item for item in band_info if isinstance(item, dict) and item.get("band")}
            band_data = []
            for configured in band_show:
                if not isinstance(configured, dict):
                    continue
                key = str(configured.get("band")).lower()
                merged = dict(configured)
                live = info_by_band.get(key)
                if live:
                    merged.update({k: v for k, v in live.items() if k != "channel"})
                    merged["configured_channel"] = configured.get("channel")
                    merged["channel"] = live.get("channel", configured.get("channel"))
                band_data.append(merged)
            if not band_data:
                band_data = band_info
            if wireless_info.get("result") or band_data or wireless_bss.get("result"):
                self.web_result["wireless"] = {
                    "info": wireless_info.get("result", []),
                    "band": band_data,
                    "bss": wireless_bss.get("result", []),
                    "client": wireless_client.get("result", []),
                }

            led_config = await self._async_service_json("led/config")
            if led_config.get("result") is not None:
                self.web_result["led_config"] = led_config["result"]

            wan_heartbeat = await self._async_service_json("wan/heartbeat")
            if wan_heartbeat.get("result") is not None:
                self.web_result["wan_heartbeat"] = wan_heartbeat["result"]

            uptime = self.web_result.get("system_info", {}).get("uptime")
            self.web_result["uptime"] = uptime if isinstance(uptime, (int, float)) and uptime >= 0 else None
            return True
        except (ConfigEntryAuthFailed, aiohttp.ClientError, TimeoutError):
            raise
        except Exception as err:
            _LOGGER.debug(f"웹 데이터 수집 실패: {err}")
            return False

    # Summary: Read retained values immediately before a settings write; never use cached defaults.
    # Related files: select.py, switch.py, tests/test_settings.py.
    async def _async_read_setting(self, method: str, result_type: type = dict):
        try:
            response = await self._async_service_json(method)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError("Cannot read the current router settings; no change was sent") from err
        result = response.get("result")
        if response.get("error") is not None or not isinstance(result, result_type):
            raise HomeAssistantError("Cannot read the current router settings; no change was sent")
        return result

    async def _async_write_setting(self, method: str, params: dict) -> bool:
        response = await self._async_service_json(method, params)
        if not response or response.get("error") is not None or response.get("result") is None:
            raise HomeAssistantError("The router rejected the setting change")
        self._last_caching_time = 0.0
        return True

    # Summary: Apply EasyMesh global settings while limiting advanced fields to controller mode.
    # Related files: switch.py, number.py.
    async def _async_set_easymesh_global(self, values: Dict[str, Any]) -> bool:
        """Retain nested mesh settings from a fresh router response."""
        role = get_easymesh_role(self.web_result)
        if not is_easymesh_controller(self.web_result) and not (
            set(values) == {"enable"} and role == "alone"
        ):
            return False
        async with self._settings_lock:
            config = await self._async_read_setting("easymesh/config")
            current = config.get("global")
            if not isinstance(current, dict) or any(key not in current for key in values):
                raise HomeAssistantError("Required EasyMesh settings are missing; no change was sent")
            updates = dict(values)
            if "density_control" in updates:
                density = current.get("density_control")
                if not isinstance(density, dict):
                    raise HomeAssistantError("EasyMesh density settings are missing")
                density = {**density, **updates["density_control"]}
                updates["density_control"] = {
                    "enable": _setting_bool(density, "enable"),
                    "rssi": _setting_int(density, "rssi", -100, -40),
                }
            return await self._async_write_setting("easymesh/config", {"global": updates})

    async def async_set_easymesh_enabled(self, enabled: bool) -> bool:
        """Toggle EasyMesh mode through the controller setup page's global enable flag."""
        return await self._async_set_easymesh_global({"enable": bool(enabled)})

    async def async_set_easymesh_wired_backhaul_lock(self, enabled: bool) -> bool:
        return await self._async_set_easymesh_global({"bh_wired_lock": bool(enabled)})

    async def async_set_easymesh_density_control(self, enabled: bool) -> bool:
        return await self._async_set_easymesh_global({
            "density_control": {"enable": bool(enabled)}
        })

    async def async_set_easymesh_density_rssi(self, rssi: int) -> bool:
        rssi = _setting_int({"rssi": rssi}, "rssi", -100, -40)
        return await self._async_set_easymesh_global({"density_control": {"rssi": rssi}})

    async def async_set_easymesh_steering_level(self, level: int) -> bool:
        if not 1 <= int(level) <= 10:
            return False
        return await self._async_set_easymesh_global({"steering_level": int(level)})

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
        self._last_caching_time = 0.0 # 캐시 강제 만료
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
        self._last_caching_time = 0.0 # 캐시 강제 만료
        return bool(response)

    async def async_set_web_geoip_enable(self, enable: bool) -> bool:
        if not self._beta_ui or is_easymesh_agent(self.web_result):
            return False

        response = await self._async_service_json("geoip/enable", enable)
        if response.get("error"):
            _LOGGER.warning(f"GeoIP 제어 실패: {response.get('error')}")
            return False
        self._last_caching_time = 0.0 # 캐시 강제 만료
        return bool(response)

    async def async_set_web_geoip_policy(self, policy: str) -> bool:
        if not self._beta_ui or is_easymesh_agent(self.web_result):
            return False

        response = await self._async_service_json("geoip/policy/set", {"policy": policy})
        if response.get("error"):
            _LOGGER.warning(f"GeoIP policy 제어 실패: {response.get('error')}")
            return False
        self._last_caching_time = 0.0 # 캐시 강제 만료
        return bool(response)

    # Summary: Preserve the current remote-management port when changing access.
    # Related files: switch.py, tests/test_settings.py.
    async def async_set_web_accesslist_enable(self, enable: bool) -> bool:
        if not self._beta_ui:
            return False
        async with self._settings_lock:
            rows = await self._async_read_setting("acl/config", list)
            matches = [row for row in rows if isinstance(row, dict) and row.get("ntag") == "wan1"]
            if len(matches) != 1 or not isinstance(matches[0].get("open"), dict):
                raise HomeAssistantError("Remote management settings are missing or ambiguous")
            port = _setting_int(matches[0]["open"], "port", 1, 65535)
            return await self._async_write_setting(
                "acl/config", {"ntag": "wan1", "open": {"flag": bool(enable), "port": port}}
            )

    # Summary: Preserve the router's ARP packet threshold when toggling protection.
    # Related files: switch.py, tests/test_settings.py.
    async def async_set_security_switch(self, key: str, value: bool) -> bool:
        if not self._beta_ui:
            return False
        if key == "arp_virus":
            async with self._settings_lock:
                config = await self._async_read_setting("dos/config")
                arp = config.get("arp_virus")
                if not isinstance(arp, dict):
                    raise HomeAssistantError("ARP protection settings are missing")
                pps = _setting_int(arp, "pps", 0)
                return await self._async_write_setting(
                    "dos/config", {"arp_virus": {"run": bool(value), "pps": pps}}
                )
        if key == "csrf":
            params = {"csrf": {"run": bool(value)}}
        elif key in ("syn_flood", "smurf", "ip_source_routing", "ip_spoofing", "inbound_ping", "outbound_ping"):
            params = {key: bool(value)}
        else:
            return False
        return await self._async_write_setting("dos/config", params)

    # Summary: Preserve router-provided LED times when only changing the mode.
    # Related files: select.py, tests/test_settings.py.
    async def async_set_web_led_config(
        self, mode: str, on_time: int | None = None, off_time: int | None = None
    ) -> bool:
        if not self._beta_ui:
            return False
        if mode not in ("on", "off", "schedule"):
            raise HomeAssistantError("Invalid Night LED mode")
        async with self._settings_lock:
            current = dict(await self._async_read_setting("led/config"))
            if on_time is not None:
                current["on"] = on_time
            if off_time is not None:
                current["off"] = off_time
            params = {
                "mode": mode, "on": _setting_int(current, "on", 0, 23),
                "off": _setting_int(current, "off", 0, 23), "commit": True,
            }
            return await self._async_write_setting("led/config", params)

    async def async_set_web_upnp_enable(self, enable: bool) -> bool:
        # UPnP 설정 (연결될 파일: switch.py)
        if not self._beta_ui:
            return False
        response = await self._async_service_json("upnp/config", bool(enable))
        if not response.get("error"):
            self._last_caching_time = 0.0 # 캐시 강제 만료
            return True
        return False

    # Summary: Change only requested schedule fields, retaining fresh router values.
    # Related files: switch.py, select.py, tests/test_settings.py.
    async def async_set_web_reboot_timer(
        self, run: bool | None, hour: int | None = None,
        min_time: int | None = None, days: List[str] | None = None,
    ) -> bool:
        if not self._beta_ui:
            return False
        async with self._settings_lock:
            current = dict(await self._async_read_setting("reboot/timer"))
            for key, value in (("run", run), ("hour", hour), ("min", min_time), ("days", days)):
                if value is not None:
                    current[key] = value
            params = {
                "run": _setting_bool(current, "run"),
                "hour": _setting_int(current, "hour", 0, 23),
                "min": _setting_int(current, "min", 0, 59),
                "days": _setting_days(current),
            }
            return await self._async_write_setting("reboot/timer", params)

    # Summary: Retain the router's WAN detection interval when toggling reconnection.
    # Related files: switch.py, tests/test_settings.py.
    async def async_set_web_wan_heartbeat(self, run: bool, interval: int | None = None) -> bool:
        if not self._beta_ui:
            return False
        async with self._settings_lock:
            current = dict(await self._async_read_setting("wan/heartbeat"))
            if interval is not None:
                current["interval"] = interval
            return await self._async_write_setting(
                "wan/heartbeat", {"run": bool(run), "interval": _setting_int(current, "interval", 0)}
            )

    # Summary: Bound legacy login attempts and classify rejected credentials.
    # Related files: config_flow.py, coordinator.py.
    async def login(self) -> bool:
        for urn in (LOGIN_NEW_URN, LOGIN_URN):
            if await self._async_legacy_login(urn):
                return True
        raise RouterConnectionError("Legacy login response was not recognized")

    async def _async_legacy_login(self, urn: str) -> bool:
        data = {"username": self._user_id, "passwd": self._user_pw}
        if urn == LOGIN_NEW_URN:
            data.update(tmenu="main", smenu="main")
        try:
            session = await self._async_get_session()
            async with session.post(self._url + urn, data=data, allow_redirects=True) as response:
                if response.status in (404, 405):
                    return False
                if response.status in (401, 403):
                    self._reject_auth()
                response.raise_for_status()
                text = await response.text()
                if self._capture_session(response, text):
                    return True
                if re.search(
                    r"login[_ -]?(?:fail|error)|invalid.*(?:password|credential)|"
                    r"incorrect.*(?:password|credential)|name=[\"']?passwd|"
                    r"일치하지|잘못된|로그인.*실패|captcha|locked",
                    text, re.IGNORECASE,
                ):
                    self._reject_auth()
                return False
        except (aiohttp.ClientError, TimeoutError):
            self._defer_retry()
            raise

    async def m_login(self) -> bool:
        if await self._async_legacy_login(M_LOGIN_URN):
            return True
        raise RouterConnectionError("Mobile login response was not recognized")

    async def session_update_beta_ui(self) -> None:
        """Extend sessions through the shared authentication boundary."""
        await self._async_service_json("session/update")

    # Summary: Reject invalid credentials once without logging credentials or sessions.
    # Related files: config_flow.py, coordinator.py.
    async def login_beta_ui(self) -> bool:
        data = {"method": "session/login", "params": {"id": self._user_id, "pw": self._user_pw}}
        try:
            session = await self._async_get_session()
            async with session.post(
                self._url + BETA_SERVICE_URN, json=data, headers=self.headers.copy()
            ) as response:
                if response.status in (401, 403):
                    self._reject_auth()
                response.raise_for_status()
                try:
                    result = loads(await response.text())
                except (ValueError, TypeError) as err:
                    raise RouterConnectionError("Invalid login response") from err
                if not isinstance(result, dict) or not result:
                    raise RouterConnectionError("Empty login response")
                if result.get("result") == "done":
                    if self._capture_session(response):
                        return True
                    raise RouterConnectionError("Login response did not provide a session")
                error = result.get("error")
                if (isinstance(error, dict) and error.get("code") != -32601) or result.get("result") in (
                    False, "fail", "failed", "denied", "invalid"
                ):
                    self._reject_auth()
                raise RouterConnectionError("Login response was not recognized")
        except (aiohttp.ClientError, TimeoutError):
            self._defer_retry()
            raise

    async def verify_beta_ui(self) -> bool:
        """Do not attempt legacy logins when UI detection fails over the network."""
        urn = BETA_UI_URN if BETA_UI_URN.startswith("/") else f"/{BETA_UI_URN}"
        try:
            session = await self._async_get_session()
            async with session.get(f"{self._url}{urn}flutter_bootstrap.js", timeout=3) as response:
                if response.status in (404, 405):
                    return False
                response.raise_for_status()
                return response.status == 200
        except (aiohttp.ClientError, TimeoutError):
            self._defer_retry()
            raise

    async def verify_mobile(self) -> bool:
        text = await self._async_request("GET", f"{self._url}{HOSTINFO_URN}")
        self._ismobile = "iux" in text if text else False
        return True

    async def check_mesh(self) -> bool:
        text = await self._async_request("GET", f"{self._url}{MESH_URN}")
        if not text:
            return self._ismesh
        mode_match = re.search(r'<input\b[^>]*id=["\']mode_none["\'][^>]*>', text or "", flags=re.IGNORECASE | re.DOTALL)
        if not mode_match:
            return self._ismesh
        self._ismesh = bool(mode_match and "checked" not in mode_match.group(0).lower())
        return self._ismesh

    async def m_check_mesh(self) -> bool:
        text = await self._async_request("GET", f"{self._url}{M_MESH_URN}")
        if not text:
            return self._ismesh
        try:
            res_json = loads(text)
            if isinstance(res_json, dict):
                self._ismesh = "easymesh" in res_json
        except Exception:
            pass
        return self._ismesh

    async def beta_ui_check_mesh(self) -> bool:
        response = await self._async_service_json("easymesh/info")
        result = response.get("result")
        if isinstance(result, dict) and "active" in result:
            self._ismesh = bool(result["active"])
        return self._ismesh

    async def wlan_check(self, rssi_limit: int = DEFAULT_RSSI_LIMIT) -> Dict:
        result_dict = {"session": True}
        for band, urn in [("2.4GHz", WLAN_2G_URN), ("5GHz", WLAN_5G_URN)]:
            text = await self._async_request("GET", self._url + urn)
            result_dict.update(self.device_parsing(_extract_table_rows(text), band))
        if self._ismesh: result_dict.update(await self.get_mesh_station(rssi_limit=rssi_limit))
        return result_dict

    async def m_wlan_check(self, rssi_limit: int = DEFAULT_RSSI_LIMIT) -> Dict:
        result_dict = {"session": True}
        for band, urn in [("2.4GHz", M_WLAN_2G_URN), ("5GHz", M_WLAN_5G_URN)]:
            text = await self._async_request("GET", self._url + urn)
            try: result_dict.update(self.json_parsing(loads(text), band))
            except Exception: continue
        if self._ismesh: result_dict.update(await self.get_mesh_station(rssi_limit=rssi_limit))
        return result_dict

    async def beta_ui_wlan_check(self, rssi_limit: int = DEFAULT_RSSI_LIMIT) -> Dict:
        """Preserve authentication failures instead of treating them as empty device lists."""
        response = await self._async_service_json("network/interface/lan/stations")
        devices = response.get("result")
        if not isinstance(devices, list):
            self._defer_retry()
            raise RouterConnectionError("Router client list response was not a list")
        result = self.beta_ui_device_parsing(devices)
        if self._ismesh:
            result.update(await self.get_mesh_station(rssi_limit=rssi_limit))
        result["session"] = True
        return result

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

    async def get_mesh_station(self, rssi_limit: int = DEFAULT_RSSI_LIMIT) -> Dict:
        """EasyMesh 기기 목록 조회 및 파싱 (예외 격리 및 RSSI 임계값 유기적 조절)."""
        text = await self._async_request("GET", f"{self._url}{MESH_STATION_URN}")
        res = {}
        
        try:
            data = loads(text)
            stations = data.get("station", [])
        except Exception as err:
            _LOGGER.debug(f"Failed to parse EasyMesh topology JSON: {err}")
            return res

        for s in stations:
            try:
                if not isinstance(s, dict):
                    continue
                mac = s.get("mac")
                if not mac:
                    continue
                mac = mac.strip().replace(":", "").replace("-", "").lower()
                
                # 'Unknown' 혹은 'WIRED' 연결 타입은 필터링 (무선 기기만 추적 대상)
                connection = str(s.get("connection") or "").strip()
                if connection in ["Unknown", "WIRED"]:
                    continue

                # 경과 시간(stay_time) 안전 계산
                try:
                    timestamp = int(s.get("timestamp", 0) or 0)
                    connected_ts = int(s.get("connected_ts", 0) or 0)
                    td_seconds = max(0, timestamp - connected_ts)
                    td = timedelta(seconds=td_seconds)
                except (ValueError, TypeError):
                    td = timedelta(seconds=0)

                stay_time_str = f"{td.days}일 {td.seconds//3600}시간 {(td.seconds//60)%60}분 {td.seconds%60}초"

                # RSSI 안전 파싱
                rssi_val = s.get("rssi")
                rssi_int = 0
                if rssi_val is not None:
                    try:
                        rssi_int = int(rssi_val)
                    except (ValueError, TypeError):
                        rssi_int = 0

                # RSSI 한계값(rssi_limit)과 대조하여 재실 여부 판정
                # 만약 사용자가 RSSI 차단을 끄고 싶다면 설정에서 -100 등의 값을 입력하면 됩니다.
                state = "home" if rssi_val is None or rssi_int >= rssi_limit else "not_home"
                
                res[mac] = {
                    "ip": s.get("ip", "N/A"),
                    "band": s.get("mode", "Unknown"),
                    "stay_time": stay_time_str,
                    "rssi": rssi_int if rssi_val is not None else None,
                    "state": state
                }
            except Exception as err:
                _LOGGER.debug(f"Error parsing EasyMesh station {s.get('mac', 'unknown')}: {err}")
                
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
            except (ConfigEntryAuthFailed, aiohttp.ClientError, TimeoutError):
                raise
            except Exception as err:
                _LOGGER.debug(f"JSON-RPC 재부팅 시도 실패: {err}")

        url = f"{self._url}/sess-bin/timepro.cgi?tmenu=sysconf&smenu=reboot&act=reboot"
        try:
            await self._async_request("GET", url)
            _LOGGER.info("공유기 재부팅 명령 전송 (Web CGI)")
            return True
        except (ConfigEntryAuthFailed, aiohttp.ClientError, TimeoutError):
            raise
        except Exception as err: 
            _LOGGER.debug(f"Web CGI 재부팅 시도 실패: {err}")
            return False



    # Summary: Preserve the actual WireGuard address, port and NAT setting on toggles.
    # Related files: switch.py, tests/test_settings.py.
    async def async_set_web_wg_server_run(self, run: bool) -> bool:
        if not self._beta_ui or is_easymesh_agent(self.web_result):
            return False
        async with self._settings_lock:
            current = await self._async_read_setting("wg/server/show")
            address = current.get("address")
            if not isinstance(address, str) or not address:
                raise HomeAssistantError("The router did not provide its WireGuard address")
            try:
                ip_interface(address)
            except ValueError as err:
                raise HomeAssistantError("The router returned an invalid WireGuard address") from err
            params = {
                "active": bool(run), "address": address,
                "port": _setting_int(current, "port", 1, 65535),
                "nat": _setting_bool(current, "nat"), "commit": True,
            }
            return await self._async_write_setting("wg/server/set", params)

    async def async_set_web_portforward_enable(self, enable: bool) -> bool:
        """포트포워딩 기능의 활성화 상태를 제어한다. (연결될 파일: switch.py)"""
        # 요약: 포트포워딩의 활성화 여부를 true/false로 제어한다.
        # 연결 파일: switch.py
        if not self._beta_ui:
            return False
        response = await self._async_service_json("portforward/config", {"enable": bool(enable)})
        if not response.get("error"):
            self._last_caching_time = 0.0 # 캐시 강제 만료
            return True
        return False

    # Summary: Read and toggle DNS security settings while preserving the router configuration.
    # Related files: switch.py.
    async def _async_read_dns_security(self, method: str) -> dict[str, Any] | None:
        response = await self._async_service_json(f"{method}/get")
        config = response.get("result") if response.get("error") is None else None
        if method == "network/dns/redirect" and isinstance(config, dict):
            config = config.get("config")
        if isinstance(config, dict) and isinstance(config.get("enable"), bool):
            self.web_result[method] = config["enable"]
            return config
        self.web_result.pop(method, None)
        return None

    async def async_set_dns_security(self, method: str, enabled: bool) -> bool:
        async with self._dns_security_lock:
            config = await self._async_read_dns_security(method)
            if config is None:
                return False
            if config["enable"] == enabled:
                return True
            response = await self._async_service_json(
                f"{method}/set", {**config, "enable": enabled}
            )
            applied = await self._async_read_dns_security(method)
            return (
                response.get("error") is None
                and response.get("result") is not None
                and applied is not None
                and applied["enable"] == enabled
            )

    async def async_set_web_upnp_relay_enable(self, enable: bool) -> bool:
        """UPnP 포트포워드 릴레이 기능의 활성화 상태를 제어한다. (연결될 파일: switch.py)"""
        # 요약: UPnP 릴레이 기능을 단일 bool 값으로 제어한다.
        # 연결 파일: switch.py
        if not self._beta_ui:
            return False
        response = await self._async_service_json("upnp/relay", bool(enable))
        if not response.get("error"):
            self._last_caching_time = 0.0 # 캐시 강제 만료
            return True
        return False

    async def async_set_web_nat_config(self, enable: bool) -> bool:
        """인터넷 연결 유지(NAT) 설정을 제어한다. (연결될 파일: switch.py)"""
        # 요약: 인터넷 연결 유지(NAT) 설정의 활성화 여부를 제어한다.
        # 연결 파일: switch.py
        if not self._beta_ui:
            return False
        response = await self._async_service_json("nat/config", bool(enable))
        if not response.get("error"):
            self._last_caching_time = 0.0 # 캐시 강제 만료
            return True
        return False

    async def async_get_wireless_channel_list(self, band: str) -> List[str]:
        """특정 무선 대역(band)에서 지원하는 채널 목록을 조회한다. (연결될 파일: select.py)"""
        if not self._beta_ui:
            return ["auto"]
        
        # 1차 시도: 단일 문자열 "2g", "5g" 등으로 전달
        response = await self._async_service_json("wireless/channel/list", band)
        
        # 2차 시도: 만약 에러가 나거나 리스트가 안 오면 딕셔너리로 {"band": band} 전달
        if response.get("error") or not isinstance(response.get("result"), list):
            response = await self._async_service_json("wireless/channel/list", {"band": band})
            
        result = response.get("result")
        if isinstance(result, list):
            channels = []
            for ch in result:
                if isinstance(ch, dict):
                    ch_val = ch.get("channel") or ch.get("value")
                    if ch_val is not None:
                        channels.append(str(ch_val))
                else:
                    channels.append(str(ch))
            
            # "auto" 혹은 "0" 정규화 및 수동 주입
            clean_channels = []
            for c in channels:
                if c in ("0", "0.0", "auto", "Auto", "AUTO"):
                    if "auto" not in clean_channels:
                        clean_channels.append("auto")
                else:
                    # 채널 본딩 정보 매핑 (예: 149.155 -> 149 (80MHz))
                    norm_c = channel_option_value(c)
                    if norm_c not in clean_channels:
                        clean_channels.append(norm_c)
            
            if "auto" not in clean_channels:
                clean_channels.insert(0, "auto")
            return clean_channels
        return ["auto"]

    # Summary: Preserve the current radio enable state when changing its channel.
    # Related files: select.py, tests/test_settings.py.
    async def async_set_wireless_channel(self, band: str, channel: str) -> bool:
        if not self._beta_ui:
            return False
        async with self._settings_lock:
            current = {}
            for method in ("wireless/band/show", "wireless/band/info"):
                rows = await self._async_read_setting(method, list)
                matches = [
                    row for row in rows if isinstance(row, dict)
                    and str(row.get("band")).lower() == str(band).lower()
                ]
                if len(matches) > 1:
                    raise HomeAssistantError("The router returned ambiguous wireless band settings")
                if matches:
                    current.update(matches[0])
            params = {
                "band": band, "channel": channel,
                "enable": _setting_bool(current, "enable"), "commit": True,
            }
            return await self._async_write_setting("wireless/band/set", params)






