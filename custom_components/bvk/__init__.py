"""Custom integration to integrate BVK's smart water meters with Home Assistant.

For more details about this integration, please refer to
https://github.com/mkapusnik/ha-bvk
"""
import logging
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Set up all platforms for this device/entry
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when it's updated
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove config entry from domain
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
