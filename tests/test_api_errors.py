"""Test cloud backoff and write failure contracts."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import (
    ClientConnectionError,
    ClientResponse,
    ClientResponseError,
    ClientSession,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.myuplink.api import (
    AsyncConfigEntryAuth,
    MyUplink,
    MyUplinkRateLimitError,
    Parameter,
    System,
    Throttle,
)
from custom_components.myuplink.coordinator import MyUplinkCoordinator


@pytest.fixture
def response() -> MagicMock:
    """Provide a response whose body and headers can be adjusted per scenario."""
    result = MagicMock(spec=ClientResponse)
    result.status = 200
    result.headers = {}
    result.json = AsyncMock(return_value={"payload": {"state": "ok"}})
    result.read = AsyncMock(return_value=b"")
    return result


@pytest.fixture
def auth(response: MagicMock) -> AsyncConfigEntryAuth:
    """Provide OAuth and HTTP session mocks around the real auth helper."""
    session = MagicMock(spec=ClientSession)
    session.request = AsyncMock(return_value=response)
    oauth = MagicMock()
    oauth.async_ensure_token_valid = AsyncMock()
    oauth.token = {"access_token": "synthetic-token"}
    return AsyncConfigEntryAuth(session, oauth)


@pytest.mark.parametrize(
    ("headers", "seconds"),
    [
        pytest.param({"Retry-After": "90"}, 90, id="retry-after"),
        pytest.param({"RateLimit-Reset": "120"}, 120, id="reset-window"),
        pytest.param(
            {"Retry-After": "invalid", "RateLimit-Reset": "not-a-number"},
            60,
            id="invalid-headers",
        ),
        pytest.param({}, 60, id="missing-headers"),
    ],
)
async def test_429_does_not_sleep(
    auth: AsyncConfigEntryAuth,
    response: MagicMock,
    headers: dict[str, str],
    seconds: int,
) -> None:
    """Release the failed response and retry on a future coordinator update."""
    response.status = 429
    response.headers = headers
    with (
        patch("custom_components.myuplink.api.asyncio.sleep") as sleep,
        pytest.raises(MyUplinkRateLimitError) as error,
    ):
        await auth.request("get", "systems/me")
    assert seconds - 1 <= error.value.retry_after <= seconds
    assert auth.rate_limit_remaining == 0
    response.release.assert_called_once()
    sleep.assert_not_called()


async def test_http_date_retry_after(
    auth: AsyncConfigEntryAuth, response: MagicMock
) -> None:
    """Support the HTTP-date form of Retry-After."""
    response.status = 429
    response.headers = {
        "Retry-After": format_datetime(
            datetime.now(UTC) + timedelta(seconds=120), usegmt=True
        )
    }
    with pytest.raises(MyUplinkRateLimitError) as error:
        await auth.request("get", "systems/me")
    assert 118 <= error.value.retry_after <= 120


async def test_exhausted_window(auth: AsyncConfigEntryAuth) -> None:
    """Avoid issuing requests before the server's window reset."""
    auth.rate_limit_remaining = 0
    auth.rate_limit_reset_at = datetime.now(UTC) + timedelta(seconds=90)
    with (
        patch("custom_components.myuplink.api.asyncio.sleep") as sleep,
        pytest.raises(MyUplinkRateLimitError) as error,
    ):
        async with Throttle(auth):
            pytest.fail("An exhausted window must not issue a request")
    assert 89 <= error.value.retry_after <= 90
    sleep.assert_not_called()


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        pytest.param(
            ClientResponseError(MagicMock(), (), status=500),
            "api_error",
            id="server-error",
        ),
        pytest.param(ClientConnectionError(), "connection_error", id="network"),
        pytest.param(TimeoutError(), "connection_error", id="timeout"),
        pytest.param(MyUplinkRateLimitError(60), "rate_limited", id="rate-limited"),
    ],
)
async def test_write_errors(
    api: MyUplink, error: Exception, translation_key: str
) -> None:
    """Never silently return success after a rejected parameter write."""
    with (
        patch.object(api.auth, "request", new=AsyncMock(side_effect=error)),
        pytest.raises(HomeAssistantError) as raised,
    ):
        await api.patch_parameter("device-1", "123", 20)
    assert raised.value.translation_key == translation_key


@pytest.mark.parametrize(
    "status", [pytest.param(401, id="unauthorized"), pytest.param(403, id="forbidden")]
)
async def test_write_starts_reauth(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: MyUplink,
    response: MagicMock,
    status: int,
) -> None:
    """A failed authenticated write also offers account reauthorization."""
    entry.runtime_data = MyUplinkCoordinator(hass, entry, api)
    response.raise_for_status.side_effect = ClientResponseError(
        MagicMock(), (), status=status
    )
    with (
        patch.object(api.auth, "request", new=AsyncMock(return_value=response)),
        patch.object(ConfigEntry, "async_start_reauth") as reauth,
        pytest.raises(HomeAssistantError),
    ):
        await api.patch_zone_property("device-1", "zone-1", "setpoint", "20")
    reauth.assert_called_once_with(hass)


@pytest.mark.parametrize(
    "status", [pytest.param(200, id="ok"), pytest.param(204, id="no-content")]
)
async def test_write_success(api: MyUplink, response: MagicMock, status: int) -> None:
    """Accept successful 2xx writes even without a response body."""
    response.status = status
    with patch.object(
        api.auth, "request", new=AsyncMock(return_value=response)
    ) as request:
        await api.patch_parameter("device-1", "123", 20)
        await api.patch_zone_property("device-1", "zone-1", "setpoint", "20")
        await api.put_smart_home_mode("system-1", "Home")
    assert request.await_count == 3


