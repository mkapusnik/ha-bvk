"""Sensor platform for BVK."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

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

from .const import DOMAIN, CONF_NAME, CONF_USERNAME, CONF_PASSWORD

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

    # Extract credentials from entry data
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
        self._username = username
        self._password = password
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        # TODO: Implement API call or data retrieval logic here
        # Use self._username and self._password for authentication
        # Example of how this might be implemented:
        # async with aiohttp.ClientSession() as session:
        #     auth_data = {"username": self._username, "password": self._password}
        #     async with session.post("https://api.example.com/auth", json=auth_data) as resp:
        #         token = await resp.json()
        #         # Use token for subsequent API calls

        # This is a placeholder that returns a static value
        _LOGGER.debug("Using credentials: %s / %s", self._username, self._password)
        return {"value": 42}


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
