from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .api import is_easymesh_controller
from .const import CONF_URL, DOMAIN

# Summary: Expose supported EasyMesh controller thresholds as number entities.
# Related files: api.py, coordinator.py, switch.py, const.py.
_LOGGER = logging.getLogger(__name__)


def _mesh_global_config(web_data: dict[str, Any]) -> dict[str, Any]:
    mesh = web_data.get("easymesh", {}) if isinstance(web_data, dict) else {}
    config = mesh.get("config", {}) if isinstance(mesh, dict) else {}
    global_config = config.get("global", {}) if isinstance(config, dict) else {}
    return global_config if isinstance(global_config, dict) else {}


def _entity_name(name: str, entry: ConfigEntry) -> str:
    return f"{name} ({entry.data.get(CONF_URL)})"


def _migrate_entity_id(registry, unique_id: str, name: str) -> None:
    """Move a legacy model-based entity ID to the integration's named format."""
    entity_id = registry.async_get_entity_id("number", DOMAIN, unique_id)
    if entity_id is None:
        return
    new_entity_id = f"number.{slugify(name)}"
    if entity_id == new_entity_id:
        return
    try:
        registry.async_update_entity(entity_id, new_entity_id=new_entity_id)
    except HomeAssistantError as err:
        _LOGGER.warning("Could not rename EasyMesh number entity %s: %s", entity_id, err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    web_data = (coordinator.data or {}).get("web", {})
    global_config = _mesh_global_config(web_data)
    controller = is_easymesh_controller(web_data)
    density = global_config.get("density_control")
    density_enabled = isinstance(density, dict) and density.get("enable") is True
    entities: list[NumberEntity] = []
    registry = er.async_get(hass)

    density_unique_id = f"{entry.entry_id}_easymesh_density_rssi"
    steering_unique_id = f"{entry.entry_id}_easymesh_steering_level"
    _migrate_entity_id(
        registry,
        density_unique_id,
        _entity_name("EasyMesh Station RSSI Limit", entry),
    )
    _migrate_entity_id(
        registry,
        steering_unique_id,
        _entity_name("EasyMesh Steering Level", entry),
    )

    supported = {
        density_unique_id: controller and density_enabled,
        steering_unique_id: controller and "steering_level" in global_config,
    }
    for unique_id, is_supported in supported.items():
        if not is_supported:
            entity_id = registry.async_get_entity_id("number", DOMAIN, unique_id)
            if entity_id:
                registry.async_remove(entity_id)

    if controller:
        if density_enabled:
            entities.append(IPTimeEasyMeshDensityRSSINumber(coordinator, entry))
        if "steering_level" in global_config:
            entities.append(IPTimeEasyMeshSteeringLevelNumber(coordinator, entry))

    async_add_entities(entities)


class _IPTimeEasyMeshNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, entry, name: str, unique_suffix: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = _entity_name(name, entry)
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_step = 1

    @property
    def device_info(self) -> dict[str, Any]:
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        model = web_data.get("model", "ipTIME Router")
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM Networks",
            "model": model,
        }


class IPTimeEasyMeshDensityRSSINumber(_IPTimeEasyMeshNumber):
    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "EasyMesh Station RSSI Limit", "easymesh_density_rssi")
        self._attr_native_min_value = -100
        self._attr_native_max_value = -40
        self._attr_native_unit_of_measurement = "dBm"

    @property
    def native_value(self) -> float | None:
        density = _mesh_global_config(self.coordinator.data.get("web", {}) if self.coordinator.data else {}).get("density_control", {})
        value = density.get("rssi") if isinstance(density, dict) else None
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.api.async_set_easymesh_density_rssi(round(value))
        await self.coordinator.async_request_refresh()


class IPTimeEasyMeshSteeringLevelNumber(_IPTimeEasyMeshNumber):
    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "EasyMesh Steering Level", "easymesh_steering_level")
        self._attr_native_min_value = 1
        self._attr_native_max_value = 10

    @property
    def native_value(self) -> float | None:
        value = _mesh_global_config(self.coordinator.data.get("web", {}) if self.coordinator.data else {}).get("steering_level")
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.api.async_set_easymesh_steering_level(round(value))
        await self.coordinator.async_request_refresh()
