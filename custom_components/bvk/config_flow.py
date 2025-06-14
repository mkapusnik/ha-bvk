"""Config flow for BVK integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

# This is the schema that used to display the UI to the user
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BVK."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate the data can be used to set up a connection
                self._validate_input(user_input)

                # Create entry
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # If there is no user input or there were errors, show the form again
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    def _validate_input(self, data: dict) -> None:
        """Validate the user input allows us to connect."""
        # TODO: Validate the data can be used to set up a connection.
        # If it cannot, throw an exception.
        if len(data[CONF_NAME]) < 3:
            raise InvalidAuth

        # Validate username and password are not empty
        if not data[CONF_USERNAME] or not data[CONF_PASSWORD]:
            raise InvalidAuth


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
