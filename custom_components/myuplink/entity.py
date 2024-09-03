"""Definition of base myUplink Entity."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .api import Device, Parameter
from .const import DOMAIN


class MyUplinkEntity(CoordinatorEntity):
    """Base class for myUplink Entities."""

    def __init__(self, coordinator: DataUpdateCoordinator, device: Device) -> None:
        """Initialize class."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{device.id}"
        self._update_from_device(device)

    @property
    def device_info(self):
        """Return the device_info of the device."""
        name_data = self._device.name.split()
        model = name_data[0]
        manufacturer = None
        if len(name_data) > 1:
            # Assumes first word in raw name is manufacturer
            model = " ".join(name_data[1:])
            manufacturer = name_data[0]
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=manufacturer,
            model=model,
            name=self._device.name,
            sw_version=self._device.current_firmware_version,
        )

    def _update_from_device(self, device: Device) -> None:
        """Update attrs from device."""
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for system in self.coordinator.data:
            for device in system.devices:
                if device.id == self._device.id:
                    self._update_from_device(device)

        super().async_write_ha_state()


class MyUplinkParameterEntity(MyUplinkEntity):
    """Representation of a myUplink parameter entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, device: Device, parameter: Parameter
    ) -> None:
        """Initialize a myUplink parameter entity."""
        super().__init__(coordinator, device)
        self._update_from_parameter(parameter)

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        self._parameter = parameter
        if self._parameter.category and self._device.name != self._parameter.category:
            self._attr_name = f"{self._parameter.category} {self._parameter.name} ({self._parameter.id})"
        else:
            self._attr_name = f"{self._parameter.name} ({self._parameter.id})"
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{self._parameter.id}"

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

    @property
    def available(self):
        """Return if the device is online."""
        return super().available and self._device.connection_state == "Connected"
