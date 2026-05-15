from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_URL, CONF_USE_SNMP, CONF_SNMP_MODE, SNMP_MODE_RW, SNMP_MODE_RO

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """버전 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    
    use_snmp = entry.options.get(CONF_USE_SNMP, entry.data.get(CONF_USE_SNMP, False))
    snmp_mode = entry.options.get(CONF_SNMP_MODE, entry.data.get(CONF_SNMP_MODE, SNMP_MODE_RO))
    
    # 1. 재부팅 버튼 (기본 제공하되, SNMP 읽기 전용 모드에서는 제외)
    # SNMP를 사용하지 않거나(Web 모드), SNMP 읽기/쓰기 모드인 경우에만 표시
    if not use_snmp or snmp_mode in [SNMP_MODE_RW, "write"]:
        entities.append(IPTimeRebootButton(coordinator, entry))
    
    # 2. 펌웨어 업그레이드 버튼 (SNMP 읽기/쓰기 모드에서만 표시)
    if use_snmp and snmp_mode in [SNMP_MODE_RW, "write"]:
        entities.append(IPTimeUpgradeButton(coordinator, entry))
        
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
        self._attr_name = f"ipTIME Reboot ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_reboot"

    async def async_press(self) -> None:
        """버튼이 눌렸을 때 실행."""
        await self.coordinator.api.async_reboot()

    @property
    def device_info(self) -> dict[str, Any]:
        snmp_data = self.coordinator.data.get("snmp", {}) if self.coordinator.data else {}
        model = snmp_data.get("model", "ipTIME Router")
        version = snmp_data.get("version", "Unknown")
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM Networks",
            "model": model,
            "sw_version": version,
        }

class IPTimeUpgradeButton(CoordinatorEntity, ButtonEntity):
    """공유기 펌웨어 자동 업데이트 버튼."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self.entity_description = ButtonEntityDescription(
            key="upgrade",
            name="Firmware Auto Upgrade",
            icon="mdi:update",
        )
        self._attr_name = f"ipTIME Auto Upgrade ({entry.data.get(CONF_URL)})"
        self._attr_unique_id = f"{entry.entry_id}_upgrade"

    async def async_press(self) -> None:
        """버튼이 눌렸을 때 실행."""
        await self.coordinator.api.async_upgrade_firmware()

    @property
    def device_info(self) -> dict[str, Any]:
        snmp_data = self.coordinator.data.get("snmp", {}) if self.coordinator.data else {}
        model = snmp_data.get("model", "ipTIME Router")
        version = snmp_data.get("version", "Unknown")
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": model,
            "manufacturer": "EFM Networks",
            "model": model,
            "sw_version": version,
        }
