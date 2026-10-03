"""Home Assistant actions for DHCP reservations."""

import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, is_presence_list_entry


# Summary: Register router-specific actions, including response-only list retrieval.
# Related files: __init__.py, dhcp.py, api.py, services.yaml, translations/*.json.
def async_register_services(hass):
    async def handle(call):
        entry_id = call.data["config_entry_id"]
        entry = hass.config_entries.async_get_entry(entry_id)
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if entry is None or entry.domain != DOMAIN or is_presence_list_entry(entry.data) or coordinator is None:
            raise HomeAssistantError("Select a loaded ipTIME router configuration")
        operation = call.service.split("_", 1)[0]
        try:
            return await coordinator.api.dhcp.execute(
                operation, call.data.get("mac"), call.data.get("ip"),
                call.data.get("description"),
            )
        except (ValueError, TypeError, KeyError) as err:
            raise HomeAssistantError(str(err)) from err

    for operation in ("get", "add", "update", "delete"):
        fields = {vol.Required("config_entry_id"): cv.string}
        if operation != "get":
            fields[vol.Required("mac")] = cv.string
        if operation in ("add", "update"):
            fields[vol.Required("ip")] = cv.string
            fields[vol.Optional("description")] = cv.string
        name = "get_dhcp_reservations" if operation == "get" else f"{operation}_dhcp_reservation"
        hass.services.async_register(
            DOMAIN, name, handle, schema=vol.Schema(fields),
            supports_response=SupportsResponse.ONLY if operation == "get" else SupportsResponse.OPTIONAL,
        )
