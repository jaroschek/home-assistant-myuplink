"""Test reload behavior for options and OAuth changes."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import jwt
import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    OAuth2Session,
)

from custom_components.myuplink.config_flow import OAuth2FlowHandler
from custom_components.myuplink.const import (
    CONF_ADDITIONAL_PARAMETER,
    CONF_EXPERT_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("setup_entry")


async def test_setup_has_no_update_listener(entry: ConfigEntry) -> None:
    """OAuth reload helpers must not be combined with an update listener."""
    assert entry.update_listeners == []


@pytest.mark.parametrize(
    ("scan_interval", "reload_count"),
    [
        pytest.param(DEFAULT_SCAN_INTERVAL, 0, id="unchanged"),
        pytest.param(60, 1, id="changed"),
    ],
)
async def test_options_reload(
    hass: HomeAssistant,
    entry: ConfigEntry,
    options_input: dict[str, bool | int],
    scan_interval: int,
    reload_count: int,
) -> None:
    """Save options and reload exactly once only when they change."""
    options = {**options_input, CONF_SCAN_INTERVAL: scan_interval}
    expected_options = {**entry.options, **options}

    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "options"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], options
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == expected_options
    assert reload.await_count == reload_count
    assert reload.call_args_list == [call(entry.entry_id)] * reload_count


async def test_expert_options_reload(
    hass: HomeAssistant, entry: ConfigEntry, options_input: dict[str, bool | int]
) -> None:
    """Wait for expert options before saving and reloading."""
    options = {**options_input, CONF_EXPERT_MODE: True, CONF_SCAN_INTERVAL: 60}
    original_options = dict(entry.options)

    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], options
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "expert"
        assert entry.options == original_options
        reload.assert_not_awaited()

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_ADDITIONAL_PARAMETER: "[54321]"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert options.items() <= entry.options.items()
    assert entry.options[CONF_ADDITIONAL_PARAMETER] == "[54321]"
    reload.assert_awaited_once_with(entry.entry_id)


async def test_cancel_expert_options(
    hass: HomeAssistant, entry: ConfigEntry, options_input: dict[str, bool | int]
) -> None:
    """Cancelling an expert flow must leave the entry unchanged."""
    original_options = dict(entry.options)

    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {**options_input, CONF_EXPERT_MODE: True}
        )
        hass.config_entries.options.async_abort(result["flow_id"])
        await hass.async_block_till_done()

    assert entry.options == original_options
    reload.assert_not_awaited()


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        pytest.param(SOURCE_REAUTH, "reauth_successful", id="reauth"),
        pytest.param(SOURCE_RECONFIGURE, "reconfigure_successful", id="reconfigure"),
    ],
)
@pytest.mark.parametrize(
    "token_claims",
    [
        pytest.param({"sub": "test-account"}, id="unchanged-token"),
        pytest.param({"sub": "test-account", "jti": "new"}, id="new-token"),
    ],
)
async def test_oauth_reload(
    hass: HomeAssistant,
    entry: ConfigEntry,
    source: str,
    reason: str,
    token_claims: dict[str, str],
) -> None:
    """Reload after OAuth completion without reporting deprecated listener usage."""
    token = {
        **entry.data["token"],
        "access_token": jwt.encode(
            token_claims,
            "test-secret-for-myuplink-regression-tests",
            algorithm="HS256",
        ),
    }
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": source, "entry_id": entry.entry_id}

    with (
        patch.object(hass.config_entries, "async_reload", return_value=True) as reload,
        patch("homeassistant.config_entries.report_usage") as report_usage,
    ):
        result = await flow.async_oauth_create_entry(
            {"auth_implementation": DOMAIN, "token": token}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert entry.data["token"] == token
    assert entry.data["other_data"] == "preserved"
    reload.assert_awaited_once_with(entry.entry_id)
    report_usage.assert_not_called()


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(SOURCE_REAUTH, id="reauth"),
        pytest.param(SOURCE_RECONFIGURE, id="reconfigure"),
    ],
)
async def test_oauth_account_mismatch(
    hass: HomeAssistant, entry: ConfigEntry, source: str
) -> None:
    """Reject an OAuth response for a different account without reloading."""
    original_data = dict(entry.data)
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": source, "entry_id": entry.entry_id}

    with (
        patch.object(hass.config_entries, "async_reload", return_value=True) as reload,
        pytest.raises(AbortFlow) as error,
    ):
        await flow.async_oauth_create_entry(
            {
                "auth_implementation": DOMAIN,
                "token": {
                    "access_token": jwt.encode(
                        {"sub": "different-account"},
                        "test-secret-for-myuplink-regression-tests",
                        algorithm="HS256",
                    )
                },
            }
        )

    assert error.value.reason == "unique_id_mismatch"
    assert entry.data == original_data
    reload.assert_not_awaited()


async def test_token_refresh_does_not_reload(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A background OAuth token refresh must not reload the integration."""
    token = {**entry.data["token"], "access_token": "refreshed", "expires_at": 3600}
    implementation = MagicMock(spec=AbstractOAuth2Implementation)
    implementation.async_refresh_token = AsyncMock(return_value=token)
    session = OAuth2Session(hass, entry, implementation)

    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        await session.async_ensure_token_valid()
        await hass.async_block_till_done()

    assert entry.data["token"] == token
    implementation.async_refresh_token.assert_awaited_once()
    reload.assert_not_awaited()
