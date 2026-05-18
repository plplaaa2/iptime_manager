# 🚀 ipTIME Manager for Home Assistant

[🇺🇸 English Version](./README.md) | [🇰🇷 한국어 버전](./README.ko.md)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.0.1-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

ipTIME 공유기를 위한 가장 강력하고 현대적인 Home Assistant 통합 구성요소입니다. 최신 플러터(Flutter) 기반 베타 UI 모델부터 **3세대 IUX(반응형 모바일 웹 UI) 적용 공유기(AX 시리즈 등)**까지 폭넓게 지원하며, 초고성능 **JSON-RPC (Web API) 전용 구조**로 완전히 전환되어 복잡한 SNMP 설정 없이 완벽한 실시간 모니터링과 시스템 제어를 선사합니다.

---

## ✨ 주요 기능 및 동작 방식

### ⚡ 스마트 캐싱 엔진 (Smart Caching Engine) 탑재
* **네트워크 및 CPU 부하 70% 이상 혁신적 감축**: 공유기 하드웨어 부하를 원천 차단하기 위해 지능형 메모리 캐싱 레이어를 도입했습니다.
* **유기적 수명 주기 제어**: 공유기 모델명과 같이 변하지 않는 정적 정보는 최초 1회 수집 후 영구 캐싱하며, 포트/DNS/DoS 설정/UPnP/재부팅 스케줄/WireGuard 상태 등 준정적 데이터는 5분에서 최대 1시간 동안 메모리에 캐싱합니다.
* **실시간 즉시 반영 (Mutation Invalidation)**: 사용자가 홈어시스턴트에서 스위치를 조작하거나 설정을 변경하는 즉시 관련 데이터의 메모리 캐시를 즉시 파괴(Invalidation)하고 공유기에 즉각 반영한 뒤, 실시간 동기화 상태를 갱신합니다. 매 5초 주기마다 14회 이상 발생하던 무거운 JSON-RPC/CGI 호출을 핵심 4~5개로 압축했습니다.

### 🚨 실시간 외부 인터넷(WAN) 단절 및 공인 IP 변경 감지 알림
* **물리적 링크 & IP 상태 추적**: 외부 WAN 포트의 이더넷 케이블 분리/연결 상태 및 공인 IP 주소의 할당 해제/획득 상태를 실시간 모니터링합니다.
* **지속 알림(Persistent Notification) 자동 팝업**: 인터넷이 단절되거나 공인 IP 주소가 바뀌는 것을 감지하는 즉시, 홈어시스턴트 대시보드 상단에 **이전 IP 및 새로 할당받은 공인 IP 정보를 포함한 실시간 경보/안내 영구 알림**을 생성하여 스마트홈의 연결 상태를 즉각 파악할 수 있도록 돕습니다.

### 📡 개별 Wi-Fi SSID(BSS) 단위 무선 제어 스위치
* **엔티티 단일 통합 및 리소스 최적화**: 중복되고 갱신이 느리던 Wi-Fi 이진 센서를 제거하고, 직관적인 무선 제어 스위치(`switch`)로 완벽 통합했습니다.
* **상태 시각화 & SSID 개별 제어**: 개별 스위치 엔티티 하나만으로 무선 대역(band), SSID 이름, 보안 방식(security), SSID 숨김 여부(hide) 등을 대시보드 카드에서 한눈에 확인하고 즉시 토글할 수 있습니다. 밴드 단위 제어가 아닌 개별 SSID(BSS) 단위의 정밀 제어를 적용하여 무선 제어 시 공유기 무선 칩셋 전체가 리부팅되거나 사물인터넷(IoT) 기기들의 통신 연결이 끊기는 현상을 완벽하게 예방합니다.

