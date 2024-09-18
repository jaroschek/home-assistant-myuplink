"""Support for myUplink update platform."""

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Device
from .const import CONF_FETCH_FIRMWARE, DOMAIN
from .entity import MyUplinkDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up update platform entities."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[UpdateEntity] = []

    if entry.options.get(CONF_FETCH_FIRMWARE, True):
        for system in coordinator.data:
            [
                entities.append(MyUplinkUpdateEntity(coordinator, device))
                for device in system.devices
            ]

    async_add_entities(entities)


class MyUplinkUpdateEntity(MyUplinkDeviceEntity, UpdateEntity):
    """Representation of a myUplink update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True

    def _update_from_device(self, device: Device) -> None:
        """Update attrs from device."""
        super()._update_from_device(device)

        self._attr_translation_key = f"{DOMAIN}_firmware"
        self._attr_unique_id = f"{DOMAIN}_{device.id}_firmware"

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self._device.firmware_info.current_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._device.firmware_info.desired_version
