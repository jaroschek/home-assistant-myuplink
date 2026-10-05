"""Test polling error classification, backoff, and recovery."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectionError, ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.myuplink.api import MyUplink, MyUplinkRateLimitError, System
from custom_components.myuplink.coordinator import MyUplinkCoordinator


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(
            ClientResponseError(MagicMock(), (), status=401),
            ConfigEntryAuthFailed,
            id="expired-auth",
        ),
        pytest.param(
            ClientResponseError(MagicMock(), (), status=403),
            ConfigEntryAuthFailed,
            id="revoked-access",
        ),
        pytest.param(
            ClientResponseError(MagicMock(), (), status=503),
            UpdateFailed,
            id="server-unavailable",
        ),
        pytest.param(ClientConnectionError(), UpdateFailed, id="network-failure"),
        pytest.param(TimeoutError(), UpdateFailed, id="timeout"),
    ],
)
async def test_polling_error(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: MyUplink,
    error: Exception,
    expected: type[Exception],
) -> None:
    """Keep authorization failures distinct from temporary outages."""
    coordinator = MyUplinkCoordinator(hass, entry, api)
    with patch.object(api, "get_systems", side_effect=error), pytest.raises(expected):
        await coordinator._async_update_data()


async def test_rate_limit_backoff(
    hass: HomeAssistant, entry: ConfigEntry, api: MyUplink
) -> None:
    """Pass server backoff to Home Assistant's retry scheduler."""
    coordinator = MyUplinkCoordinator(hass, entry, api)
    with (
        patch.object(api, "get_systems", side_effect=MyUplinkRateLimitError(90)),
        pytest.raises(UpdateFailed) as error,
    ):
        await coordinator._async_update_data()
    assert error.value.retry_after == 90


async def test_failure_logged_once_and_recovery(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: MyUplink,
    system: System,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Repeated outages produce one error and recover with fresh data."""
    coordinator = MyUplinkCoordinator(hass, entry, api)
    with patch.object(
        api,
        "get_systems",
        new=AsyncMock(
            side_effect=[ClientConnectionError(), ClientConnectionError(), [system]]
        ),
    ):
        await coordinator.async_refresh()
        assert not coordinator.last_update_success
        await coordinator.async_refresh()
        await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data == [system]
    assert coordinator.update_interval == timedelta(seconds=300)
    assert caplog.text.count("Error fetching myUplink data") == 1


@pytest.mark.parametrize(
    "status",
    [pytest.param(401, id="expired-auth"), pytest.param(403, id="revoked-access")],
)
async def test_runtime_reauth(
    hass: HomeAssistant, entry: ConfigEntry, api: MyUplink, status: int
) -> None:
    """A runtime authentication failure starts Home Assistant reauthentication."""
    coordinator = MyUplinkCoordinator(hass, entry, api)
    with (
        patch.object(
            api,
            "get_systems",
            side_effect=ClientResponseError(MagicMock(), (), status=status),
        ),
        patch.object(ConfigEntry, "async_start_reauth") as reauth,
    ):
        await coordinator.async_refresh()
    assert not coordinator.last_update_success
    reauth.assert_called_once_with(hass, None, None)
