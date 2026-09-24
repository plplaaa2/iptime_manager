# Changelog

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
