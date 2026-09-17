# Home Assistant용 ipTIME Manager

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.0.8-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

EFM ipTIME 공유기를 로컬 네트워크를 통해 Home Assistant에서 모니터링하고 제어하는 사용자 지정 통합 구성요소입니다. 공유기의 로컬 웹 API를 사용하며 SNMP 설정이나 외부 클라우드 서비스가 필요하지 않습니다.

## 주요 기능

- 공유기 모델, 펌웨어, 가동 시간, WAN IP 및 네트워크 정보
- Wi-Fi SSID와 대역별 채널 상태 확인 및 제어
- LAN/WAN 포트 연결 상태와 링크 속도 센서
- 외부 HTTPS 연결을 기준으로 한 실제 인터넷 연결 상태 바이너리 센서
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

- `sensor`: 공유기 상태, 펌웨어, WAN IP, DNS, GeoIP 정보
- `binary_sensor`: LAN/WAN 물리 링크 및 실제 인터넷 연결 상태
- `switch`: Wi-Fi, 보안, WireGuard, 포트포워딩, UPnP 제어
- `select`: Wi-Fi 채널, GeoIP 정책, 나이트 LED, 자동 재부팅 설정
- `button`: 공유기 재부팅
- `device_tracker`: 선택한 기기의 재실 상태

## 주의사항

- 제공되는 엔티티와 설정은 ipTIME 모델 및 펌웨어에 따라 달라집니다.
- 공유기 설정을 변경하면 네트워크 연결이 일시적으로 끊길 수 있습니다.
- IPTV 모드, NAT/Keep Connection, EasyMesh 운영 모드 제어는 공유기 재부팅을 유발할 수 있어 의도적으로 제공하지 않습니다.
- 외부 원격 관리와 보안 설정은 신중하게 변경하세요.

## 문제 신고

문제를 신고할 때는 공유기 모델, 펌웨어 버전, Home Assistant 버전과 관련 로그를 함께 제공해 주세요. 게시 전에 비밀번호, 토큰 등 민감한 정보를 제거해야 합니다.

[GitHub Issues에 문제 신고](https://github.com/plplaaa2/iptime_manager/issues)

## 라이선스

MIT License
