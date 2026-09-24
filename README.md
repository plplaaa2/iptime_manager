# ipTIME Manager for Home Assistant

[🇺🇸 English Version](./README.md) | [🇰🇷 한국어 버전](./README.ko.md)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.0.8-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

Home Assistant integration for monitoring and controlling EFM ipTIME routers over your local network. No SNMP setup is required.

## Features

- Router information, firmware updates, WAN IP and DNS
- Wi-Fi switches and channel selection
- WAN/LAN link speed, packet activity and Internet Status
- WireGuard server control and latest peer handshake information
- EasyMesh controller settings for wired backhaul lock, dense deployment, RSSI threshold and steering level
- EasyMesh router mode and connected Agent count
- Individual presence sensors for selected devices, grouped under one Home Presence device
- Security settings, GeoIP, port forwarding and UPnP
- Night LED, scheduled reboot and a reboot button in Diagnostics

Available features depend on the router model and firmware.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=iptime_manager)

Open the link above, install **ipTIME Manager** in HACS, and restart Home Assistant.

### Manual

Copy `custom_components/iptime_manager` into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Setup

1. Open **Settings → Devices & services → Add integration**.
2. Search for **ipTIME Manager**.
3. Choose **Add a router** or **Add a presence sensor list**.
4. For a router, enter its address and administrator credentials. For Home Presence, select devices and name each sensor.

Home Presence can be created when a standalone router or EasyMesh controller is configured. Each selected device gets its own named sensor under the Home Presence device. Devices are checked across all configured routers, including Agents.

When adding a router, use its management address, for example `http://192.168.0.1`. Include the port if it uses a custom management port.

## Reading status

- **WAN/LAN Port** shows the physical connection. **WAN/LAN Status** shows recent traffic activity; an idle device can be off.
- **Internet Status** checks external access from Home Assistant and assumes HA uses this router for Internet access. It is omitted in detected hub/AP mode; cabling-only hub setups may not be recognized.
- **WireGuard Last Handshake** shows the latest handshake time, which can update during a connection.

See the [changelog](custom_components/iptime_manager/CHANGELOG.md) for release and development changes.

## Support

Report issues through [GitHub Issues](https://github.com/plplaaa2/iptime_manager/issues), including your router model, firmware and Home Assistant version. Remove credentials from logs before sharing them.

[Support this project on Ko-fi](https://ko-fi.com/plplaaa2)

## License

[MIT](LICENSE)