### 🔒 3세대 IUX 보안 제어 및 지능형 실시간 경보/안전장치 (Lock-out 방지)
* **8종 보안 스위치 엔티티**: 3세대 IUX(반응형 모바일 웹 UI) 보안 API를 완벽하게 해독하여 원격 관리 포트 허용/차단, CSRF 보안 차단, ARP Virus 차단, Inbound Ping 응답 제어 등 공유기 내부의 핵심 보안 기능 8종을 안전하게 켜고 끌 수 있습니다.
* **실시간 보안 옵션 비활성화 경고 알림**: 8종 보안 옵션(CSRF, ARP Virus, SYN Flood, Smurf, IP Source Routing, IP Spoofing, Inbound/Outbound Ping) 중 켜져 있던 옵션이 꺼졌을 때(비활성화) 이를 실시간으로 즉각 감지합니다. 홈어시스턴트 지속 알림(Persistent Notification)을 통해 **각 보안 기능이 어떤 역할을 하는지 친절한 한글 설명**과 **비활성화 시 노출되는 보안 위험 취약성 정보**를 경고 메시지로 즉시 팝업하여, 잘 모르는 사용자가 실수로 핵심 보안 옵션을 꺼두는 사고를 사전에 강력하게 방지합니다.
* **GeoIP 국가 차단 및 락아웃 방지**: GeoIP 차단 누적 건수 센서(`sensor`) 및 차단 정책 설정 셀렉터(`select`)를 제공합니다. GeoIP 특정 국가 허용(Country Allow) 모드로 변경 시 허용 국가 목록이 완전히 비어 있거나 한국('kr')이 누락되는 경우, **대한민국 국가 코드('kr')를 강제로 자동 추가**하여 사용자 본인이 공유기 관리 페이지에서 영구적으로 차단(락아웃)되는 위험한 사고를 완벽히 막아줍니다.

### 🔌 NAT 고급 기능 제어 (포트포워드, UPnP 릴레이)
* **네트워크 정책 제어 스위치**: 공유기의 포트포워딩 기능 및 UPnP 릴레이 기능을 홈어시스턴트 대시보드 카드에서 즉각 제어할 수 있는 편리한 스위치(`switch`)를 제공합니다. 외부 서비스 연동 시 포트 개방 및 해제를 홈어시스턴트 대시보드에서 간편하고 동적으로 수행할 수 있습니다.

### 🔑 WireGuard VPN 서버 제어
* **구동 모드 원클릭 제어**: 공유기에 내장된 WireGuard VPN 서버의 동작 상태를 감지하고 켜고 끄는 스위치(`switch.wireguard_server`)를 제공합니다.
* **공유기 규격 밸리데이션 통과**: 공유기 펌웨어가 요구하는 JSON-RPC 규격을 준수하여, 읽기 전용 속성이나 비표준 파라미터(pubkey 등)를 철저히 정제하고 필수 5대 규격 필드(`run`, `ip`, `subnet`, `port`, `nat`)만을 엄격하게 전송하므로 동작 에러가 발생하지 않습니다.

### 🌙 나이트 LED 및 자동 재부팅(Auto Reboot) 사용자 설정 보존 메커니즘
* **나이트 LED 모드 & 스케줄 제어**: 야간 시간대에 공유기 LED 라이트를 끄는 나이트 LED 모드(Disabled, Scheduled, Always Off)를 변경할 수 있는 셀렉터(`select.sysmisc_night_led`)를 구현했습니다. 
* **자동 재부팅 요일 및 스케줄 제어**: 언제나 최적의 속도를 유지하기 위해 공유기 자동 재부팅 스위치 및 요일 변경 셀렉터(`select.auto_reboot_day`)를 제공합니다.
* **사용자 설정 메모리 보존 (Memory Retention)**: LED 모드를 스케줄로 복원하거나 자동 재부팅 스위치를 조작할 때, API 통신 속도로 인해 기존 사용자가 웹 UI 등에서 수동으로 구성해 둔 새벽 재부팅 시각(Hour/Minute)이나 커스텀 LED 시간 스케줄 설정이 초기화되지 않도록 **인스턴스 멤버 변수에 기존 값을 기억하고 최우선 적용**합니다.

### 👥 스마트한 재실 감지 (Presence Detection) 및 클린업
* **사용자 친화적 기기 보존**: 옵션에서 모든 기기를 체크 해제하더라도 기존 등록 기기 데이터(`devices`)가 유실되지 않도록 보존하여, 다음번에 구성 옵션에서 손쉽게 체크박스 선택만으로 다시 재실센서에 등록할 수 있습니다.
* **제외 센서의 완벽한 자동 삭제**: 구성 옵션에서 제외(체크 해제)한 기기는 홈어시스턴트 내부의 **Entity Registry**에서 즉시 완전 삭제(`async_remove`)되므로, "사용 불가능" 또는 "복구됨" 상태로 지저분하게 남지 않고 대시보드에서 완벽하게 클린 정리됩니다.

