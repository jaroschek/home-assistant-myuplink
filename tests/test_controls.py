"""Test entity controls, permissions, and optional metadata."""

from unittest.mock import patch

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.number import NumberDeviceClass
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from custom_components.myuplink.api import Device, Parameter, System
from custom_components.myuplink.binary_sensor import MyUplinkParameterBinarySensorEntity
from custom_components.myuplink.coordinator import MyUplinkCoordinator
from custom_components.myuplink.number import MyUplinkParameterNumberEntity
from custom_components.myuplink.select import (
    MyUplinkParameterSelectEntity,
    MyUplinkSmartHomeModeDeviceSelectEntity,
    MyUplinkSmartHomeModeSystemSelectEntity,
)
from custom_components.myuplink.switch import MyUplinkParameterSwitchEntityEntity
from custom_components.myuplink.update import MyUplinkUpdateEntity
from custom_components.myuplink.water_heater import MyUplinkWaterHeaterEntity


@pytest.mark.parametrize(
    ("point_id", "value", "expected", "device_class"),
    [
        pytest.param(10733, 0, True, BinarySensorDeviceClass.LOCK, id="unlocked"),
        pytest.param(10733, 1, False, BinarySensorDeviceClass.LOCK, id="locked"),
        pytest.param(
            10733, -32768, None, BinarySensorDeviceClass.LOCK, id="unknown-lock"
        ),
        pytest.param(
            10905, 1, True, BinarySensorDeviceClass.RUNNING, id="running-first"
        ),
        pytest.param(
            10906, 0, False, BinarySensorDeviceClass.RUNNING, id="idle-second"
        ),
        pytest.param(123, -32768, None, None, id="unknown-boolean"),
    ],
)
def test_boolean_metadata(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    point_id: int,
    value: int,
    expected: bool | None,
    device_class: BinarySensorDeviceClass | None,
) -> None:
    """Known boolean points expose their correct semantics, including missing values."""
    parameter.raw_data.update(parameterId=point_id, value=value)
    entity = MyUplinkParameterBinarySensorEntity(coordinator, device, parameter)
    assert entity.is_on is expected
    assert entity.device_class == device_class


@pytest.mark.parametrize(
    ("unit", "device_class", "translation_key"),
    [
        pytest.param(
            "°C", NumberDeviceClass.TEMPERATURE, "parameter", id="temperature"
        ),
        pytest.param("DM", None, "parameter_degree_minutes", id="degree-minutes"),
    ],
)
async def test_number_control(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    unit: str,
    device_class: NumberDeviceClass | None,
    translation_key: str,
) -> None:
    """Scale API bounds but send the native requested value to the API."""
    parameter.raw_data.update(
        writable=True,
        parameterUnit=unit,
        minValue=50,
        maxValue=650,
        stepValue=5,
        scaleValue=0.1,
    )
    entity = MyUplinkParameterNumberEntity(coordinator, device, parameter)
    assert entity.native_min_value == 5
    assert entity.native_max_value == 65
    assert entity.native_step == 0.5
    assert entity.device_class == device_class
    assert entity.translation_key == translation_key
    with (
        patch.object(device.system.api, "patch_parameter") as write,
        patch.object(entity, "async_update") as refresh,
    ):
        await entity.async_set_native_value(23.5)
    write.assert_awaited_once_with(device.id, "123", 23.5)
    refresh.assert_awaited_once()


def test_number_optional_bounds(
    coordinator: MyUplinkCoordinator, device: Device, parameter: Parameter
) -> None:
    """Absent bounds and step use Home Assistant's defaults."""
    parameter.raw_data.update(
        minValue=None, maxValue=None, stepValue=None, scaleValue=None
    )
    entity = MyUplinkParameterNumberEntity(coordinator, device, parameter)
    entity.hass = coordinator.hass
    assert entity.native_min_value == 0
    assert entity.native_max_value == 100
    assert entity.native_step is None
    assert entity.step == 1
    assert parameter.scale_value == 1


@pytest.mark.parametrize(
    ("method", "value"),
    [
        pytest.param("async_turn_on", 1, id="turn-on"),
        pytest.param("async_turn_off", 0, id="turn-off"),
    ],
)
async def test_switch_control(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    method: str,
    value: int,
) -> None:
    """Boolean controls write a numeric value and then request fresh data."""
    parameter.raw_data.update(writable=True, value=-32768)
    entity = MyUplinkParameterSwitchEntityEntity(coordinator, device, parameter)
    assert entity.is_on is None
    with (
        patch.object(device.system.api, "patch_parameter") as write,
        patch.object(entity, "async_update") as refresh,
    ):
        await getattr(entity, method)()
    write.assert_awaited_once_with(device.id, "123", value)
    refresh.assert_awaited_once()


