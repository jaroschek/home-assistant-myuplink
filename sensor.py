"""Support for myUplink sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Parameter
from .const import DOMAIN, BINARY_SENSORS, DEGREE_MINUTES
from .entity import MyUplinkParameterEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for system in coordinator.data:
        for device in system.devices:
            for parameter in device.parameters:
                if parameter.id not in BINARY_SENSORS:
                    entities.append(
                        MyUplinkParameterSensorEntity(coordinator, device, parameter)
                    )

    async_add_entities(entities)


class MyUplinkParameterSensorEntity(MyUplinkParameterEntity, SensorEntity):
    """Representation of a myUplink parameter sensor entity."""

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        super()._update_from_parameter(parameter)
        self._attr_native_value = self._parameter.value
        self._attr_native_unit_of_measurement = self._parameter.unit
        if self._parameter.unit == TEMP_CELSIUS:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif self._parameter.unit == DEGREE_MINUTES:
            self._attr_device_class = "degree_minutes"
