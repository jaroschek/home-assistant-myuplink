"""Support for myUplink climate."""
from __future__ import annotations

import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import Device, Zone
from .const import DOMAIN
from .entity import MyUplinkEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the climate platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ClimateEntity] = []

    for system in coordinator.data:
        for device in system.devices:
            for zone in device.zones:
                entities.append(MyUplinkZoneClimateEntity(coordinator, device, zone))

    async_add_entities(entities)


class MyUplinkZoneClimateEntity(MyUplinkEntity, ClimateEntity):
    """Representation of an myUplink climate entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, device: Device, zone: Zone
    ) -> None:
        """Initialize a myUplink climate entity."""
        super().__init__(coordinator, device)
        self._update_from_zone(zone)

    def _update_from_zone(self, zone: Zone) -> None:
        """Update attrs from parameter."""
        self._zone = zone
        self._attr_name = f"{self._device.name} {self._zone.name}"
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{self._zone.id}"
        self._attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.HEAT, HVACMode.COOL]
        if self._zone.mode == "heatcool":
            self._attr_hvac_mode = HVACMode.HEAT_COOL
        elif self._zone.mode == "heating":
            self._attr_hvac_mode = HVACMode.HEAT
        elif self._zone.mode == "cooling":
            self._attr_hvac_mode = HVACMode.COOL
        else:
            self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.IDLE
        if self._zone.is_celsius:
            self._attr_temperature_unit = TEMP_CELSIUS
        else:
            self._attr_temperature_unit = TEMP_FAHRENHEIT
        self._attr_supported_features = 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for system in self.coordinator.data:
            for device in system.devices:
                if device.id == self._device.id:
                    super()._update_from_device(device)
                    for zone in device.zones:
                        if zone.id == self._zone.id:
                            self._update_from_zone(zone)

        super().async_write_ha_state()
