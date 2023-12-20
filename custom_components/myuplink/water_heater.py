"""Support for myUplink sensors."""
from __future__ import annotations

import logging

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import Device, Parameter
from .const import DOMAIN, WATER_HEATERS
from .entity import MyUplinkEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[WaterHeaterEntity] = []

    for system in coordinator.data:
        for device in system.devices:
            if device.name[:7] in WATER_HEATERS:
                entities.append(MyUplinkWaterHeaterEntity(coordinator, device))

    async_add_entities(entities)


class MyUplinkWaterHeaterEntity(MyUplinkEntity, WaterHeaterEntity):
    """Representation of a myUplink paramater binary sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, device: Device) -> None:
        super().__init__(coordinator, device)
        self._update_from_parameters()

    def _update_from_parameters(self) -> None:
        """Update attrs from parameter."""
        # super()._update_from_parameter(parameter)
        parameter_map: dict[int, Parameter] = {}
        for parameter in self._device.parameters:
            parameter_map[parameter.id] = parameter
        # for some reason the min_value is formated like this: "2000" = 20.00 Celcius
        self._attr_min_temp = (
            parameter_map[527].min_value * parameter_map[527].scale_value
        )
        self._attr_max_temp = (
            parameter_map[527].max_value * parameter_map[527].scale_value
        )
        self._attr_current_temperature = parameter_map[528].value
        self._attr_target_temperature = parameter_map[527].value
        self._attr_target_temperature_high = self._attr_target_temperature
        self._attr_target_temperature_low = (
            self._attr_target_temperature - parameter_map[516].value
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        operation_types = []
        for enum in parameter_map[500].enum_values:
            operation_types.append(enum["text"])
        self._attr_current_operation = parameter_map[406].string_value
        self._attr_operation_list = operation_types
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
        )

    async def async_set_temperature(self, temperature: float, entity_id: str) -> None:
        """Update the current value."""
        for parameter in self._device.parameters:
            if parameter.id == 527:
                await parameter.update_parameter(temperature)
        await self.async_update()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Update the current value."""
        for parameter in self._device.parameters:
            if parameter.id == 500:
                operation_types = {}
                for enum in parameter.enum_values:
                    operation_types[enum["text"]] = enum["value"]
                await parameter.update_parameter(operation_types[operation_mode])
        await self.async_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for system in self.coordinator.data:
            for device in system.devices:
                if device.id == self._device.id:
                    super()._update_from_device(device)
                    self._update_from_parameters()

        super().async_write_ha_state()
