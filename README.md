# 🚀 ipTIME Manager for Home Assistant

[🇺🇸 English Version](./README.md) | [🇰🇷 한국어 버전](./README.ko.md)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.0.0-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

The most powerful and modern Home Assistant integration for EFM ipTIME routers. Providing seamless support from the latest beta UI models to AX-series routers, it has transitioned completely to a high-performance **JSON-RPC (Web API) architecture**, delivering comprehensive monitoring and robust system controls without requiring any complex SNMP configuration.

---

## ✨ Features

### 💻 Real-Time System Information Monitoring
* **Core System Telemetry**: Safely and reliably delivers primary diagnostic sensors (`sensor`) such as router Uptime, Model name, Firmware version (with real-time updates detection), WAN IP & MAC address, Primary/Secondary DNS, and cumulative GeoIP Blocked Count.

### 🌐 Network Ports Status & Visual Enhancements
* **WAN & LAN 1-4 Port Sensors**: Monitors real-time physical link connectivity via binary sensors (`binary_sensor`) utilizing the native `connectivity` device class.
* **Dynamic Material Design Icons**: Automatically toggles between `mdi:ethernet` and `mdi:ethernet-off` based on connection state, maximizing the visual aesthetics of your Home Assistant dashboard cards.

### 🛡️ Premium Controls & System Integration
* **One-Click IPTV Mode Selector**: Unleashes full control over IPTV configurations, extending beyond the standard KT mode to support 6 specialized ISP profiles across KT, SK Broadband, LG Uplus, and local cable systems (SCS, Hyundai HCN) via a dedicated select entity (`select.iptime_iptv_mode`).
* **WireGuard VPN Switch**: Toggles the execution state of your router's built-in WireGuard VPN server via switch controls (`switch.iptime_wireguard_server`).
* **Auto-Reboot Management**: Offers immediate reboot triggers (`button.iptime_reboot`) and automated reboot toggles (`switch.iptime_auto_reboot`) to keep your router in top-performing condition.

### 👥 High-Performance Presence Detection (Device Tracker)
* **Zero-Loss Target Persistence Architecture**: Resolves data loss issues where previously discovered devices were destroyed when selecting zero targets. Even if you deselect all targets in the config flow, your custom-named device mapping (`devices`) is **fully preserved** inside the config entry.
* **Standardized i18n Translation Support**: Completely decoupled localization assets into native `en.json` and `ko.json` resources for flawless internationalization.

### 🔒 AX-Series Security & Wireless Management
* **8 Security Switches**: Reverse-engineered AX-series security APIs to provide individual toggle entities for Remote Management, CSRF Protection, ARP Virus Shield, Inbound Ping responses, and more.
* **GeoIP Security Policies**: Includes active GeoIP block settings and total block counts monitoring.
* **SSID BSSID-Level Wireless Controls**: Separates 2.4GHz, 5GHz, and 6GHz Wi-Fi toggles so that toggling an individual band does not interrupt the entire wireless chipset.

---

## 📊 Entity Summary

| Platform | Features & Entities |
| :--- | :--- |
| **`sensor`** | Router Uptime, Model Name, Firmware Version, WAN IP/MAC, GeoIP Blocked Count, etc. |
| **`binary_sensor`** | WAN & LAN 1-4 Link Status (`connectivity`), Wi-Fi band active states |
| **`switch`** | Wi-Fi SSIDs toggles, WireGuard Server toggle, Auto-Reboot toggles, **[8 Security Controls]** Remote Admin/CSRF/ARP Virus, etc. |
| **`select`** | IPTV Mode Selector (6 options), GeoIP block policy settings |
| **`button`** | Router immediate trigger (`button.iptime_reboot`) |

---

## 📺 ISP IPTV Settings Guide

While EFM ipTIME routers **officially document and support only KT IPTV settings** in their manual, this integration reverse-engineers the inner Web APIs to unlock **full raw IPTV configurations for all major Korean ISPs and specialized MSO cable systems**.

| Option (HA Select) | Technical Implementation & Target ISP Details |
| :--- | :--- |
| **`Disabled`** | Deactivates IPTV routing logic. |
| **`Private IP (IGMP Proxy) - SKB, LGU+`** | Standard IGMP Proxy routing keeping the set-top box under private IP range, optimized for SK Broadband & LG Uplus. |
| **`Public IP (LAN Port) - KT`** | Bridges the external WAN interface directly to a designated LAN port, allocating a dedicated Public IP to the set-top box. Highly stable, official KT mode. |
| **`Public IP (MACVLAN) - KT`** | Advanced MACVLAN virtualization mode for KT set-top box integration. |
| **`Public IP (LAN Port) - SCS`** | Bridges and tunnels Public IP directly to the designated LAN port for **Seokyeong Cable System (SCS)** and **Hyundai HCN** networks. |
| **`Private IP (All Ports) - SCS`** | Opens IGMP multicast streams to all LAN ports under private IP ranges for local cable networks (SCS). |

---

## ⚙️ Installation & Configuration

### 1. Automatic Installation (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=https%3A%2F%2Fgithub.com%2Fplplaaa2%2Fiptime_manager&category=integration)

Click the button above to add this repository directly inside HACS, install **ipTIME Manager**, and restart your Home Assistant instance.

### 2. Manual Installation
1. Go to **HACS** -> **Integrations** -> click three dots in top-right -> select **Custom repositories**
2. Paste `https://github.com/plplaaa2/iptime_manager` and select **Integration** category
3. Install **ipTIME Manager** and restart Home Assistant

### 3. Integration Setup (Config Flow)
* **No SNMP configuration is required** for any core functionality.
* Simply enter your router's **Web administrator login credentials**, and the integration will immediately populate all entities!

---

## ☕ Support Me
If this project saves your time and helps you manage your smart home, consider supporting development with a warm cup of coffee!

<a href='https://ko-fi.com/plplaaa2' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://cdn.ko-fi.com/cdn/kofi1.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

---

## 📄 License
This project is open-source and licensed under the MIT License.
