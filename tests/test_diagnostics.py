"""Test diagnostic redaction and manual removal of absent devices."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.myuplink import async_remove_config_entry_device
from custom_components.myuplink.api import Device
from custom_components.myuplink.const import DOMAIN
from custom_components.myuplink.coordinator import MyUplinkCoordinator
from custom_components.myuplink.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_cached_and_redacted(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: MyUplinkCoordinator,
    device: Device,
) -> None:
    """Diagnostics neither disclose identifiers and credentials nor call the cloud."""
    with patch.object(coordinator.api.auth, "request", new=AsyncMock()) as request:
        result = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(result)
    for secret in (
        entry.data["token"]["access_token"],
        entry.data["token"]["refresh_token"],
        entry.unique_id,
        device.serial_number,
        device.id,
        device.system.id,
        device.name,
        "Living room",
    ):
        assert secret not in serialized
    assert result["coordinator"]["last_update_success"]
    assert result["systems"][0]["devices"][0]["parameters"][0]["id"] == 123
    request.assert_not_awaited()


async def test_diagnostics_unloaded(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unloaded entries still provide redacted configuration diagnostics."""
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert set(result) == {"config_entry"}
    assert result["config_entry"]["data"] == "**REDACTED**"


@pytest.mark.parametrize(
    "present",
    [pytest.param(True, id="in-use"), pytest.param(False, id="removed-from-cloud")],
)
async def test_manual_device_removal(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: MyUplinkCoordinator,
    device: Device,
    present: bool,
) -> None:
    """Keep active devices and allow users to remove absent ones explicitly."""
    registered = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, device.id)}
    )
    coordinator.async_set_updated_data({True: [device.system], False: []}[present])
    assert (
        await async_remove_config_entry_device(hass, entry, registered) is not present
    )


async def test_remove_from_unloaded_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Allow cleanup when the account cannot be loaded."""
    registered = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "old-device")}
    )
    assert await async_remove_config_entry_device(hass, entry, registered)
