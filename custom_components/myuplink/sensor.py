"""Support for myUplink sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Device, Parameter, Zone
from .const import (
    CONF_FETCH_NOTIFICATIONS,
    DOMAIN,
    TRANSLATED_PARAMETER_IDS,
    CustomUnits,
)
from .entity import (
    MyUplinkDeviceEntity,
    MyUplinkParameterEntity,
    MyUplinkZoneEntity,
    async_setup_entities,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the platform entities."""

    coordinator = entry.runtime_data

    def build_entities() -> list[SensorEntity]:
        """Build entities from the current snapshot."""
        entities: list[SensorEntity] = []

        for system in coordinator.data:
            for device in system.devices:
                if entry.options.get(CONF_FETCH_NOTIFICATIONS, True):
                    entities.append(
                        MyUplinkNotificationsSensorEntity(coordinator, device)
                    )
                for parameter in device.parameters:
                    if coordinator.parameter_platform(parameter) == Platform.SENSOR:
                        if (
                            not parameter.unit
                            and len(parameter.enum_values) == 0
                            and not isinstance(parameter.value, (int, float))
                        ):
                            continue
                        entities.append(
                            MyUplinkParameterSensorEntity(
                                coordinator, device, parameter
                            )
                        )
                for zone in device.zones:
                    if zone.is_command_only:
                        entities.append(
                            MyUplinkZoneModeSensorEntity(coordinator, device, zone)
                        )
                    else:
                        if zone.indoor_co2 is not None:
                            entities.append(
                                MyUplinkZoneCO2SensorEntity(coordinator, device, zone)
                            )
                        if zone.indoor_humidity is not None:
                            entities.append(
                                MyUplinkZoneHumiditySensorEntity(
                                    coordinator, device, zone
                                )
                            )
                        if zone.temperature is not None:
                            entities.append(
                                MyUplinkZoneTemperatureSensorEntity(
                                    coordinator, device, zone
                                )
                            )
        return entities

    async_setup_entities(entry, async_add_entities, build_entities)


class MyUplinkParameterSensorEntity(MyUplinkParameterEntity, SensorEntity):
    """Representation of a myUplink parameter sensor entity."""

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Apply normalized units and clear metadata that no longer applies."""
        super()._update_from_parameter(parameter)
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_native_unit_of_measurement = parameter.unit or None
        self._attr_options = None

        if not parameter.unit and parameter.enum_values:
            self._attr_device_class = SensorDeviceClass.ENUM
            if parameter.id in TRANSLATED_PARAMETER_IDS:
                self._attr_translation_key = str(parameter.id)
            self._attr_options = [option["text"] for option in parameter.enum_values]
            self._attr_native_value = (
                parameter.string_value if parameter.value is not None else None
            )
            return

        metadata = (
            (
                UnitOfTemperature,
                SensorDeviceClass.TEMPERATURE,
                SensorStateClass.MEASUREMENT,
            ),
            (UnitOfEnergy, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL),
            (
                UnitOfFrequency,
                SensorDeviceClass.FREQUENCY,
                SensorStateClass.MEASUREMENT,
            ),
            (UnitOfPower, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
            (
                UnitOfElectricCurrent,
                SensorDeviceClass.CURRENT,
                SensorStateClass.MEASUREMENT,
            ),
            (
                UnitOfElectricPotential,
                SensorDeviceClass.VOLTAGE,
                SensorStateClass.MEASUREMENT,
            ),
            (UnitOfPressure, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
            (
                UnitOfVolumeFlowRate,
                SensorDeviceClass.VOLUME_FLOW_RATE,
                SensorStateClass.MEASUREMENT,
            ),
        )
        for units, device_class, state_class in metadata:
            if parameter.unit in units:
                self._attr_device_class = device_class
                self._attr_state_class = state_class
                break
        if parameter.unit in (
            UnitOfTime.SECONDS,
            UnitOfTime.MINUTES,
            UnitOfTime.HOURS,
            UnitOfTime.DAYS,
        ):
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif parameter.unit == CustomUnits.DEGREE_MINUTES:
            self._attr_translation_key = "parameter_degree_minutes"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif parameter.unit == PERCENTAGE:
            self._attr_translation_key = "parameter_percentage"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = parameter.value


class MyUplinkNotificationsSensorEntity(MyUplinkDeviceEntity, SensorEntity):
    """Representation of a myUplink alarm sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
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

        self._attr_translation_key = "myuplink_zone_mode"
        self._attr_translation_placeholders = {"zone": zone.name}
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{zone.id}_mode"

        self._attr_native_value = zone.mode


class MyUplinkZoneCO2SensorEntity(MyUplinkZoneEntity, SensorEntity):
    """Representation of a myUplink zone CO2 sensor entity."""

    _attr_device_class = SensorDeviceClass.CO2
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def _update_from_zone(self, zone: Zone) -> None:
        """Update attrs from zone."""
        super()._update_from_zone(zone)

        self._attr_translation_key = "myuplink_zone_co2"
        self._attr_translation_placeholders = {"zone": zone.name}
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{zone.id}_co2"

        self._attr_native_value = zone.indoor_co2


class MyUplinkZoneHumiditySensorEntity(MyUplinkZoneEntity, SensorEntity):
    """Representation of a myUplink zone humidity sensor entity."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def _update_from_zone(self, zone: Zone) -> None:
        """Update attrs from zone."""
        super()._update_from_zone(zone)

        self._attr_translation_key = "myuplink_zone_humidity"
        self._attr_translation_placeholders = {"zone": zone.name}
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{zone.id}_humidity"

        self._attr_native_value = zone.indoor_humidity


class MyUplinkZoneTemperatureSensorEntity(MyUplinkZoneEntity, SensorEntity):
    """Representation of a myUplink zone temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def _update_from_zone(self, zone: Zone) -> None:
        """Update attrs from zone."""
        super()._update_from_zone(zone)

        self._attr_translation_key = "myuplink_zone_temperature"
        self._attr_translation_placeholders = {"zone": zone.name}
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{zone.id}_temperature"

        self._attr_native_value = zone.temperature
        if zone.is_celsius:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        else:
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
