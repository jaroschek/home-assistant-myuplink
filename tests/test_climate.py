"""Test smart-home thermostat modes and fresh optional readings."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.const import UnitOfTemperature

from custom_components.myuplink.api import Device, Zone
from custom_components.myuplink.climate import MyUplinkZoneClimateEntity
from custom_components.myuplink.coordinator import MyUplinkCoordinator


@pytest.mark.parametrize(
    ("mode", "target"),
    [
        pytest.param("heat", 21, id="heating"),
        pytest.param("cool", 24, id="cooling"),
        pytest.param("heatcool", 22, id="shared-setpoint"),
    ],
)
def test_zone_target(
    coordinator: MyUplinkCoordinator, device: Device, zone: Zone, mode: str, target: int
) -> None:
    """Heat-cool mode uses its shared target instead of the cooling target."""
    zone.raw_data.update(mode=mode, setpoint=22, indoorHumidity=0)
    entity = MyUplinkZoneClimateEntity(coordinator, device, zone)
    assert entity.target_temperature == target
    assert entity.current_humidity == 0


@pytest.mark.parametrize(
    ("supported", "mode", "expected"),
    [
        pytest.param(
            "heat,unsupported", "heat", [HVACMode.HEAT], id="unknown-reported-mode"
        ),
        pytest.param("", "cool", [HVACMode.COOL], id="current-mode-only"),
        pytest.param(None, "unsupported", [], id="no-supported-mode"),
    ],
)
def test_supported_modes(
    coordinator: MyUplinkCoordinator,
    device: Device,
    zone: Zone,
    supported: str | None,
    mode: str,
    expected: list[HVACMode],
) -> None:
    """Unsupported cloud values do not crash setup or create invalid modes."""
    zone.raw_data.update(supportedModes=supported, mode=mode)
    entity = MyUplinkZoneClimateEntity(coordinator, device, zone)
    assert entity.hvac_modes == expected


def test_optional_readings_clear(
    coordinator: MyUplinkCoordinator, device: Device, zone: Zone
) -> None:
    """Missing readings cannot retain the previous humidity or target."""
    entity = MyUplinkZoneClimateEntity(coordinator, device, zone)
    zone.raw_data.update(
        indoorHumidity=None, setpoint=None, setpointHeat=None, setpointCool=None
    )
    entity._update_from_zone(zone)
    assert entity.current_humidity is None
    assert entity.target_temperature is None


@pytest.mark.parametrize(
    ("mode", "property_name"),
    [
        pytest.param("heat", "setpointHeat", id="heating"),
        pytest.param("cool", "setpointCool", id="cooling"),
        pytest.param("heatcool", "setpoint", id="shared-setpoint"),
    ],
)
async def test_temperature_action(
    coordinator: MyUplinkCoordinator,
    device: Device,
    zone: Zone,
    mode: str,
    property_name: str,
) -> None:
    """Send the target to the correct API field for the active mode."""
    zone.raw_data["mode"] = mode
    entity = MyUplinkZoneClimateEntity(coordinator, device, zone)
    with (
        patch.object(
            device.system.api, "patch_zone_property", new=AsyncMock()
        ) as write,
        patch.object(entity, "async_write_ha_state"),
    ):
        await entity.async_set_temperature(temperature=23)
    write.assert_awaited_once_with(device.id, "1", property_name, 23)
    assert entity.target_temperature == 23


async def test_hvac_action(
    coordinator: MyUplinkCoordinator, device: Device, zone: Zone
) -> None:
    """Write a supported HVAC mode and then update the displayed state."""
    entity = MyUplinkZoneClimateEntity(coordinator, device, zone)
    with (
        patch.object(
            device.system.api, "patch_zone_property", new=AsyncMock()
        ) as write,
        patch.object(entity, "async_write_ha_state"),
    ):
        await entity.async_set_hvac_mode(HVACMode.COOL)
    write.assert_awaited_once_with(device.id, "1", "mode", "cool")
    assert entity.hvac_mode == HVACMode.COOL


def test_fahrenheit_optional_bounds(
    coordinator: MyUplinkCoordinator, device: Device, zone: Zone
) -> None:
    """A zone can omit bounds and use Fahrenheit without losing the temperature."""
    zone.raw_data.update(isCelsius=False, setpointRangeMin=None, setpointRangeMax=None)
    entity = MyUplinkZoneClimateEntity(coordinator, device, zone)
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.current_temperature == 20
