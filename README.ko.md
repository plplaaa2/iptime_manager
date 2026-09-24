# Home Assistant용 ipTIME Manager

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.0.8-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

EFM ipTIME 공유기를 로컬 네트워크에서 모니터링하고 제어하는 Home Assistant 통합 구성요소입니다. SNMP 설정 없이 사용할 수 있습니다.

## 주요 기능

- 공유기 정보, 펌웨어 업데이트, WAN IP 및 DNS
- Wi-Fi 켜기·끄기와 채널 선택
- WAN/LAN 연결 속도, 패킷 활동 및 인터넷 연결 상태
- WireGuard 서버 제어와 최근 접속 피어 정보
- EasyMesh 컨트롤러의 유선 백홀 고정, 메시 밀집 구성, RSSI 기준 및 스티어링 설정
- EasyMesh 공유기 모드와 연결된 Agent 수
- 여러 공유기에서 감지되는 선택 기기를 하나의 재실 센서 목록으로 통합
- 보안 설정, GeoIP, 포트포워딩 및 UPnP
- 나이트 LED, 자동 재부팅과 진단 항목의 재부팅 버튼

지원 기능은 공유기 모델과 펌웨어에 따라 다릅니다.

## 설치

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=iptime_manager)

위 링크를 열고 HACS에서 **ipTIME Manager**를 설치한 뒤 Home Assistant를 재시작합니다.

### 수동 설치

`custom_components/iptime_manager` 폴더를 Home Assistant의 `config/custom_components/` 아래에 복사한 뒤 재시작합니다.

## 설정

1. **설정 → 기기 및 서비스 → 통합 구성요소 추가**를 선택합니다.
2. **ipTIME Manager**를 검색합니다.
3. `공유기 추가` 또는 `재실 센서 목록 추가`를 선택합니다.
4. 공유기 추가는 주소와 관리자 계정을 입력합니다. 재실 센서 목록은 등록된 공유기에서 기기를 선택하고 목록 이름을 지정합니다.

재실 목록은 단일 공유기 또는 EasyMesh 컨트롤러가 등록돼 있을 때 만들 수 있습니다. 목록에 선택한 기기는 Agent를 포함해 등록된 모든 공유기에서 감지하며, 하나라도 감지되면 해당 목록 센서가 켜집니다.

공유기 추가 시 공유기 관리 주소(예: `http://192.168.0.1`)를 사용하세요. 별도 관리 포트를 사용한다면 주소에 포트도 포함합니다.

## 상태 확인

- **WAN/LAN Port**는 물리 연결, **WAN/LAN Status**는 최근 통신 활동을 표시합니다. 통신이 없는 기기는 Status가 꺼질 수 있습니다.
- **Internet Status**는 HA에서 외부 접속을 확인하므로 HA가 해당 공유기를 통해 인터넷을 사용하는 구성을 전제로 합니다. 허브/AP 모드에서는 제외되지만, 배선만 바꾼 허브 구성은 자동 판별하지 못할 수 있습니다.
- **WireGuard Last Handshake**는 가장 최근 handshake 시각입니다. 연결 중에도 갱신될 수 있습니다.

버전별 변경 사항은 [변경 이력](custom_components/iptime_manager/CHANGELOG.md)을 참고하세요.

## 문의 및 지원

[GitHub Issues](https://github.com/plplaaa2/iptime_manager/issues)에 공유기 모델, 펌웨어 및 Home Assistant 버전을 함께 알려주세요. 로그를 공유할 때는 인증 정보를 제거하세요.

[Ko-fi로 후원하기](https://ko-fi.com/plplaaa2)

## 라이선스

[MIT](LICENSE)
