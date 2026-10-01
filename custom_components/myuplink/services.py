"""Services for myUplink integration."""

from __future__ import annotations

import logging
from typing import cast

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_register_admin_service,
)

from .api import Device
from .const import (
    ATTR_PARAMETER_ID,
    ATTR_PROPERTY_NAME,
    ATTR_VALUE,
    ATTR_ZONE_ID,
    DOMAIN,
)
from .coordinator import MyUplinkConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_DEVICE_PARAMETER_VALUE = "set_device_parameter_value"

SERVICE_SCHEMA_SET_DEVICE_PARAMETER_VALUE = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): selector.TextSelector(),
        vol.Required(ATTR_PARAMETER_ID): selector.TextSelector(),
        vol.Required(ATTR_VALUE): selector.TextSelector(),
    }
)

SERVICE_SET_DEVICE_ZONE_PROPERTY_VALUE = "set_device_zone_property_value"

SERVICE_SCHEMA_SET_DEVICE_ZONE_PROPERTY_VALUE = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): selector.TextSelector(),
        vol.Required(ATTR_ZONE_ID): selector.TextSelector(),
        vol.Required(ATTR_PROPERTY_NAME): selector.TextSelector(),
        vol.Required(ATTR_VALUE): selector.TextSelector(),
    }
)

SERVICE_LIST: list[tuple[str, vol.Schema]] = [
    (SERVICE_SET_DEVICE_PARAMETER_VALUE, SERVICE_SCHEMA_SET_DEVICE_PARAMETER_VALUE),
    (
        SERVICE_SET_DEVICE_ZONE_PROPERTY_VALUE,
        SERVICE_SCHEMA_SET_DEVICE_ZONE_PROPERTY_VALUE,
    ),
]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for myUplink integration."""

    async def async_call_myuplink_service(service_call: ServiceCall) -> None:
        """Call myUpLink service."""

        if not (
            device := await _async_get_selected_myuplink_device(hass, service_call)
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"service": service_call.service},
            )

        value = service_call.data[ATTR_VALUE]

        _LOGGER.debug("Executing service %s", service_call.service)

        if service_call.service == SERVICE_SET_DEVICE_PARAMETER_VALUE:
            parameter_id = service_call.data[ATTR_PARAMETER_ID]
            await device.system.api.patch_parameter(device.id, parameter_id, value)
        else:
            zone_id = service_call.data[ATTR_ZONE_ID]
            property_name = service_call.data[ATTR_PROPERTY_NAME]
            await device.system.api.patch_zone_property(
                device.id, zone_id, property_name, value
            )

    for service, schema in SERVICE_LIST:
        if not hass.services.has_service(DOMAIN, service):
            async_register_admin_service(
                hass, DOMAIN, service, async_call_myuplink_service, schema
            )


async def _async_get_selected_myuplink_device(
    hass: HomeAssistant, service_call: ServiceCall
) -> Device | None:
    """Get myUplink device for service call."""

    device_id = service_call.data[ATTR_DEVICE_ID]
    device_registry = dr.async_get(hass)
    hass_device = device_registry.async_get(device_id)
    if hass_device is None:
        return None

    for entry_id in await async_extract_config_entry_ids(service_call):
        config_entry = hass.config_entries.async_get_entry(entry_id)
        if (
            config_entry
            and config_entry.domain == DOMAIN
            and config_entry.state == ConfigEntryState.LOADED
        ):
            coordinator = cast(MyUplinkConfigEntry, config_entry).runtime_data
            for domain, identifier in hass_device.identifiers:
                if (
                    domain == DOMAIN
                    and (device := coordinator.devices_by_id.get(identifier))
                    is not None
                ):
                    _LOGGER.debug("Found device %s", device.id)
                    return device

    return None
