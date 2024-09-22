"""Config flow for myUplink."""

from __future__ import annotations

from collections.abc import Mapping
import json
import logging
from typing import Any

import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_SCAN_INTERVAL, UnitOfTime
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow, selector
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ADDITIONAL_PARAMETER,
    CONF_DISCONNECTED_AVAILABLE,
    CONF_ENABLE_SMART_HOME_MODE,
    CONF_EXPERT_MODE,
    CONF_FETCH_FIRMWARE,
    CONF_FETCH_NOTIFICATIONS,
    CONF_PARAMETER_WHITELIST,
    CONF_PLATFORM_OVERRIDE,
    CONF_WRITABLE_OVERRIDE,
    DEFAULT_PLATFORM_OVERRIDE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WRITABLE_OVERRIDE,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SCAN_INTERVAL_STEP,
    SCOPES,
)

_LOGGER = logging.getLogger(__name__)


def get_options_schema(data: ConfigType) -> Schema:
    """Return the options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_ENABLE_SMART_HOME_MODE,
                default=data.get(CONF_ENABLE_SMART_HOME_MODE, True),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_FETCH_FIRMWARE, default=data.get(CONF_FETCH_FIRMWARE, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_FETCH_NOTIFICATIONS,
                default=data.get(CONF_FETCH_NOTIFICATIONS, True),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    mode=selector.NumberSelectorMode.BOX,
                    step=SCAN_INTERVAL_STEP,
                    unit_of_measurement=UnitOfTime.SECONDS,
                )
            ),
            vol.Required(
                CONF_DISCONNECTED_AVAILABLE,
                default=data.get(CONF_DISCONNECTED_AVAILABLE, False),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_EXPERT_MODE,
                default=data.get(CONF_EXPERT_MODE, False),
            ): selector.BooleanSelector(),
        }
    )


def get_expert_schema(data: ConfigType) -> Schema:
    """Return the expert schema."""
    try:
        platform_override = json.dumps(
            json.loads(
                data.get(CONF_PLATFORM_OVERRIDE, json.dumps(DEFAULT_PLATFORM_OVERRIDE))
            )
        )
    except json.decoder.JSONDecodeError:
        platform_override = json.dumps(DEFAULT_PLATFORM_OVERRIDE)

    try:
        writable_override = json.dumps(
            json.loads(
                data.get(CONF_WRITABLE_OVERRIDE, json.dumps(DEFAULT_WRITABLE_OVERRIDE))
            )
        )
    except json.decoder.JSONDecodeError:
        writable_override = json.dumps(DEFAULT_WRITABLE_OVERRIDE)

    try:
        parameter_whitlist = json.dumps(
            json.loads(data.get(CONF_PARAMETER_WHITELIST, "[]"))
        )
    except json.decoder.JSONDecodeError:
        parameter_whitlist = "[]"

    try:
        additional_parameter = json.dumps(
            json.loads(data.get(CONF_ADDITIONAL_PARAMETER, "[]"))
        )
    except json.decoder.JSONDecodeError:
        additional_parameter = "[]"

    return vol.Schema(
        {
            vol.Optional(
                CONF_PLATFORM_OVERRIDE,
                default=platform_override,
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_WRITABLE_OVERRIDE,
                default=writable_override,
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_PARAMETER_WHITELIST,
                default=parameter_whitlist,
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_ADDITIONAL_PARAMETER,
                default=additional_parameter,
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
        }
    )


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle myUplink OAuth2 authentication."""

    DOMAIN = DOMAIN

    _data: dict[str, Any] = {}

    _options: dict[str, Any] = {}

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
        self, options_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options step."""
        if options_input is None:
            return self.async_show_form(
                step_id="options", data_schema=get_options_schema(self._options)
            )
        self._options = options_input
        if options_input.get(CONF_EXPERT_MODE, False):
            return await self.async_step_expert()
        return self.async_create_entry(
            title=self.flow_impl.name, data=self._data, options=self._options
        )

    async def async_step_expert(
        self, expert_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the expert step."""
        if expert_input is None:
            return self.async_show_form(
                step_id="expert", data_schema=get_expert_schema(self._options)
            )
        self._options.update(expert_input)
        return self.async_create_entry(
            title=self.flow_impl.name, data=self._data, options=self._options
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
        return await self.async_step_options(options_input=user_input)

    async def async_step_options(
        self, options_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options step."""
        if options_input is None:
            return self.async_show_form(
                step_id="options", data_schema=get_options_schema(self.options)
            )
        self.options.update(options_input)
        if options_input.get(CONF_EXPERT_MODE, False):
            return await self.async_step_expert()
        return self.async_create_entry(title="", data=self.options)

    async def async_step_expert(
        self, expert_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the expert step."""
        if expert_input is None:
            return self.async_show_form(
                step_id="expert", data_schema=get_expert_schema(self.options)
            )
        self.options.update(expert_input)
        return self.async_create_entry(title="", data=self.options)
