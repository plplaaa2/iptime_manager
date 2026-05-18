# ipTIME Manager for Home Assistant

[🇺🇸 English Version](./README.md) | [🇰🇷 한국어 버전](./README.ko.md)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.0.2-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

EFM ipTIME 공유기 연동을 위한 Home Assistant 통합 구성요소입니다. 3세대 모바일 IUX 및 최신 Flutter 베타 UI가 탑재된 AX 시리즈 등의 공유기를 지원하며, JSON-RPC (Web API) 통신 방식으로 동작하여 복잡한 SNMP 설정 없이 간편하게 실시간 상태를 확인하고 제어할 수 있습니다.

---

## 주요 기능

### 1. 스마트 캐싱 엔진 (Smart Caching Engine)
* **공유기 부하 감소**: 지능형 메모리 캐싱 레이어를 적용해 잦은 API 호출을 방지합니다.
* **유기적 수명 주기 관리**: 공유기 모델명 등 변하지 않는 정보는 최초 1회 수집 후 영구 캐싱하며, 포트/DNS/보안 제어/UPnP/재부팅 스케줄/WireGuard 상태 등은 5분~1시간 동안 메모리에 캐싱합니다.
* **제어 즉시 반영 (Mutation Invalidation)**: 대시보드에서 스위치나 설정을 변경하면 즉시 관련 메모리 캐시를 만료시키고 공유기에 동기화하여 실시간 상태 피드백을 제공합니다.

### 2. 인터넷(WAN) 단절 및 공인 IP 변경 감지
* **물리적 링크 & IP 상태 추적**: 외부 WAN 포트 케이블 연결 및 공인 IP 주소 변경 상태를 감지합니다.
* **지속 알림(Persistent Notification)**: 인터넷이 끊기거나 공인 IP 주소가 바뀌면 이전 IP 및 새로 할당받은 IP 정보를 포함한 알림창을 대시보드에 자동으로 생성합니다.

### 3. 개별 Wi-Fi SSID(BSS) 토글 스위치
* **SSID 단위 개별 제어**: 2.4G/5G/6G 대역의 개별 SSID를 켜고 끌 수 있는 토글 스위치(`switch`)를 제공합니다.
* **네트워크 순단 예방**: 밴드 전체를 끄는 것이 아닌 개별 SSID(BSS) 단위로 제어하므로 무선 칩셋 전체 재부팅으로 인한 IoT 기기들의 튕김 현상을 예방합니다.

### 4. 3세대 IUX 보안 스위치 및 GeoIP 안전장치 (락아웃 방지)
* **8종 보안 제어**: 원격 관리 포트, CSRF 보안 차단, ARP 바이러스 차단, Inbound Ping 제어 등 8종 보안 설정을 스위치로 다룹니다.
* **비활성화 감지 알림**: 8종 보안 옵션 중 켜져 있던 옵션이 비활성화되면 취약 위험성에 대한 간결한 안내와 함께 대시보드에 알림을 띄웁니다.
* **GeoIP 국가 허용 락아웃 방지**: GeoIP 차단 건수 센서 및 정책 설정 셀렉터를 지원합니다. 특정 국가 허용(Country Allow) 모드로 변경 시 허용 국가 목록이 완전히 비어 있으면 대한민국 코드('kr')를 강제로 자동 삽입하여 사용자 본인이 공유기 관리 페이지에서 영구적으로 차단되는 사고를 방지합니다.

### 5. NAT 고급 기능 제어 (포트포워드, UPnP 릴레이)
* **대시보드 원격 스위치**: 공유기의 포트포워딩 기능 및 UPnP 릴레이 기능의 활성화 스위치를 제공합니다.

### 6. WireGuard VPN 서버 제어
* **서버 동작 제어**: 내장 WireGuard VPN 서버의 실행 상태 스위치를 지원합니다.
* **API 규격 준수**: 공유기 펌웨어 JSON-RPC 스키마가 요구하는 필수 5대 필드(`run`, `ip`, `subnet`, `port`, `nat`)만을 정제 전송하여 제어 오류가 발생하지 않습니다.

### 7. 나이트 LED 및 자동 재부팅 설정 보존
* **나이트 LED 및 자동 재부팅 관리**: 야간 LED 모드 셀렉터 및 자동 재부팅 요일 변경 셀렉터를 제공합니다.
* **스케줄 보존 (Memory Retention)**: 옵션 스위치를 조작할 때, 사용자가 수동으로 입력해 두었던 세부 시각(재부팅 시각/LED 스케줄 시작 시간 등) 정보가 기본값으로 강제 리셋되지 않도록 인스턴스 내에 기존 설정값을 저장하고 보존합니다.

### 8. 스마트 재실 감지 & 자동 엔티티 클린업
* **기기 보존**: 옵션에서 모든 기기를 체크 해제하더라도 기존 등록 기기 데이터(MAC 및 커스텀 이름)가 유실되지 않고 안전하게 보존되어 추후 편리하게 재사용 가능합니다.
* **불필요한 엔티티 삭제**: 구성 옵션에서 제외(체크 해제)한 기기는 홈어시스턴트 Entity Registry 수준에서 즉시 완전 삭제하여 대시보드 상태가 깔끔하게 정돈됩니다.

### 9. 이원화 폴링 수집 및 스캔 주기(scan_interval) 커스텀화
* **초 단위 스캔 주기 선택**: 갱신 및 옵션 수정 화면에서 사용자가 원하는 재실 스캔 주기(초)를 직접 지정할 수 있습니다.
* **5초 지능형 스로틀러**: 스캔 주기를 1~3초로 타이트하게 단축하더라도, 무겁고 오버헤드가 큰 시스템/포트/무선 데이터 수집은 **최소 5초 주기로 스로틀링 작동**하도록 격리 독립시켜 공유기 과부하를 원천 차단합니다.
* **제어 0초 실시간 반응**: 5초 대기 스로틀이 돌고 있더라도, 사용자가 대시보드 스위치나 옵션을 조작하면 즉각적으로 강제 동기화가 진행되어 최상의 피드백 속도를 보장합니다.

