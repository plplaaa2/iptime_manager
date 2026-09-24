from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import get_easymesh_role
from .const import (
    CONF_CONSIDER_HOME,
    CONF_DEVICE_MODE,
    CONF_ENTRY_TYPE,
    CONF_TARGET,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_DEVICE_MODE,
    DEVICE_MODE_CONTROLLER,
    DEVICE_MODE_SINGLE,
    DOMAIN,
    ENTRY_TYPE_PRESENCE_LIST,
)

# Summary: Aggregate selected MAC presence across every configured router coordinator.
# Related files: __init__.py, config_flow.py, binary_sensor.py, device_tracker.py.

_LOGGER = logging.getLogger(__name__)


def _normalize_mac(mac: Any) -> str:
    return str(mac or "").replace(":", "").replace("-", "").lower()


class IPTimePresenceListCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Combine presence reports without issuing additional router requests."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.targets = {
            _normalize_mac(mac)
            for mac in entry.options.get(CONF_TARGET, entry.data.get(CONF_TARGET, []))
            if _normalize_mac(mac)
        }
        self._last_seen: dict[str, Any] = {}
        self._last_device_info: dict[str, dict[str, Any]] = {}
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_presence_{entry.entry_id}",
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        coordinators = self.hass.data.get(DOMAIN, {})
        entries = {
            entry.entry_id: entry
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_PRESENCE_LIST
        }
        configured_devices = self.entry.options.get("devices", self.entry.data.get("devices", {}))
        now = dt_util.utcnow()
        eligible_source_found = False

        for entry_id, source_entry in entries.items():
            coordinator = coordinators.get(entry_id)
            source_data = getattr(coordinator, "data", None) if coordinator else None
            if (
                not isinstance(source_data, dict)
                or coordinator.last_update_success is False
                or source_data.get("presence_scan_success") is False
            ):
                continue

            web_data = source_data.get("web", {})
            role = get_easymesh_role(web_data)
            mode = source_entry.options.get(
                CONF_DEVICE_MODE,
                source_entry.data.get(CONF_DEVICE_MODE, DEFAULT_DEVICE_MODE),
            )
            if role != "agent" and (
                role in ("controller", "alone")
                or mode in (DEVICE_MODE_SINGLE, DEVICE_MODE_CONTROLLER)
            ):
                eligible_source_found = True

            source_devices = source_data.get("devices", {})
            if not isinstance(source_devices, dict):
                continue
            source_names = source_entry.data.get("devices", {})
            for raw_mac, info in source_devices.items():
                mac = _normalize_mac(raw_mac)
                if mac not in self.targets or not isinstance(info, dict):
                    continue
                if info.get("state") != "home":
                    continue
                self._last_seen[mac] = now
                self._last_device_info[mac] = {
                    "name": configured_devices.get(mac)
                    or source_names.get(raw_mac)
                    or source_names.get(mac)
                    or info.get("name")
                    or mac,
                    "ip": info.get("ip"),
                    "band": info.get("band"),
                    "rssi": info.get("rssi"),
                }

        timeout = self.entry.options.get(
            CONF_CONSIDER_HOME,
            self.entry.data.get(CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME),
        )
        present_devices: dict[str, dict[str, Any]] = {}
        for mac in self.targets:
            last_seen = self._last_seen.get(mac)
            if last_seen is None or (now - last_seen).total_seconds() >= timeout:
                continue
            present_devices[mac] = dict(self._last_device_info.get(mac, {"name": configured_devices.get(mac, mac)}))

        return {
            "eligible": eligible_source_found,
            "devices": present_devices,
            "selected_count": len(self.targets),
        }
