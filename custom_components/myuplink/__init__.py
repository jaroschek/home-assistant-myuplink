"""The myUplink integration."""

from __future__ import annotations

import logging
from http import HTTPStatus

import aiohttp
import jwt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .api import AsyncConfigEntryAuth, MyUplink
from .const import PLATFORMS, SCOPES
from .coordinator import MyUplinkCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions independently of account availability."""
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up myUplink from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(aiohttp_client.async_get_clientsession(hass), session)

    try:
        await auth.async_get_access_token()
    except aiohttp.ClientResponseError as err:
        _LOGGER.debug("API error: %s (%s)", err.status, err.message)
        if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except (aiohttp.ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady from err

    if not set(SCOPES).issubset(entry.data["token"]["scope"].split()):
        raise ConfigEntryAuthFailed

    api = MyUplink(auth, f"{hass.config.language}-{hass.config.country}", entry)

    coordinator = MyUplinkCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if entry.version == 1 and entry.minor_version == 1:
        token = jwt.decode(
            entry.data["token"]["access_token"], options={"verify_signature": False}
        )
        hass.config_entries.async_update_entry(
            entry, unique_id=token["sub"], minor_version=2
        )

    _LOGGER.info(
        "Migration to version %s.%s successful", entry.version, entry.minor_version
    )

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True
