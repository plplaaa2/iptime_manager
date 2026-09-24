import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

# Summary: Remove legacy per-device trackers after migration to aggregate presence lists.
# Related files: __init__.py, presence.py, binary_sensor.py.

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Remove existing device trackers; new presence is represented by binary sensors."""
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registered.domain == "device_tracker" and registered.unique_id.startswith(prefix):
            _LOGGER.info("Removing legacy ipTIME presence tracker: %s", registered.entity_id)
            registry.async_remove(registered.entity_id)
