"""Test first-time OAuth setup and configuration error recovery."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    async_register_implementation,
)

from custom_components.myuplink.application_credentials import (
    async_get_authorization_server,
)
from custom_components.myuplink.config_flow import (
    OAuth2FlowHandler,
    get_expert_schema,
)
from custom_components.myuplink.const import (
    CONF_ADDITIONAL_PARAMETER,
    CONF_EXPERT_MODE,
    CONF_PARAMETER_WHITELIST,
    CONF_PLATFORM_OVERRIDE,
    CONF_WRITABLE_OVERRIDE,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    SCOPES,
)


@pytest.fixture
def oauth_implementation(hass: HomeAssistant) -> MagicMock:
    """Provide an OAuth provider without making network requests."""
    implementation = MagicMock(spec=AbstractOAuth2Implementation)
    implementation.name = "myUplink"
    implementation.domain = DOMAIN
    implementation.async_generate_authorize_url = AsyncMock(
        return_value="https://api.myuplink.com/oauth/authorize"
    )
    implementation.async_resolve_external_data = AsyncMock(
        return_value={
            "access_token": jwt.encode(
                {"sub": "new-account"},
                "test-oauth-secret-at-least-32-bytes-long",
                algorithm="HS256",
            ),
            "refresh_token": "test-refresh-token",
            "scope": " ".join(SCOPES),
            "expires_in": 3600,
        }
    )
    async_register_implementation(hass, DOMAIN, implementation)
    return implementation


@pytest.fixture
def flow(hass: HomeAssistant, oauth_implementation: MagicMock) -> OAuth2FlowHandler:
    """Provide a new account's flow."""
    handler = OAuth2FlowHandler()
    handler.hass = hass
    handler.handler = DOMAIN
    handler.context = {"source": SOURCE_USER}
    handler.flow_impl = oauth_implementation
    return handler


@pytest.mark.usefixtures("oauth_implementation")
async def test_complete_initial_flow(
    hass: HomeAssistant, options_input: dict[str, bool | int]
) -> None:
    """Create an account only after completing OAuth and the options step."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_setup", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "pick_implementation"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"implementation": DOMAIN}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert "READSYSTEM" in result["url"]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "test-code"}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["step_id"] == "options"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], options_input
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "new-account"
    assert result["result"].options == options_input


async def test_initial_expert_flow(
    flow: OAuth2FlowHandler, options_input: dict[str, bool | int]
) -> None:
    """Save expert options together with initial account credentials."""
    result = await flow.async_step_creation()
    assert result["step_id"] == "options"
    result = await flow.async_step_options({**options_input, CONF_EXPERT_MODE: True})
    assert result["step_id"] == "expert"
    result = await flow.async_step_expert({CONF_ADDITIONAL_PARAMETER: "[54321]"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_ADDITIONAL_PARAMETER] == "[54321]"
    assert result["options"][CONF_EXPERT_MODE] is True


async def test_duplicate_account(flow: OAuth2FlowHandler, entry: ConfigEntry) -> None:
    """Reject an account that already has a config entry."""
    with pytest.raises(AbortFlow) as error:
        await flow.async_oauth_create_entry(dict(entry.data))
    assert error.value.reason == "already_configured"


@pytest.mark.parametrize(
    "field",
    [
        pytest.param(CONF_PLATFORM_OVERRIDE, id="platform-override"),
        pytest.param(CONF_WRITABLE_OVERRIDE, id="writable-override"),
        pytest.param(CONF_PARAMETER_WHITELIST, id="parameter-whitelist"),
        pytest.param(CONF_ADDITIONAL_PARAMETER, id="additional-parameters"),
    ],
)
def test_legacy_invalid_expert_options(field: str) -> None:
    """Legacy invalid JSON must not prevent reopening the options form."""
    schema = get_expert_schema({field: "invalid-json"})
    assert schema({})[field] != "invalid-json"


async def test_reauth_confirmation(flow: OAuth2FlowHandler, entry: ConfigEntry) -> None:
    """Reauthentication asks for confirmation before contacting the provider."""
    flow.context = {"source": SOURCE_REAUTH, "entry_id": entry.entry_id}
    result = await flow.async_step_reauth(entry.data)
    assert result["step_id"] == "reauth_confirm"
    with patch.object(
        flow, "async_step_user", return_value={"type": FlowResultType.FORM}
    ) as user:
        await flow.async_step_reauth_confirm({})
    user.assert_awaited_once_with()


async def test_reconfigure_starts_oauth(flow: OAuth2FlowHandler) -> None:
    """Reconfiguration returns to OAuth account authorization."""
    with patch.object(
        flow, "async_step_user", return_value={"type": FlowResultType.FORM}
    ) as user:
        await flow.async_step_reconfigure()
    user.assert_awaited_once_with()


async def test_oauth_error_recovery(
    flow: OAuth2FlowHandler, oauth_implementation: MagicMock
) -> None:
    """A fresh attempt can succeed after the OAuth provider times out."""
    oauth_implementation.async_resolve_external_data.side_effect = [
        TimeoutError,
        oauth_implementation.async_resolve_external_data.return_value,
    ]
    flow.external_data = {"code": "test-code"}
    result = await flow.async_step_creation()
    assert result["reason"] == "oauth_timeout"
    result = await flow.async_step_creation()
    assert result["step_id"] == "options"
    assert flow.logger is logging.getLogger("custom_components.myuplink.config_flow")


async def test_authorization_server(hass: HomeAssistant) -> None:
    """Publish the myUplink OAuth endpoints to application credentials."""
    server = await async_get_authorization_server(hass)
    assert server.authorize_url == OAUTH2_AUTHORIZE
    assert server.token_url == OAUTH2_TOKEN
