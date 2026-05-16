# 🚀 ipTIME Manager for Home Assistant

[🇺🇸 English Version](./README.md) | [🇰🇷 한국어 버전](./README.ko.md)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.4.0-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

ipTIME 공유기를 위한 가장 강력하고 현대적인 Home Assistant 통합 구성요소입니다. 최신 베타 UI 모델부터 AX 시리즈 공유기까지 폭넓게 지원하며, 초고성능 **JSON-RPC (Web API) 전용 구조**로 완벽하게 탈바꿈하여 SNMP 의존성 없이 완벽한 모니터링과 제어를 제공합니다.

---

## ✨ 주요 기능

### 💻 정밀한 시스템 정보 실시간 모니터링
* **핵심 시스템 지표 모니터링**: 공유기 가동 시간(Uptime), 공유기 모델명, 펌웨어 버전(최신 버전 실시간 비교), WAN IP 및 MAC 주소, DNS 정보, 그리고 GeoIP 공격 차단 누적 수를 실시간 감시 센서(`sensor`)로 안전하고 확실하게 제공합니다.

### 🌐 네트워크 포트 실시간 가동성 및 시각화 개선
* **WAN / LAN 1~4 포트 모니터링**: 포트별 실시간 물리 연결 상태를 `connectivity` 디바이스 클래스의 이진 센서(`binary_sensor`)로 제공합니다.
* **직관적인 동적 아이콘**: 연결 여부에 따라 `mdi:ethernet` 및 `mdi:ethernet-off` 아이콘이 유기적으로 변경되어 홈 대시보드의 직관성을 극대화합니다.

### 🛡️ 고급 기능 및 시스템 제어 통합
* **IPTV 설정 원클릭 변경**: ipTIME 공식 가이드에서 제한적으로만 명시된 IPTV 모드를 완전히 해방하여, 3대 주요 통신사(KT, SKB, LGU+) 및 지역 케이블 방송(서경방송, 현대HCN 등)의 6종 특수 IPTV 설정 모드를 원클릭으로 정밀 제어할 수 있는 셀렉터(`select.iptime_iptv_mode`) 엔티티를 완벽 제공합니다.
* **WireGuard VPN 제어**: 외부 접속용 WireGuard VPN 서버의 기동 상태 모니터링 및 실시간 토글 제어 스위치(`switch.iptime_wireguard_server`)를 연동했습니다.
* **자동 재부팅 관리**: 수동 재부팅 실행 버튼(`button.iptime_reboot`) 및 스위치(`switch.iptime_auto_reboot`) 기능을 통해 언제나 쾌적한 공유기 상태를 유지합니다.

### 👥 스마트한 재실 감지 (Presence Detection) 고도화
* **무파괴 타깃 분리 저장 아키텍처**: 사용자가 추적 대상을 0개로 비워두고 옵션을 저장하더라도, 기존에 수동 매핑해 둔 소중한 공유기 기기 딕셔너리(`devices`) 목록이 **절대 삭제되지 않고 안전하게 보존**되도록 개선하여 데이터 유실 문제를 완전히 해결했습니다.
* **MAC 주소 시각화 개선**: 기기 추가/설정 변경 화면의 MAC 주소 표현 방식을 대문자와 콜론 구분자 표준 규격(`00:11:22:33:44:55`)으로 표시하여 가동 시인성을 대폭 높였습니다.
* **글로벌 표준 다국어(i18n) 수립**: 영어(`en.json`)와 한국어(`ko.json`)의 깔끔한 다국어 현지화 번역을 완비했습니다. (한글 환경의 경우 `"재실 감지 대상 기기 선택"`으로 알기 쉽게 표시)

### 🔒 AX 시리즈 보안 및 무선 고급 제어
* **8종 보안 스위치**: 원격 관리, CSRF, ARP Virus, Inbound Ping 등 8종의 보안 제어 스위치를 개별 제공합니다.
* **GeoIP 정책 제어**: GeoIP 정책 설정 셀렉터 및 GeoIP 차단 건수 센서를 제공합니다.
* **Wi-Fi BSS(SSID) 개별 제어**: IoT 네트워크 분리 및 Wi-Fi 대역(2.4G / 5G / 6G)의 무선 스위치 동작 시 전체 무선이 중단되지 않도록 SSID 단위 개별 토글 처리를 보장합니다.

