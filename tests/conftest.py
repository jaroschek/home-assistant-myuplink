"""Local Home Assistant fixtures for the myUplink regression tests."""

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

import jwt
import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame

from custom_components.myuplink import async_setup_entry
from custom_components.myuplink.config_flow import OAuth2FlowHandler
from custom_components.myuplink.const import (
    CONF_ADDITIONAL_PARAMETER,
    CONF_DISCONNECTED_AVAILABLE,
    CONF_ENABLE_SMART_HOME_MODE,
    CONF_ENABLE_SMART_HOME_ZONE,
    CONF_EXPERT_MODE,
    CONF_FETCH_FIRMWARE,
    CONF_FETCH_NOTIFICATIONS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SCOPES,
)


@pytest.fixture
async def hass(tmp_path: Path) -> AsyncGenerator[HomeAssistant]:
    """Provide Home Assistant without starting integrations or writing config."""
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    frame.async_setup(instance)
    loader.async_setup(instance)
    with patch.object(instance.config_entries, "_async_schedule_save"):
        yield instance
        await instance.async_stop()


@pytest.fixture
def entry(hass: HomeAssistant) -> ConfigEntry:
    """Provide a registered OAuth entry with existing expert options."""
    config_entry = ConfigEntry(
        domain=DOMAIN,
        title="myUplink",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": jwt.encode(
                    {"sub": "test-account"},
                    "test-secret-for-myuplink-regression-tests",
                    algorithm="HS256",
                ),
                "refresh_token": "test-refresh-token",
                "scope": " ".join(SCOPES),
                "expires_at": 0,
            },
            "other_data": "preserved",
        },
        options={
            CONF_ENABLE_SMART_HOME_MODE: True,
            CONF_ENABLE_SMART_HOME_ZONE: True,
            CONF_FETCH_FIRMWARE: True,
            CONF_FETCH_NOTIFICATIONS: True,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_DISCONNECTED_AVAILABLE: False,
            CONF_EXPERT_MODE: False,
            CONF_ADDITIONAL_PARAMETER: "[12345]",
        },
        source="user",
        version=1,
        minor_version=2,
        unique_id="test-account",
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )
    hass.config_entries._entries[config_entry.entry_id] = config_entry  # noqa: SLF001
    return config_entry


@pytest.fixture
def options_input(entry: ConfigEntry) -> dict[str, bool | int]:
    """Provide the general options separately from existing expert options."""
    options = dict(entry.options)
    del options[CONF_ADDITIONAL_PARAMETER]
    return options


@pytest.fixture(autouse=True)
def mock_flow_handler() -> Generator[None]:
    """Load the custom flow instead of Home Assistant's built-in integration."""
    with patch(
        "homeassistant.config_entries._async_get_flow_handler",
        return_value=OAuth2FlowHandler,
    ):
        yield


@pytest.fixture
async def setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the entry without making API requests or loading platforms."""
    with (
        patch(
            "custom_components.myuplink.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch("custom_components.myuplink.config_entry_oauth2_flow.OAuth2Session"),
        patch("custom_components.myuplink.aiohttp_client.async_get_clientsession"),
        patch("custom_components.myuplink.AsyncConfigEntryAuth", autospec=True),
        patch("custom_components.myuplink.DataUpdateCoordinator", autospec=True),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch("custom_components.myuplink.async_setup_services"),
    ):
        assert await async_setup_entry(hass, entry)
