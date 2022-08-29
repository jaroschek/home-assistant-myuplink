"""Definition of base myUplink Entity"""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .api import Device
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
        name_data.reverse()
        manufacturer = name_data.pop()
        name_data.reverse()
        model = " ".join(name_data)
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=manufacturer,
            model=model,
            name=self._device.name,
            sw_version=self._device.current_firmware_version,
        )

    @property
    def available(self):
        """Return if the device is online."""
        return super().available and self._device.connection_state == "Connected"

    def _update_from_device(self, device: Device) -> None:
        """Update attrs from device."""
        self._device = device
        self._attr_name = self._device.name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for system in self.coordinator.data:
            for device in system.devices:
                if device.id == self._device.id:
                    self._update_from_device(device)

        super().async_write_ha_state()
