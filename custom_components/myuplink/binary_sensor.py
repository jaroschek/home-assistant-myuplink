"""Support for myUplink sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Device, Parameter
from .const import DOMAIN
from .coordinator import MyUplinkConfigEntry
from .entity import MyUplinkDeviceEntity, MyUplinkParameterEntity, async_setup_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyUplinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform entities."""

    coordinator = entry.runtime_data

    def build_entities() -> list[BinarySensorEntity]:
        """Build entities from the current snapshot."""
        entities: list[BinarySensorEntity] = []

        for system in coordinator.data:
            for device in system.devices:
                entities.append(MyUplinkConnectedBinarySensor(coordinator, device))
                entities.extend(
                    MyUplinkParameterBinarySensorEntity(coordinator, device, parameter)
                    for parameter in device.parameters
                    if coordinator.parameter_platform(parameter)
                    == Platform.BINARY_SENSOR
                )
        return entities

    async_setup_entities(entry, async_add_entities, build_entities)


class MyUplinkParameterBinarySensorEntity(MyUplinkParameterEntity, BinarySensorEntity):
    """Representation of a myUplink paramater binary sensor."""

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        super()._update_from_parameter(parameter)
        value = self._parameter.value
        self._attr_is_on = bool(int(value)) if value is not None else None

        if self._parameter.id == 10733:
            self._attr_is_on = not bool(int(value)) if value is not None else None
            self._attr_device_class = BinarySensorDeviceClass.LOCK
        elif self._parameter.id in (10905, 10906):
            self._attr_device_class = BinarySensorDeviceClass.RUNNING


class MyUplinkConnectedBinarySensor(MyUplinkDeviceEntity, BinarySensorEntity):
    """Representation of an myUplink connected sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _requires_connection = False

    def _update_from_device(self, device: Device) -> None:
        """Update attrs from device."""
        super()._update_from_device(device)

        self._attr_translation_key = "myuplink_connection_state"
        self._attr_unique_id = f"{DOMAIN}_{device.id}_connection_state"

    @property
    def is_on(self) -> bool:
        """Get the powerwall connected to tesla state."""
        return self._device.connection_state == "Connected"
