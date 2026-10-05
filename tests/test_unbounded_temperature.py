"""Test iGate temperature points without API bounds, reported in issue #234."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.number import NumberDeviceClass
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant

from custom_components.myuplink.api import Parameter
from custom_components.myuplink.coordinator import MyUplinkCoordinator
from custom_components.myuplink.number import (
    MyUplinkParameterNumberEntity,
    async_setup_entry,
)


@pytest.fixture
def temperature_point(parameter: Parameter) -> Parameter:
    """Use the heat-setpoint metadata supplied by the iGate reporter."""
    parameter.device.raw_data["product"]["name"] = "iGate 2.0"
    parameter.raw_data.update(
        category="1.2 - Indoor Climate",
        parameterId="160121",
        parameterName="Heat Setpoint",
        parameterUnit="°F",
        writable=True,
        timestamp="2026-04-05T21:58:21+00:00",
        value=68,
        strVal="68°F",
        minValue=None,
        maxValue=None,
        stepValue=10,
        scaleValue="0.1",
        zoneId=None,
    )
    return parameter


@pytest.mark.parametrize(
    ("point_id", "value", "unit"),
    [
        pytest.param("160121", 68, "°F", id="reported-heat-setpoint"),
        pytest.param("160122", 73, "°F", id="reported-cool-setpoint"),
        pytest.param("160121", 20, "°C", id="celsius"),
        pytest.param("160121", 68.5, "°F", id="fractional-temperature"),
    ],
)
def test_unbounded_temperatures_are_numbers(
    temperature_point: Parameter, point_id: str, value: float, unit: str
) -> None:
    """Discover writable numeric temperatures in either native unit."""
    temperature_point.raw_data.update(
        parameterId=point_id, value=value, parameterUnit=unit
    )
    assert temperature_point.get_platform() == Platform.NUMBER


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="missing"),
        pytest.param("68", id="numeric-text"),
        pytest.param("", id="empty-text"),
        pytest.param(True, id="boolean"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
        pytest.param(-32768, id="unavailable-sentinel"),
    ],
)
def test_invalid_temperatures_remain_sensors(
    temperature_point: Parameter, value: float | str | None
) -> None:
    """Do not create numeric controls from unavailable or nonnumeric readings."""
    temperature_point.raw_data["value"] = value
    assert temperature_point.get_platform() == Platform.SENSOR


@pytest.mark.parametrize(
    "unit",
    [
        pytest.param("", id="unitless"),
        pytest.param("kW", id="power"),
        pytest.param("DM", id="degree-minutes"),
        pytest.param("manufacturer-unit", id="unknown-unit"),
    ],
)
def test_other_unbounded_points_remain_sensors(
    temperature_point: Parameter, unit: str
) -> None:
    """The automatic fallback only applies to temperature units."""
    temperature_point.raw_data["parameterUnit"] = unit
    assert temperature_point.get_platform() == Platform.SENSOR


def test_thermostat_name_remains_a_sensor(temperature_point: Parameter) -> None:
    """The reporter's writable text point must not become a number."""
    temperature_point.raw_data.update(
        parameterId="160303",
        parameterUnit="",
        value="",
        parameterName="Thermostat Name",
    )
    assert temperature_point.get_platform() == Platform.SENSOR


def test_read_only_temperature_remains_a_sensor(
    temperature_point: Parameter,
) -> None:
    """A numeric reading does not grant write access."""
    temperature_point.raw_data["writable"] = False
    assert temperature_point.get_platform() == Platform.SENSOR


def test_temperature_without_write_permission_remains_a_sensor(
    temperature_point: Parameter,
) -> None:
    """Respect the account's subscription policy."""
    system = temperature_point.device.system
    system.premium_manage = False
    system.api.writable_without_subscription = False
    assert temperature_point.get_platform() == Platform.SENSOR


def test_temperature_writable_override(temperature_point: Parameter) -> None:
    """An explicit read-only override keeps precedence."""
    temperature_point.device.system.api.writable_override = {160121: False}
    assert temperature_point.get_platform() == Platform.SENSOR


def test_temperature_platform_override(temperature_point: Parameter) -> None:
    """An explicit platform override keeps precedence."""
    temperature_point.device.system.api.platform_override = {160121: Platform.SENSOR}
    assert temperature_point.get_platform() == Platform.SENSOR


@pytest.mark.parametrize(
    ("metadata", "platform"),
    [
        pytest.param(
            {
                "enumValues": [
                    {"value": "0", "text": "Off"},
                    {"value": "1", "text": "On"},
                ]
            },
            Platform.SWITCH,
            id="boolean-enum",
        ),
        pytest.param(
            {
                "enumValues": [
                    {"value": "0", "text": "Eco"},
                    {"value": "2", "text": "Comfort"},
                ]
            },
            Platform.SELECT,
            id="select-enum",
        ),
        pytest.param(
            {"minValue": 0, "maxValue": 1, "stepValue": 1},
            Platform.SWITCH,
            id="boolean-bounds",
        ),
        pytest.param(
            {"minValue": 0, "parameterUnit": "kW"},
            Platform.NUMBER,
            id="bounded-power",
        ),
    ],
)
def test_existing_temperature_platform_rules(
    temperature_point: Parameter, metadata: dict[str, object], platform: Platform
) -> None:
    """Boolean, enum, and bounded-number detection retain priority."""
    temperature_point.raw_data.update(metadata)
    assert temperature_point.get_platform() == platform


def test_native_temperature_reading(
    temperature_point: Parameter, coordinator: MyUplinkCoordinator
) -> None:
    """Preserve the reported value, scaled step, and default number bounds."""
    entity = MyUplinkParameterNumberEntity(
        coordinator, temperature_point.device, temperature_point
    )
    assert entity.native_value == 68
    assert entity.native_step == 1
    assert entity.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT
    assert entity.device_class == NumberDeviceClass.TEMPERATURE
    assert entity.unique_id == "myuplink_device-1_160121"
    assert entity.native_min_value == 0
    assert entity.native_max_value == 100


async def test_temperature_write_is_not_rescaled(
    temperature_point: Parameter,
) -> None:
    """Send the native setpoint without applying the API's scale twice."""
    with patch.object(temperature_point.device.system.api, "patch_parameter") as write:
        await temperature_point.update_parameter(70)
    write.assert_awaited_once_with("device-1", "160121", 70)


async def test_temperature_discovery(
    hass: HomeAssistant,
    temperature_point: Parameter,
    coordinator: MyUplinkCoordinator,
) -> None:
    """Use the 1.9 coordinator to discover the control without duplicates."""
    add_entities = MagicMock()
    await async_setup_entry(hass, coordinator.api.entry, add_entities)
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], MyUplinkParameterNumberEntity)
    assert entities[0].native_value == 68
    coordinator.async_set_updated_data([temperature_point.device.system])
    add_entities.assert_called_once()


async def test_temperature_action_requests_refresh(
    temperature_point: Parameter, coordinator: MyUplinkCoordinator
) -> None:
    """A successful write requests authoritative readings from the coordinator."""
    entity = MyUplinkParameterNumberEntity(
        coordinator, temperature_point.device, temperature_point
    )
    with (
        patch.object(temperature_point.device.system.api, "patch_parameter") as write,
        patch.object(coordinator, "async_request_refresh") as refresh,
    ):
        await entity.async_set_native_value(70)
    write.assert_awaited_once_with("device-1", "160121", 70)
    refresh.assert_awaited_once()
    assert entity.native_value == 68
