"""Support for myUplink sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Parameter
from .const import DOMAIN, BINARY_SENSORS, SWITCHES, SELECTS, NUMBERS, CustomUnits
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
                if parameter.id not in BINARY_SENSORS + SWITCHES + SELECTS + NUMBERS:
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

        if len(parameter.enum_values):
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_translation_key = self._parameter.id
            self._attr_native_value = str(int(self._parameter.value))
            self._attr_options = []
            for option in parameter.enum_values:
                self._attr_options.append(str(int(option["value"])))

        else:
            self._attr_native_unit_of_measurement = self._parameter.unit

            if self._parameter.unit == UnitOfTemperature.CELSIUS:
                self._attr_device_class = SensorDeviceClass.TEMPERATURE
            elif self._parameter.unit == UnitOfEnergy.KILO_WATT_HOUR:
                self._attr_device_class = SensorDeviceClass.ENERGY
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            elif self._parameter.unit in (UnitOfPower.KILO_WATT, UnitOfPower.WATT):
                self._attr_device_class = SensorDeviceClass.POWER
            elif self._parameter.unit in (
                UnitOfTime.DAYS,
                UnitOfTime.HOURS,
                CustomUnits.TIME_DAY,
                CustomUnits.TIME_DAYS,
                CustomUnits.TIME_HOUR,
                CustomUnits.TIME_HOURS,
            ):
                self._attr_device_class = SensorDeviceClass.DURATION
            elif self._parameter.unit == CustomUnits.POWER_WS:
                self._attr_device_class = SensorDeviceClass.POWER
                self._attr_native_unit_of_measurement = UnitOfPower.WATT
            elif self._parameter.unit == CustomUnits.DEGREE_MINUTES:
                self._attr_device_class = "degree_minutes"
            elif self._parameter.unit in (PERCENTAGE, CustomUnits.VOLUME_LM):
                self._attr_icon = "mdi:speedometer"
