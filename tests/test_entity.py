"""Test shared entity naming and stable identities."""

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.myuplink.api import Device, Parameter, System
from custom_components.myuplink.entity import (
    MyUplinkParameterEntity,
    MyUplinkSystemEntity,
)
from custom_components.myuplink.update import MyUplinkUpdateEntity


def test_parameter_identity(
    coordinator: DataUpdateCoordinator[list[System]],
    device: Device,
    parameter: Parameter,
) -> None:
    """Name a point relative to its device while retaining the existing unique ID."""
    entity = MyUplinkParameterEntity(coordinator, device, parameter)
    assert entity.has_entity_name
    assert entity.translation_key == "parameter"
    assert entity.translation_placeholders == {
        "name": "Heating Supply temperature",
        "id": "123",
    }
    assert entity.unique_id == "myuplink_device-1_123"
    assert entity.device_info["identifiers"] == {("myuplink", "device-1")}


def test_system_and_firmware_identity(
    coordinator: DataUpdateCoordinator[list[System]], system: System, device: Device
) -> None:
    """Keep stable identifiers for system and firmware entities."""
    entity = MyUplinkSystemEntity(coordinator, system)
    firmware = MyUplinkUpdateEntity(coordinator, device)
    assert entity.has_entity_name
    assert entity.unique_id == "myuplink_system-1"
    assert firmware.has_entity_name
    assert firmware.unique_id == "myuplink_device-1_firmware"
