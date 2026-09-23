Project layout (updated 2026-09-23).
The integration is distributed from custom_components/iptime_manager.
changelog.jsonl and caution.jsonl are local development records excluded from Git.
Credential files are intentionally omitted from this listing.

iptime_manager (root)
|   .gitignore
|   LICENSE
|   changelog.jsonl (local)
|   hacs.json
|   icon.png
|   README.md
|   README.ko.md
|   tree.md
|
+---.github
|   \---workflows
|           hassfest.yaml
|           validate.yaml
|
\---custom_components
    |   caution.jsonl (local)
    |   changelog.jsonl (local)
    |   web_api.md
    |
    \---iptime_manager
        |   __init__.py
        |   api.py
        |   binary_sensor.py
        |   button.py
        |   CHANGELOG.md
        |   config_flow.py
        |   const.py
        |   coordinator.py
        |   device_tracker.py
        |   manifest.json
        |   number.py
        |   select.py
        |   sensor.py
        |   strings.json
        |   switch.py
        |   
        +---brand
        |       icon.png
        |       logo.png
        |       
        \---translations
                en.json
                ko.json

Module responsibilities:
- api.py: router API access, elapsed WireGuard handshake conversion, port packet activity and router-mode detection.
- coordinator.py: collection scheduling, conditional Internet probing, mode-change reload and events.
- binary_sensor.py: physical Port links, packet Status sensors, Internet Status and EasyMesh entities.
- sensor.py: diagnostic system sensors and latest WireGuard peer/handshake sensors.
- number.py: supported EasyMesh controller thresholds (density RSSI and steering level).
- button.py: diagnostic reboot button.
- device_tracker.py: primary presence entities outside Diagnostics.
