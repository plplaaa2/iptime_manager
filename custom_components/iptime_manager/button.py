from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_URL

# 요약: 공유기를 재부팅(Reboot)하는 액션을 담당하는 버튼 엔티티
# 연결될 파일: api.py, coordinator.py

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """버튼 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    
    # 1. 재부팅 버튼 (Web API 기반으로 항상 제공)
    entities.append(IPTimeRebootButton(coordinator, entry))
    
    if entities:
        async_add_entities(entities)

class IPTimeRebootButton(CoordinatorEntity, ButtonEntity):
    """공유기 재부팅 버튼."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self.entity_description = ButtonEntityDescription(
            key="reboot",
            name="Reboot Router",
            icon="mdi:restart",
        )
        self._attr_name = f"Reboot ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_reboot"

    async def async_press(self) -> None:
        """버튼이 눌렸을 때 실행."""
        await self.coordinator.api.async_reboot()

    @property
    def device_info(self) -> dict[str, Any]:
        """기기 정보 제공."""
        web_data = self.coordinator.data.get("web", {}) if self.coordinator.data else {}
        model = web_data.get("model", "ipTIME Router")
        version = web_data.get("firmware", {}).get("version", "Unknown")
        
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM Networks",
            "model": model,
            "sw_version": version,
        }
