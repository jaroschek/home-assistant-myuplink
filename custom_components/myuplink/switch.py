"""Support for myUplink sensors."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
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
    entities: list[SwitchEntity] = []

    for system in coordinator.data:
        for device in system.devices:
            for parameter in device.parameters:
                if parameter.find_fitting_entity() == Platform.SWITCH:
                    entities.append(
                        MyUplinkParameterSwitchEntityEntity(
                            coordinator, device, parameter
                        )
                    )

    async_add_entities(entities)


class MyUplinkParameterSwitchEntityEntity(MyUplinkParameterEntity, SwitchEntity):
    """Representation of a myUplink paramater binary sensor."""

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Update attrs from parameter."""
        super()._update_from_parameter(parameter)
        self._attr_is_on = bool(int(self._parameter.value))

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self._parameter.update_parameter(1)
        await self.async_update()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._parameter.update_parameter(0)
        await self.async_update()