---

## 📊 지원 엔티티 요약

| 플랫폼 | 주요 제공 기능 및 엔티티 |
| :--- | :--- |
| **`device_tracker`** | 지정한 MAC 주소 기기의 실시간 재실(Home/Away) 감지 센서 (지정 기기별 개별 생성) |
| **`sensor`** | 공유기 Uptime, 모델명, 펌웨어 버전(최신 버전 비교 센서 포함), WAN IP 및 MAC 주소, DNS 정보, GeoIP 차단 누적 수 등 |
| **`binary_sensor`** | WAN 및 LAN 1~4 포트 이더넷 케이블 물리 연결 상태 (Connectivity 디바이스 클래스 지원) |
| **`switch`** | Wi-Fi 개별 SSID(BSS) 제어, WireGuard 서버 제어, 자동 재부팅 관리, 포트포워드 제어, UPnP 릴레이 제어, **[보안 8종]** 원격 관리/CSRF/ARP Virus/Ping Block 등 |
| **`select`** | 나이트 LED 모드 설정, 자동 재부팅 요일 설정, GeoIP 정책 설정 |
| **`button`** | 공유기 즉시 안전 재부팅 (`button.reboot`) |

---

## 🛡️ 안전 제일(Safety-First) 설계 기조 안내

스마트홈의 핵심인 공유기 통신의 신뢰성과 안정성을 극대화하기 위하여 설계 기조를 개편했습니다. 
설정 변경 시 **공유기 하드웨어 칩셋의 물리적인 즉시 강제 재부팅을 유발하여 집안 전체 네트워크 마비 및 스마트홈 가동 중단을 초래**하는 다음 두 엔티티는 안전을 위해 **엔티티 목록에서 영구 탈퇴 및 코드 상에서 완벽히 격리**되었습니다.

1. **IPTV 모드 제어 셀렉터** (`select.iptime_iptv_mode` 영구 삭제)
2. **인터넷 공유기능(NAT/Keep Connection) 스위치** (`switch.iptime_keep_connection` 영구 삭제)

> [!IMPORTANT]
> 본 조치는 공유기 하드웨어의 설계적 한계로 인한 통신 끊김 및 기기 락 현상을 예방하기 위해 취해진 절대적인 안전 조치입니다. 해당 설정 변경이 필요하신 경우 반드시 공유기의 웹 관리자 화면(192.168.0.1)에 직접 접속하여 안전하게 수동 변경해 주시기 바랍니다.

---

## ⚙️ 설치 및 설정 가이드

### 1. 자동 설치 (추천)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=iptime_manager)

위 버튼을 눌러 HACS 저장소 추가 후 **ipTIME Manager** 설치 후 Home Assistant를 재시작해 주세요.

### 2. 수동 설치
1. HACS -> Integrations -> 우측 상단 메뉴 -> **Custom repositories** 선택
2. `https://github.com/plplaaa2/iptime_manager` 추가 (Category: Integration)
3. **ipTIME Manager** 설치 후 Home Assistant 재시작

### 3. 통합 구성요소 설정 (Config Flow)
* 별도의 복잡한 SNMP 설정이나 추가 모듈 활성화가 **전혀 필요하지 않습니다.**
* 오직 공유기의 **웹 관리자 계정 정보 (아이디, 비밀번호)** 입력만으로 모든 실시간 모니터링과 풍부한 대시보드 제어 기능을 곧바로 사용하실 수 있습니다!

---

## ☕ 후원하기
이 프로젝트가 도움이 되셨다면 따뜻한 커피 한 잔으로 개발자를 응원해 주세요!

<a href='https://ko-fi.com/plplaaa2' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://cdn.ko-fi.com/cdn/kofi1.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

---

## 📄 라이선스
본 프로젝트는 **MIT 라이선스**를 따르는 오픈소스 소프트웨어입니다. 공유기 펌웨어 역공학 및 로컬 네트워크 API 통신 규약을 기반으로 합법적이고 안전하게 상호운용성을 확보하도록 설계되었으며, 사용 중에 발생하는 위험 요소에 대해 라이선스 면책 조항이 적용됩니다.
