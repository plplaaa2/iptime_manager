# Changelog

## [1.1.2] - 2026-11-25

### Breaking Changes — Home Assistant Admin Permissions

* **Restricted key actions and entities that modify router settings to Home Assistant admins only.** Here, "admin" refers to a Home Assistant administrator user.
* **Applied admin permission checks to six actions for adding, updating, and deleting port forwarding rules and DHCP reservations.** Read/lookup actions remain available as before.
* **Home Assistant admin permissions are now required to change GeoIP, Access List, attack defense, global port forwarding enable, UPnP / UPnP Relay, WireGuard, and DNS security settings.**
* **The same permission checks now apply to turning Wi-Fi on/off and changing channels, EasyMesh mode / backhaul / density control / RSSI / steering, router reboot / scheduled reboot, and keep-alive / WAN reconnect.**
* Standard users can continue to view status and presence, and control the Night LED. Running restricted controls from a dashboard or action will show a permission error.
* Internal automation calls without user context are allowed. Automation or script calls that pass a standard user context are blocked for restricted controls.

### Requirements

* **Home Assistant 2026.1.0 or later** is required.

### Fixes

* Removed forced entity ID changes for EasyMesh number and switch entities so registered IDs are preserved across reloads and restarts.
* Stopped retry loops when the router rejects login and requested Home Assistant re-authentication instead. Updates the existing integration with credentials verified on the Korean or English re-authentication screen.
* Increased the retry backoff interval for communication errors from 15 seconds up to a maximum of 5 minutes. Avoids re-logging in solely on empty or malformed responses, and coalesces concurrent session refreshes into a single request.
* Requires both manufacturer `EFM Networks` and device type `InternetGatewayDevice:1` during SSDP discovery.
* Removed automatic addition of South Korea (`kr`) when selecting GeoIP Country Allow. Existing registered country lists are preserved.

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
