"""Coordinate myUplink polling and classify runtime failures."""

import logging
from datetime import timedelta
from http import HTTPStatus

from aiohttp import ClientError, ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Device, MyUplink, MyUplinkRateLimitError, Parameter, System, Zone
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MyUplinkCoordinator(DataUpdateCoordinator[list[System]]):
    """Fetch account data with Home Assistant's retry and reauthentication support."""

    def __init__(
        self, hass: HomeAssistant, entry: MyUplinkConfigEntry, api: MyUplink
    ) -> None:
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
        self.systems_by_id: dict[str, System] = {}
        self.devices_by_id: dict[str, Device] = {}
        self.parameters_by_id: dict[tuple[str, int], Parameter] = {}
        self.zones_by_id: dict[tuple[str, int], Zone] = {}
        self._parameter_platforms: dict[tuple[str, int], Platform] = {}

    def parameter_platform(self, parameter: Parameter) -> Platform:
        """Retain a point's platform until reload to avoid duplicate entities."""
        key = (parameter.device.id, parameter.id)
        if key not in self._parameter_platforms:
            self._parameter_platforms[key] = parameter.get_platform()
        return self._parameter_platforms[key]

    def _index_data(self, systems: list[System]) -> None:
        """Index each successful snapshot for entity lookup."""
        self.systems_by_id = {system.id: system for system in systems}
        self.devices_by_id = {
            device.id: device for system in systems for device in system.devices
        }
        self.parameters_by_id = {
            (device.id, parameter.id): parameter
            for device in self.devices_by_id.values()
            for parameter in device.parameters
        }
        self.zones_by_id = {
            (device.id, zone.id): zone
            for device in self.devices_by_id.values()
            for zone in device.zones
        }

    @callback
    def async_set_updated_data(self, data: list[System]) -> None:
        """Keep lookups consistent with explicitly supplied data."""
        self._index_data(data)
        super().async_set_updated_data(data)

    async def _async_update_data(self) -> list[System]:
        """Refresh data without charging rate-limit waits to a global timeout."""
        try:
            systems = await self.api.get_systems()
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
        self._index_data(systems)
        return systems


type MyUplinkConfigEntry = ConfigEntry[MyUplinkCoordinator]
