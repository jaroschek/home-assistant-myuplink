"""Support for myUplink sensors."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Device, Parameter
from .const import DOMAIN
from .entity import MyUplinkEntity, MyUplinkParameterEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = []

    for system in coordinator.data:
        for device in system.devices:
            entities.append(MyUplinkConnectedBinarySensor(coordinator, device))
            for parameter in device.parameters:
                if parameter.find_fitting_entity() == Platform.BINARY_SENSOR:
                    entities.append(
                        MyUplinkParameterBinarySensorEntity(
                            coordinator, device, parameter
                        )
                    )

    async_add_entities(entities)


class MyUplinkParameterBinarySensorEntity(MyUplinkParameterEntity, BinarySensorEntity):
    """Representation of a myUplink paramater binary sensor."""

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        super()._update_from_parameter(parameter)
        self._attr_is_on = bool(int(self._parameter.value))

        if self._parameter.id == 10733:
            self._attr_is_on = not bool(int(self._parameter.value))
            self._attr_device_class = BinarySensorDeviceClass.LOCK
        elif self._parameter.id in (10905, 10906):
            self._attr_device_class = BinarySensorDeviceClass.RUNNING


class MyUplinkConnectedBinarySensor(MyUplinkEntity, BinarySensorEntity):
    """Representation of an myUplink connected sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def _update_from_device(self, device: Device) -> None:
        """Update attrs from device."""
        super()._update_from_device(device)

        self._attr_name = f"{self._device.name} Connection State"
        self._attr_unique_id = f"{DOMAIN}_{device.id}_connection_state"

    @property
    def is_on(self) -> bool:
        """Get the powerwall connected to tesla state."""
        return self._device.connection_state == "Connected"