---

## 지원 엔티티 요약

| 플랫폼 | 주요 제공 기능 및 엔티티 |
| :--- | :--- |
| **`device_tracker`** | 지정한 MAC 주소 기기의 실시간 재실(Home/Away) 감지 센서 |
| **`sensor`** | 공유기 Uptime, 모델명, 펌웨어 버전(최신 버전 비교 포함), WAN IP 및 MAC 주소, DNS 정보, GeoIP 차단 누적 수 등 |
| **`binary_sensor`** | WAN 및 LAN 1~4 포트 이더넷 케이블 물리 연결 상태 (Connectivity 디바이스 클래스 지원) |
| **`switch`** | Wi-Fi 개별 SSID 제어, WireGuard 서버 제어, 자동 재부팅 관리, 포트포워드 제어, UPnP 릴레이 제어, **[보안 8종]** 원격 관리/CSRF/ARP Virus/Ping Block 등 |
| **`select`** | 나이트 LED 모드 설정, 자동 재부팅 요일 설정, GeoIP 정책 설정 |
| **`button`** | 공유기 즉시 안전 재부팅 (`button.reboot`) |

---

## 안전 제어 설계 기조 안내

스마트홈의 심장인 홈 네트워크의 안정성을 위해 다음과 같이 설계를 개편했습니다. 
설정 변경 시 **공유기 하드웨어 칩셋의 물리적인 즉시 강제 재부팅을 유발하여 집안 전체 네트워크 마비 및 스마트홈 연동 단절을 초래**하는 다음 두 엔티티는 안전을 위해 **엔티티 목록에서 영구적으로 제외**되었습니다.

1. **IPTV 모드 제어 셀렉터** (`select.iptime_iptv_mode` 영구 삭제)
2. **인터넷 공유기능(NAT/Keep Connection) 스위치** (`switch.iptime_keep_connection` 영구 삭제)

> [!IMPORTANT]
> 본 조치는 공유기 하드웨어의 설계적 한계로 인한 연동 끊김 및 기기 락 현상을 예방하기 위해 취해진 안전 조치입니다. 해당 설정 변경이 필요하신 경우 반드시 공유기의 웹 관리자 화면(192.168.0.1)에 직접 접속하여 수동으로 변경해 주시기 바랍니다.

---

## 설치 및 설정 가이드

### 1. 자동 설치 (추천)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=iptime_manager)

위 버튼을 눌러 HACS 저장소 추가 후 **ipTIME Manager** 설치 후 Home Assistant를 재시작해 주세요.

### 2. 수동 설치
1. HACS -> Integrations -> 우측 상단 메뉴 -> **Custom repositories** 선택
2. `https://github.com/plplaaa2/iptime_manager` 추가 (Category: Integration)
3. **ipTIME Manager** 설치 후 Home Assistant 재시작

### 3. 통합 구성요소 설정 (Config Flow) 및 옵션 변경 (Options Flow)
* **SNMP 설정 불필요**: 복잡한 SNMP 설정이나 추가 패키지 설치 없이 즉시 작동합니다.
* **최초 등록 단계 (Config Flow)**:
  * **공유기 주소(URL)**: 공유기 접속 IP 주소 (예: `http://192.168.0.1`. 만약 80번 포트가 아닌 외부 원격 관리 포트를 설정해 두었다면 `http://192.168.0.1:8080`과 같이 포트 번호를 포함하여 작성)
  * **계정 정보**: 공유기 웹 관리자 로그인 아이디 및 비밀번호
  * **감지 간격 (Scan Interval)**: 재실 기기 상태를 스캔할 주기 (기본값 **5초**. 최하 1초부터 사용자 환경에 맞춰 자유롭게 조절 가능)
* **상세 구성 변경 단계 (Options Flow)**: 연동 완료 후 언제든지 카드 화면의 `설정(Configure)` 버튼을 통해 아래 설정을 변경할 수 있습니다.
  * **재실 감지 대상 단말기 선택**: 현재 공유기에 접속 중이거나 등록된 무선 단말 목록이 실시간으로 검색되어 체크박스로 표시되며, 추적을 원하는 기기를 선택해 `device_tracker` 엔티티를 생성합니다.
  * **외출(not_home) 판단 지연 시간**: 모바일 기기가 일시적으로 Wi-Fi 절전 모드나 수신율 저하로 연결이 끊어졌을 때, 재실 상태가 즉각 Away로 플래핑(Flapping) 오작동하는 것을 유예해 주는 대기 시간 (초 단위, 기본값 180초 추천).
  * **RSSI 기준치 (RSSI Limit)**: 무선 신호 감도가 설정된 임계값(dBm) 이하로 떨어지면 집에 없는 것으로 판단할 임계 감도 (기본값 **-90dBm**).

---

## 후원하기
이 프로젝트가 도움이 되셨다면 따뜻한 커피 한 잔으로 개발자를 응원해 주세요!

<a href='https://ko-fi.com/plplaaa2' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://cdn.ko-fi.com/cdn/kofi1.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

---

## 라이선스
본 프로젝트는 **MIT 라이선스**를 따르는 오픈소스 소프트웨어입니다. 공유기 펌웨어 역공학 및 로컬 네트워크 API 통신 규약을 기반으로 합법적이고 안전하게 상호운용성을 확보하도록 설계되었으며, 사용 중에 발생하는 위험 요소에 대해 라이선스 면책 조항이 적용됩니다.
