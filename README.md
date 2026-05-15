# 🚀 ipTIME Manager for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.2.0-orange.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

ipTIME 공유기를 위한 가장 강력하고 현대적인 Home Assistant 통합 구성요소입니다. 최신 베타 UI 모델부터 구형 모델까지 폭넓게 지원하며, 네트워크 트래픽 감시 및 시스템 상세 모니터링 기능을 제공합니다.

---

## ✨ 주요 기능

### 📱 최신 모델 및 베타 UI 완벽 지원
*   **Flutter 기반 UI 대응**: 최신 펌웨어를 사용하는 공유기의 기기 목록을 완벽하게 파싱합니다.
*   **계층형 데이터 분석**: 기기별 IP, 이름, 신호 세기(RSSI), 연결 밴드 정보를 정확하게 수집합니다.
*   **고도화된 세션 관리**: SameSite=Strict 쿠키 정책을 우회하여 끊김 없는 데이터를 보장합니다.

### 📊 실시간 네트워크 모니터링 (SNMP v3)
*   **전용 MIB 정밀 분석**: ipTIME 전용 OID를 통해 **모델명**, **펌웨어 버전**, **포트별 링크 속도**를 센서로 제공합니다.
*   **트래픽 통계**: 포트별 업로드/다운로드 누적 트래픽 및 실시간 속도를 감시합니다.
*   **보안 강화**: SNMP v3 (Auth MD5)를 지원하여 안전한 데이터 수신이 가능합니다.

### 🛠 스마트한 재실 추적 및 제어
*   **비동기 스캐닝**: `aiohttp` 기반의 비동기 통신으로 시스템 부하를 최소화합니다.
*   **EasyMesh 통합**: 컨트롤러와 에이전트에 연결된 모든 기기를 통합하여 관리합니다.
*   **원격 재부팅**: 버튼 하나로 공유기를 원격에서 안전하게 재부팅할 수 있습니다.

---

## ⚙️ 설치 및 설정 가이드

### 1. 자동 설치 (추천)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=https%3A%2F%2Fgithub.com%2Fplplaaa2%2Fiptime_manager&category=integration)

위 버튼을 눌러 저장소 추가 후 **ipTIME Manager** 설치 후 Home Assistant 재시작

### 2. HACS를 통한 설치
1.  HACS -> Integrations -> 우측 상단 메뉴 -> **Custom repositories** 선택
2.  `https://github.com/plplaaa2/iptime_manager` 추가 (Category: Integration)
3.  **ipTIME Manager** 설치 후 Home Assistant 재시작

### 3. SNMP 서버 설정 (중요)
트래픽 모니터링 및 모델명 센서를 사용하려면 공유기 관리 페이지에서 SNMP 서버를 활성화해야 합니다.
*   **v2c**: 커뮤니티 이름(기본값: `public`) 설정
*   **v3 (추천)**: 
    *   사용자 이름 및 인증 암호 설정 (MD5 방식)
    *   **주의**: 일부 최신 모델은 설정 후 공유기를 재부팅해야 SNMP 데이터가 정상적으로 전달됩니다.

---

## ☕ 후원하기
이 프로젝트가 도움이 되셨다면 따뜻한 커피 한 잔으로 개발자를 응원해 주세요!

<a href='https://ko-fi.com/plplaaa2' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://cdn.ko-fi.com/cdn/kofi1.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

---

## 📄 라이선스
이 프로젝트는 MIT 라이선스를 따릅니다.
