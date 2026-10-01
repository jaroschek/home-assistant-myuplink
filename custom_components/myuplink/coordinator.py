"""Coordinate myUplink polling and classify runtime failures."""

import logging
from datetime import timedelta
from http import HTTPStatus

from aiohttp import ClientError, ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyUplink, MyUplinkRateLimitError, System
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MyUplinkCoordinator(DataUpdateCoordinator[list[System]]):
    """Fetch account data with Home Assistant's retry and reauthentication support."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: MyUplink) -> None:
        """Bind the client and polling interval to this account."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="myUplink",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.api = api

    async def _async_update_data(self) -> list[System]:
        """Refresh data without charging rate-limit waits to a global timeout."""
        try:
            return await self.api.get_systems()
        except MyUplinkRateLimitError as err:
            raise UpdateFailed(
                "The myUplink request limit was reached", retry_after=err.retry_after
            ) from err
        except ClientResponseError as err:
            if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise ConfigEntryAuthFailed("myUplink authorization expired") from err
            raise UpdateFailed(f"myUplink API returned HTTP {err.status}") from err
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed("Unable to communicate with myUplink") from err
