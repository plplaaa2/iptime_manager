from __future__ import annotations

import logging
import asyncio
import re
import aiohttp
from typing import Any, Dict, List, Optional, Final
from json import loads
from bs4 import BeautifulSoup
from datetime import timedelta
from .const import *

PYSNMP_ERROR = None
try:
    from pysnmp.hlapi.asyncio import (
        SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
        ObjectType, ObjectIdentity, getCmd, nextCmd, setCmd, Integer32, UsmUserData,
        usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
        usmNoPrivProtocol, usmDESPrivProtocol
    )
    # AES 프로토콜은 버전에 따라 이름이 다를 수 있으므로 별도 처리
    try:
        from pysnmp.hlapi.asyncio import usmAes128PrivProtocol
    except ImportError:
        try:
            from pysnmp.hlapi.asyncio import usmAesCfb128Protocol as usmAes128PrivProtocol
        except ImportError:
            usmAes128PrivProtocol = None
            
    PYSNMP_AVAILABLE = True
except ImportError as err:
    PYSNMP_AVAILABLE = False
    PYSNMP_ERROR = str(err)

# 요약: ipTIME 공유기와의 통신(Web CGI, SNMP)을 담당하는 API 클래스
# 연결될 파일: const.py, coordinator.py

_LOGGER = logging.getLogger(__name__)

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
        self.snmp_result: Dict[str, Any] = {}
        self._snmp_engine = None if not PYSNMP_AVAILABLE else SnmpEngine()
        self._last_snmp_auth = None
        self._last_snmp_transport = None
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
            _LOGGER.error(f"ipTIME Web 데이터 수집 성공: 기기 {len(self.result)-1}대 감지 (최초 MAC: {first_mac})")
        else:
            _LOGGER.error("ipTIME Web 데이터 수집 실패: 로그인 세션은 확보했으나 기기 목록이 비어있습니다.")
        
        # 3. 세션 만료 체크
        if self.result.get("session") is False:
            _LOGGER.debug("세션 만료 감지, 다음 주기에서 재로그인 시도")
            self.efm_session_id = None
            return False
            
        return True

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
                    _LOGGER.error(f"베타 UI 로그인 거부됨: {res_json}")
        except Exception as err:
            _LOGGER.error(f"베타 UI 로그인 예외 발생: {err}")
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
        soup = BeautifulSoup(text, "html.parser")
        mode = soup.find("input", attrs={"id": "mode_none"})
        self._ismesh = mode and "checked" not in mode.attrs
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
            soup = BeautifulSoup(text, "html.parser")
            result_dict.update(self.device_parsing(soup.find_all("tr"), band))
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
            tds = device.find_all("td")
            if len(tds) == 4:
                mac = tds[0].text.strip().replace(":", "").replace("-", "").lower()
                ip_match = re.search(r"\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}", tds[3].text)
                result_dict[mac] = {"ip": ip_match.group() if ip_match else "N/A", "band": band, "stay_time": tds[2].text.strip(), "state": "home"}
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
        """공유기 재부팅 (Web CGI 우선, SNMP 보조)."""
        # 1. Web CGI 방식 시도
        url = f"{self._url}/sess-bin/timepro.cgi?tmenu=sysconf&smenu=reboot&act=reboot"
        try:
            await self._async_request("GET", url)
            _LOGGER.info("공유기 재부팅 명령 전송 (Web CGI)")
            return True
        except Exception: 
            _LOGGER.debug("Web CGI 재부팅 시도 실패")

        # 2. SNMP 방식 시도 (MIB 기반)
        if PYSNMP_AVAILABLE and self._snmp_engine and self._last_snmp_auth and self._last_snmp_transport:
            try:
                _LOGGER.info("공유기 재부팅 명령 시도 (SNMP)")
                await setCmd(
                    self._snmp_engine, self._last_snmp_auth, self._last_snmp_transport, ContextData(),
                    ObjectType(ObjectIdentity(OID_REBOOT_IPTIME), Integer32(1))
                )
                return True
            except Exception: pass
        
        return False

    async def async_get_snmp_data(self, **kwargs) -> bool:
        if not PYSNMP_AVAILABLE:
            _LOGGER.error(f"ipTIME SNMP 수집 실패: pysnmp 라이브러리를 불러올 수 없습니다. (원인: {PYSNMP_ERROR}) manifest.json의 설정을 확인하세요.")
            return False
        _LOGGER.error(f"ipTIME SNMP 라이브러리 로드 확인됨. 버전: {kwargs.get('version', 'v2c')}")
        try:
            if self._snmp_engine is None: self._snmp_engine = SnmpEngine()
            version = kwargs.get("version", "v2c")
            community = kwargs.get("community", "public")
            
            if version == "v3":
                auth_proto_map = {"md5": usmHMACMD5AuthProtocol, "sha": usmHMACSHAAuthProtocol}
                priv_proto_map = {"none": usmNoPrivProtocol, "des": usmDESPrivProtocol, "aes": usmAes128PrivProtocol}
                
                auth_key = kwargs.get("auth_key")
                priv_key = kwargs.get("priv_key")
                # NoPriv인 경우 priv_key를 명시적으로 None 처리
                if not priv_key or kwargs.get("priv_protocol", "none").lower() == "none":
                    priv_key = None

                auth_data = UsmUserData(
                    kwargs.get("username", ""), 
                    authKey=auth_key, 
                    privKey=priv_key,
                    authProtocol=auth_proto_map.get(kwargs.get("auth_protocol", "md5").lower(), usmHMACMD5AuthProtocol),
                    privProtocol=priv_proto_map.get(kwargs.get("priv_protocol", "none").lower(), usmNoPrivProtocol)
                )
            else: 
                auth_data = CommunityData(community, mpModel=0 if version == "v1" else 1)

            port = kwargs.get("port", DEFAULT_SNMP_PORT)
            transport = UdpTransportTarget((self._host, port), timeout=10, retries=2)
            self._last_snmp_auth = auth_data
            self._last_snmp_transport = transport
            
            # 1. 시스템 정보 수집 (Uptime, Model, Version)
            sys_info_oids = [
                (OID_UPTIME, "uptime"),
                (OID_MODEL, "model"),
                (OID_VERSION, "version"),
                (OID_PRIMARY_DNS, "primary_dns"),
                (OID_SECONDARY_DNS, "secondary_dns"),
                (OID_WAN_MAC, "wan_mac"),
                (OID_LAN_MAC, "lan_mac")
            ]
            for oid, key in sys_info_oids:
                try:
                    # 각 OID마다 개별적으로 요청 (타임아웃 적용)
                    _LOGGER.error(f"ipTIME SNMP {key} 요청 시작 (OID: {oid})")
                    
                    # 3.14 호환성을 위해 직접 await 시도
                    iterator = await asyncio.wait_for(
                        getCmd(
                            self._snmp_engine,
                            auth_data,
                            UdpTransportTarget((self._host, port), timeout=2, retries=0),
                            ContextData(),
                            ObjectType(ObjectIdentity(oid))
                        ),
                        timeout=3
                    )
                    _LOGGER.debug(f"ipTIME SNMP {key} 응답 수신 성공")
                    errorIndication, errorStatus, errorIndex, varBinds = iterator
                    if not errorIndication and not errorStatus:
                        val = varBinds[0][1]
                        if key == "uptime": self.snmp_result[key] = int(val)
                        else: self.snmp_result[key] = val.prettyPrint()
                        _LOGGER.debug(f"ipTIME SNMP {key} 수집 성공: {self.snmp_result[key]}")
                    else:
                        _LOGGER.error(f"ipTIME SNMP {key} 수집 실패: {errorIndication or errorStatus}")
                except Exception:
                    _LOGGER.exception(f"ipTIME SNMP {key} 요청 중 예외 발생")

            # 2. 네트워크 인터페이스 정보 수집 (이름/상태: ipTIME MIB, 트래픽: 표준 MIB-II)
            interfaces = {}
            # 2-1. 이름 및 상태 수집 (ipTIME 전용 MIB)
            target_if_prefix = (1, 3, 6, 1, 4, 1, 12874, 1, 2, 2) # 테이블 레벨에서 시작
            current_oid = ObjectType(ObjectIdentity(".1.3.6.1.4.1.12874.1.2.2"))
            prefix_len_if = len(target_if_prefix)
            loop_count = 0
            while loop_count < 100:
                loop_count += 1
                try:
                    iterator = await asyncio.wait_for(
                        nextCmd(self._snmp_engine, auth_data, transport, ContextData(), current_oid),
                        timeout=3
                    )
                    errIndication, errStatus, errIndex, varBindTable = iterator
                except Exception: break
                if errIndication or errStatus or not varBindTable: break
                varBind = varBindTable[0][0]
                oid_obj = varBind[0]
                val = varBind[1]
                
                # 진단용: 처음 몇 개의 데이터는 무조건 출력
                if loop_count <= 5:
                    _LOGGER.warning(f"인터페이스 수집 진단 (Loop {loop_count}): OID={oid_obj}, Val={val.prettyPrint()}")

                if oid_obj.asTuple()[:prefix_len_if] != target_if_prefix: 
                    _LOGGER.warning(f"인터페이스 수집 중단: Prefix 불일치 (OID: {oid_obj})")
                    break
                parts = oid_obj.asTuple()
                if len(parts) >= prefix_len_if + 3: # Entry(1) + Col + Index 구조 확인
                    try:
                        # Entry(1)이 포함된 경우와 아닌 경우 모두 대응
                        if parts[prefix_len_if] == 1:
                            col, idx = parts[prefix_len_if + 1], parts[prefix_len_if + 2]
                        else:
                            col, idx = parts[prefix_len_if], parts[prefix_len_if + 1]
                        if idx not in interfaces: interfaces[idx] = {"name": "", "status": 0}
                        val = varBind[1]
                        if col == 2: 
                            interfaces[idx]["name"] = val.prettyPrint().strip().replace('"', '')
                            _LOGGER.warning(f"인터페이스 이름 확인: Index {idx} -> '{interfaces[idx]['name']}'")
                        elif col == 3:
                            interfaces[idx]["mode"] = int(val)
                        elif col == 4: 
                            interfaces[idx]["status"] = int(val)
                            _LOGGER.warning(f"인터페이스 상태 확인: Index {idx} ('{interfaces[idx].get('name')}') -> {val}")
                    except Exception as e:
                        _LOGGER.debug(f"인터페이스 파싱 중 오류: {e}")
                current_oid = ObjectType(oid_obj)

            # 2-2. 트래픽 정보 수집 (ipTIME MIB에 정의되지 않아 생략)
            # ipTIME MIB 전용 모드이므로 표준 MIB-II 호출을 수행하지 않습니다.
            pass

            # 최종 결과 구성
            final_interfaces = {}
            for idx, v in interfaces.items():
                iface_name = v["name"] if v["name"] else f"Port {idx}"
                final_interfaces[iface_name] = {"status": v["status"], "mode": v.get("mode", 0)}
            
            self.snmp_result["interfaces"] = final_interfaces
            _LOGGER.info(f"ipTIME 네트워크 포트 수집 완료: {len(final_interfaces)}개 포트")

            # 2-3. 추가 시스템 정보 (WAN 상태 등 스칼라 값)
            try:
                # WanStatus (.1.5.5.0) 직접 조회
                iterator = await asyncio.wait_for(
                    getCmd(self._snmp_engine, auth_data, transport, ContextData(), ObjectType(ObjectIdentity(".1.3.6.1.4.1.12874.1.5.5.0"))),
                    timeout=2
                )
                err, _, _, vbs = iterator
                if not err and vbs:
                    self.snmp_result["wan_status_raw"] = int(vbs[0][1])
                    _LOGGER.warning(f"WAN 상태 직접 조회 결과 (.5.5.0): {self.snmp_result['wan_status_raw']}")
            except Exception: pass
            
            # 3. 무선 네트워크(WIFI) 정보 수집 (테이블 워킹 방식으로 통합 수집)
            wifi_list = {}
            target_wifi_prefix = (1, 3, 6, 1, 4, 1, 12874, 1, 4, 2, 1)
            current_oid = ObjectType(ObjectIdentity(".1.3.6.1.4.1.12874.1.4.2.1"))
            prefix_len_wifi = len(target_wifi_prefix)
            loop_count = 0
            while loop_count < 150:
                loop_count += 1
                try:
                    iterator = await asyncio.wait_for(
                        nextCmd(self._snmp_engine, auth_data, transport, ContextData(), current_oid),
                        timeout=3
                    )
                    errIndication, errStatus, errIndex, varBindTable = iterator
                except Exception: break
                if errIndication or errStatus or not varBindTable: break
                varBind = varBindTable[0][0]
                oid_obj = varBind[0]
                if oid_obj.asTuple()[:prefix_len_wifi] != target_wifi_prefix: break
                parts = oid_obj.asTuple()
                if len(parts) >= prefix_len_wifi + 2:
                    try:
                        col, idx = parts[prefix_len_wifi], parts[prefix_len_wifi + 1]
                        if idx not in wifi_list: 
                            wifi_list[idx] = {"ssid": "", "channel": 0, "mode": 0, "security": 0, "broadcast": 1, "protocol": 0, "enable": 1}
                        
                        val = varBind[1]
                        val_str = val.prettyPrint() if val is not None else ""
                        _LOGGER.warning(f"WiFi 상세 데이터 감지: Index {idx}, Col {col} -> {val_str}")
                        
                        if not val_str or val_str == "":
                            current_oid = ObjectType(oid_obj)
                            continue

                        if col == 2: wifi_list[idx]["ssid"] = val_str.strip().replace('"', '')
                        elif col == 3: wifi_list[idx]["broadcast"] = int(val)
                        elif col == 4: wifi_list[idx]["mode"] = int(val)
                        elif col == 5: wifi_list[idx]["security"] = int(val)
                        elif col == 7: wifi_list[idx]["radius_ip"] = val.prettyPrint()
                        elif col == 8: wifi_list[idx]["auth_mode"] = int(val)
                        elif col == 9: wifi_list[idx]["enable"] = int(val)
                        elif col == 10: wifi_list[idx]["channel"] = int(val)
                        elif col == 11: wifi_list[idx]["protocol"] = int(val)
                    except Exception as e:
                        _LOGGER.debug(f"WiFi 파싱 중 오류: {e}")
                
                current_oid = ObjectType(oid_obj)

            # 유효한 SSID만 필터링 (이름이 없거나 비정상적인 데이터 제외)
            filtered_wifi = {
                idx: info for idx, info in wifi_list.items() 
                if info.get("ssid") and len(info["ssid"].strip()) > 0
            }
            self.snmp_result["wifi"] = filtered_wifi
            
            # 3-2. 무선 스칼라 정보 수집 (On/Off 상태 찾기용)
            try:
                target_wl_scalar = (1, 3, 6, 1, 4, 1, 12874, 1, 4, 1)
                current_oid = ObjectType(ObjectIdentity(".1.3.6.1.4.1.12874.1.4.1"))
                for _ in range(10):
                    iterator = await asyncio.wait_for(nextCmd(self._snmp_engine, auth_data, transport, ContextData(), current_oid), timeout=2)
                    err, _, _, vbs = iterator
                    if err or not vbs: break
                    oid_obj = vbs[0][0]
                    if oid_obj.asTuple()[:len(target_wl_scalar)] != target_wl_scalar: break
                    _LOGGER.warning(f"무선 스칼라 데이터 감지 (.4.1): OID={oid_obj}, Val={vbs[0][1].prettyPrint()}")
                    current_oid = ObjectType(oid_obj)
            except Exception: pass

            if not wifi_list:
                _LOGGER.info("ipTIME 무선 네트워크 정보를 찾지 못했습니다. (WiFi 비활성화 또는 지원되지 않는 모델)")
            else:
                _LOGGER.info(f"ipTIME 무선 네트워크 목록 수집 완료: {len(wifi_list)}개 SSID 감지")
            
            return True
        except Exception as err:
            _LOGGER.error(f"SNMP 데이터 수집 오류: {err}")
            return False

    async def async_upgrade_firmware(self) -> bool:
        """SNMP를 통해 펌웨어 자동 업데이트를 지시합니다."""
        if not self._last_snmp_auth or not self._last_snmp_transport or not PYSNMP_AVAILABLE:
            _LOGGER.error("펌웨어 업데이트 실패: SNMP가 아직 초기화되지 않았습니다.")
            return False
            
        try:
            # OID 1.3.6.1.4.1.12874.1.5.6.0 에 0(즉시 업데이트) 전송
            iterator = await asyncio.wait_for(
                setCmd(
                    self._snmp_engine, self._last_snmp_auth, self._last_snmp_transport, ContextData(),
                    ObjectType(ObjectIdentity(".1.3.6.1.4.1.12874.1.5.6.0"), Integer32(0))
                ),
                timeout=5
            )
            errIndication, errStatus, errIndex, varBinds = iterator
            if errIndication or errStatus:
                _LOGGER.error(f"펌웨어 업데이트 명령 전송 실패: {errIndication or errStatus}")
                return False
            _LOGGER.info("펌웨어 업데이트 명령 전송 완료. 기기가 재부팅되며 업데이트를 시작할 수 있습니다.")
            return True
        except Exception as err:
            _LOGGER.error(f"펌웨어 업데이트 명령 전송 중 오류: {err}")
            return False

    async def async_snmp_set(self, oid: str, value: int) -> bool:
        """범용 SNMP Set 명령을 수행합니다."""
        if not self._last_snmp_auth or not self._last_snmp_transport or not PYSNMP_AVAILABLE:
            _LOGGER.error(f"SNMP 제어 실패 (OID: {oid}): SNMP가 초기화되지 않았습니다.")
            return False
            
        try:
            iterator = await asyncio.wait_for(
                setCmd(
                    self._snmp_engine, self._last_snmp_auth, self._last_snmp_transport, ContextData(),
                    ObjectType(ObjectIdentity(oid), Integer32(value))
                ),
                timeout=5
            )
            errIndication, errStatus, errIndex, varBinds = iterator
            if errIndication or errStatus:
                _LOGGER.error(f"SNMP 제어 명령 전송 실패 (OID: {oid}): {errIndication or errStatus}")
                return False
            _LOGGER.info(f"SNMP 제어 명령 전송 성공 (OID: {oid}, Value: {value})")
            return True
        except Exception as err:
            _LOGGER.error(f"SNMP 제어 중 예외 발생 (OID: {oid}): {err}")
            return False
