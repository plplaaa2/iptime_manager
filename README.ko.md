# Home Assistant용 ipTIME Manager

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.1.0-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

EFM ipTIME 공유기를 로컬 네트워크에서 모니터링하고 제어하는 Home Assistant 통합 구성요소입니다. SNMP 설정 없이 사용할 수 있습니다.

## 주요 기능

- 공유기 정보, 펌웨어 업데이트, WAN IP 및 DNS
- Wi-Fi 켜기·끄기와 채널 선택
- WAN/LAN 연결 속도, 패킷 활동 및 인터넷 연결 상태
- WireGuard 서버 제어와 최근 접속 피어 정보
- EasyMesh 컨트롤러의 유선 백홀 고정, 메시 밀집 구성, RSSI 기준 및 스티어링 설정
- EasyMesh 공유기 모드와 연결된 Agent 수
- 선택한 기기마다 재실 추적기(device_tracker)를 만들고 `Home Presence` 기기 아래에 모아 표시
- 보안 설정, GeoIP, 포트포워딩 및 UPnP
- Beta UI 공유기의 DHCP 수동 IP 할당·포트 포워딩 규칙 조회·추가·수정·삭제 액션
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
4. 공유기는 주소와 관리자 계정을 입력합니다. 공유기가 아직 없다면 먼저 빈 재실 센서 목록을 만들고, 공유기를 등록한 뒤 옵션에서 기기를 선택해 센서 이름을 설정할 수 있습니다.

새 기기를 재실 센서로 등록하려면 단일 공유기 또는 EasyMesh 컨트롤러가 필요합니다. Home Presence 목록 자체는 공유기 없이 먼저 만들 수 있으며, 공유기 등록 후 옵션에서 감지할 기기를 추가하면 됩니다. 선택한 기기는 Agent를 포함해 등록된 모든 공유기에서 감지하며, 기기별 추적기는 해당 기기가 감지되면 `home`, 감지되지 않으면 `not_home` 상태가 됩니다. 추적기들은 `Home Presence` 기기 아래에 표시됩니다.

공유기 추가 시 공유기 관리 주소(예: `http://192.168.0.1`)를 사용하세요. 별도 관리 포트를 사용한다면 주소에 포트도 포함합니다.

## 상태 확인

### 포트 포워딩 액션

Beta UI 공유기에서 다음 액션을 사용할 수 있습니다.

- `iptime_manager.get_port_forward_rules`: 수동 규칙(`rules`)과 UPnP 규칙(`upnp_rules`) 조회.
- `iptime_manager.add_port_forward_rule`: 규칙 추가.
- `iptime_manager.update_port_forward_rule`: 기존 규칙 이름(`name`)으로 수정. 생략한 값은 유지하며 `new_name`으로 이름을 바꿀 수 있습니다.
- `iptime_manager.delete_port_forward_rule`: 기존 규칙 이름(`name`)으로 삭제.

모든 액션에서 `config_entry_id`로 공유기를 선택합니다. 활성 규칙 추가 시 이름, 프로토콜(`tcp`/`udp`/`tcpudp`),
내부 IP와 외부·내부 시작 포트가 필요합니다. 종료 포트는 선택 사항이며 시작 포트만 새로 입력하면 단일 포트입니다.
범위 지정 시 외부·내부 포트 개수가 같아야 합니다. 규칙별 설명 필드는 공유기 API에 없으며 규칙 이름으로 구분합니다.

```yaml
- action: iptime_manager.add_port_forward_rule
  data:
    config_entry_id: YOUR_ROUTER_CONFIG_ENTRY_ID
    name: Web server
    protocol: tcp
    internal_ip: 192.168.0.50
    external_port_start: 8080
    internal_port_start: 80
```

조회 액션에는 `response_variable`을 지정하세요. 변경 액션도 선택적으로 결과 목록을 응답으로 받을 수 있습니다.
이름 중복, LAN 주소, 같은 프로토콜의 활성 수동·UPnP 외부 포트 겹침을 검사하고 변경 후 재조회로 확인합니다.
UPnP 규칙은 조회와 충돌 검사만 지원하고, 공유기의 고정 규칙은 수정·삭제하지 않습니다. GRE 매핑 수정은 지원하지 않습니다.
공유기 웹 UI 또는 UPnP에서 동시에 발생하는 변경까지 차단할 수는 없습니다.

추가는 기본적으로 활성화됩니다. 비활성 규칙을 추가하거나 기존 규칙을 끄려면 `name`과 `active: false`만 입력하세요.
비활성 요청에서는 프로토콜·IP·포트를 함께 입력할 수 없습니다. 활성화하려면 `active: true`를 입력하며,
기존 매핑이 없는 규칙은 프로토콜·IP·포트도 필요합니다. 포트 포워딩 전체 기능의 켜짐 여부는 기존 스위치로 제어합니다.

### DHCP 수동 IP 할당 액션

Beta UI를 지원하는 공유기에서 `iptime_manager.get_dhcp_reservations`,
`add_dhcp_reservation`, `update_dhcp_reservation`, `delete_dhcp_reservation` 액션을 사용할 수 있습니다.
액션 입력의 `config_entry_id`에서 공유기를 선택하고, 변경 시 `mac`과 추가·수정 시 `ip`를 입력합니다.
`description`은 선택 사항이며 수정 시 생략하면 유지하고 빈 문자열이면 지웁니다. 수정 대상 MAC은 변경하지 않습니다.

조회는 `reservations` 목록(MAC, IP, description)을 응답으로 반환합니다. 스크립트에서는 다음처럼 사용합니다.

```yaml
- action: iptime_manager.get_dhcp_reservations
  data:
    config_entry_id: YOUR_ROUTER_CONFIG_ENTRY_ID
  response_variable: dhcp
```

추가·수정은 예약 목록과 연결 기기의 중복 IP, LAN 범위 및 공유기 주소를 검사합니다.
조회 실패 시 변경을 중단하고, 변경 후 목록을 다시 읽어 결과를 확인합니다.
오프라인 기기의 수동 고정 IP나 공유기 웹 UI에서 동시에 수행한 변경까지 차단하지는 못합니다.
예약 변경은 기존 DHCP 임대를 즉시 갱신하지 않으므로 기기의 임대 갱신 또는 재연결이 필요할 수 있습니다.

- **WAN/LAN Port**는 물리 연결, **WAN/LAN Status**는 최근 통신 활동을 표시합니다. 통신이 없는 기기는 Status가 꺼질 수 있습니다.
- **Internet Status**는 HA에서 외부 접속을 확인하므로 HA가 해당 공유기를 통해 인터넷을 사용하는 구성을 전제로 합니다. 허브/AP 모드에서는 제외되지만, 배선만 바꾼 허브 구성은 자동 판별하지 못할 수 있습니다.
- **WireGuard Last Handshake**는 가장 최근 handshake 시각입니다. 연결 중에도 갱신될 수 있습니다.

버전별 변경 사항은 [변경 이력](custom_components/iptime_manager/CHANGELOG.md)을 참고하세요.

## 문의 및 지원

[GitHub Issues](https://github.com/plplaaa2/iptime_manager/issues)에 공유기 모델, 펌웨어 및 Home Assistant 버전을 함께 알려주세요. 로그를 공유할 때는 인증 정보를 제거하세요.

[Ko-fi로 후원하기](https://ko-fi.com/plplaaa2)

## 라이선스

[MIT](LICENSE)
