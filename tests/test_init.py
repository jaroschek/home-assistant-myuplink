"""Test entry initialization, unloading, and migration."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import ClientConnectionError, ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.myuplink import (
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.myuplink.const import PLATFORMS


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(
            ClientResponseError(MagicMock(), (), status=HTTPStatus.UNAUTHORIZED),
            ConfigEntryAuthFailed,
            id="unauthorized",
        ),
        pytest.param(
            ClientResponseError(MagicMock(), (), status=HTTPStatus.FORBIDDEN),
            ConfigEntryAuthFailed,
            id="forbidden",
        ),
        pytest.param(
            ClientResponseError(MagicMock(), (), status=HTTPStatus.SERVICE_UNAVAILABLE),
            ConfigEntryNotReady,
            id="server-unavailable",
        ),
        pytest.param(
            ClientConnectionError("Connection failed"),
            ConfigEntryNotReady,
            id="connection-failed",
        ),
        pytest.param(TimeoutError(), ConfigEntryNotReady, id="token-timeout"),
    ],
)
async def test_token_failure(
    hass: HomeAssistant,
    entry: ConfigEntry,
    error: Exception,
    expected: type[Exception],
) -> None:
    """Classify token errors before loading any platform."""
    with (
        patch(
            "custom_components.myuplink.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch("custom_components.myuplink.config_entry_oauth2_flow.OAuth2Session"),
        patch("custom_components.myuplink.aiohttp_client.async_get_clientsession"),
        patch("custom_components.myuplink.AsyncConfigEntryAuth", autospec=True) as auth,
        patch.object(hass.config_entries, "async_forward_entry_setups") as forward,
        pytest.raises(expected),
    ):
        auth.return_value.async_get_access_token.side_effect = error
        await async_setup_entry(hass, entry)
    forward.assert_not_awaited()


async def test_missing_scope(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ask for authorization again when account permissions are incomplete."""
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, "token": {**entry.data["token"], "scope": "READSYSTEM"}},
    )
    with (
        patch(
            "custom_components.myuplink.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch("custom_components.myuplink.config_entry_oauth2_flow.OAuth2Session"),
        patch("custom_components.myuplink.aiohttp_client.async_get_clientsession"),
        patch("custom_components.myuplink.AsyncConfigEntryAuth", autospec=True),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await async_setup_entry(hass, entry)


@pytest.mark.parametrize(
    "unload_ok",
    [pytest.param(True, id="success"), pytest.param(False, id="failure")],
)
async def test_unload(hass: HomeAssistant, entry: ConfigEntry, unload_ok: bool) -> None:
    """Return the platform unload result without losing failed platforms."""
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=unload_ok
    ) as unload:
        assert await async_unload_entry(hass, entry) is unload_ok
    unload.assert_awaited_once_with(entry, PLATFORMS)


@pytest.mark.parametrize(
    "minor_version",
    [pytest.param(1, id="legacy"), pytest.param(2, id="current")],
)
async def test_migrate(
    hass: HomeAssistant, entry: ConfigEntry, minor_version: int
) -> None:
    """Migrate account identity without changing credentials or options."""
    hass.config_entries.async_update_entry(entry, minor_version=minor_version)
    original_data = dict(entry.data)
    original_options = dict(entry.options)
    assert await async_migrate_entry(hass, entry)
    assert entry.unique_id == "test-account"
    assert entry.minor_version == 2
    assert entry.data == original_data
    assert entry.options == original_options
