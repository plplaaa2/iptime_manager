import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_URL, CONF_ID, CONF_PASSWORD, PLATFORMS
from .api import IPTimeAPI
from .coordinator import IPTimeDataUpdateCoordinator

# Blocking import 경고 해결을 위한 플랫폼 선행 임포트
from . import device_tracker, sensor, button, binary_sensor, switch, select

# 요약: ipTIME Manager 통합 구성요소의 진입점 및 초기화 로직
# 연결될 파일: api.py, coordinator.py, const.py, sensor.py, device_tracker.py, button.py

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """통합 구성요소 설정."""
    _LOGGER.info(f"ipTIME Manager 통합 구성요소 시작 (URL: {entry.data[CONF_URL]})")
    api = IPTimeAPI(hass, entry.data[CONF_URL], entry.data[CONF_ID], entry.data[CONF_PASSWORD])
    coordinator = IPTimeDataUpdateCoordinator(hass, api, entry)
    
    _LOGGER.info("ipTIME 데이터 최초 수집 시도...")
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.info("ipTIME 데이터 최초 수집 완료")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("ipTIME 엔티티 등록 완료")
    
    # 옵션 변경 시 실행될 리스너 등록
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """UI에서 옵션이 변경되면 플랫폼을 다시 로드합니다."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """통합 구성요소 언로드."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.async_close()
    return unload_ok
