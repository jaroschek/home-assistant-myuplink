"""Test late entity discovery, missing data, and listener cleanup."""

import importlib
import logging
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import EntityPlatform

from custom_components.myuplink.api import Device, Parameter, System, Zone
from custom_components.myuplink.binary_sensor import MyUplinkConnectedBinarySensor
from custom_components.myuplink.const import CONF_DISCONNECTED_AVAILABLE, DOMAIN
from custom_components.myuplink.coordinator import MyUplinkCoordinator
from custom_components.myuplink.entity import (
    MyUplinkDeviceEntity,
    MyUplinkParameterEntity,
    MyUplinkSystemEntity,
    MyUplinkZoneEntity,
)
from custom_components.myuplink.sensor import MyUplinkParameterSensorEntity


@pytest.mark.parametrize(
    "platform",
    [
        pytest.param(platform, id=platform.value)
        for platform in Platform
        if platform.value
        in {
            "binary_sensor",
            "climate",
            "number",
            "select",
            "sensor",
            "switch",
            "update",
            "water_heater",
        }
    ],
)
async def test_dynamic_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    zone: Zone,
    platform: Platform,
) -> None:
    """Each platform adds a new device once and stops listening on entry unload."""
    device.raw_data["product"]["name"] = "18760NE"
    device.parameters = [parameter] + [
        Parameter({**parameter.raw_data, "parameterId": str(point_id)}, device)
        for point_id in (406, 500, 516, 527, 528)
    ]
    device.system.api.platform_override[123] = platform
    coordinator.async_set_updated_data([device.system])
    added: list[Entity] = []
    module = importlib.import_module(f"custom_components.myuplink.{platform}")
    await module.async_setup_entry(hass, entry, added.extend)
    original_count = len(added)
    assert original_count > 0
    new_device = Device({**device.raw_data, "id": "device-2"}, device.system)
    new_device.parameters = [
        Parameter(dict(point.raw_data), new_device) for point in device.parameters
    ]
    new_device.zones = [Zone(dict(zone.raw_data), new_device)]
    new_device.notifications = []
    new_device.firmware_info = device.firmware_info
    device.system.devices.append(new_device)
    coordinator.async_set_updated_data([device.system])
    assert len(added) > original_count
    assert len({entity.unique_id for entity in added}) == len(added)
    after_discovery = len(added)
    coordinator.async_set_updated_data([device.system])
    assert len(added) == after_discovery
    await entry._async_process_on_unload(hass)
    assert not coordinator._listeners


@pytest.mark.parametrize(
    "entity_type",
    [
        pytest.param(MyUplinkSystemEntity, id="system"),
        pytest.param(MyUplinkDeviceEntity, id="device"),
        pytest.param(MyUplinkParameterEntity, id="point"),
        pytest.param(MyUplinkZoneEntity, id="zone"),
    ],
)
def test_missing_snapshot(
    coordinator: MyUplinkCoordinator,
    system: System,
    device: Device,
    parameter: Parameter,
    zone: Zone,
    entity_type: type[MyUplinkSystemEntity] | type[MyUplinkDeviceEntity],
) -> None:
    """Existing entities become unavailable when their cloud data disappears."""
    entities = {
        MyUplinkSystemEntity: MyUplinkSystemEntity(coordinator, system),
        MyUplinkDeviceEntity: MyUplinkDeviceEntity(coordinator, device),
        MyUplinkParameterEntity: MyUplinkParameterEntity(
            coordinator, device, parameter
        ),
        MyUplinkZoneEntity: MyUplinkZoneEntity(coordinator, device, zone),
    }
    entity = entities[entity_type]
    unique_id = entity.unique_id
    assert entity.available
    coordinator.async_set_updated_data([])
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()
        assert not entity.available
        coordinator.async_set_updated_data([system])
        entity._handle_coordinator_update()
    assert entity.available
    assert entity.unique_id == unique_id


def test_missing_point_and_zone(
    coordinator: MyUplinkCoordinator, device: Device, parameter: Parameter, zone: Zone
) -> None:
    """Retaining a device must not keep its vanished points or zones available."""
    point_entity = MyUplinkParameterEntity(coordinator, device, parameter)
    zone_entity = MyUplinkZoneEntity(coordinator, device, zone)
    device.parameters = []
    device.zones = []
    coordinator.async_set_updated_data([device.system])
    with (
        patch.object(point_entity, "async_write_ha_state"),
        patch.object(zone_entity, "async_write_ha_state"),
    ):
        point_entity._handle_coordinator_update()
        zone_entity._handle_coordinator_update()
    assert not point_entity.available
    assert not zone_entity.available


@pytest.mark.parametrize(
    "keep_available",
    [
        pytest.param(False, id="unavailable"),
        pytest.param(True, id="cached-availability"),
    ],
)
def test_disconnected_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    keep_available: bool,
) -> None:
    """Keep the connectivity diagnostic usable when a device goes offline."""
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_DISCONNECTED_AVAILABLE: keep_available}
    )
    device.raw_data["connectionState"] = "Disconnected"
    point = MyUplinkParameterEntity(coordinator, device, parameter)
    connectivity = MyUplinkConnectedBinarySensor(coordinator, device)
    assert point.available is keep_available
    assert connectivity.available
    assert not connectivity.is_on


async def test_existing_registry_customizations(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
) -> None:
    """Recreating an entity preserves its registry ID and customized name."""
    registry = er.async_get(hass)
    registered = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "myuplink_device-1_123",
        config_entry=entry,
        suggested_object_id="my_supply_temperature",
    )
    registry.async_update_entity(registered.entity_id, name="My heating sensor")
    platform = EntityPlatform(
        hass=hass,
        logger=logging.getLogger(DOMAIN),
        domain="sensor",
        platform_name=DOMAIN,
        platform=None,
        scan_interval=timedelta(seconds=300),
        entity_namespace=None,
    )
    platform.config_entry = entry
    entity = MyUplinkParameterSensorEntity(coordinator, device, parameter)
    await platform.async_add_entities([entity])
    assert entity.entity_id == registered.entity_id
    assert registry.async_get(entity.entity_id).name == "My heating sensor"
    assert hass.states.get(entity.entity_id).state == "20.0"
    coordinator.async_set_updated_data([])
    assert hass.states.get(entity.entity_id).state == "unavailable"
    await platform.async_reset()
