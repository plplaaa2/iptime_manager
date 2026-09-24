Project layout (updated 2026-09-24).
The integration is distributed from custom_components/iptime_manager.
changelog.jsonl, changelog_1.jsonl and caution.jsonl are local development records excluded from Git.
Credential files are intentionally omitted from this listing.

iptime_manager (root)
|   .gitignore
|   LICENSE
|   changelog.jsonl (local, latest)
|   changelog_1.jsonl (local, older records)
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
        |   presence.py
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
- binary_sensor.py: physical Port links, packet Status sensors, Internet Status and EasyMesh agent connectivity entities.
- sensor.py: diagnostic system sensors, connected EasyMesh Agent count and latest WireGuard peer/handshake sensors.
- number.py: supported EasyMesh controller thresholds (density RSSI and steering level).
- button.py: diagnostic reboot button.
- device_tracker.py: removes legacy per-device tracker entities after migration.
- presence.py: aggregates selected device presence across all configured router coordinators.
