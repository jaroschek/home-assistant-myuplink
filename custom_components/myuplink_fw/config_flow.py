"""Config flow for myUplink."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL, SCOPES

_LOGGER = logging.getLogger(__name__)


def get_options_schema(data: ConfigType) -> Schema:
    """Return the options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL))
        }
    )


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle myUplink OAuth2 authentication."""

    DOMAIN = DOMAIN

    _data: dict[str, Any] = {}

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(SCOPES)}

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the flow."""
        _LOGGER.debug("Finishing post-oauth configuration")
        if self.source == SOURCE_REAUTH:
            _LOGGER.debug("Skipping post-oauth configuration")
            return self.async_create_entry(title=self.flow_impl.name, data=data)
        self._data = data
        return await self.async_step_options()

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options step."""
        if user_input is None:
            return self.async_show_form(
                step_id="options", data_schema=get_options_schema(self._data)
            )
        return self.async_create_entry(
            title=self.flow_impl.name, data=self._data, options=user_input
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Options callback for Eaton ePDU."""
        return OptionsFlow(config_entry)


class OptionsFlow(OptionsFlowWithConfigEntry):
    """Options flow to handle myUplink options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize form."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title, data=user_input
            )
        return self.async_show_form(
            step_id="init", data_schema=get_options_schema(self.options)
        )
