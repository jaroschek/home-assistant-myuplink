"""Test action registration, permissions, and account selection."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import device_registry as dr

from custom_components.myuplink import async_setup, async_unload_entry
from custom_components.myuplink.const import DOMAIN
from custom_components.myuplink.services import (
    SERVICE_LIST,
    SERVICE_SET_DEVICE_PARAMETER_VALUE,
    SERVICE_SET_DEVICE_ZONE_PROPERTY_VALUE,
)


async def test_actions_without_account(hass: HomeAssistant) -> None:
    """Actions exist even when no account has loaded."""
    assert await async_setup(hass, {})
    assert await async_setup(hass, {})
    for service, _ in SERVICE_LIST:
        assert hass.services.has_service(DOMAIN, service)
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_PARAMETER_VALUE,
            {"device_id": "missing-device", "parameter_id": "123", "value": "20"},
            blocking=True,
        )
    assert error.value.translation_key == "device_not_found"


async def test_actions_survive_unload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unloading one account does not remove integration actions."""
    await async_setup(hass, {})
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        assert await async_unload_entry(hass, entry)
    for service, _ in SERVICE_LIST:
        assert hass.services.has_service(DOMAIN, service)


async def test_raw_action_requires_admin(hass: HomeAssistant) -> None:
    """A non-admin cannot write arbitrary configuration parameters."""
    await async_setup(hass, {})
    hass.auth = MagicMock()
    hass.auth.async_get_user = AsyncMock(return_value=SimpleNamespace(is_admin=False))
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEVICE_PARAMETER_VALUE,
            {"device_id": "any-device", "parameter_id": "123", "value": "20"},
            blocking=True,
            context=Context(user_id="non-admin"),
        )


@pytest.mark.parametrize(
    ("service", "fields", "method", "expected"),
    [
        pytest.param(
            SERVICE_SET_DEVICE_PARAMETER_VALUE,
            {"parameter_id": "123", "value": "20"},
            "patch_parameter",
            ("api-device", "123", "20"),
            id="parameter",
        ),
        pytest.param(
            SERVICE_SET_DEVICE_ZONE_PROPERTY_VALUE,
            {"zone_id": "zone-1", "property_name": "setpoint", "value": "20"},
            "patch_zone_property",
            ("api-device", "zone-1", "setpoint", "20"),
            id="zone",
        ),
    ],
)
async def test_select_loaded_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    service: str,
    fields: dict[str, str],
    method: str,
    expected: tuple[str, ...],
) -> None:
    """Route an admin action to the selected account's API device."""
    await async_setup(hass, {})
    entry._async_set_state(hass, ConfigEntryState.LOADED, None)
    api = MagicMock()
    api.patch_parameter = AsyncMock()
    api.patch_zone_property = AsyncMock()
    device = SimpleNamespace(id="api-device", system=SimpleNamespace(api=api))
    entry.runtime_data = SimpleNamespace(data=[SimpleNamespace(devices=[device])])
    registered = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device.id)},
        name="Heat pump",
    )
    hass.auth = MagicMock()
    hass.auth.async_get_user = AsyncMock(return_value=SimpleNamespace(is_admin=True))
    await hass.services.async_call(
        DOMAIN,
        service,
        {"device_id": registered.id, **fields},
        blocking=True,
        context=Context(user_id="admin"),
    )
    getattr(api, method).assert_awaited_once_with(*expected)