---

## 📊 지원 엔티티 요약

| 플랫폼 | 주요 제공 기능 및 엔티티 |
| :--- | :--- |
| **`sensor`** | 공유기 가동 시간(Uptime), 공유기 모델명, 펌웨어 버전, WAN IP/MAC 주소, GeoIP 차단 누적 수 등 |
| **`binary_sensor`** | WAN 및 LAN 1~4 포트 연결 상태 (`connectivity`), Wi-Fi 밴드별 활성화 상태 |
| **`switch`** | Wi-Fi 밴드별 SSID 제어, WireGuard 서버 켜기/끄기, 자동 재부팅 관리, **[보안 8종]** 원격 관리/CSRF/ARP Virus 등 |
| **`select`** | IPTV 모드 설정(6종 옵션), GeoIP 정책 설정 |
| **`button`** | 공유기 즉시 재부팅 (`button.iptime_reboot`) |

---

## 📺 IPTV 연동 세부 가이드 (ISP IPTV Settings Guide)

ipTIME 공유기는 **공식 매뉴얼 상으로 오직 KT IPTV만 지원 및 설정법이 명시**되어 있으나, 본 통합 구성요소는 공유기 내부의 비공식/비공개 API 엔드포인트까지 역공학하여 **국내의 모든 주요 통신사 및 특수 케이블망 IPTV 서비스**를 원클릭으로 지원합니다.

| 선택 옵션 (HA Select) | 실제 작동 방식 및 대상 ISP 설명 |
| :--- | :--- |
| **`Disabled`** | IPTV 연결 모드를 사용하지 않습니다. |
| **`Private IP (IGMP Proxy) - SKB, LGU+`** | SK브로드밴드 및 LG유플러스 환경에서 사설 IP를 유지한 채 멀티캐스트 스트리밍을 라우팅해주는 표준 IGMP Proxy 설정입니다. |
| **`Public IP (LAN Port) - KT`** | KT 올레TV 셋톱박스용 공인 IP를 특정 단독 포트에 100% 브릿지 방식으로 밀어주는 가장 안정적인 공식 지원 모드입니다. |
| **`Public IP (MACVLAN) - KT`** | KT 셋톱박스로의 가상 MACVLAN 연결을 제공하는 고도화된 주소 매핑 모드입니다. |
| **`Public IP (LAN Port) - SCS`** | **서경방송(SCS)** 및 **현대HCN** 등 지역 케이블 방송 셋톱박스에 독점 공인 IP를 특정 LAN 포트로 직접 브릿지해주는 비공식 모드입니다. |
| **`Private IP (All Ports) - SCS`** | 서경방송 사설 IP 환경용으로, 특정 포트 지정을 생략하고 공유기 하위의 모든 LAN 포트에서 멀티캐스트 트래픽을 오픈하여 연결하는 모드입니다. |

---

## ⚙️ 설치 및 설정 가이드

### 1. 자동 설치 (추천)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=https%3A%2F%2Fgithub.com%2Fplplaaa2%2Fiptime_manager&category=integration)

위 버튼을 눌러 HACS 저장소 추가 후 **ipTIME Manager** 설치 후 Home Assistant를 재시작해 주세요.

### 2. 수동 설치
1. HACS -> Integrations -> 우측 상단 메뉴 -> **Custom repositories** 선택
2. `https://github.com/plplaaa2/iptime_manager` 추가 (Category: Integration)
3. **ipTIME Manager** 설치 후 Home Assistant 재시작

### 3. 통합 구성요소 설정 (Config Flow)
* 별도의 복잡한 SNMP 설정이나 추가 모듈 활성화가 **전혀 필요하지 않습니다.**
* 오직 공유기의 **웹 관리자 계정 정보**만으로 모든 모니터링과 풍부한 제어 기능을 곧바로 사용하실 수 있습니다!

---

## ☕ 후원하기
이 프로젝트가 도움이 되셨다면 따뜻한 커피 한 잔으로 개발자를 응원해 주세요!

<a href='https://ko-fi.com/plplaaa2' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://cdn.ko-fi.com/cdn/kofi1.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

---

## 📄 라이선스
이 프로젝트는 MIT 라이선스를 따릅니다.
