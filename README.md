# 🚀 ipTIME Manager for Home Assistant

[🇺🇸 English Version](./README.md) | [🇰🇷 한국어 버전](./README.ko.md)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-v1.4.0-blue.svg?style=for-the-badge)
[![kofi](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

The most powerful and modern Home Assistant integration for EFM ipTIME routers. Supporting all models featuring the **3rd-generation responsive IUX (including AX-series)** and the latest Flutter-based Beta UI, it has transitioned completely to a high-performance **JSON-RPC (Web API) architecture**, delivering flawless real-time monitoring and robust system control without requiring any complex SNMP configuration.

---

## ✨ Features & Technical Details

### ⚡ Smart Caching Engine
* **Over 70% Reduction in Network & CPU Overhead**: Introduces a high-performance, intelligent memory caching layer to eliminate heavy router processor usage.
* **Dynamic Lifecycle Management**: Static data (such as the router model name) is fetched once and cached permanently. Semi-static configurations (DNS, DoS, UPnP, Reboot schedules, WireGuard states) are cached in memory for 5 minutes to 1 hour.
* **Instant Mutation Invalidation**: When you toggle a switch or modify a selection in Home Assistant, the integration immediately invalidates the corresponding memory cache, pushes the change, and triggers a forced background update. This reduces the previous 14+ JSON-RPC calls per 5-second interval down to 4–5 core queries.

### 🚨 Real-Time WAN Cable & Public IP Change Tracking
* **Physical Cable & Lease Monitoring**: Actively monitors physical Ethernet link state on the WAN port and the public IP lease status.
* **Persistent Notification System**: If the WAN cable is unplugged, or the public IP changes, the integration immediately generates a persistent alert (`persistent_notification`) on your Home Assistant dashboard, displaying both the **previous IP** and the **newly assigned IP** so you are never left in the dark.

### 📡 SSID-Level Wi-Fi Switches & Band Separation
* **Unified Entities & Optimization**: Replaced redundant, slow-updating Wi-Fi binary sensors with unified, high-performance wireless switches (`switch`).
* **Granular SSID Control**: A single switch entity manages and displays the active state, frequency band, SSID name, security method, and visibility (hidden/visible). Toggles operate on a per-SSID (BSS) level rather than the entire band, preventing router wireless chipset restarts and keeping other IoT devices connected seamlessly.

### 🔒 3rd-Gen IUX Security & Smart GeoIP Lockout Safeguard
* **8 Dedicated Security Switches**: Reverse-engineered 3rd-generation responsive IUX security APIs to control Remote Admin port access, CSRF security block, ARP Virus Shield, Inbound Ping block, and more.
* **Lockout Disaster Prevention**: Includes GeoIP total blocked count (`sensor`) and policy selection (`select`). When switching to Country Allow mode, if the allow list is empty or missing, the integration **automatically force-injects the South Korea ('kr') code**, preventing catastrophic lockouts where you accidentally block your own administrative access.

### 🔌 Advanced NAT Settings (Port Forwarding & UPnP Relay)
* **Dashboard Toggle Switches**: Offers switch entities (`switch`) to toggle the router's Port Forwarding and UPnP Relay features directly from your dashboard cards, making manual configuration changes extremely easy.

### 🔑 Robust WireGuard VPN Server Control
* **One-Click Execution Switch**: Easily toggle the execution state of your router's built-in WireGuard VPN server (`switch.wireguard_server`).
* **Strict Parameter Filtering**: Adheres strictly to the JSON-RPC firmware validation. Read-only and non-standard attributes (e.g., `pubkey`) are thoroughly filtered out, transmitting only the 5 essential schema fields (`run`, `ip`, `subnet`, `port`, `nat`) to avoid API validation errors.

### 🌙 Night LED & Auto Reboot Custom Configuration Retention
* **System Settings Selectors**: Toggles Night LED modes (Disabled, Scheduled, Always Off) via `select.sysmisc_night_led` and automated reboot days via `select.auto_reboot_day`.
* **Memory Retention Mechanism**: When switching LED modes back to Scheduled or toggling the Auto Reboot switches, the integration remembers your custom night-LED hours and early morning reboot times (`Hour`/`Minute`) inside instance variables, preventing the router from reverting them to default values.

---

## 📊 Entity Summary

| Platform | Features & Entities |
| :--- | :--- |
| **`sensor`** | Router Uptime, Model Name, Firmware Version (with latest update comparison), WAN IP & MAC Address, Primary/Secondary DNS, GeoIP Cumulative Blocked Count, etc. |
| **`binary_sensor`** | WAN & LAN 1-4 Physical Link Status (`connectivity` device class supported) |
| **`switch`** | SSID-level Wi-Fi toggles, WireGuard Server toggle, Auto-Reboot toggle, Port Forwarding toggle, UPnP Relay toggle, **[8 Security Controls]** Remote Admin/CSRF/ARP Virus/Ping Block, etc. |
| **`select`** | Night LED Mode, Auto-Reboot Day, GeoIP Policy Settings |
| **`button`** | Router Safe Reboot Trigger (`button.reboot`) |

---

## 🛡️ Safety-First Integration Architecture

To ensure maximum reliability of your smart home network, we have revised the core integration architecture. 
Toggling settings that **trigger a physical, hardware-level reboot of the router chipsets—resulting in house-wide network outages and smart home interruptions**—have been **permanently retired from the integration entities and isolated from the codebase**:

1. **IPTV Mode Selector** (`select.iptime_iptv_mode` permanently removed)
2. **Internet Sharing Switch** (`switch.iptime_keep_connection` permanently removed)

> [!IMPORTANT]
> These modifications are absolute safety measures taken to prevent smart home lockout and network freezing caused by router hardware design limitations. If you must adjust your IPTV or NAT sharing configuration, please access the router's web admin UI (192.168.0.1) directly and perform the changes manually.

---

## ⚙️ Installation & Configuration

### 1. Automatic Installation (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=iptime_manager)

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
If this project saves you time and helps you manage your smart home, consider supporting development with a warm cup of coffee!

<a href='https://ko-fi.com/plplaaa2' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://cdn.ko-fi.com/cdn/kofi1.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

---

## 📄 License
This project is open-source software licensed under the **MIT License**. Built for inter-operability via reverse-engineered local HTTP/JSON-RPC protocols, it contains legal exemptions and liability limitations detailed in the LICENSE file.
