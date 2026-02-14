import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_homeassistant_modules(monkeypatch: pytest.MonkeyPatch):
    """Provide minimal Home Assistant module stubs.

    This lets us run basic sanity tests without pulling in the full HA
    dependency stack.
    """

    # homeassistant.config_entries
    ha_config_entries = types.ModuleType("homeassistant.config_entries")

    class _ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            # Home Assistant's ConfigFlow allows keyword arguments like domain=...
            return super().__init_subclass__()

    class _ConfigEntry:
        pass

    ha_config_entries.ConfigFlow = _ConfigFlow
    ha_config_entries.ConfigEntry = _ConfigEntry

    # homeassistant.const
    ha_const = types.ModuleType("homeassistant.const")

    class _UnitOfVolume:
        CUBIC_METERS = "m3"

    class _Platform:
        SENSOR = "sensor"

    ha_const.UnitOfVolume = _UnitOfVolume
    ha_const.Platform = _Platform

    # homeassistant.core
    ha_core = types.ModuleType("homeassistant.core")

    class _HomeAssistant:
        pass

    ha_core.HomeAssistant = _HomeAssistant

    # homeassistant.components.sensor
    ha_components_sensor = types.ModuleType("homeassistant.components.sensor")

    class _SensorEntity:
        pass

    class _SensorDeviceClass:
        WATER = "water"

    class _SensorStateClass:
        TOTAL_INCREASING = "total_increasing"

    ha_components_sensor.SensorEntity = _SensorEntity
    ha_components_sensor.SensorDeviceClass = _SensorDeviceClass
    ha_components_sensor.SensorStateClass = _SensorStateClass

    # homeassistant.helpers.entity_platform
    ha_helpers_entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    ha_helpers_entity_platform.AddEntitiesCallback = object

    # homeassistant.helpers.update_coordinator
    ha_helpers_update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    class _DataUpdateCoordinator:
        def __init__(self, *args, **kwargs):
            self.last_update_success = True

    class _UpdateFailed(Exception):
        pass

    ha_helpers_update_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
    ha_helpers_update_coordinator.UpdateFailed = _UpdateFailed

    # homeassistant (package root)
    ha_root = types.ModuleType("homeassistant")
    ha_root.config_entries = ha_config_entries

    stubs = {
        "homeassistant": ha_root,
        "homeassistant.config_entries": ha_config_entries,
        "homeassistant.const": ha_const,
        "homeassistant.core": ha_core,
        "homeassistant.components.sensor": ha_components_sensor,
        "homeassistant.helpers.entity_platform": ha_helpers_entity_platform,
        "homeassistant.helpers.update_coordinator": ha_helpers_update_coordinator,
    }

    # voluptuous is used by config flow; we only need enough for module import.
    vol = types.ModuleType("voluptuous")

    def _schema(x):
        return x

    def _required(key, default=None):
        return key

    vol.Schema = _schema
    vol.Required = _required
    stubs["voluptuous"] = vol

    # Minimal stubs for runtime deps used in sensor.py
    aiohttp = types.ModuleType("aiohttp")

    class _ClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("aiohttp.ClientSession.get stubbed in tests")

    aiohttp.ClientSession = _ClientSession
    stubs["aiohttp"] = aiohttp

    async_timeout = types.ModuleType("async_timeout")

    class _timeout:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async_timeout.timeout = _timeout
    stubs["async_timeout"] = async_timeout

    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)
