"""Shared myUplink entities and discovery lifecycle."""

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Device, Parameter, System, Zone
from .const import CONF_DISCONNECTED_AVAILABLE, DOMAIN
from .coordinator import MyUplinkCoordinator


@callback
def async_setup_entities(
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    build_entities: Callable[[], Iterable[Entity]],
) -> None:
    """Discover new entities after every refresh and unsubscribe on unload."""
    known_ids: set[str | None] = set()

    @callback
    def async_discover() -> None:
        entities = []
        for entity in build_entities():
            if entity.unique_id not in known_ids:
                known_ids.add(entity.unique_id)
                entities.append(entity)
        if entities:
            async_add_entities(entities)

    async_discover()
    entry.async_on_unload(entry.runtime_data.async_add_listener(async_discover))


class MyUplinkSystemEntity(CoordinatorEntity[MyUplinkCoordinator]):
    """Base class for account-system entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MyUplinkCoordinator, system: System) -> None:
        """Initialize stable identity and initial state."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{system.id}"
        self._present = True
        self._update_from_system(system)

    @property
    def available(self) -> bool:
        """Return availability of the current system snapshot."""
        return super().available and self._present

    @property
    def device_info(self) -> DeviceInfo:
        """Return the system's registry information."""
        name_data = self._system.name.split()
        return DeviceInfo(
            identifiers={(DOMAIN, self._system.id)},
            manufacturer=name_data[0] if len(name_data) > 1 else None,
            model=" ".join(name_data[1:]) if len(name_data) > 1 else self._system.name,
            name=self._system.name,
        )

    def _update_from_system(self, system: System) -> None:
        """Apply a new system snapshot."""
        self._system = system

    @callback
    def _handle_coordinator_update(self) -> None:
        """Mark missing systems unavailable without retaining a current state."""
        system = self.coordinator.systems_by_id.get(self._system.id)
        self._present = system is not None
        if system is not None:
            self._update_from_system(system)
        self.async_write_ha_state()


class MyUplinkDeviceEntity(CoordinatorEntity[MyUplinkCoordinator]):
    """Base class for device entities."""

    _attr_has_entity_name = True
    _requires_connection = True

    def __init__(self, coordinator: MyUplinkCoordinator, device: Device) -> None:
        """Initialize stable identity and initial state."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{device.id}"
        self._present = True
        self._update_from_device(device)

    @property
    def available(self) -> bool:
        """Return whether the current snapshot can provide device data."""
        return (
            super().available
            and self._present
            and (
                not self._requires_connection
                or self._device.connection_state == "Connected"
                or self._device.system.api.entry.options.get(
                    CONF_DISCONNECTED_AVAILABLE, False
                )
            )
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        name_data = self._device.name.split()
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=name_data[0] if len(name_data) > 1 else None,
            model=" ".join(name_data[1:]) if len(name_data) > 1 else self._device.name,
            name=self._device.name,
            serial_number=self._device.serial_number,
            sw_version=self._device.current_firmware_version,
        )

    def _update_from_device(self, device: Device) -> None:
        """Apply a new device snapshot."""
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply fresh data or mark a missing device unavailable."""
        device = self.coordinator.devices_by_id.get(self._device.id)
        self._present = device is not None
        if device is not None:
            self._update_from_device(device)
        self.async_write_ha_state()


class MyUplinkParameterEntity(MyUplinkDeviceEntity):
    """Base class for parameter entities."""

    def __init__(
        self, coordinator: MyUplinkCoordinator, device: Device, parameter: Parameter
    ) -> None:
        """Initialize a point with its existing unique ID."""
        super().__init__(coordinator, device)
        self._update_from_parameter(parameter)

    def _update_from_parameter(self, parameter: Parameter) -> None:
        """Apply parameter data and its device-relative name."""
        self._parameter = parameter
        self._attr_translation_key = "parameter"
        if parameter.category and self._device.name != parameter.category:
            name = f"{parameter.category} {parameter.name}"
        else:
            name = parameter.name
        self._attr_translation_placeholders = {"name": name, "id": str(parameter.id)}
        self._attr_unique_id = f"{DOMAIN}_{self._device.id}_{parameter.id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Mark a point unavailable if it disappears from a successful refresh."""
        device = self.coordinator.devices_by_id.get(self._device.id)
        parameter = self.coordinator.parameters_by_id.get(
            (self._device.id, self._parameter.id)
        )
        self._present = device is not None and parameter is not None
        if device is not None and parameter is not None:
            self._update_from_device(device)
            self._update_from_parameter(parameter)
        self.async_write_ha_state()


class MyUplinkZoneEntity(MyUplinkDeviceEntity):
    """Base class for smart-home zone entities."""

    def __init__(
        self, coordinator: MyUplinkCoordinator, device: Device, zone: Zone
    ) -> None:
        """Initialize a zone with its existing unique ID."""
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}_{device.id}_zone_{zone.id}"
        self._update_from_zone(zone)

    def _update_from_zone(self, zone: Zone) -> None:
        """Apply a new zone snapshot."""
        self._zone = zone

    @callback
    def _handle_coordinator_update(self) -> None:
        """Mark a zone unavailable if it disappears from the latest data."""
        device = self.coordinator.devices_by_id.get(self._device.id)
        zone = self.coordinator.zones_by_id.get((self._device.id, self._zone.id))
        self._present = device is not None and zone is not None
        if device is not None and zone is not None:
            self._update_from_device(device)
            self._update_from_zone(zone)
        self.async_write_ha_state()
