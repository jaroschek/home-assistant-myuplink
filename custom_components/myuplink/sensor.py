"""Support for myUplink sensors."""

from __future__ import annotations

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

from .api import Device, Parameter, System, Zone
from .const import CONF_FETCH_NOTIFICATIONS, DOMAIN, CustomUnits
from .entity import MyUplinkDeviceEntity, MyUplinkParameterEntity, MyUplinkZoneEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the platform entities."""

    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for system in coordinator.data:
        system: System
        for device in system.devices:
            device: Device
            if entry.options.get(CONF_FETCH_NOTIFICATIONS, True):
                entities.append(MyUplinkNotificationsSensorEntity(coordinator, device))
            for parameter in device.parameters:
                parameter: Parameter
                if parameter.get_platform() == Platform.SENSOR:
                    if (
                        not parameter.unit
                        and len(parameter.enum_values) == 0
                        and not isinstance(parameter.value, (int, float))
                    ):
                        continue
                    entities.append(
                        MyUplinkParameterSensorEntity(coordinator, device, parameter)
                    )
            for zone in device.zones:
                zone: Zone
                if zone.is_command_only:
                    entities.append(
                        MyUplinkZoneModeSensorEntity(coordinator, device, zone)
                    )
                else:
                    if zone.indoor_co2 is not None and zone.indoor_co2 != 0:
                        entities.append(
                            MyUplinkZoneCO2SensorEntity(coordinator, device, zone)
                        )
                    if zone.indoor_humidity is not None and zone.indoor_humidity != 0:
                        entities.append(
                            MyUplinkZoneHumiditySensorEntity(coordinator, device, zone)
                        )
                    if zone.temperature is not None and zone.temperature != 0:
                        entities.append(
                            MyUplinkZoneTemperatureSensorEntity(
                                coordinator, device, zone
                            )
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
                self._attr_state_class = SensorStateClass.TOTAL
            elif self._parameter.unit == UnitOfFrequency.HERTZ:
                self._attr_device_class = SensorDeviceClass.FREQUENCY
                self._attr_state_class = SensorStateClass.MEASUREMENT
            elif self._parameter.unit in (UnitOfPower.KILO_WATT, UnitOfPower.WATT):
                self._attr_device_class = SensorDeviceClass.POWER
                self._attr_state_class = SensorStateClass.MEASUREMENT
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
                self._attr_state_class = SensorStateClass.MEASUREMENT
                self._attr_native_unit_of_measurement = UnitOfPower.WATT
            elif self._parameter.unit == CustomUnits.DEGREE_MINUTES:
                self._attr_device_class = "degree_minutes"
            elif self._parameter.unit in (PERCENTAGE, CustomUnits.VOLUME_LM):
                self._attr_icon = "mdi:speedometer"

            self._attr_native_value = self._parameter.value


class MyUplinkNotificationsSensorEntity(MyUplinkDeviceEntity, SensorEntity):
    """Representation of a myUplink alarm sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def _update_from_device(self, device: Device) -> None:
        """Update attrs from device."""
        super()._update_from_device(device)

        self._attr_translation_key = f"{DOMAIN}_notifications"
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


class MyUplinkZoneModeSensorEntity(MyUplinkZoneEntity, SensorEntity):
    """Representation of a myUplink zone mode sensor entity."""

    def _update_from_zone(self, zone: Zone) -> None:
        """Update attrs from zone."""
        super()._update_from_zone(zone)

        self._attr_name = f"{zone.name} Mode"
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{zone.id}_mode"

        self._attr_native_value = zone.mode


class MyUplinkZoneCO2SensorEntity(MyUplinkZoneEntity, SensorEntity):
    """Representation of a myUplink zone CO2 sensor entity."""

    _attr_device_class = SensorDeviceClass.CO2

    def _update_from_zone(self, zone: Zone) -> None:
        """Update attrs from zone."""
        super()._update_from_zone(zone)

        self._attr_name = f"{zone.name} CO2"
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{zone.id}_co2"

        self._attr_native_value = zone.indoor_co2


class MyUplinkZoneHumiditySensorEntity(MyUplinkZoneEntity, SensorEntity):
    """Representation of a myUplink zone humidity sensor entity."""

    _attr_device_class = SensorDeviceClass.HUMIDITY

    def _update_from_zone(self, zone: Zone) -> None:
        """Update attrs from zone."""
        super()._update_from_zone(zone)

        self._attr_name = f"{zone.name} Humidity"
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{zone.id}_humidity"

        self._attr_native_value = zone.indoor_humidity


class MyUplinkZoneTemperatureSensorEntity(MyUplinkZoneEntity, SensorEntity):
    """Representation of a myUplink zone temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def _update_from_zone(self, zone: Zone) -> None:
        """Update attrs from zone."""
        super()._update_from_zone(zone)

        self._attr_name = f"{zone.name} Temperature"
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{zone.id}_temperature"

        self._attr_native_value = zone.temperature
        if zone.is_celsius:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        else:
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
