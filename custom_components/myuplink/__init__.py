"""The myUplink integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from http import HTTPStatus
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AsyncConfigEntryAuth, MyUplink
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up myUplink."""
    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up myUplink from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        _LOGGER.debug("API error: %s (%s)", err.code, err.message)
        if err.code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    api = MyUplink(
        AsyncConfigEntryAuth(aiohttp_client.async_get_clientsession(hass), session),
        f"{hass.config.language}-{hass.config.country}",
        entry,
    )

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

    hass.data[DOMAIN][entry.entry_id] = coordinator

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
        hass.data[DOMAIN].pop(entry.entry_id)

    await async_unload_services(hass)

    return unload_ok
