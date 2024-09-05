"""Support for myUplink sensors."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Parameter
from .const import DOMAIN
from .entity import MyUplinkParameterEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = []

    for system in coordinator.data:
        for device in system.devices:
            [
                entities.append(
                    MyUplinkParameterNumberEntity(coordinator, device, parameter)
                )
                for parameter in device.parameters
                if parameter.get_platform() == Platform.NUMBER
            ]

    async_add_entities(entities)


class MyUplinkParameterNumberEntity(MyUplinkParameterEntity, NumberEntity):
    """Representation of a myUplink paramater binary sensor."""

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        super()._update_from_parameter(parameter)
        unit_conversion = {
            "°C": NumberDeviceClass.TEMPERATURE,
            "°F": NumberDeviceClass.TEMPERATURE,
        }
        self._attr_device_class = unit_conversion.get(parameter.unit)

        self._attr_native_unit_of_measurement = parameter.unit

        if parameter.max_value is not None:
            self._attr_native_max_value = parameter.max_value * parameter.scale_value
        if parameter.min_value is not None:
            self._attr_native_min_value = parameter.min_value * parameter.scale_value
        if parameter.step_value is not None:
            self._attr_native_step = parameter.step_value * parameter.scale_value

        self._attr_native_value = parameter.value

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._parameter.update_parameter(value)
        await self.async_update()
