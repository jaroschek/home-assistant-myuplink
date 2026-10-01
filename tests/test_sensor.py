"""Test measurement semantics, units, and translated labels."""

import json
from pathlib import Path

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import PlatformData

from custom_components.myuplink.api import Device, Parameter, Zone
from custom_components.myuplink.coordinator import MyUplinkCoordinator
from custom_components.myuplink.sensor import (
    MyUplinkParameterSensorEntity,
    MyUplinkZoneCO2SensorEntity,
    MyUplinkZoneHumiditySensorEntity,
    MyUplinkZoneTemperatureSensorEntity,
)


@pytest.mark.parametrize(
    ("api_unit", "expected_unit", "device_class", "state_class"),
    [
        pytest.param(
            "°C",
            "°C",
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
            id="celsius",
        ),
        pytest.param(
            "°F",
            "°F",
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
            id="fahrenheit",
        ),
        pytest.param(
            "KWH", "kWh", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, id="energy"
        ),
        pytest.param(
            "mWh",
            "mWh",
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            id="milliwatt-hours",
        ),
        pytest.param(
            "MWh",
            "MWh",
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            id="megawatt-hours",
        ),
        pytest.param("mwh", "mwh", None, None, id="ambiguous-energy-case"),
        pytest.param(
            "Hz",
            "Hz",
            SensorDeviceClass.FREQUENCY,
            SensorStateClass.MEASUREMENT,
            id="frequency",
        ),
        pytest.param(
            "W", "W", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, id="power"
        ),
        pytest.param(
            "days",
            "d",
            SensorDeviceClass.DURATION,
            SensorStateClass.MEASUREMENT,
            id="days",
        ),
        pytest.param(
            "hour",
            "h",
            SensorDeviceClass.DURATION,
            SensorStateClass.MEASUREMENT,
            id="hours",
        ),
        pytest.param(
            "sec",
            "s",
            SensorDeviceClass.DURATION,
            SensorStateClass.MEASUREMENT,
            id="seconds",
        ),
        pytest.param(
            "min",
            "min",
            SensorDeviceClass.DURATION,
            SensorStateClass.MEASUREMENT,
            id="minutes",
        ),
        pytest.param(
            "A",
            "A",
            SensorDeviceClass.CURRENT,
            SensorStateClass.MEASUREMENT,
            id="current",
        ),
        pytest.param(
            "V",
            "V",
            SensorDeviceClass.VOLTAGE,
            SensorStateClass.MEASUREMENT,
            id="voltage",
        ),
        pytest.param(
            "bar",
            "bar",
            SensorDeviceClass.PRESSURE,
            SensorStateClass.MEASUREMENT,
            id="pressure",
        ),
        pytest.param(
            "l/m",
            "L/min",
            SensorDeviceClass.VOLUME_FLOW_RATE,
            SensorStateClass.MEASUREMENT,
            id="volume-flow",
        ),
        pytest.param(
            "DM", "DM", None, SensorStateClass.MEASUREMENT, id="degree-minutes"
        ),
        pytest.param("%", "%", None, SensorStateClass.MEASUREMENT, id="percentage"),
        pytest.param("Ws", "Ws", None, None, id="unclassified-ws"),
        pytest.param("unknown", "unknown", None, None, id="unknown-unit"),
        pytest.param("", None, None, None, id="unitless"),
    ],
)
def test_unit_metadata(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    api_unit: str,
    expected_unit: str | None,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
) -> None:
    """Classify only units whose quantity and semantics are known."""
    parameter.raw_data["parameterUnit"] = api_unit
    entity = MyUplinkParameterSensorEntity(coordinator, device, parameter)
    assert entity.native_unit_of_measurement == expected_unit
    assert entity.device_class == device_class
    assert entity.state_class == state_class
    assert entity.native_value == 20


def test_metadata_reset(
    coordinator: MyUplinkCoordinator, device: Device, parameter: Parameter
) -> None:
    """A changed unit must not retain a previous temperature classification."""
    entity = MyUplinkParameterSensorEntity(coordinator, device, parameter)
    parameter.raw_data["parameterUnit"] = "Ws"
    entity._update_from_parameter(parameter)
    assert entity.device_class is None
    assert entity.state_class is None
    assert entity.native_unit_of_measurement == "Ws"


@pytest.mark.parametrize(
    ("point_id", "translation_key"),
    [
        pytest.param(123, "parameter", id="api-enum"),
        pytest.param(406, "406", id="translated-enum"),
    ],
)
def test_enum_sensor(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    point_id: int,
    translation_key: str,
) -> None:
    """Keep API text states while providing names and state translations."""
    parameter.raw_data.update(
        parameterId=point_id,
        parameterUnit="",
        enumValues=[{"value": "3", "text": "Eco"}, {"value": "4", "text": "Normal"}],
        value=4,
        strVal="Normal",
    )
    entity = MyUplinkParameterSensorEntity(coordinator, device, parameter)
    assert entity.device_class == SensorDeviceClass.ENUM
    assert entity.options == ["Eco", "Normal"]
    assert entity.native_value == "Normal"
    assert entity.translation_key == translation_key
    parameter.raw_data["value"] = -32768
    entity._update_from_parameter(parameter)
    assert entity.native_value is None


@pytest.mark.parametrize(
    ("celsius", "expected"),
    [
        pytest.param(True, UnitOfTemperature.CELSIUS, id="celsius"),
        pytest.param(False, UnitOfTemperature.FAHRENHEIT, id="fahrenheit"),
    ],
)
def test_zone_units(
    coordinator: MyUplinkCoordinator,
    device: Device,
    zone: Zone,
    celsius: bool,
    expected: UnitOfTemperature,
) -> None:
    """Zone measurements expose valid units and long-term statistics metadata."""
    zone.raw_data["isCelsius"] = celsius
    temperature = MyUplinkZoneTemperatureSensorEntity(coordinator, device, zone)
    humidity = MyUplinkZoneHumiditySensorEntity(coordinator, device, zone)
    co2 = MyUplinkZoneCO2SensorEntity(coordinator, device, zone)
    assert temperature.native_unit_of_measurement == expected
    assert temperature.state_class == SensorStateClass.MEASUREMENT
    assert humidity.native_unit_of_measurement == PERCENTAGE
    assert co2.native_unit_of_measurement == "ppm"


@pytest.mark.parametrize(
    ("language", "suffix"),
    [
        pytest.param("en", "Humidity", id="english"),
        pytest.param("de", "Luftfeuchtigkeit", id="german"),
        pytest.param("da", "Luftfugtighed", id="danish"),
        pytest.param("nb", "Luftfuktighet", id="norwegian"),
    ],
)
def test_translated_zone_name(
    hass: HomeAssistant,
    coordinator: MyUplinkCoordinator,
    device: Device,
    zone: Zone,
    language: str,
    suffix: str,
) -> None:
    """Resolve real project translations with the user-defined zone placeholder."""
    translations = json.loads(
        (
            Path(__file__).parents[1]
            / "custom_components"
            / "myuplink"
            / "translations"
            / f"{language}.json"
        ).read_text()
    )
    entity = MyUplinkZoneHumiditySensorEntity(coordinator, device, zone)
    entity.platform_data = PlatformData(hass, domain="sensor", platform_name="myuplink")
    entity.platform_data.platform_translations = {
        "component.myuplink.entity.sensor.myuplink_zone_humidity.name": translations[
            "entity"
        ]["sensor"]["myuplink_zone_humidity"]["name"]
    }
    assert entity.name == f"Living room {suffix}"
