"""Regression tests for iGate 2.0 points reported in issue #234.

Run with Python 3.13.2+ and homeassistant==2026.1.0, pytest installed:
    python -m pytest -q tests/test_unbounded_temperature.py
Cloud transport is mocked; these tests do not contact myUplink.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.number import NumberDeviceClass
from homeassistant.const import Platform

from custom_components.myuplink.api import Device, MyUplink, Parameter, System
from custom_components.myuplink.number import (
    MyUplinkParameterNumberEntity,
    async_setup_entry,
)


@pytest.fixture
def temperature_point():
    """Use the real API model with the reported heat-setpoint metadata."""
    entry = MagicMock()
    entry.options = {}
    api = MyUplink(MagicMock(), "en-US", entry)
    system = System({"systemId": "system", "name": "Home"}, api)
    device = Device(
        {
            "id": "device",
            "connectionState": "Connected",
            "product": {"name": "iGate 2.0", "serialNumber": "test"},
        },
        system,
    )
    return Parameter(
        {
            "category": "1.2 - Indoor Climate",
            "parameterId": "160121",
            "parameterName": "Heat Setpoint",
            "parameterUnit": "°F",
            "writable": True,
            "timestamp": "2026-04-05T21:58:21+00:00",
            "value": 68,
            "strVal": "68°F",
            "smartHomeCategories": [],
            "minValue": None,
            "maxValue": None,
            "stepValue": 10,
            "enumValues": [],
            "scaleValue": "0.1",
            "zoneId": None,
        },
        device,
    )


@pytest.mark.parametrize("point_id,value", [("160121", 68), ("160122", 73)])
def test_reported_setpoints_are_numbers(temperature_point, point_id, value):
    temperature_point.raw_data.update(parameterId=point_id, value=value)
    assert temperature_point.get_platform() == Platform.NUMBER


@pytest.mark.parametrize("unit", ["°C", "°F"])
def test_temperature_units_are_supported(temperature_point, unit):
    temperature_point.raw_data["parameterUnit"] = unit
    assert temperature_point.get_platform() == Platform.NUMBER


@pytest.mark.parametrize(
    "value", [None, "68", "", True, float("nan"), float("inf"), -32768]
)
def test_missing_and_nonnumeric_values_remain_sensors(temperature_point, value):
    temperature_point.raw_data["value"] = value
    assert temperature_point.get_platform() == Platform.SENSOR


@pytest.mark.parametrize("unit", ["", "kW", "DM", "manufacturer-unit"])
def test_other_unbounded_points_remain_sensors(temperature_point, unit):
    temperature_point.raw_data["parameterUnit"] = unit
    assert temperature_point.get_platform() == Platform.SENSOR


def test_thermostat_name_is_not_a_number(temperature_point):
    temperature_point.raw_data.update(
        parameterId="160303",
        parameterUnit="",
        value="",
        parameterName="Thermostat Name",
    )
    assert temperature_point.get_platform() == Platform.SENSOR


def test_read_only_temperature_remains_a_sensor(temperature_point):
    temperature_point.raw_data["writable"] = False
    assert temperature_point.get_platform() == Platform.SENSOR


def test_missing_write_permission_remains_a_sensor(temperature_point):
    system = temperature_point.device.system
    system.premium_manage = False
    system.api.writable_without_subscription = False
    assert temperature_point.get_platform() == Platform.SENSOR


def test_writable_override_is_respected(temperature_point):
    temperature_point.device.system.api.writable_override = {160121: False}
    assert temperature_point.get_platform() == Platform.SENSOR


def test_platform_override_has_priority(temperature_point):
    temperature_point.device.system.api.platform_override = {160121: Platform.SENSOR}
    assert temperature_point.get_platform() == Platform.SENSOR


@pytest.mark.parametrize(
    "metadata,platform",
    [
        (
            {
                "enumValues": [
                    {"value": "0", "text": "Off"},
                    {"value": "1", "text": "On"},
                ]
            },
            Platform.SWITCH,
        ),
        (
            {
                "enumValues": [
                    {"value": "0", "text": "Eco"},
                    {"value": "2", "text": "Comfort"},
                ]
            },
            Platform.SELECT,
        ),
        ({"minValue": 0, "maxValue": 1, "stepValue": 1}, Platform.SWITCH),
        ({"minValue": 0, "parameterUnit": "kW"}, Platform.NUMBER),
    ],
)
def test_existing_platform_rules_keep_priority(temperature_point, metadata, platform):
    temperature_point.raw_data.update(metadata)
    assert temperature_point.get_platform() == platform


def test_number_preserves_native_reading_and_scaled_step(temperature_point):
    entity = MyUplinkParameterNumberEntity(
        MagicMock(), temperature_point.device, temperature_point
    )
    assert entity.native_value == 68
    assert entity.native_step == 1
    assert entity.native_unit_of_measurement == "°F"
    assert entity.device_class == NumberDeviceClass.TEMPERATURE
    assert entity.unique_id == "myuplink_device_160121"
    # Document the existing NumberEntity defaults; do not invent device limits.
    assert entity.native_min_value == 0
    assert entity.native_max_value == 100


def test_reported_scale_is_not_applied_twice_on_write(temperature_point):
    api = temperature_point.device.system.api
    api.patch_parameter = AsyncMock()
    asyncio.run(temperature_point.update_parameter(70))
    api.patch_parameter.assert_awaited_once_with("device", "160121", 70)


def test_platform_setup_discovers_the_control(temperature_point):
    device = temperature_point.device
    system = device.system
    system.devices = [device]
    device.parameters = [temperature_point]
    entry = system.api.entry
    entry.runtime_data.data = [system]
    add_entities = MagicMock()
    asyncio.run(async_setup_entry(MagicMock(), entry, add_entities))
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], MyUplinkParameterNumberEntity)
    assert entities[0].native_value == 68


def test_number_action_sends_native_temperature_and_requests_refresh(temperature_point):
    api = temperature_point.device.system.api
    api.patch_parameter = AsyncMock()
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    entity = MyUplinkParameterNumberEntity(
        coordinator, temperature_point.device, temperature_point
    )
    asyncio.run(entity.async_set_native_value(70))
    api.patch_parameter.assert_awaited_once_with("device", "160121", 70)
    coordinator.async_request_refresh.assert_awaited_once()
