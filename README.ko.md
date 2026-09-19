# Home Assistant용 ipTIME Manager

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.0.8-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

EFM ipTIME 공유기를 로컬 네트워크를 통해 Home Assistant에서 모니터링하고 제어하는 사용자 지정 통합 구성요소입니다. 공유기의 로컬 웹 API를 사용하며 SNMP 설정이나 외부 클라우드 서비스가 필요하지 않습니다.

## 주요 기능

- 공유기 모델, 펌웨어, 가동 시간, WAN IP 및 네트워크 정보
- Wi-Fi SSID와 대역별 채널 상태 확인 및 제어
- LAN/WAN 물리 연결 상태·링크 속도 및 별도의 패킷 활동 센서
- 라우터 모드에서 외부 HTTPS 응답을 확인하는 Internet Status 센서
- WireGuard 마지막 접속 기기 이름과 마지막 handshake 시각 센서
- 포트포워딩, UPnP 릴레이, WireGuard 서버 제어
- 보안 설정, GeoIP 정책, 나이트 LED, 자동 재부팅 제어
- 선택한 연결 기기의 재실 상태 추적
- WAN, 보안 설정, 물리 포트 상태 변경 이벤트 제공

지원 기능은 공유기 모델과 펌웨어에 따라 다를 수 있습니다.

## 설치

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=iptime_manager)

1. 위 버튼을 누르거나 HACS에서 `ipTIME Manager`를 검색합니다.
2. 통합 구성요소를 설치합니다.
3. Home Assistant를 재시작합니다.

### 수동 설치

저장소의 `custom_components/iptime_manager` 폴더를 Home Assistant의 `config/custom_components/` 아래에 복사한 뒤 Home Assistant를 재시작합니다.

## 설정

1. **설정 → 기기 및 서비스 → 통합 구성요소 추가**를 선택합니다.
2. `ipTIME Manager`를 검색합니다.
3. 공유기 주소와 관리자 계정을 입력합니다.
4. 필요하면 감지 간격과 추적할 기기를 설정합니다.

공유기 주소는 일반적으로 `http://192.168.0.1`입니다. 공유기 웹 관리 화면에서 사용하는 관리자 계정을 입력하세요.

## 제공 엔티티

- `sensor`: 공유기 상태, 펌웨어, WAN IP, DNS, GeoIP, WireGuard 마지막 피어 이름·handshake 시각(진단 항목)
- `binary_sensor`: LAN/WAN 물리 링크, 포트별 통신 활동 및 인터넷 연결 상태
- `switch`: Wi-Fi, 보안, WireGuard, 포트포워딩, UPnP 제어
- `select`: Wi-Fi 채널, GeoIP 정책, 나이트 LED, 자동 재부팅 설정
- `button`: 공유기 재부팅(실수로 누르는 일을 줄이기 위해 진단 항목에 배치)
- `device_tracker`: 선택한 기기의 재실 상태(진단이 아닌 일반 항목)

| 엔티티 | 디바이스 클래스 | 켜짐 / 꺼짐 아이콘 |
| :--- | :--- | :--- |
| WAN Port, LAN 1~4 Port | `connectivity` | `mdi:ethernet` / `mdi:ethernet-off` |
| WAN Status, LAN 1~4 Status | `running` | `mdi:lan-connect` / `mdi:lan-disconnect` |
| Internet Status | `connectivity` | `mdi:web` / `mdi:web-off` |
| WireGuard Last Peer Name | 없음(문자열) | `mdi:account-network` |
| WireGuard Last Handshake | `timestamp` | `mdi:clock-outline` |

## 개발 버전 변경 사항 적용

- 현재 변경은 `dev` 브랜치에 반영되어 있으며, 외부 표기 버전은 1.0.8을 유지합니다. 변경 코드를 설치한 후 HA를 재시작하세요.
- 기존 포트 센서와 인터넷 센서는 고유 ID를 유지하고 이름을 변경합니다. 사용자가 직접 지정한 이름이나 아이콘은 기본 표시보다 우선할 수 있습니다.
- WireGuard Connected Peer Count 엔티티는 자동 정리됩니다. 해당 엔티티를 참조하던 대시보드·자동화는 새 센서에 맞게 수정해야 합니다.
- WireGuard는 `last_handshake`가 가장 작은 피어를 선택하며, 조회 시각에서 경과 초를 빼 마지막 시각을 계산합니다. `0초`도 유효하고 기록이 없으면 `unknown`입니다. 연결 중에도 handshake가 갱신되므로 최초 접속 시각이나 현재 접속 여부를 뜻하지 않습니다.

## 주의사항

- `WAN Port`, `LAN 1 Port`~`LAN 4 Port`는 물리 연결 상태와 링크 속도를 제공합니다.
- 각 포트의 `Status`는 최근 30초 내 수신·송신 패킷이 모두 관측되었는지 표시합니다. 인터넷 정상 여부를 보장하지 않으며, 정상 기기도 통신이 없으면 꺼질 수 있습니다. 속성에는 조회 간 패킷 증가량과 마지막 활동 관측 시각을 제공합니다.
- 연결된 포트의 첫 조회·카운터 초기화·통계 누락은 꺼짐으로 단정하지 않고 `unknown`으로 처리합니다. 통신 활동은 웹 데이터 갱신 주기(최소 5초)에 맞춰 확인합니다.
- `Internet Status`는 NAT와 WAN 사용이 활성화된 경우 제공하며, WAN 포트가 LAN 역할이거나 NAT/WAN이 비활성화된 허브/AP 설정에서는 제거하고 외부 검사를 중단합니다. 모드 설정은 약 5분마다 확인합니다. NAT/WAN 설정을 그대로 두고 LAN 배선만 바꾼 구성은 자동 구분하지 못할 수 있습니다.
- 인터넷 검사는 HA에서 외부 HTTPS 응답을 확인하므로 HA가 해당 공유기를 통해 인터넷을 사용하는 구성을 전제로 합니다.
- 라우터 모드에서 인터넷만 끊기면 Internet Status는 유지되며 꺼짐으로 표시합니다. 허브/AP 모드 변경이 확인되면 통합을 다시 로드하여 센서 구성을 반영합니다.

- 제공되는 엔티티와 설정은 ipTIME 모델 및 펌웨어에 따라 달라집니다.
- 공유기 설정을 변경하면 네트워크 연결이 일시적으로 끊길 수 있습니다.
- IPTV 모드, NAT/Keep Connection, EasyMesh 운영 모드 제어는 공유기 재부팅을 유발할 수 있어 의도적으로 제공하지 않습니다.
- 외부 원격 관리와 보안 설정은 신중하게 변경하세요.

## 문제 신고

문제를 신고할 때는 공유기 모델, 펌웨어 버전, Home Assistant 버전과 관련 로그를 함께 제공해 주세요. 게시 전에 비밀번호, 토큰 등 민감한 정보를 제거해야 합니다.

[GitHub Issues에 문제 신고](https://github.com/plplaaa2/iptime_manager/issues)

## 라이선스

MIT License
