"""Support for myUplink sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Device, Parameter
from .const import WATER_HEATERS
from .coordinator import MyUplinkConfigEntry
from .entity import MyUplinkDeviceEntity, async_setup_entities

PARALLEL_UPDATES = 0
REQUIRED_PARAMETERS = {406, 500, 516, 527, 528}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyUplinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform entities."""

    coordinator = entry.runtime_data

    def build_entities() -> list[WaterHeaterEntity]:
        """Build entities from the current snapshot."""
        entities: list[WaterHeaterEntity] = []

        for system in coordinator.data:
            for device in system.devices:
                if device.name[:7] in WATER_HEATERS and REQUIRED_PARAMETERS.issubset(
                    parameter.id for parameter in device.parameters
                ):
                    entities.append(MyUplinkWaterHeaterEntity(coordinator, device))
        return entities

    async_setup_entities(entry, async_add_entities, build_entities)


class MyUplinkWaterHeaterEntity(MyUplinkDeviceEntity, WaterHeaterEntity):
    """Representation of a myUplink paramater binary sensor."""

    _attr_name = None

    @property
    def available(self) -> bool:
        """Require all points needed for water-heater controls."""
        return super().available and self._parameters_available

    def _update_from_device(self, device: Device) -> None:
        """Update controls only while the required points are present."""
        super()._update_from_device(device)
        self._parameters_available = REQUIRED_PARAMETERS.issubset(
            parameter.id for parameter in device.parameters
        )
        if self._parameters_available:
            self._update_from_parameters()

    def _update_from_parameters(self) -> None:
        """Update attrs from parameter."""
        parameter_map: dict[int, Parameter] = {}
        for parameter in self._device.parameters:
            parameter_map[parameter.id] = parameter
        # API bounds are raw values; readings are already scaled.
        target = parameter_map[527]
        if (minimum := target.min_value) is not None:
            self._attr_min_temp = minimum * target.scale_value
        if (maximum := target.max_value) is not None:
            self._attr_max_temp = maximum * target.scale_value
        self._attr_current_temperature = parameter_map[528].value
        self._attr_target_temperature = parameter_map[527].value
        self._attr_target_temperature_high = self._attr_target_temperature
        hysteresis = parameter_map[516].value
        self._attr_target_temperature_low = (
            self._attr_target_temperature - hysteresis
            if self._attr_target_temperature is not None and hysteresis is not None
            else None
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

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Update the current value."""
        temperature = float(kwargs[ATTR_TEMPERATURE])
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
