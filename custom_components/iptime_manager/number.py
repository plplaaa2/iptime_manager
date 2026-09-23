from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import is_easymesh_controller
from .const import DOMAIN

# Summary: Expose supported EasyMesh controller thresholds as number entities.
# Related files: api.py, coordinator.py, switch.py, const.py.


def _mesh_global_config(web_data: dict[str, Any]) -> dict[str, Any]:
    mesh = web_data.get("easymesh", {}) if isinstance(web_data, dict) else {}
    config = mesh.get("config", {}) if isinstance(mesh, dict) else {}
    global_config = config.get("global", {}) if isinstance(config, dict) else {}
    return global_config if isinstance(global_config, dict) else {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    web_data = (coordinator.data or {}).get("web", {})
    global_config = _mesh_global_config(web_data)
    controller = is_easymesh_controller(web_data)
    entities: list[NumberEntity] = []
    registry = er.async_get(hass)

    supported = {
        f"{entry.entry_id}_easymesh_density_rssi": controller and isinstance(global_config.get("density_control"), dict),
        f"{entry.entry_id}_easymesh_steering_level": controller and "steering_level" in global_config,
    }
    for unique_id, is_supported in supported.items():
        if not is_supported:
            entity_id = registry.async_get_entity_id("number", DOMAIN, unique_id)
            if entity_id:
                registry.async_remove(entity_id)

    if controller:
        if isinstance(global_config.get("density_control"), dict):
            entities.append(IPTimeEasyMeshDensityRSSINumber(coordinator, entry))
        if "steering_level" in global_config:
            entities.append(IPTimeEasyMeshSteeringLevelNumber(coordinator, entry))

    async_add_entities(entities)


class _IPTimeEasyMeshNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, entry, translation_key: str, unique_suffix: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_translation_key = translation_key
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
        super().__init__(coordinator, entry, "easymesh_density_rssi", "easymesh_density_rssi")
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
        super().__init__(coordinator, entry, "easymesh_steering_level", "easymesh_steering_level")
        self._attr_native_min_value = 1
        self._attr_native_max_value = 10

    @property
    def native_value(self) -> float | None:
        value = _mesh_global_config(self.coordinator.data.get("web", {}) if self.coordinator.data else {}).get("steering_level")
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.api.async_set_easymesh_steering_level(round(value))
        await self.coordinator.async_request_refresh()
