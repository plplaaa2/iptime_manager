# ipTIME Manager for Home Assistant

[🇺🇸 English Version](./README.md) | [🇰🇷 한국어 버전](./README.ko.md)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.0.2-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

Home Assistant integration for EFM ipTIME routers. Supporting models with the 3rd-generation responsive IUX (including AX-series) and the latest Flutter-based Beta UI, it operates entirely on a JSON-RPC (Web API) architecture for lightweight, real-time monitoring and system control without complex SNMP configuration.

---

## Features

### 1. Smart Caching Engine
* **Reduced Overhead**: Incorporates a memory caching layer to prevent excessive API queries.
* **Lifecycle Management**: Static parameters (e.g., model name) are queried once and permanently cached. Semi-static configurations (DNS, DoS, UPnP, Reboot schedules, WireGuard states) are cached for 5 minutes to 1 hour.
* **Instant Mutation Invalidation**: Modifying a switch or selection immediately invalidates the corresponding memory cache, pushing changes to the router and forcing an immediate background update for instant feedback.

### 2. WAN Status & Public IP Change Tracking
* **Link & IP Monitoring**: Monitors the WAN physical Ethernet link and public IP lease status.
* **Persistent Notifications**: Triggers a Home Assistant persistent notification containing both the previous and newly assigned IP addresses when a WAN disconnection or public IP change occurs.

### 3. SSID-Level Wi-Fi Switches
* **SSID Toggles**: Provides switch (`switch`) entities to toggle individual SSIDs on 2.4G, 5G, and 6G bands.
* **Network Stability**: Operating at the BSS (SSID) level rather than restarting the entire wireless chipset avoids dropping connections on other smart home IoT devices.

### 4. 3rd-Gen IUX Security Controls & GeoIP Lockout Prevention
* **8 Security Switches**: Exposes 8 core security settings—including Remote Admin Port, CSRF block, and ARP Virus shield—as individual switches.
* **Disabled Option Alerts**: Triggers a dashboard alert with concise explanations of security functions and specific risks when any of the 8 safety controls is turned off.
* **GeoIP Safety Guard**: Supports GeoIP block counts and policy selection. Automatically force-adds the South Korea ('kr') country code if the allow list is empty when switching to Country Allow mode, preventing administrative lockout.

### 5. NAT & Port Forwarding / UPnP Controls
* **Dashboard Toggles**: Provides switches to activate or deactivate Port Forwarding and UPnP Relay directly from the Home Assistant UI.

### 6. WireGuard VPN Server Control
* **Server Execution Switch**: Manages the execution state of the built-in WireGuard VPN server.
* **API Compliance**: Transmits only the 5 schema fields (`run`, `ip`, `subnet`, `port`, `nat`) required by the firmware validation schema to prevent API runtime errors.

### 7. Night LED & Auto Reboot Schedule Preservation
* **Schedule Selectors**: Features selectors for Night LED modes and Auto-Reboot days.
* **Memory Retention**: Preserves previously configured custom times (reboot time, night LED schedule) in memory so that toggling option switches does not force-reset them to default firmware values.

### 8. Smart Presence Detection & Clean Entity Deletion
* **Device Preservation**: Retains device MAC addresses and custom names in memory even if they are unchecked in the options flow, allowing easy reactivations.
* **Registry Cleanup**: Removes unchecked devices immediately from Home Assistant's Entity Registry (`async_remove`), preventing inactive sensors from cluttering the dashboard.

### 9. Dual-Interval Intelligent Polling & Custom scan_interval
* **Custom Polling Rates**: Allows users to specify the presence scan frequency (seconds) during setup or via the options flow.
* **5-Second Isolation (Safety Throttling)**: Even with rapid presence scans (e.g., every 1–3 seconds), heavier web queries (SSID, DNS, system details) are throttled to a minimum 5-second interval to avoid router CPU lockups.
* **Zero-Delay Mutative Actions**: Dashboard switch toggles bypass the 5-second throttling interval to execute instantly and fetch fresh states immediately.

---

## Entity Summary

| Platform | Features & Entities |
| :--- | :--- |
| **`device_tracker`** | Real-time presence detection (Home/Away) for selected devices by MAC address |
| **`sensor`** | Router Uptime, Model Name, Firmware Version (with update status), WAN IP & MAC Address, Primary/Secondary DNS, GeoIP Block Count, etc. |
| **`binary_sensor`** | WAN & LAN 1-4 Physical Link Status (`connectivity` device class supported) |
| **`switch`** | SSID-level Wi-Fi toggles, WireGuard Server toggle, Auto-Reboot toggle, Port Forwarding toggle, UPnP Relay toggle, **[8 Security Controls]** Remote Admin/CSRF/ARP Virus/Ping Block, etc. |
| **`select`** | Night LED Mode, Auto-Reboot Day, GeoIP Policy Settings |
| **`button`** | Router Safe Reboot Trigger (`button.reboot`) |

---

## Safety-First Integration Design

To maintain smart home connectivity, actions that trigger a physical hardware-level reboot—causing complete network outages—have been permanently retired from the integration entities:

1. **IPTV Mode Selector** (`select.iptime_iptv_mode` permanently removed)
2. **Internet Sharing Switch** (`switch.iptime_keep_connection` permanently removed)

> [!IMPORTANT]
> This safety measure prevents connectivity lockouts due to hardware limitations. If you must adjust IPTV or NAT settings, please perform them manually via the router's web admin UI (192.168.0.1).

---

## Installation & Configuration

### 1. Automatic Installation (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=iptime_manager)

Click the button above to add this repository directly inside HACS, install **ipTIME Manager**, and restart Home Assistant.

### 2. Manual Installation
1. Go to **HACS** -> **Integrations** -> click three dots in top-right -> select **Custom repositories**
2. Paste `https://github.com/plplaaa2/iptime_manager` and select **Integration** category
3. Install **ipTIME Manager** and restart Home Assistant

### 3. Integration Setup (Config Flow)
* **No SNMP configuration is required** for any core functionality.
* Simply enter your router's **Web administrator login credentials**, and the integration will immediately populate all entities!

---

## Support Me
If this project saves you time and helps you manage your smart home, consider supporting development with a warm cup of coffee!

<a href='https://ko-fi.com/plplaaa2' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://cdn.ko-fi.com/cdn/kofi1.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

---

## License
This project is licensed under the **MIT License**. Built for inter-operability via reverse-engineered local HTTP/JSON-RPC protocols, it contains legal exemptions and liability limitations detailed in the LICENSE file.
