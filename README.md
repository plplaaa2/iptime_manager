# ipTIME Manager for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Latest release](https://img.shields.io/github/v/release/plplaaa2/iptime_manager?style=for-the-badge)](https://github.com/plplaaa2/iptime_manager/releases)

A Home Assistant custom integration for monitoring and controlling EFM ipTIME routers over the local network. It uses the router's local web API and does not require SNMP configuration or an external cloud service.

## Features

- Router model, firmware, uptime, WAN IP, and network information
- Wi-Fi SSID and band channel monitoring and control
- LAN/WAN port connection and link-speed sensors
- Port forwarding, UPnP relay, and WireGuard server controls
- Security settings, GeoIP policy, night LED, and auto-reboot controls
- Presence tracking for selected connected devices
- Home Assistant events for WAN, security, and physical port changes

Available features depend on the router model and firmware.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=iptime_manager)

1. Open the link above, or search for `ipTIME Manager` in HACS.
2. Install the integration.
3. Restart Home Assistant.

### Manual

Copy `custom_components/iptime_manager` into the `config/custom_components/` directory of your Home Assistant installation, then restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & services → Add integration**.
2. Search for `ipTIME Manager`.
3. Enter the router address and administrator credentials.
4. Configure the scan interval and tracked devices if needed.

The router address is typically `http://192.168.0.1`. Use the same administrator account as the router's web management interface.

## Entities

- `sensor`: router status, firmware, WAN IP, DNS, and GeoIP information
- `binary_sensor`: LAN/WAN port and Wi-Fi connection status
- `switch`: Wi-Fi, security, WireGuard, port forwarding, and UPnP controls
- `select`: Wi-Fi channel, GeoIP policy, night LED, and auto-reboot settings
- `button`: router reboot
- `device_tracker`: presence for selected devices

## Important notes

- Supported entities and settings vary by ipTIME model and firmware.
- Changing router settings may temporarily interrupt network connectivity.
- IPTV mode, NAT/Keep Connection, and EasyMesh operating mode controls are intentionally not exposed because they may trigger a router restart.
- Change remote-management and security settings carefully.

## Support

When reporting an issue, include the router model, firmware version, Home Assistant version, and relevant logs. Remove passwords, tokens, and other sensitive information before posting.

[Open an issue on GitHub](https://github.com/plplaaa2/iptime_manager/issues)

## License

MIT License
