"""Sensor platform for BVK."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.storage import Store

from .api import BVKApiClient
from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    TOKEN_CACHE_KEY,
)

_LOGGER = logging.getLogger(__name__)

# Time between updating data from the integration
SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    name = entry.data[CONF_NAME]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # Create update coordinator
    coordinator = BVKCoordinator(hass, username, password)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Add sensor entity
    async_add_entities([BVKSensor(coordinator, name, entry.entry_id)], True)


class BVKCoordinator(DataUpdateCoordinator):
    """BVK custom coordinator."""

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.username = username
        self.password = password
        self.api_client = BVKApiClient(username, password)
        self.token_store = Store(hass, 1, DOMAIN + "_" + TOKEN_CACHE_KEY)

        # Register session cleanup
        self.async_on_remove(self._async_cleanup)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from BVK website."""
        try:
            # Try to get cached token
            stored_data = await self.token_store.async_load()
            if stored_data and "token" in stored_data:
                self.api_client.token = stored_data["token"]
                _LOGGER.debug("Using cached token")

            # Get data from the API client
            data = await self.api_client.async_get_data()

            # If we got a new token during the data retrieval, cache it
            if self.api_client.token and (not stored_data or stored_data.get("token") != self.api_client.token):
                await self.token_store.async_save({"token": self.api_client.token})
                _LOGGER.debug("Cached new authentication token")

            return data

        except Exception as e:
            _LOGGER.error("Error updating BVK data: %s", str(e))
            return {"value": None}

    async def _async_cleanup(self) -> None:
        """Close the API client session."""
        await self.api_client.async_close_session()
        _LOGGER.debug("Closed API client session")


class BVKSensor(CoordinatorEntity, SensorEntity):
    """Representation of a BVK Sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = "m³"

    def __init__(
        self, coordinator: BVKCoordinator, name: str, entry_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_sensor"
        self._attr_name = "Water Consumption"

        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": name,
            "manufacturer": "BVK Manufacturer",
            "model": "BVK Model",
            "sw_version": "1.0.0",
        }

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.data.get("value") if self.coordinator.data else None
