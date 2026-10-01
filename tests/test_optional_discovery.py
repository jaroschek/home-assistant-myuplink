"""Test optional entity discovery and empty API measurements."""

import importlib

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.myuplink import climate, sensor
from custom_components.myuplink.api import Device, Parameter, Zone
from custom_components.myuplink.coordinator import (
    MyUplinkConfigEntry,
    MyUplinkCoordinator,
)


@pytest.mark.parametrize(
    ("readings", "expected"),
    [
        pytest.param(
            {"commandOnly": True},
            {"myuplink_device-1_123", "myuplink_device-1_1_mode"},
            id="command-only-zone",
        ),
        pytest.param(
            {"temperature": 0, "indoorHumidity": 0, "indoorCo2": 0},
            {
                "myuplink_device-1_123",
                "myuplink_device-1_1_temperature",
                "myuplink_device-1_1_humidity",
                "myuplink_device-1_1_co2",
            },
            id="zero-is-a-reading",
        ),
        pytest.param(
            {"temperature": None, "indoorHumidity": None, "indoorCo2": None},
            {"myuplink_device-1_123"},
            id="absent-readings",
        ),
    ],
)
async def test_optional_zone_sensors(
    hass: HomeAssistant,
    entry: MyUplinkConfigEntry,
    coordinator: MyUplinkCoordinator,
    zone: Zone,
    readings: dict[str, object],
    expected: set[str],
) -> None:
    """Create only sensors whose readings are provided, including valid zeros."""
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "fetch_notifications": False}
    )
    zone.raw_data.update(readings)
    added: list[Entity] = []
    await sensor.async_setup_entry(hass, entry, added.extend)
    assert {entity.unique_id for entity in added} == expected
    await entry._async_process_on_unload(hass)


async def test_unknown_unitless_point(
    hass: HomeAssistant,
    entry: MyUplinkConfigEntry,
    coordinator: MyUplinkCoordinator,
    parameter: Parameter,
    device: Device,
) -> None:
    """An unclassified unitless missing value must not create an invalid sensor."""
    device.zones = []
    parameter.raw_data.update(parameterUnit="", value=-32768)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "fetch_notifications": False}
    )
    added: list[Entity] = []
    await sensor.async_setup_entry(hass, entry, added.extend)
    assert added == []
    await entry._async_process_on_unload(hass)


async def test_command_only_climate(
    hass: HomeAssistant,
    entry: MyUplinkConfigEntry,
    coordinator: MyUplinkCoordinator,
    zone: Zone,
) -> None:
    """Command-only zones do not advertise unsupported thermostat actions."""
    zone.raw_data["commandOnly"] = True
    added: list[Entity] = []
    await climate.async_setup_entry(hass, entry, added.extend)
    assert added == []
    await entry._async_process_on_unload(hass)


@pytest.mark.parametrize(
    ("platform", "option"),
    [
        pytest.param(Platform.SELECT, "enable_smart_home_mode", id="mode-disabled"),
        pytest.param(Platform.UPDATE, "fetch_firmware", id="firmware-disabled"),
        pytest.param(
            Platform.WATER_HEATER, "fetch_firmware", id="heater-missing-points"
        ),
    ],
)
async def test_optional_platform_disabled(
    hass: HomeAssistant,
    entry: MyUplinkConfigEntry,
    coordinator: MyUplinkCoordinator,
    device: Device,
    platform: Platform,
    option: str,
) -> None:
    """Optional firmware, system modes, and incomplete heater mappings stay absent."""
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, option: False}
    )
    device.raw_data["product"]["name"] = "18760NE"
    device.parameters = []
    added: list[Entity] = []
    module = importlib.import_module(f"custom_components.myuplink.{platform}")
    await module.async_setup_entry(hass, entry, added.extend)
    assert added == []
    await entry._async_process_on_unload(hass)
