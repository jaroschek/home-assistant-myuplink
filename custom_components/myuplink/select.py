"""Support for myUplink sensors."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Parameter
from .const import DOMAIN
from .entity import MyUplinkParameterEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []

    for system in coordinator.data:
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
    """Representation of a myUplink paramater binary sensor."""

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        super()._update_from_parameter(parameter)
        self._attr_translation_key = str(self._parameter.id)
        self._attr_options = []
        for enum in parameter.enum_values:
            self._attr_options.append(enum["text"])
        self._attr_current_option = parameter.string_value

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        options = {}
        for enum in self._parameter.enum_values:
            options[enum["text"]] = enum["value"]
        await self._parameter.update_parameter(options[option])
        await self.async_update()
