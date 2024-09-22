"""Support for myUplink sensors."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Device, Parameter, System
from .const import (
    CONF_DISCONNECTED_AVAILABLE,
    CONF_ENABLE_SMART_HOME_MODE,
    DOMAIN,
    SmartHomeModes,
)
from .entity import MyUplinkDeviceEntity, MyUplinkParameterEntity, MyUplinkSystemEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the platform entities."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []

    enable_smart_home_mode = entry.options.get(CONF_ENABLE_SMART_HOME_MODE, True)

    for system in coordinator.data:
        if enable_smart_home_mode:
            if len(system.devices) == 1:
                entities.append(
                    MyUplinkSmartHomeModeDeviceSelectEntity(
                        coordinator, system.devices[0]
                    )
                )
            else:
                entities.append(
                    MyUplinkSmartHomeModeSystemSelectEntity(coordinator, system)
                )

        for device in system.devices:
            [
                entities.append(
                    MyUplinkParameterSelectEntity(coordinator, device, parameter)
                )
                for parameter in device.parameters
                if parameter.get_platform() == Platform.SELECT
            ]

    async_add_entities(entities)


class MyUplinkParameterSelectEntity(MyUplinkParameterEntity, SelectEntity):
    """Representation of a myUplink paramater select sensor."""

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        super()._update_from_parameter(parameter)
        self._attr_translation_key = str(self._parameter.id)
        self._attr_options = []
        for enum in parameter.enum_values:
            self._attr_options.append(enum["text"])
        self._attr_current_option = parameter.string_value

    async def async_select_option(self, option: str) -> None:
        """Change the selected parameter option."""
        options = {}
        for enum in self._parameter.enum_values:
            options[enum["text"]] = enum["value"]
        await self._parameter.update_parameter(options[option])
        await self.async_update()


class MyUplinkSmartHomeModeDeviceSelectEntity(MyUplinkDeviceEntity, SelectEntity):
    """Representation of a myUplink smart home mode select sensor for a single device system."""

    _attr_has_entity_name = True

    def _update_from_device(self, device: Device) -> None:
        """Update attrs from device."""
        super()._update_from_device(device)
        self._attr_translation_key = f"{DOMAIN}_smart_home_mode"
        self._attr_unique_id = f"{DOMAIN}_{device.system.id}_smart_home_mode"
        self._attr_options = []
        for mode in SmartHomeModes:
            self._attr_options.append(mode.lower())
        self._attr_current_option = device.system.smart_home_mode.lower()

    async def async_select_option(self, option: str) -> None:
        """Change the selected smart home mode option."""
        await self._device.system.update_smart_home_mode(option.title())
        await self.async_update()

    @property
    def available(self):
        """Return if the device is online."""
        return super().available and (
            self._device.connection_state == "Connected"
            or self._device.system.api.entry.options.get(
                CONF_DISCONNECTED_AVAILABLE, False
            )
        )


class MyUplinkSmartHomeModeSystemSelectEntity(MyUplinkSystemEntity, SelectEntity):
    """Representation of a myUplink smart home mode select sensor for a multi device system."""

    _attr_has_entity_name = True

    def _update_from_system(self, system: System) -> None:
        """Update attrs from system."""
        super()._update_from_system(system)
        self._attr_translation_key = f"{DOMAIN}_smart_home_mode"
        self._attr_unique_id = f"{DOMAIN}_{system.id}_smart_home_mode"
        self._attr_options = []
        for mode in SmartHomeModes:
            self._attr_options.append(mode.lower())
        self._attr_current_option = system.smart_home_mode.lower()

    async def async_select_option(self, option: str) -> None:
        """Change the selected smart home mode option."""
        await self._system.update_smart_home_mode(option.title())
        await self.async_update()
