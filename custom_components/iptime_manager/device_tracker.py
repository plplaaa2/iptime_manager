import logging
from typing import Any

from homeassistant.components import zone
from homeassistant.components.device_tracker import (
    DeviceTrackerEntityCapabilityAttribute,
    SourceType,
    TrackerEntity,
    TrackingType,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TARGET, DOMAIN, is_presence_list_entry

# Summary: Expose each selected Home Presence client as a Home Assistant device_tracker.
# Related files: __init__.py, presence.py, config_flow.py.

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Home Presence trackers or remove legacy router trackers."""
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    if is_presence_list_entry(entry.data):
        targets = entry.options.get(CONF_TARGET, entry.data.get(CONF_TARGET, []))
        current_unique_ids = {
            f"{entry.entry_id}_presence_{str(mac).replace(':', '').replace('-', '').lower()}"
            for mac in targets
        }
        for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
            if (
                registered.domain == "binary_sensor"
                and registered.unique_id.startswith(f"{entry.entry_id}_presence_")
            ):
                _LOGGER.info("Removing previous presence binary sensor: %s", registered.entity_id)
                registry.async_remove(registered.entity_id)
            elif (
                registered.domain == "device_tracker"
                and registered.unique_id.startswith(f"{entry.entry_id}_presence_")
                and registered.unique_id not in current_unique_ids
            ):
                registry.async_remove(registered.entity_id)

        coordinator = hass.data[DOMAIN][entry.entry_id]
        async_add_entities(
            [IPTimeHomePresenceTracker(coordinator, entry, mac) for mac in targets]
        )
        return

    prefix = f"{entry.entry_id}_"
    for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registered.domain == "device_tracker" and registered.unique_id.startswith(prefix):
            _LOGGER.info("Removing legacy ipTIME presence tracker: %s", registered.entity_id)
            registry.async_remove(registered.entity_id)


class IPTimeHomePresenceTracker(CoordinatorEntity, TrackerEntity):
    """Track one selected client under the shared Home Presence device."""

    _attr_source_type = SourceType.ROUTER
    _attr_capability_attributes = {
        DeviceTrackerEntityCapabilityAttribute.TRACKING_TYPE: TrackingType.CONNECTION
    }

    def __init__(self, coordinator, entry: ConfigEntry, mac: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._mac = str(mac).replace(":", "").replace("-", "").lower()
        names = entry.options.get("device_names", entry.data.get("device_names", {}))
        self._attr_name = names.get(self._mac, self._mac)
        self._attr_unique_id = f"{entry.entry_id}_presence_{self._mac}"

    @property
    def is_connected(self) -> bool:
        return self._mac in (self.coordinator.data or {}).get("devices", {})

    @property
    def icon(self) -> str:
        return "mdi:cellphone" if self.is_connected else "mdi:cellphone-off"

    @property
    def state(self) -> str:
        return STATE_HOME if self.is_connected else STATE_NOT_HOME

    @property
    def in_zones(self) -> list[str]:
        return [zone.ENTITY_ID_HOME] if self.is_connected else []

    @property
    def available(self) -> bool:
        return super().available and bool((self.coordinator.data or {}).get("eligible"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = (self.coordinator.data or {}).get("devices", {}).get(self._mac, {})
        return {
            "ip": device.get("ip"),
            "mac": ":".join(self._mac[index:index + 2] for index in range(0, 12, 2)).upper(),
            "band": device.get("band"),
            "rssi": device.get("rssi"),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, "home_presence")},
            "name": "Home Presence",
            "manufacturer": "ipTIME",
        }