async def test_smart_mode_rejected(api: MyUplink, response: MagicMock) -> None:
    """A 200 response with a failed command payload is still a failed write."""
    response.json.return_value = {"payload": {"state": "error"}}
    with (
        patch.object(api.auth, "request", new=AsyncMock(return_value=response)),
        pytest.raises(HomeAssistantError) as error,
    ):
        await api.put_smart_home_mode("system-1", "Away")
    assert error.value.translation_key == "write_rejected"


async def test_smart_mode_invalid_response(api: MyUplink, response: MagicMock) -> None:
    """Invalid command confirmation is a visible action error."""
    response.json.side_effect = ValueError("Invalid JSON")
    with (
        patch.object(api.auth, "request", new=AsyncMock(return_value=response)),
        pytest.raises(HomeAssistantError) as error,
    ):
        await api.put_smart_home_mode("system-1", "Away")
    assert error.value.translation_key == "write_rejected"


async def test_read_only_parameter(parameter: Parameter) -> None:
    """A read-only point cannot pretend to accept a value."""
    with pytest.raises(ServiceValidationError) as error:
        await parameter.update_parameter(21)
    assert error.value.translation_key == "parameter_not_writable"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ClientResponseError(MagicMock(), (), status=500), id="http-500"),
        pytest.param(ClientResponseError(MagicMock(), (), status=502), id="http-502"),
        pytest.param(ClientResponseError(MagicMock(), (), status=503), id="http-503"),
        pytest.param(ClientResponseError(MagicMock(), (), status=504), id="http-504"),
        pytest.param(ClientConnectionError(), id="connection"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_subscription_outage_logged_once(
    api: MyUplink,
    system: System,
    response: MagicMock,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Keep known permissions during repeated failures of the optional endpoint."""
    response.json.return_value = {"subscriptions": [{"type": "manage"}]}
    with (
        patch("custom_components.myuplink.api.monotonic", side_effect=[0, 901, 902]),
        patch.object(
            api.auth, "request", new=AsyncMock(side_effect=[response, error, error])
        ),
    ):
        assert await api.get_premium_manage(system)
        assert await api.get_premium_manage(system)
        assert await api.get_premium_manage(system)
    assert caplog.text.count("subscription lookup failed") == 1


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(401, id="unauthorized"),
        pytest.param(403, id="forbidden"),
        pytest.param(429, id="rate-limited"),
    ],
)
async def test_subscription_errors_propagate(
    api: MyUplink, system: System, status: int
) -> None:
    """Subscription lookup must not hide expired authentication or rate limits."""
    with (
        patch.object(
            api.auth,
            "request",
            new=AsyncMock(
                side_effect=ClientResponseError(MagicMock(), (), status=status)
            ),
        ),
        pytest.raises(ClientResponseError),
    ):
        await api.get_premium_manage(system)


async def test_unconfirmed_redirect(api: MyUplink, response: MagicMock) -> None:
    """An unhandled redirect is not confirmation of a completed write."""
    response.status = 302
    with (
        patch.object(api.auth, "request", new=AsyncMock(return_value=response)),
        pytest.raises(HomeAssistantError) as error,
    ):
        await api.patch_parameter("device-1", "123", 20)
    assert error.value.translation_key == "write_rejected"


async def test_headers_and_timeout(
    auth: AsyncConfigEntryAuth, response: MagicMock
) -> None:
    """Preserve caller headers and enforce the HTTP timeout alongside OAuth."""
    response.headers = {
        "RateLimit-Limit": "25",
        "RateLimit-Remaining": "5",
        "RateLimit-Reset": "60",
    }
    assert (
        await auth.request("get", "systems/me", headers={"Accept-Language": "de-DE"})
        is response
    )
    request = auth._websession.request.call_args
    assert request.args == ("get", "https://api.myuplink.com/v2/systems/me")
    assert request.kwargs["headers"] == {
        "Accept-Language": "de-DE",
        "authorization": "Bearer synthetic-token",
    }
    assert request.kwargs["timeout"].total == 30
    assert auth.rate_limit_limit == 25
    assert auth.rate_limit_remaining == 5
    assert 59 <= (auth.rate_limit_reset_at - datetime.now(UTC)).total_seconds() <= 60


@pytest.mark.parametrize(
    ("remaining", "reset_offset", "elapsed", "sleep_expected"),
    [
        pytest.param(5, 60, 0, True, id="pace-low-window"),
        pytest.param(5, 60, 3, False, id="already-paced"),
        pytest.param(0, -1, 3, False, id="expired-window"),
    ],
)
async def test_throttle_pacing(
    auth: AsyncConfigEntryAuth,
    remaining: int,
    reset_offset: int,
    elapsed: int,
    sleep_expected: bool,
) -> None:
    """Pace only requests near the limit and permit expired windows to resume."""
    auth.rate_limit_remaining = remaining
    auth.rate_limit_reset_at = datetime.now(UTC) + timedelta(seconds=reset_offset)
    throttle = Throttle(auth)
    throttle._last_request_time = datetime.now(UTC) - timedelta(seconds=elapsed)
    with patch("custom_components.myuplink.api.asyncio.sleep") as sleep:
        async with throttle:
            pass
    assert sleep.called is sleep_expected


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(None, id="null-body"),
        pytest.param([], id="array-body"),
        pytest.param({"payload": None}, id="null-payload"),
        pytest.param({"payload": {}}, id="missing-confirmation"),
    ],
)
async def test_malformed_mode_confirmation(
    api: MyUplink, response: MagicMock, data: object
) -> None:
    """An unexpected JSON structure is reported as a failed action."""
    response.json.return_value = data
    with (
        patch.object(api.auth, "request", return_value=response),
        pytest.raises(HomeAssistantError) as error,
    ):
        await api.put_smart_home_mode("system-1", "Away")
    assert error.value.translation_key == "write_rejected"
