# Changelog

## [1.1.2] - 2026-11-25

### 주요 변경사항 — Home Assistant 관리자 권한

- **공유기 설정을 변경하는 주요 액션과 엔티티를 HA 관리자 전용으로 제한했습니다.** 여기서 관리자는 Home Assistant의 관리자 사용자를 의미합니다.
- **포트포워딩 규칙·DHCP 예약의 추가·수정·삭제 액션 6개**에 관리자 권한 검사를 적용했습니다. 조회 액션은 기존처럼 사용할 수 있습니다.
- **GeoIP, Access List, 공격 방어, 포트포워딩 전체 활성화, UPnP·UPnP Relay, WireGuard, DNS 보안 설정**을 변경하려면 HA 관리자 권한이 필요합니다.
- **Wi-Fi 켜기·끄기와 채널 변경, EasyMesh 모드·백홀·밀집 제어·RSSI·스티어링, 공유기 재부팅·예약 재부팅, 연결 유지·WAN 재연결**에도 같은 권한 검사를 적용했습니다.
- 일반 사용자는 상태·재실 조회와 Night LED 제어를 계속 사용할 수 있습니다. 제한된 제어를 대시보드나 액션으로 실행하면 권한 오류가 표시됩니다.
- 사용자 정보가 없는 내부 자동화 호출은 허용합니다. 일반 사용자 정보가 전달되는 자동화·스크립트 호출은 제한된 제어에서 차단됩니다.

### 요구 사항

- **Home Assistant 2026.1.0 이상**이 필요합니다.

### 수정

- EasyMesh 숫자·스위치 엔티티의 ID 강제 변경을 제거해 다시 로드하거나 재시작해도 등록된 ID를 유지합니다.
- 공유기가 로그인을 거절하면 반복 시도를 중단하고 HA 재인증을 요청합니다. 한글·영문 재인증 화면에서 검증한 계정 정보로 기존 통합을 갱신합니다.
- 통신 오류의 재시도 간격을 15초부터 최대 5분까지 늘립니다. 빈 응답·잘못된 응답만으로 재로그인하지 않으며, 동시 요청의 세션 갱신을 하나로 합칩니다.
- SSDP 자동 발견 시 제조사 EFM Networks와 InternetGatewayDevice:1 유형을 모두 요구합니다.
- GeoIP의 Country Allow 선택 시 한국(kr)을 자동으로 추가하던 동작을 제거했습니다. 이미 등록된 국가 목록은 유지합니다.

### 검증 상태

- 오프라인 테스트 56개와 앞선 수정 커밋의 HACS Validation·hassfest를 통과했습니다.
- 실제 HA·공유기의 관리자/일반 사용자 제어, 비밀번호 변경 후 재인증, 자동화 동작과 재시작 후 엔티티 ID 유지는 실환경 테스트가 필요합니다.

## [1.1.1] - 2026-11-12

### Added

- Add independent DNS redirect and encrypted DNS blocking switches for supported beta UI routers.

## [1.1.0] - 2026-10-03

### Added

- Add port forwarding list, add, update and delete actions with optional partial updates and rule renaming.
- Validate LAN targets and overlapping user/UPnP ports, protect fixed rules and verify changes through readback.
- Add response-capable DHCP reservation list, add, update and delete actions for beta UI routers.
- Validate duplicate reservation and connected-device IPs, LAN addresses and existing targets; serialize changes per router and verify them by reading back reservations.
- Provide English and Korean action fields and usage examples. These actions require beta UI support; live Home Assistant and router validation is pending.

## [1.0.9] - 2026-09-28

### Changed

- Integrate presence tracking across standalone and EasyMesh routers, with individually named device trackers under one Home Presence device.
- Allow creating an empty Home Presence list and adding devices later from its options.

### Fixed

- Support existing Home Presence entries and preserve tracking when EasyMesh changes to standalone mode.

## [1.0.8] - 2026-09-24

### Changed

- Added named aggregate presence sensor lists across configured routers; standalone routers and EasyMesh controllers enable list creation, while Agent observations also contribute to presence.
- Removed per-device device_tracker entities and clean up their registry entries when router entries load.
- Added EasyMesh controller controls for wired backhaul lock, dense configuration, station RSSI limit and steering level.
- Restricted controller controls to active controllers and hid GeoIP, WireGuard and DNS entities in Agent mode.
- Read router uptime from `system/info.uptime` instead of WAN/LAN connection duration.
- Added a diagnostic Router Mode sensor and a default-disabled EasyMesh controller mode switch.
- Count only connected EasyMesh agents in the Agent Count sensor.

### Fixed

- Fixed EasyMesh controller 5 GHz channel selector values by matching bonded channels on their primary channel number.
- Corrected the EasyMesh density RSSI range to match the router UI (`-100` to `-40 dBm`).
- Registered EasyMesh controller controls from the detected controller role and supported settings, independently of the generic beta UI control block.
- Renamed EasyMesh number entities consistently and show the density RSSI number only while dense configuration is enabled.
- Fixed EasyMesh Agent binary sensors to report disconnected agents from their status and backhaul fields.

- Replaced WireGuard peer count with the latest peer name and handshake time.
- Separated WAN/LAN physical Port sensors from traffic Status sensors.
- Renamed Internet Connectivity to Internet Status and excluded detected hub/AP mode.
- Moved reboot into Diagnostics and presence trackers into the main entity section.
- Added Internet Connectivity monitoring.
- Fixed Wi-Fi channel reporting and WireGuard peer discovery.
- Improved HACS compatibility and translations.

- **Migration note:** Existing WAN/LAN Status sensors are renamed to WAN/LAN Port, and Internet Connectivity to Internet Status. Review dashboard and automation references after updating; the new WAN/LAN Status sensors report traffic activity instead of physical link state.
- **Presence migration note:** Existing per-device device_tracker entities are removed. Create a presence sensor list and update automations that referenced the old trackers.

## [1.0.7] - 2026-08-05

- Added EasyMesh SSID information and device mode selection.
- Added a WireGuard connected peer count sensor.

## [1.0.6] - 2026-08-05

- Added EasyMesh status and Agent monitoring.
- Organized diagnostic and configuration entities.

## [1.0.5] - 2026-07-13

- Fixed a Home Assistant device tracker compatibility warning.

## [1.0.4] - 2026-05-27

- Added firmware update detection and notifications.

## [1.0.3] - 2026-05-18

- Added Wi-Fi channel selection and physical LAN/WAN port monitoring.
- Added security and WAN status events for Home Assistant automations.
- Disabled WAN and LAN MAC sensors by default.

## [1.0.2] - 2026-05-18

- Added randomized/private MAC address warnings.
- Added configurable presence tracking intervals and improved polling efficiency.

## [1.0.1] - 2026-05-18

- Fixed device selection persistence and removal of untracked devices.
- Improved English and Korean localization.

## [1.0.0] - 2026-05-17

- Initial release with router monitoring, Wi-Fi and security controls, and presence tracking.
