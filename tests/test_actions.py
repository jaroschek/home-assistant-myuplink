"""Test failed entity actions and Home Assistant action signatures."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.myuplink.api import Device, Parameter, System, Zone
from custom_components.myuplink.climate import MyUplinkZoneClimateEntity
from custom_components.myuplink.number import MyUplinkParameterNumberEntity
from custom_components.myuplink.water_heater import MyUplinkWaterHeaterEntity


async def test_failed_temperature_write(
    coordinator: DataUpdateCoordinator[list[System]], device: Device, zone: Zone
) -> None:
    """Do not update the target or raw zone state after an API failure."""
    entity = MyUplinkZoneClimateEntity(coordinator, device, zone)
    with (
        patch.object(
            device.system.api,
            "patch_zone_property",
            new=AsyncMock(side_effect=HomeAssistantError()),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_set_temperature(temperature=23)
    assert entity.target_temperature == 21
    assert zone.setpoint_heating == 21


async def test_failed_number_write(
    coordinator: DataUpdateCoordinator[list[System]],
    device: Device,
    parameter: Parameter,
) -> None:
    """Reject writes to a point that became read-only."""
    entity = MyUplinkParameterNumberEntity(coordinator, device, parameter)
    with pytest.raises(ServiceValidationError):
        await entity.async_set_native_value(23)
    assert entity.native_value == 20


async def test_water_heater_temperature_contract(
    coordinator: DataUpdateCoordinator[list[System]],
    device: Device,
    parameter: Parameter,
) -> None:
    """Accept Home Assistant's temperature kwargs without requiring entity_id."""
    parameter.raw_data.update(parameterId="527", writable=True)
    with patch.object(MyUplinkWaterHeaterEntity, "_update_from_parameters"):
        entity = MyUplinkWaterHeaterEntity(coordinator, device)
    with (
        patch.object(device.system.api, "patch_parameter", new=AsyncMock()) as write,
        patch.object(entity, "async_update", new=AsyncMock()) as refresh,
    ):
        await entity.async_set_temperature(temperature=45)
    write.assert_awaited_once_with(device.id, "527", 45)
    refresh.assert_awaited_once()


async def test_command_only_zone(zone: Zone) -> None:
    """Unsupported command-only zones report validation errors."""
    zone.raw_data["commandOnly"] = True
    with pytest.raises(ServiceValidationError) as error:
        await zone.update_zone_property("setpoint", 23)
    assert error.value.translation_key == "zone_command_only"
