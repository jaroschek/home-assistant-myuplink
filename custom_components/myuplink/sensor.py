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
    EntityCategory,
    Platform,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Device, Parameter
from .const import DOMAIN, CustomUnits
from .entity import MyUplinkEntity, MyUplinkParameterEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for system in coordinator.data:
        for device in system.devices:
            entities.append(MyUplinkNotificationsSensorEntity(coordinator, device))
            for parameter in device.parameters:
                if parameter.find_fitting_entity() == Platform.SENSOR:
                    if (
                        not parameter.unit
                        and not len(parameter.enum_values)
                        and not isinstance(parameter.value, (int, float))
                    ):
                        continue
                    entities.append(
                        MyUplinkParameterSensorEntity(coordinator, device, parameter)
                    )

    async_add_entities(entities)


class MyUplinkParameterSensorEntity(MyUplinkParameterEntity, SensorEntity):
    """Representation of a myUplink parameter sensor entity."""

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        super()._update_from_parameter(parameter)

        if not self._parameter.unit and len(parameter.enum_values):
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_translation_key = str(self._parameter.id)
            self._attr_options = []
            for option in parameter.enum_values:
                self._attr_options.append(option["text"])
            self._attr_native_value = self._parameter.string_value

        else:
            self._attr_native_unit_of_measurement = self._parameter.unit

            if self._parameter.unit in (
                UnitOfTemperature.CELSIUS,
                UnitOfTemperature.FAHRENHEIT,
            ):
                self._attr_device_class = SensorDeviceClass.TEMPERATURE
                self._attr_state_class = SensorStateClass.MEASUREMENT
            elif self._parameter.unit == UnitOfEnergy.KILO_WATT_HOUR:
                self._attr_device_class = SensorDeviceClass.ENERGY
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            elif self._parameter.unit == UnitOfFrequency.HERTZ:
                self._attr_device_class = SensorDeviceClass.FREQUENCY
            elif self._parameter.unit in (UnitOfPower.KILO_WATT, UnitOfPower.WATT):
                self._attr_device_class = SensorDeviceClass.POWER
            elif self._parameter.unit in (
                UnitOfTime.DAYS,
                UnitOfTime.HOURS,
                UnitOfTime.MINUTES,
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

            self._attr_native_value = self._parameter.value


class MyUplinkNotificationsSensorEntity(MyUplinkEntity, SensorEntity):
    """Representation of a myUplink alarm sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def _update_from_device(self, device: Device) -> None:
        """Update attrs from device."""
        super()._update_from_device(device)

        self._attr_name = f"{device.name} Notifications"
        self._attr_unique_id = f"{DOMAIN}_{device.id}_notifications"

        self._attr_native_value = len(device.notifications)

        self._attr_extra_state_attributes = {
            "notifications": [
                {
                    "header": notification.header,
                    "description": notification.description,
                    "status": notification.status,
                    "severity": notification.severity,
                    "equipment": notification.equipment,
                    "alarm_number": notification.alarm_number,
                    "created": notification.created_datetime,
                }
                for notification in device.notifications
            ]
        }
