"""Support for myUplink sensors."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Parameter
from .const import DOMAIN, BINARY_SENSORS
from .entity import MyUplinkParameterEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = []

    for system in coordinator.data:
        for device in system.devices:
            for parameter in device.parameters:
                if parameter.id in BINARY_SENSORS:
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
        self._attr_is_on = not bool(int(self._parameter.value))
        self._attr_device_class = BinarySensorDeviceClass.LOCK
