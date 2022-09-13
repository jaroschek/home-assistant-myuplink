"""Support for myUplink sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import Device, Parameter
from .const import DOMAIN, DEGREE_MINUTES
from .entity import MyUplinkEntity

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
                entities.append(
                    MyUplinkParameterSensorEntity(coordinator, device, parameter)
                )

    async_add_entities(entities)


class MyUplinkParameterSensorEntity(MyUplinkEntity, SensorEntity):
    """Representation of a myUplink temperature reporting sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, device: Device, parameter: Parameter
    ) -> None:
        """Initialize a myUplink parameter sensor."""
        super().__init__(coordinator, device)
        self._update_from_parameter(parameter)

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        self._parameter = parameter
        self._attr_name = f"{self._device.name} {self._parameter.name}"
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{self._parameter.id}"
        self._attr_native_value = self._parameter.value
        self._attr_native_unit_of_measurement = self._parameter.unit
        if self._parameter.unit == TEMP_CELSIUS:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif self._parameter.unit == DEGREE_MINUTES:
            self._attr_device_class = "degree_minutes"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for system in self.coordinator.data:
            for device in system.devices:
                if device.id == self._device.id:
                    super()._update_from_device(device)
                    for parameter in device.parameters:
                        if parameter.id == self._parameter.id:
                            self._update_from_parameter(parameter)

        super().async_write_ha_state()