async def test_switch_failure(
    coordinator: MyUplinkCoordinator, device: Device, parameter: Parameter
) -> None:
    """A rejected write neither changes the displayed state nor triggers success refresh."""
    parameter.raw_data.update(writable=True, value=0)
    entity = MyUplinkParameterSwitchEntityEntity(coordinator, device, parameter)
    with (
        patch.object(
            device.system.api, "patch_parameter", side_effect=HomeAssistantError
        ),
        patch.object(entity, "async_update") as refresh,
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_turn_on()
    assert entity.is_on is False
    refresh.assert_not_awaited()


@pytest.mark.parametrize(
    "point_id",
    [pytest.param(123, id="generic-point"), pytest.param(500, id="known-point")],
)
async def test_parameter_select(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    point_id: int,
) -> None:
    """Map the API's displayed enum text back to its write value."""
    parameter.raw_data.update(
        parameterId=point_id,
        writable=True,
        enumValues=[{"value": "3", "text": "Eco"}, {"value": "4", "text": "Normal"}],
        strVal="Normal",
    )
    entity = MyUplinkParameterSelectEntity(coordinator, device, parameter)
    assert entity.options == ["Eco", "Normal"]
    assert entity.current_option == "Normal"
    with (
        patch.object(device.system.api, "patch_parameter") as write,
        patch.object(entity, "async_update") as refresh,
    ):
        await entity.async_select_option("Eco")
    write.assert_awaited_once_with(device.id, str(point_id), "3")
    refresh.assert_awaited_once()


@pytest.mark.parametrize(
    "entity_type",
    [
        pytest.param(MyUplinkSmartHomeModeDeviceSelectEntity, id="single-device"),
        pytest.param(MyUplinkSmartHomeModeSystemSelectEntity, id="multi-device"),
    ],
)
async def test_smart_home_mode_select(
    coordinator: MyUplinkCoordinator,
    system: System,
    device: Device,
    entity_type: type[MyUplinkSmartHomeModeDeviceSelectEntity]
    | type[MyUplinkSmartHomeModeSystemSelectEntity],
) -> None:
    """Both registry layouts retain a system identity and write the same API mode."""
    entities = {
        MyUplinkSmartHomeModeDeviceSelectEntity: MyUplinkSmartHomeModeDeviceSelectEntity(
            coordinator, device
        ),
        MyUplinkSmartHomeModeSystemSelectEntity: MyUplinkSmartHomeModeSystemSelectEntity(
            coordinator, system
        ),
    }
    entity = entities[entity_type]
    assert entity.unique_id == "myuplink_system-1_smart_home_mode"
    assert entity.current_option == "default"
    assert "home" in entity.options
    with (
        patch.object(system.api, "put_smart_home_mode") as write,
        patch.object(entity, "async_update") as refresh,
    ):
        await entity.async_select_option("home")
    write.assert_awaited_once_with(system.id, "Home")
    refresh.assert_awaited_once()


def test_firmware_entity(coordinator: MyUplinkCoordinator, device: Device) -> None:
    """Report installed and desired versions without advertising installation support."""
    entity = MyUplinkUpdateEntity(coordinator, device)
    assert entity.installed_version == "1.0"
    assert entity.latest_version == "1.1"
    assert entity.supported_features == 0


@pytest.fixture
def water_heater(device: Device, parameter: Parameter) -> Device:
    """Provide the five points required by the supported heater mapping."""
    device.raw_data["product"]["name"] = "18760NE"
    device.parameters = [
        Parameter(
            {
                **parameter.raw_data,
                "parameterId": point_id,
                "value": value,
                "writable": True,
            },
            device,
        )
        for point_id, value in ((406, 4), (500, 4), (516, 5), (527, 50), (528, 49))
    ]
    device.parameters[0].raw_data["strVal"] = "Normal"
    device.parameters[1].raw_data["enumValues"] = [
        {"value": "3", "text": "Eco"},
        {"value": "4", "text": "Normal"},
    ]
    device.parameters[3].raw_data.update(minValue=350, maxValue=650, scaleValue=0.1)
    return device


async def test_water_heater_operations(
    coordinator: MyUplinkCoordinator, water_heater: Device
) -> None:
    """Expose the supported heater's bounds, hysteresis, readings, and operations."""
    entity = MyUplinkWaterHeaterEntity(coordinator, water_heater)
    assert entity.available
    assert entity.min_temp == 35
    assert entity.max_temp == 65
    assert entity.current_temperature == 49
    assert entity.target_temperature == 50
    assert entity.target_temperature_high == 50
    assert entity.target_temperature_low == 45
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.current_operation == "Normal"
    assert entity.operation_list == ["Eco", "Normal"]
    with (
        patch.object(water_heater.system.api, "patch_parameter") as write,
        patch.object(entity, "async_update") as refresh,
    ):
        await entity.async_set_operation_mode("Eco")
    write.assert_awaited_once_with(water_heater.id, "500", "3")
    refresh.assert_awaited_once()
    water_heater.parameters.pop()
    entity._update_from_device(water_heater)
    assert not entity.available


@pytest.mark.parametrize(
    ("target", "hysteresis"),
    [
        pytest.param(-32768, 5, id="missing-target"),
        pytest.param(50, -32768, id="missing-hysteresis"),
    ],
)
def test_water_heater_optional_values(
    coordinator: MyUplinkCoordinator, water_heater: Device, target: int, hysteresis: int
) -> None:
    """Missing readings and bounds do not break setup or derive a false lower target."""
    water_heater.parameters[2].raw_data["value"] = hysteresis
    water_heater.parameters[3].raw_data.update(
        value=target, minValue=None, maxValue=None
    )
    entity = MyUplinkWaterHeaterEntity(coordinator, water_heater)
    assert entity.target_temperature_low is None
