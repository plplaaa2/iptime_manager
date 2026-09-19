# Changelog

## Unreleased - dev (2026-09-19)

- Replaced WireGuard Connected Peer Count with diagnostic Last Peer Name and Last Handshake timestamp sensors. Interpret firmware `last_handshake` as elapsed seconds, accept zero, and remove the retired count entity on setup.
- Renamed physical link entities to WAN Port and LAN 1–4 Port, preserving unique IDs and Ethernet icons.
- Added separate WAN/LAN Status entities with the `running` device class, based on RX and TX packet activity within 30 seconds. Expose packet deltas and last observed activity; handle initial samples, missing statistics and counter resets.
- Renamed Internet Connectivity to Internet Status while preserving its unique ID. Omit the entity and stop HTTPS probes in detected hub/AP configurations; reload on confirmed mode changes.
- Internet checks still originate from Home Assistant. Cabling-only hub arrangements with NAT/WAN left enabled cannot always be identified.
- Moved the reboot button into Diagnostics and presence trackers out of Diagnostics, preserving their existing actions and tracking behavior.
- Updated English/Korean documentation and API notes. Public version remains 1.0.8.
- Validated Python syntax, encoding, helper logic, entity identities, conditional Internet monitoring, and live router packet samples. Home Assistant UI behavior has not yet been verified.

## [1.0.8] - 2026-09-17

- Added HACS validation and Hassfest GitHub Actions.
- Updated HACS metadata to comply with the current schema.
- Added the `hub` integration type and sorted manifest keys.
- Updated the default README to concise English documentation.
- Added a concise Korean README as `README.ko.md`.
- Updated integration brand images to 256×256 PNG files.
- Fixed translation files to match the Home Assistant translation schema.

- Added an Internet Connectivity binary sensor using an external HTTPS probe every 5 seconds.
- fixed live Wi-Fi channel state and WireGuard peer discovery.

## [1.0.7] - 2026-08-05

- Added read-only EasyMesh SSID attributes without exposing passwords or keys.
- Added a diagnostic sensor for the number of connected WireGuard peers.
- Added device mode selection to Config Flow: auto, single router, EasyMesh Controller, or EasyMesh Agent.

## [1.0.6] - 2026-08-05

- Added EasyMesh activation and Agent count diagnostic entities.
- Added per-Agent connection status entities and Controller metadata attributes.
- Classified router identity and status sensors as diagnostic entities.
- Classified Wi-Fi channel, auto-reboot day, night LED, and GeoIP policy selectors as configuration entities.

## [1.0.5] - 2026-07-13

- Updated the `ScannerEntity` import path to remove a Home Assistant deprecation warning.
- Improved compatibility with future Home Assistant releases.

## [1.0.4] - 2026-05-27

- Added firmware update detection and persistent notifications.
- Added a direct link to the router settings page in update notifications.

## [1.0.3] - 2026-05-18

- Added Wi-Fi channel selection and physical LAN/WAN port monitoring.
- Added security and WAN status events for Home Assistant automations.
- Disabled WAN and LAN MAC sensors by default.

## [1.0.2] - 2026-05-18

- Added randomized/private MAC address warnings.
- Added configurable scan intervals and presence tracking options.
- Improved polling performance with separate presence and router data intervals.

## [1.0.1] - 2026-05-18

- Fixed Options Flow device selection persistence.
- Removed excluded device trackers from the entity registry.
- Improved English and Korean localization.

## [1.0.0] - 2026-05-17

- Initial stable release using the ipTIME local JSON-RPC web API.
- Added router monitoring, Wi-Fi controls, security controls, and presence tracking.
