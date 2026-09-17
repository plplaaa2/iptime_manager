# ipTIME Manager Web API Reference



이 문서는 현재까지 확인한 `beta UI` 웹 API 정보를 정리한 참고용 파일이다.



## 공통 사항



- 베타 UI 기반 호출은 `POST /cgi/service.cgi`를 사용한다.

- 본 통합에서는 `web_result`에 웹 API 결과를 저장한다.

- `SNMP 사용`이 켜져 있어도 웹 데이터는 함께 수집한다.

- 일부 API는 라우터 모델과 펌웨어 버전에 따라 이름이 달라질 수 있다.



## 확인된 엔드포인트



### 세션



- `session/login`

  - 로그인에 사용한다.

- `session/update`

  - 세션 연장에 사용한다.



### 시스템 정보



- `firmware/info`

  - 현재 펌웨어 정보.

- `firmware/version/latest`

  - 최신 펌웨어 버전 확인.



### 네트워크 정보



- `network/interface/lan/info`

  - LAN 상태, IP, MAC, connected period

- `network/interface/wan1/info`

  - WAN 상태, IP, MAC, connected period

- `network/dns/info`

  - DNS 서버 목록

- `port/link/status`

  - 포트 링크 상태

- 외부 HTTPS 연결 확인

  - Home Assistant에서 실제 인터넷 도달성을 5초 주기로 확인한다.
  - WAN 링크와 IP가 유지되어도 외부 연결이 실패하면 인터넷 연결 바이너리 센서가 꺼진다.



### 무선 정보



- `wireless/info`, `wireless/band/info`, `wireless/bss/show`, `wireless/client/show`

- `wireless/band/set`, `wireless/bss/set`

  - 무선 밴드 및 개별 SSID(BSS) 제어



### 보안 설정



- `geoip/get`, `geoip/policy/set`, `geoip/enable`, `geoip/blocked/pcount`

  - 국가별 접속 제한 제어 및 통계

- `dos/config` (AX 시리즈)

  - 각종 보안 스위치 상태 및 설정 (`csrf`, `arp_virus`, `syn_flood`, `smurf`, `inbound_ping` 등)

  - `Get`: `{"method": "dos/config"}`

  - `Set`: `{"method": "dos/config", "params": {"key": value}}`

- `acl/config` (AX 시리즈)

  - 원격 관리 및 접속 제어 (Access List)

  - `Get`: `{"method": "acl/config"}`

  - `Set`: `{"method": "acl/config", "params": {"ntag": "wan1", "open": {"flag": bool, "port": int}}}`

  - `wan1` 항목의 `open.flag`가 "외부 접속 보안 사용(원격 관리)" 여부임.

- `accesslist/get`

  - 구형 모델용 Access List 상태 조회



### 기타 시스템 설정 (sysmisc)



- `led/config`

  - 나이트 LED모드 설정 및 조회

  - `Get`: `{"method": "led/config"}`

  - `Set`: `{"method": "led/config", "params": {"mode": "off" | "on" | "interval", "on": int, "off": int}}`

  - `mode` 값: `off` (비활성화), `on` (항상 꺼짐), `interval` (시간 설정)

  - `on`과 `off`는 분 단위 시간 (예: 22:00 -> 1320, 08:00 -> 480)

- `upnp/config`

  - UPnP 활성화/비활성화

  - `Get`: `{"method": "upnp/config"}`

  - `Set`: `{"method": "upnp/config", "params": bool}`

- `reboot/timer`

  - 공유기 자동 재시작 스케줄 설정

  - `Get`: `{"method": "reboot/timer"}`

  - `Set`: `{"method": "reboot/timer", "params": {"run": bool, "hour": int, "min": int, "days": List[str]}}`

- `nat/config`

  - 인터넷 연결 유지 설정

  - `Get`: `{"method": "nat/config"}`

  - `Set`: `{"method": "nat/config", "params": bool}`

- `wan/heartbeat`

  - WAN포트 끊김 시 재연결 설정

  - `Get`: `{"method": "wan/heartbeat"}`

  - `Set`: `{"method": "wan/heartbeat", "params": {"run": bool, "interval": int}}`

- `reboot/now`

  - 공유기 즉시 재시작

  - `Set`: `{"method": "reboot/now"}`

- `iptv/config` (읽기 전용)

  - IPTV 설정 정보 및 지정 포트 상태 수집 (조회 전용)

  - `Get`: `{"method": "iptv/config"}`

