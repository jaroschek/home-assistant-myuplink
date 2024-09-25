"""Services for myUplink integration."""

from __future__ import annotations

import logging

from aiohttp import ClientResponseError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, selector
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import Device
from .const import ATTR_PARAMETER_ID, ATTR_VALUE, DOMAIN

_LOGGER = logging.getLogger(__name__)

MYUPLINK_SERVICES = "myuplink_services"

SERVICE_SET_DEVICE_PARAMETER_VALUE = "set_device_parameter_value"

SERVICE_SCHEMA_SET_DEVICE_PARAMETER_VALUE = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): selector.TextSelector(),
        vol.Required(ATTR_PARAMETER_ID): selector.TextSelector(),
        vol.Required(ATTR_VALUE): selector.TextSelector(),
    }
)

SERVICE_LIST: list[tuple[str, vol.Schema | None]] = [
    (SERVICE_SET_DEVICE_PARAMETER_VALUE, SERVICE_SCHEMA_SET_DEVICE_PARAMETER_VALUE),
]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for myUplink integration."""

    for service, _ in SERVICE_LIST:
        if hass.services.has_service(DOMAIN, service):
            return

    async def async_call_myuplink_service(service_call: ServiceCall) -> None:
        """Call myUpLink service."""

        if not (
            device := await _async_get_selected_myuplink_device(hass, service_call)
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"service": service_call.service},
            )

        _LOGGER.debug("Executing service %s", service_call.service)

        try:
            parameter_id = service_call.data.get(ATTR_PARAMETER_ID)
            value = service_call.data.get(ATTR_VALUE)
            await device.system.api.patch_parameter(
                device.id,
                parameter_id,
                value,
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                f"The myUplink API returned an error trying to set the parameter {parameter_id} to value {value} for device {device.id,}"
                f" Code: {ex.status}  Message: {ex.message}"
            ) from ex

    for service, schema in SERVICE_LIST:
        hass.services.async_register(
            DOMAIN, service, async_call_myuplink_service, schema
        )


async def _async_get_selected_myuplink_device(
    hass: HomeAssistant, service_call: ServiceCall
) -> Device | None:
    """Get myUplink device for service call."""

    device_id = service_call.data.get(ATTR_DEVICE_ID)
    device_registry = dr.async_get(hass)

    for entry_id in await async_extract_config_entry_ids(hass, service_call):
        config_entry = hass.config_entries.async_get_entry(entry_id)
        if (
            config_entry
            and config_entry.domain == DOMAIN
            and config_entry.state == ConfigEntryState.LOADED
        ):
            coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry_id]
            for myuplink_system in coordinator.data:
                for myuplink_device in myuplink_system.devices:
                    hass_device = device_registry.async_get_device(
                        identifiers={(DOMAIN, myuplink_device.id)}
                    )
                    if hass_device is not None and hass_device.id == device_id:
                        _LOGGER.debug("Found device %s", myuplink_device.id)
                        return myuplink_device

    return None


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services for myUplink integration."""

    if not hass.data.get(MYUPLINK_SERVICES):
        return

    hass.data[MYUPLINK_SERVICES] = False

    for service, _ in SERVICE_LIST:
        hass.services.async_remove(DOMAIN, service)
