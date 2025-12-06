import logging
import aiohttp
import async_timeout
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import UnitOfVolume

from .const import DOMAIN, CONF_API_URL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BVK sensor."""
    api_url = entry.data[CONF_API_URL]

    coordinator = BvkDataUpdateCoordinator(hass, api_url)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([BvkWaterSensor(coordinator)], True)

class BvkDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, api_url: str) -> None:
        """Initialize."""
        self.api_url = api_url
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=30), # Check API every 30 mins
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.api_url) as response:
                        if response.status != 200:
                            raise UpdateFailed(f"API returned status {response.status}")
                        return await response.json()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

class BvkWaterSensor(SensorEntity):
    """Representation of the BVK Water Sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:water"
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"bvk_water_meter"
        self._attr_name = "BVK Reading"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data or "reading" not in self.coordinator.data:
            return None
        return float(self.coordinator.data["reading"])

    @property
    def extra_state_attributes(self):
        """Return variables that are synced to state."""
        if not self.coordinator.data:
            return {}
        return {
            "timestamp": self.coordinator.data.get("timestamp")
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update the entity. Only used by the generic entity update service."""
        await self.coordinator.async_request_refresh()
