# Changelog

## Unreleased

- Added EasyMesh controller controls for wired backhaul lock, dense configuration, station RSSI limit and steering level.
- Restricted controller controls to active controllers and hid GeoIP, WireGuard and DNS entities in Agent mode.
- Read router uptime from `system/info.uptime` instead of WAN/LAN connection duration.
- Fixed EasyMesh controller 5 GHz channel selector values by matching bonded channels on their primary channel number.

## [1.0.8] - beta2 (2026-09-19)

- Replaced WireGuard peer count with the latest peer name and handshake time.
- Separated WAN/LAN physical Port sensors from traffic Status sensors.
- Renamed Internet Connectivity to Internet Status and excluded detected hub/AP mode.
- Moved reboot into Diagnostics and presence trackers into the main entity section.

> **beta2:** Existing WAN/LAN Status sensors are renamed to WAN/LAN Port, and Internet Connectivity to Internet Status. Review dashboard and automation references after updating; the new WAN/LAN Status sensors report traffic activity instead of physical link state.

## [1.0.8] - beta1 2026-09-17

- Added Internet Connectivity monitoring.
- Fixed Wi-Fi channel reporting and WireGuard peer discovery.
- Improved HACS compatibility and translations.

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
