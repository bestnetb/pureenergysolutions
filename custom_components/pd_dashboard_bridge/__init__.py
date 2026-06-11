"""PD Dashboard Bridge integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PDDashboardBridgeCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PD Dashboard Bridge from a config entry."""

    coordinator = PDDashboardBridgeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:  # noqa: BLE001 - keep bridge transport alive even if diagnostics fail.
        LOGGER.exception("PD Dashboard diagnostic platform setup failed")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a PD Dashboard Bridge config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""

    await hass.config_entries.async_reload(entry.entry_id)
