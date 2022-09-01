"""API for myUplink bound to Home Assistant OAuth."""
from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientSession, ClientResponse
from datetime import datetime, timedelta

from homeassistant.helpers import config_entry_oauth2_flow

from .const import API_HOST, API_VERSION

_LOGGER = logging.getLogger(__name__)


class AsyncConfigEntryAuth:
    """Provide myUplink authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize myUplink auth."""
        self._websession = websession
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]

    async def request(self, method, path, **kwargs) -> ClientResponse:
        """Make an authorized request."""
        headers = kwargs.get("headers")

        if headers is None:
            headers = {}
        else:
            headers = dict(headers)

        access_token = await self.async_get_access_token()
        headers["authorization"] = f"Bearer {access_token}"

        return await self._websession.request(
            method,
            f"{API_HOST}/{API_VERSION}/{path}",
            **kwargs,
            headers=headers,
        )


class Parameter:
    """Class that represents a parameter object in the myUplink API."""

    def __init__(self, raw_data: dict) -> None:
        """Initialize a parameter object."""
        self.raw_data = raw_data

    @property
    def category(self) -> str:
        """Return the category of the parameter."""
        return self.raw_data["category"]

    @property
    def id(self) -> int:
        """Return the ID of the parameter."""
        return self.raw_data["parameterId"]

    @property
    def name(self) -> str:
        """Return the name of the parameter."""
        return self.raw_data["parameterName"]

    @property
    def unit(self) -> str:
        """Return the unit of the parameter."""
        return self.raw_data["parameterUnit"]

    @property
    def is_writable(self) -> bool:
        """Return if the parameter is writable."""
        return self.raw_data["writable"]

    @property
    def timestamp(self) -> str:
        """Return the timestamp of the parameter."""
        return self.raw_data["timestamp"]

    @property
    def value(self) -> float:
        """Return the value of the paramter."""
        return self.raw_data["value"]

    @property
    def string_value(self) -> str:
        """Return the string value of the parameter."""
        return self.raw_data["strVal"]

    @property
    def smart_home_categories(self) -> list[str]:
        """Return the smart home categories of the parameter."""
        return self.raw_data["smartHomeCategories"]

    @property
    def min_value(self) -> int:
        """Return the min value of the parameter."""
        return self.raw_data["minVal"]

    @property
    def max_value(self) -> int:
        """Return the max value of the parameter."""
        return self.raw_data["maxVal"]

    @property
    def enum_values(self) -> list[str]:
        """Return the enum values of the parameter."""
        return self.raw_data["enumValues"]

    @property
    def zone_id(self) -> str:
        """Return the zone id of the parameter."""
        return self.raw_data["zoneId"]


class Zone:
    """Class that represents a zone object in the myUplink API."""

    def __init__(self, raw_data: dict) -> None:
        """Initialize a zone object."""
        self.raw_data = raw_data

    @property
    def id(self) -> int:
        """Return the ID of the zone."""
        return self.raw_data["zoneId"]

    @property
    def name(self) -> str:
        """Return the name of the zone."""
        return self.raw_data["name"]

    @property
    def is_command_only(self) -> bool:
        """Return if the zone is command only."""
        return self.raw_data["commandOnly"]

    @property
    def supported_modes(self) -> str:
        """Return the supported modes of the zone."""
        return self.raw_data["supportedModes"]

    @property
    def mode(self) -> str:
        """Return the current mode of the zone."""
        return self.raw_data["mode"]

    @property
    def temperature(self) -> float:
        """Return the current temperature of the zone."""
        return self.raw_data["temperature"]

    @property
    def setpoint(self) -> float:
        """Return the target temperature of the zone."""
        return self.raw_data["setpoint"]

    @property
    def setpoint_heating(self) -> float:
        """Return the heating setpoint value of the zone."""
        return self.raw_data["setpointHeat"]

    @property
    def setpoint_cooling(self) -> float:
        """Return the cooling setpoint value of the zone."""
        return self.raw_data["setpointCool"]

    @property
    def setpoint_range_min(self) -> int:
        """Return the minimum temperature range of the zone."""
        return self.raw_data["setpointRangeMin"]

    @property
    def setpoint_range_max(self) -> int:
        """Return the maximum temperature range of the zone."""
        return self.raw_data["setpointRangeMax"]

    @property
    def is_celsius(self) -> bool:
        """Return if the temperature in the zone is specified as celsius (true) or fahrenheit (false)."""
        return self.raw_data["isCelsius"]

    @property
    def indoor_co2(self) -> int:
        """Return the indoor co2 level of the zone."""
        return self.raw_data["indoorCo2"]

    @property
    def indoor_umidity(self) -> float:
        """Return the indoor humidity of the zone."""
        return self.raw_data["indoorHumidity"]


