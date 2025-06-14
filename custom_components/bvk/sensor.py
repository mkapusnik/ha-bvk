"""Sensor platform for BVK."""
from __future__ import annotations

import logging
import aiohttp
import asyncio
import re
from datetime import timedelta
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup

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

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    BVK_LOGIN_URL,
    BVK_MAIN_INFO_URL,
    BVK_TARGET_DOMAIN,
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
        self.session = None
        self.token_store = Store(hass, 1, f"{DOMAIN}_{TOKEN_CACHE_KEY}")
        self.token = None

        # Register session cleanup
        self.async_on_remove(self._async_cleanup)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from BVK website."""
        try:
            # Create a new session if needed
            if self.session is None:
                self.session = aiohttp.ClientSession()

            # Try to get cached token
            stored_data = await self.token_store.async_load()
            if stored_data and "token" in stored_data:
                self.token = stored_data["token"]
                _LOGGER.debug("Using cached token")

            # If no token, login and get a new one
            if not self.token:
                await self._login_and_get_token()

            # Use the token to get water consumption data
            # For now, return a placeholder value
            # In a real implementation, you would use the token to access the water consumption data
            return {"value": 42}

        except Exception as e:
            _LOGGER.error("Error updating BVK data: %s", str(e))
            return {"value": None}

    async def _login_and_get_token(self) -> None:
        """Login to BVK website and extract the authentication token."""
        try:
            # Step 1: Login to the BVK website
            login_response = await self.session.get(BVK_LOGIN_URL)

            # Extract any necessary form fields or tokens for login
            login_page = await login_response.text()
            soup = BeautifulSoup(login_page, 'html.parser')

            # Find the login form and extract any hidden fields
            login_form = soup.find('form', {'id': 'form1'})
            if not login_form:
                raise Exception("Login form not found")

            # Prepare login data
            login_data = {
                '__VIEWSTATE': soup.find('input', {'name': '__VIEWSTATE'}).get('value', ''),
                '__VIEWSTATEGENERATOR': soup.find('input', {'name': '__VIEWSTATEGENERATOR'}).get('value', ''),
                '__EVENTVALIDATION': soup.find('input', {'name': '__EVENTVALIDATION'}).get('value', ''),
                'ctl00$ContentPlaceHolder1$Login1$UserName': self.username,
                'ctl00$ContentPlaceHolder1$Login1$Password': self.password,
                'ctl00$ContentPlaceHolder1$Login1$LoginButton': 'Přihlásit'
            }

            # Submit login form
            login_post_response = await self.session.post(BVK_LOGIN_URL, data=login_data)

            # Check if login was successful
            if login_post_response.status != 200 or "Přihlášení se nezdařilo" in await login_post_response.text():
                raise Exception("Login failed")

            # Step 2: Load the main info page
            main_info_response = await self.session.get(BVK_MAIN_INFO_URL)
            main_info_page = await main_info_response.text()

            # Step 3: Find the icon with link to SUEZ Smart Solutions
            soup = BeautifulSoup(main_info_page, 'html.parser')

            # Look for links containing the target domain
            links = soup.find_all('a', href=lambda href: href and BVK_TARGET_DOMAIN in href)

            if not links:
                raise Exception("Link to SUEZ Smart Solutions not found")

            # Extract the link with authentication token
            target_link = links[0]['href']

            # Extract the authentication token from the link
            token_match = re.search(r'token=([^&]+)', target_link)
            if not token_match:
                raise Exception("Authentication token not found in link")

            self.token = token_match.group(1)

            # Store the token in cache
            await self.token_store.async_save({"token": self.token})

            _LOGGER.debug("Successfully obtained and cached authentication token")

        except Exception as e:
            _LOGGER.error("Error during login and token extraction: %s", str(e))
            raise

    async def _async_cleanup(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
            _LOGGER.debug("Closed aiohttp session")


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