- `iptv/mode` (제어용)

  - IPTV 모드 변경 제어 (에러 없는 즉각 반영 가능)

  - `Set`: `{"method": "iptv/mode", "params": {"mode": "off" | "private" | "public" | "macvlan"}}`

  - 성공 응답 시 해당 공유기 모델이 지원하는 실제 IPTV 모드 프로필과 재부팅(Reboot) 필요 여부 리스트를 반환함.

- `iptv/public/port` (제어용)

  - IPTV 공인 IP 지정 LAN 포트 할당 제어

  - `Set`: `{"method": "iptv/public/port", "params": {"port": int}}`

- `wg/server/show`, `wg/server/set`, `wg/server/clear`

  - WireGuard VPN 서버 상태 조회, 설정 및 초기화

  - `Get`: `{"method": "wg/server/show"}`

  - `Set`: `{"method": "wg/server/set", "params": {"run": bool, "ip": str, "subnet": str, "port": int, "nat": bool}}`

  - `Clear`: `{"method": "wg/server/clear"}`

- `wg/peer/show`, `wg/peer/add`, `wg/peer/change`, `wg/peer/del`

  - WireGuard VPN Peer(사용자 기기) 제어 API

- `wg/client/show`, `wg/client/add`, `wg/client/change`, `wg/client/del`

  - WireGuard VPN Client 설정 API

- `vpncli/connect`, `vpncli/disconnect`, `vpncli/server/set`, `vpncli/status/list`

  - VPN 클라이언트 연결 제어 및 조회 API



## 현재 코드 매핑



- `api.py`: 웹 API 호출과 결과 저장 담당, DoS/Access List/sysmisc/IPTV/WireGuard 제어 기능 보강

  - `coordinator.py`: 웹 데이터와 실제 인터넷 연결 상태를 엔티티에 전달

- `select.py`: GeoIP 정책, 나이트 LED모드, 자동 재부팅 요일 및 IPTV 모드 셀렉터 제공

- `switch.py`: Wi-Fi BSS 토글, 원격 관리, DoS 보안 8종 스위치, sysmisc 스위치 3종(UPnP, Auto Reboot, WAN Reconnect), 신형 고급 스위치 3종(Port Forwarding, UPnP Relay, Traffic Triage) 및 WireGuard 서버 활성화 스위치 제어

- `button.py`: 공유기 즉시 재시작 버튼 제공 (베타 UI일 경우 `reboot/now` JSON-RPC 연동)



## 메모



- `ui/accesslist`의 데이터는 `acl/config`와 `dos/config` 메서드로 나누어 관리된다.

- AX 시리즈 모델(AX3000Q 등)은 JSON-RPC 기반의 전용 보안 및 시스템 관리 API를 사용한다.

- 재실 센서는 기존처럼 웹 파싱 기반으로 유지된다.

- 즉시 재시작 기능은 안전을 고려하여 구현만 완료하고 기기 작동 테스트는 스킵되었다.

- IPTV 설정 변경 시에는 공인 포트 지정(public) 시에만 공유기가 자체적으로 재부팅을 수반하며, 사설(private) 및 꺼짐(off) 모드는 재부팅 없이 실시간 적용된다.

- **IPTV 모드와 지정 포트 API의 강제 분리 (중요)**:

  - EFM ipTIME 공유기 최신 펌웨어(JSON-RPC 베타 UI)의 IPTV 제어는 기존의 `iptv/config`에 인자를 POST 하던 방식이 완벽하게 거부되며, **`iptv/mode`**(모드 설정)와 **`iptv/public/port`**(공인 포트 할당)로 엄격하게 쪼개져 작동합니다.

  - 모드를 `off` 나 사설 `private` (IGMP Proxy) 모드로 바꿀 때 `port` 필드가 Payload에 섞여 있으면 펌웨어 유효성 예외(`Invalid params`)를 뿜으며 적용이 실패합니다.

  - 따라서 제어 시에는 반드시 `iptv/mode`를 호출하여 모드를 먼저 단독 변경하고, 공인 IP 포트 지정이 필요한 `public` 모드일 때만 순차적으로 `iptv/public/port`를 이중 호출하여 포트를 안전하게 할당해야 합니다.

