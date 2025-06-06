"""The myUplink integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from http import HTTPStatus
import logging

import aiohttp
import jwt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AsyncConfigEntryAuth, MyUplink
from .const import DEFAULT_SCAN_INTERVAL, PLATFORMS, SCOPES
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


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
        _LOGGER.debug("API error: %s (%s)", err.code, err.message)
        if err.code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    if set(entry.data["token"]["scope"].split(" ")) != set(SCOPES):
        raise ConfigEntryAuthFailed

    api = MyUplink(auth, f"{hass.config.language}-{hass.config.country}", entry)

    async def async_update_data():
        try:
            async with asyncio.timeout(30):
                return await api.get_systems()
        except aiohttp.ClientResponseError as err:
            raise UpdateFailed(f"Wrong credentials: {err}") from err
        except aiohttp.ClientConnectorError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    _LOGGER.debug(
        "Initialize coordinator with %d seconds update interval", scan_interval
    )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="myUplink",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_setup_services(hass)

    entry.current_options = {**entry.options}

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""

    if entry.current_options == entry.options:
        return

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await async_unload_services(hass)

    return unload_ok


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