class Device:
    """Class that represents a device object in the myUplink API."""

    def __init__(self, raw_data: dict, api: MyUplink) -> None:
        """Initialize a device object."""
        self.raw_data = raw_data
        self.api = api
        self.parameters = []
        self.zones = []

    @property
    def id(self) -> int:
        """Return the ID of the device."""
        return self.raw_data["id"]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.raw_data["product"]["name"]

    @property
    def connection_state(self) -> str:
        """Return the connection_state of the device."""
        return self.raw_data["connectionState"]

    @property
    def serial_number(self) -> str:
        """Return the connection_state of the device."""
        return self.raw_data["product"]["serialNumber"]

    @property
    def current_firmware_version(self) -> str:
        """Return the current firmware version of the device."""
        if "firmware" in self.raw_data:
            return self.raw_data["firmware"]["currentFwVersion"]

        return self.raw_data["currentFwVersion"]

    @property
    def desired_firmware_version(self) -> str:
        """Return the desired firmware version of the device."""
        if "firmware" in self.raw_data:
            return self.raw_data["firmware"]["desiredFwVersion"]

        return "?"

    async def async_fetch_data(self) -> None:
        """Fetch data from myUplink API."""
        self.parameters = await self.api.get_parameters(self.id)
        self.zones = await self.api.get_zones(self.id)


class System:
    """Class that represents a system object in the myUplink API."""

    def __init__(self, raw_data: dict, api: MyUplink) -> None:
        """Initialize a system object."""
        self.raw_data = raw_data
        self.api = api
        self.devices = []

    @property
    def id(self) -> int:
        """Return the ID of the system."""
        return self.raw_data["systemId"]

    @property
    def name(self) -> str:
        """Return the name of the system."""
        return self.raw_data["name"]

    @property
    def security_level(self) -> str:
        """Return the security level of the system."""
        return self.raw_data["securityLevel"]

    @property
    def has_alaram(self) -> bool:
        """Return if the system has an alaram."""
        return self.raw_data["has_alaram"]

    async def async_fetch_data(self) -> None:
        """Fetch data from myUplink API."""
        for device_data in self.raw_data["devices"]:
            device = Device(device_data, self.api)
            await device.async_fetch_data()
            self.devices.append(device)


class Throttle:
    """Throttling requests to API."""

    def __init__(self, delay):
        """Initialize throttle"""
        self._delay = delay
        self._timestamp = datetime.now()

    async def __aenter__(self):
        """Enter async throttle"""
        timestamp = datetime.now()
        delay = (self._timestamp - timestamp).total_seconds()
        if delay > 0:
            _LOGGER.debug("Delaying request by %s seconds due to throttle", delay)
            await asyncio.sleep(delay)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async throttle"""
        self._timestamp = datetime.now() + self._delay


class MyUplink:
    """Class to communicate with the myUplink API."""

    def __init__(self, auth: AsyncConfigEntryAuth) -> None:
        """Initialize the API and store the auth so we can make requests."""
        self.auth = auth
        self.lock = asyncio.Lock()
        self.throttle = Throttle(timedelta(seconds=5))

    async def get_systems(self) -> list[System]:
        """Return all systems."""
        async with self.lock, self.throttle:
            resp = await self.auth.request("get", "systems/me")
        resp.raise_for_status()
        data = await resp.json()

        systems = []
        for system_data in data["systems"]:
            system = System(system_data, self)
            await system.async_fetch_data()
            systems.append(system)
        return systems

    async def get_device(self, device_id) -> Device:
        """Return a device by id."""
        async with self.lock, self.throttle:
            resp = await self.auth.request("get", f"devices/{device_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_parameters(self, device_id) -> list[Parameter]:
        """Return all parameters for a device."""
        async with self.lock, self.throttle:
            resp = await self.auth.request("get", f"devices/{device_id}/points")
        resp.raise_for_status()
        return [Parameter(parameter) for parameter in await resp.json()]

    async def get_zones(self, device_id) -> list[Zone]:
        """Return all smart home zones for a device."""
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "get", f"devices/{device_id}/smart-home-zones"
            )
        resp.raise_for_status()
        return [Zone(zone) for zone in await resp.json()]