- **WireGuard VPN 제어 및 설정 적용 (중요)**:

  - `wg/server/set` API 호출 시, 조회(`wg/server/show`)한 딕셔너리를 그대로 인가하면 읽기 전용 필드인 `pubkey`나 비표준 파라미터(`enable`, `commit` 등)들로 인해 펌웨어 유효성 검사 에러(`Invalid parameters`)가 발생하여 제어가 거부됩니다.

  - 따라서 전송 시에는 반드시 오직 필수 5대 필드인 **`run`**, **`ip`**, **`subnet`**, **`port`**, **`nat`** 만을 엄격히 정제 및 필터링하여 전송해야 합니다.

- **WireGuard 서버 실물 API 키 맵핑 (중요)**:

  - 실물 펌웨어의 `wg/server/show` API가 주는 활성화 키는 `run`이 아닌 **`active`**, ip 주소는 `ip`가 아닌 **`address`**이며, `subnet` 필드가 생략되어 들어옵니다.

  - 따라서 수집 코디네이터에 정상 공급하려면 반드시 이 값들을 표준 홈어시스턴트 규격(`run`, `ip`, `subnet`, `port`, `nat`)으로 자동 역가공 및 가상 기본값 매핑 트랜스폼을 처리해주어야 센서 사용 불가 에러를 방지할 수 있습니다.

- **나이트 LED 설정 적용 및 데이터 쿼리 (중요)**:

  - 나이트 LED 기능을 활성화하여 홈어시스턴트에서 제어하려면, 웹 데이터 업데이트 시 반드시 `led/config` 정보를 쿼리하여 `led_config` 필드로 적재해 두어야 합니다.

  - 설정 변경 시에는 `mode`, `on`, `off` 세 가지 매개변수를 담은 JSON-RPC 패킷을 전송하며, 시간은 분 단위 정수(예: 22:00 -> 1320)로 매핑되어 적용됩니다.

- **스마트 캐싱 및 네트워크 오버헤드 최적화 (Smart Caching Engine) (중요)**:

  - 저사양 공유기 하드웨어 부하를 방지하기 위해 매 5초 주기마다 쏟아지던 14번 이상의 JSON-RPC 호출을 70% 이상 감축하였습니다.

  - **평생 캐시:** 기기 고유 모델명(`port_setup` CGI)은 변경되지 않으므로 최초 1회 로딩 시에만 수집하여 영구 저장합니다.

  - **1시간 캐시 (`3600초`):** `firmware/info`, LAN 설정, DNS 서버 정보 등.

  - **5분 캐시 (`300초`):** GeoIP 설정, DoS 설정, Access List 상태, UPnP, Reboot Timer 설정, NAT 링크 유지 설정, IPTV 모드 설정, WireGuard 서버 설정 등.

  - **실시간 조회:** WAN 공인 IP 주소, 유선 포트 케이블 연결 물리 링크 상태, 무선 클라이언트 세부 정보.

  - **즉각 캐시 만료 (Mutation Invalidation):** 홈어시스턴트에서 제어 스위치나 설정을 변경할 때, 즉시 해당 캐시 변수를 비워(`None`) 갱신 시 최신 데이터가 공유기로부터 실시간 반영되도록 동적 캐시 라이프사이클을 보장합니다.

- **자동 재시작(Auto Reboot) 및 나이트 LED 설정 보존 법칙 (중요)**:

  - 스위치 토글 혹은 요일 클릭 등 조작을 가할 때, API의 일시적인 응답 지연으로 인해 설정 정보가 공유기 초기화값(금요일 새벽 4시 / 밤 10시)으로 오염되거나 초기화되는 것을 원천 차단했습니다.

  - 사용자 커스텀 요일 및 시간 정보는 메모리 멤버 변수(`_last_valid_hour`, `_last_valid_days`, `_last_valid_on` 등)에 상시 기억하고 보존하여 제어 명령 시 최우선 복구 적용됩니다.

- **GeoIP 특정 국가 허용(Country Allow)과 락아웃(Lock-out) 예방 (중요)**:

  - GeoIP 보안 설정을 특정 국가 허용(accept) 모드로 설정할 때, 허용 국가 목록(`accept_list`)이 비어 있거나 사용자의 접속 대역인 한국(`kr`)이 누락되면 관리자의 외부 통신이 즉시 차단(락아웃)됩니다.

  - `geoip/policy/set` API 호출 시 지능형 안전 장치를 가동하여, `accept_list`가 비어 있다면 기본값으로 한국(`kr`)을 자동 채워 넣고, 기존 다른 국가 목록이 존재하더라도 한국(`kr`)이 빠져 있다면 자동으로 병합하여 락아웃 사고를 원천 방지합니다.
