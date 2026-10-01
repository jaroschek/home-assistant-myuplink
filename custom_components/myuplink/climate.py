"""Support for myUplink climate entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Zone
from .const import DOMAIN
from .entity import MyUplinkZoneEntity, async_setup_entities

THERMOSTAT_MODE_MAP: dict[str, HVACMode] = {
    "off": HVACMode.OFF,
    "auto": HVACMode.AUTO,
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "heatcool": HVACMode.HEAT_COOL,
}
THERMOSTAT_MODE_MAP_INVERTED: dict[HVACMode, str] = {
    HVACMode.OFF: "off",
    HVACMode.AUTO: "auto",
    HVACMode.HEAT: "heat",
    HVACMode.COOL: "cool",
    HVACMode.HEAT_COOL: "heatcool",
}

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the climate platform entities."""

    coordinator = entry.runtime_data

    def build_entities() -> list[ClimateEntity]:
        """Build entities from the current snapshot."""
        entities: list[ClimateEntity] = []

        for system in coordinator.data:
            for device in system.devices:
                for zone in device.zones:
                    if not zone.is_command_only:
                        entities.append(
                            MyUplinkZoneClimateEntity(coordinator, device, zone)
                        )
        return entities

    async_setup_entities(entry, async_add_entities, build_entities)


class MyUplinkZoneClimateEntity(MyUplinkZoneEntity, ClimateEntity):
    """Representation a myUplink smart home zone climate entity."""

    def _update_from_zone(self, zone: Zone) -> None:
        """Update attrs from zone."""
        super()._update_from_zone(zone)

        self._attr_translation_key = "myuplink_thermostat"
        self._attr_translation_placeholders = {"zone": zone.name}
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{zone.id}_thermostat"

        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        if zone.supported_modes is not None and zone.supported_modes != "":
            self._attr_hvac_modes = [
                THERMOSTAT_MODE_MAP[mode]
                for mode in zone.supported_modes.split(",")
                if mode in THERMOSTAT_MODE_MAP
            ]
        else:
            self._attr_hvac_modes = (
                [THERMOSTAT_MODE_MAP[zone.mode]]
                if zone.mode in THERMOSTAT_MODE_MAP
                else []
            )
        self._attr_hvac_mode = THERMOSTAT_MODE_MAP.get(zone.mode)

        self._attr_current_temperature = zone.temperature
        if zone.is_celsius:
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        else:
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

        self._attr_current_humidity = zone.indoor_humidity
        if zone.setpoint_range_max is not None:
            self._attr_max_temp = zone.setpoint_range_max
        if zone.setpoint_range_min is not None:
            self._attr_min_temp = zone.setpoint_range_min
        self._attr_target_temperature = zone.setpoint
        if zone.setpoint_heating is not None and zone.mode == "heat":
            self._attr_target_temperature = zone.setpoint_heating
        if zone.setpoint_cooling is not None and zone.mode == "cool":
            self._attr_target_temperature = zone.setpoint_cooling

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = float(kwargs[ATTR_TEMPERATURE])
        property_name = {"heat": "setpointHeat", "cool": "setpointCool"}.get(
            self._zone.mode, "setpoint"
        )
        await self._zone.update_zone_property(property_name, temperature)
        self._attr_target_temperature = temperature
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._zone.update_zone_property(
            "mode", THERMOSTAT_MODE_MAP_INVERTED[hvac_mode]
        )
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
