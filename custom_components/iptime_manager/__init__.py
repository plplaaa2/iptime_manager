import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import (
    DOMAIN,
    CONF_URL,
    CONF_ID,
    CONF_PASSWORD,
    PRESENCE_LIST_PLATFORMS,
    PLATFORMS,
    is_presence_list_entry,
)
from .api import IPTimeAPI
from .coordinator import IPTimeDataUpdateCoordinator
from .presence import IPTimePresenceListCoordinator

# Blocking import 경고 해결을 위한 플랫폼 선행 임포트
from . import device_tracker, sensor, button, binary_sensor, switch, select, number

# 요약: ipTIME Manager 통합 구성요소의 진입점 및 초기화 로직
# 연결될 파일: api.py, coordinator.py, const.py, sensor.py, device_tracker.py, button.py

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """통합 구성요소 설정."""
    hass.data.setdefault(DOMAIN, {})

    if is_presence_list_entry(entry.data):
        coordinator = IPTimePresenceListCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PRESENCE_LIST_PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(update_listener))
        _LOGGER.info("ipTIME presence list entity setup completed (%s)", entry.title)
        return True

    _LOGGER.info(f"Starting ipTIME Manager integration (URL: {entry.data[CONF_URL]})")
    api = IPTimeAPI(hass, entry.data[CONF_URL], entry.data[CONF_ID], entry.data[CONF_PASSWORD])
    coordinator = IPTimeDataUpdateCoordinator(hass, api, entry)
    
    _LOGGER.info("Attempting initial ipTIME data collection...")
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.info("Initial ipTIME data collection completed")

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("ipTIME entity setup completed")
    
    # 옵션 변경 시 실행될 리스너 등록
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """UI에서 옵션이 변경되면 플랫폼을 다시 로드합니다."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """통합 구성요소 언로드."""
    is_presence_list = is_presence_list_entry(entry.data)
    platforms = PRESENCE_LIST_PLATFORMS if is_presence_list else PLATFORMS
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        if not is_presence_list:
            await coordinator.api.async_close()
    return unload_ok
