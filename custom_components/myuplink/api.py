"""API for myUplink bound to Home Assistant OAuth."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
import json
import logging

from aiohttp import ClientResponse, ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    API_HOST,
    API_VERSION,
    CONF_ADDITIONAL_PARAMETER,
    CONF_ENABLE_SMART_HOME_MODE,
    CONF_FETCH_FIRMWARE,
    CONF_FETCH_NOTIFICATIONS,
    CONF_PARAMETER_WHITELIST,
    CONF_PLATFORM_OVERRIDE,
    CONF_WRITABLE_OVERRIDE,
    CONF_WRITABLE_WITHOUT_SUBSCRIPTION,
    DEFAULT_PLATFORM_OVERRIDE,
    DEFAULT_WRITABLE_OVERRIDE,
)

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
        await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]

    async def request(self, method, path, **kwargs) -> ClientResponse:
        """Make an authorized request."""
        headers = kwargs.pop("headers", None)

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

class Subscription:
    def __init__(self, raw_data: dict) -> None:
        self.raw_data = raw_data
    
    @property
    def type(self) -> str:
        return self.raw_data["type"]
    
    @property
    def validUntil(self) -> datetime:
        return datetime(self.raw_data("validUntil"))

class Notification:
    """Class that represents the notificationobject in the myUplink API."""

    def __init__(self, raw_data: dict) -> None:
        """Initialize a notification object."""
        self.raw_data = raw_data

    @property
    def id(self) -> str:
        """Return the ID of the notification."""
        return self.raw_data["id"]

    @property
    def alarm_number(self) -> int:
        """Return the alarm number of the notification."""
        return int(self.raw_data["alarmNumber"])

    @property
    def device_id(self) -> str:
        """Return the device ID of the notification."""
        return self.raw_data["deviceId"]

    @property
    def severity(self) -> int:
        """Return the severity of the notification."""
        return int(self.raw_data["severity"])

    @property
    def status(self) -> str:
        """Return the status of the notification."""
        return self.raw_data["status"]

    @property
    def created_datetime(self) -> str:
        """Return the created date time of the notification."""
        return self.raw_data["createdDatetime"]

    @property
    def header(self) -> str:
        """Return the header of the notification."""
        return self.raw_data["header"]

    @property
    def description(self) -> str:
        """Return the description of the notification."""
        return self.raw_data["description"]

    @property
    def equipment(self) -> str:
        """Return the equipment of the notification."""
        return self.raw_data["equipName"]


class FirmwareInfo:
    """Class that represents the firmware info object in the myUplink API."""

    def __init__(self, raw_data: dict) -> None:
        """Initialize a firmware object."""
        self.raw_data = raw_data

    @property
    def device_id(self) -> str:
        """Return the ID of the device."""
        return self.raw_data["deviceId"]

    @property
    def firmware_id(self) -> int:
        """Return the ID of the firmware."""
        return int(self.raw_data["firmwareId"])

    @property
    def current_version(self) -> str:
        """Return the current firmware version of the device."""
        if self.raw_data["currentFwVersion"].strip() == "":
            return None
        return self.raw_data["currentFwVersion"].strip()

    @property
    def pending_version(self) -> str:
        """Return the pending firmware version of the device."""
        if self.raw_data["pendingFwVersion"].strip() == "":
            return None
        return self.raw_data["pendingFwVersion"].strip()

    @property
    def desired_version(self) -> str:
        """Return the desired firmware version of the device."""
        if self.raw_data["desiredFwVersion"].strip() == "":
            return None
        return self.raw_data["desiredFwVersion"].strip()


class Parameter:
    """Class that represents a parameter object in the myUplink API."""

    def __init__(self, raw_data: dict, device: Device) -> None:
        """Initialize a parameter object."""
        self.raw_data = raw_data
        self.device = device

    @property
    def category(self) -> str:
        """Return the category of the parameter."""
        if "Text not found" in self.raw_data["category"]:
            return ""
        return self.raw_data["category"]

    @property
    def id(self) -> int:
        """Return the ID of the parameter."""
        return int(self.raw_data["parameterId"])

    @property
    def name(self) -> str:
        """Return the name of the parameter."""
        return self.raw_data["parameterName"].replace("\xad", "")

    @property
    def unit(self) -> str:
        """Return the unit of the parameter."""
        return self.get_unit(self.raw_data["parameterUnit"])

    @property
    def is_writable(self) -> bool:
        """Return if the parameter is writable."""
        if self.device.system.premium_manage or self.device.system.api.writable_without_subscription:
            if self.id in self.device.system.api.writable_override:
                return self.device.system.api.writable_override[self.id]

            return self.raw_data["writable"]
        return False

    @property
    def timestamp(self) -> str:
        """Return the timestamp of the parameter."""
        return self.raw_data["timestamp"]

    @property
    def value(self) -> float | None:
        """Return the value of the paramter."""
        if self.raw_data["value"] == -32768:
            return None

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
        return self.raw_data["minValue"]

    @property
    def max_value(self) -> int:
        """Return the max value of the parameter."""
        return self.raw_data["maxValue"]

    @property
    def step_value(self) -> int:
        """Return the step value of the parameter."""
        return self.raw_data["stepValue"]

    @property
    def enum_values(self) -> list[dict]:
        """Return the enum values of the parameter."""
        return self.raw_data["enumValues"]

    @property
    def scale_value(self) -> float | None:
        """Return the scale value of the parameter."""
        if self.raw_data["scaleValue"]:
            return float(self.raw_data["scaleValue"])

        return 1.0

    @property
    def zone_id(self) -> str:
        """Return the zone id of the parameter."""
        return self.raw_data["zoneId"]

    async def update_parameter(self, value) -> None:
        """Patch parameter if writable."""
        if not self.is_writable:
            return
        if not self.device.system.premium_manage:
            return
        await self.device.system.api.patch_parameter(
            self.device.id, str(self.id), str(value)
        )

    def get_platform(self) -> Platform:
        """Try to identify entity platform."""
        if self.id in self.device.system.api.platform_override:
            return self.device.system.api.platform_override[self.id]

        if (
            len(self.enum_values) == 2
            and self.enum_values[0]["value"] == "0"
            and self.enum_values[1]["value"] == "1"
        ) or (
            len(self.enum_values) == 0
            and self.min_value == 0
            and self.max_value == 1
            and self.step_value == 1
        ):
            if self.is_writable:
                return Platform.SWITCH
            return Platform.BINARY_SENSOR

        if len(self.enum_values) > 0 and self.is_writable:
            return Platform.SELECT

        if (self.max_value or self.min_value) and self.is_writable:
            return Platform.NUMBER

        return Platform.SENSOR

    def get_unit(self, parameter_unit) -> str:
        """Try to get the correct home assistant unit."""
        if parameter_unit != "":
            for units in (
                UnitOfEnergy,
                UnitOfFrequency,
                UnitOfPower,
                UnitOfTemperature,
                UnitOfTime,
            ):
                for unit in units:
                    if parameter_unit.lower() == unit.lower():
                        return str(unit)

        return parameter_unit


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

    # Firmware info
    firmware_info: FirmwareInfo

    # List of collected notifications
    notifications: list[Notification] = []

    # List of collected parameters
    parameters: list[Parameter] = []

    # List of collected zones
    zones: list[Zone] = []

    def __init__(self, raw_data: dict, system: System) -> None:
        """Initialize a device object."""
        self.raw_data = raw_data
        self.system = system

    @property
    def id(self) -> str:
        """Return the ID of the device."""
        return self.raw_data["id"]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return " ".join(
            list(dict.fromkeys([self.raw_data["product"]["name"], self.system.name]))
        )

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
        self.parameters = await self.system.api.get_parameters(self)
        if self.system.api.entry.options.get(CONF_FETCH_FIRMWARE, True):
            self.firmware_info = await self.system.api.get_firmware_info(self)
        # self.zones = await self.system.api.get_zones(self.id)


class System:
    """Class that represents a system object in the myUplink API."""

    # List of collected devices
    devices: list[Device] = []

    # Smart home mode of the system
    smart_home_mode: str = "Default"

    premium_manage: bool = True

    def __init__(self, raw_data: dict, api: MyUplink) -> None:
        """Initialize a system object."""
        self.raw_data = raw_data
        self.api = api

    @property
    def id(self) -> str:
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
        if not self.devices:
            self.devices = [
                Device(device_data, self) for device_data in self.raw_data["devices"]
            ]
        
        self.premium_manage = await self.api.get_premium_manage(self)

        if self.api.entry.options.get(CONF_ENABLE_SMART_HOME_MODE, True):
            self.smart_home_mode = await self.api.get_smart_home_mode(self)

        fetch_notifications = self.api.entry.options.get(CONF_FETCH_NOTIFICATIONS, True)
        if fetch_notifications:
            notifications = await self.api.get_notifications(self)

        for device in self.devices:
            if fetch_notifications:
                device.notifications = []
                for notification in notifications:
                    if notification.device_id == device.id:
                        device.notifications.append(notification)

            await device.async_fetch_data()

    async def update_smart_home_mode(self, value) -> None:
        """Put smart home mode for system."""
        await self.api.put_smart_home_mode(self.id, str(value))


class Throttle:
    """Throttling requests to API."""

    def __init__(self, delay) -> None:
        """Initialize throttle."""
        self._delay = delay
        self._timestamp = datetime.now()

    async def __aenter__(self):
        """Enter async throttle."""
        timestamp = datetime.now()
        delay = (self._timestamp - timestamp).total_seconds()
        if delay > 0:
            _LOGGER.debug("Delaying request by %s seconds due to throttle", delay)
            with suppress(asyncio.CancelledError):
                await asyncio.sleep(delay)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async throttle."""
        self._timestamp = datetime.now() + self._delay


class MyUplink:
    """Class to communicate with the myUplink API."""

    # List of collected systems
    systems: list[System] = []

    def __init__(
        self, auth: AsyncConfigEntryAuth, language_code: str, entry: ConfigEntry
    ) -> None:
        """Initialize the API and store the auth so we can make requests."""
        self.auth = auth
        self.entry = entry
        self.lock = asyncio.Lock()
        self.throttle = Throttle(timedelta(seconds=5))

        self.header = {"Accept-Language": language_code}
        
        self.writable_without_subscription = entry.options.get(CONF_WRITABLE_WITHOUT_SUBSCRIPTION, True)

        try:
            self.parameter_whitelist = json.loads(
                entry.options.get(CONF_PARAMETER_WHITELIST, "[]")
            )
        except json.decoder.JSONDecodeError:
            self.parameter_whitelist = []

        try:
            self.additional_parameter = json.loads(
                entry.options.get(CONF_ADDITIONAL_PARAMETER, "[]")
            )
        except json.decoder.JSONDecodeError:
            self.additional_parameter = []

        try:
            self.platform_override = json.loads(
                entry.options.get(
                    CONF_PLATFORM_OVERRIDE, json.dumps(DEFAULT_PLATFORM_OVERRIDE)
                ),
                object_hook=self.parse_int_keys,
            )
        except json.decoder.JSONDecodeError:
            self.platform_override = DEFAULT_PLATFORM_OVERRIDE

        try:
            self.writable_override = json.loads(
                entry.options.get(
                    CONF_WRITABLE_OVERRIDE, json.dumps(DEFAULT_WRITABLE_OVERRIDE)
                ),
                object_hook=self.parse_int_keys,
            )
        except json.decoder.JSONDecodeError:
            self.writable_override = DEFAULT_WRITABLE_OVERRIDE

    async def get_systems(self) -> list[System]:
        """Return all systems."""
        _LOGGER.debug("Fetch systems")
        async with self.lock, self.throttle:
            resp = await self.auth.request("get", "systems/me?page=1&itemsPerPage=99")
        resp.raise_for_status()
        data = await resp.json()

        self.systems = [System(system_data, self) for system_data in data["systems"]]

        _LOGGER.debug("Update systems")
        for system in self.systems:
            await system.async_fetch_data()

        return self.systems

    async def get_notifications(self, system: System) -> list[Notification]:
        """Return all active notifications by system id."""
        _LOGGER.debug("Fetch notifications for system %s", system.id)
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "get",
                f"systems/{system.id}/notifications/active?page=1&itemsPerPage=99",
                headers=self.header,
            )
        resp.raise_for_status()
        data = await resp.json()

        return [Notification(notification) for notification in data["notifications"]]

    async def get_premium_manage(self, system: System) -> bool:
        """Check for a premium subscription to allow writing values."""
        _LOGGER.debug("Fetch subscriptions for system %s", system.id)
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "get", f"systems/{system.id}/subscriptions"
            )
        resp.raise_for_status()
        if resp.status == 200:
            data = await resp.json()
            for element in data:
                for subscription in data["subscriptions"]:
                    if Subscription(subscription).type == "manage":
                        return True
        return False


        
    async def get_smart_home_mode(self, system: System) -> str:
        """Return smart home mode by system id."""
        _LOGGER.debug("Fetch smart home mode for system %s", system.id)
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "get", f"systems/{system.id}/smart-home-mode"
            )
        resp.raise_for_status()
        data = await resp.json()

        return data["smartHomeMode"]

    async def put_smart_home_mode(self, system_id, value: str) -> bool:
        """Set the smart home mode for a system."""
        _LOGGER.debug(
            "Put smart home mode for system %s with value %s",
            system_id,
            value,
        )
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "put",
                f"systems/{system_id}/smart-home-mode",
                data=json.dumps({"smartHomeMode": value}),
                headers={"Content-Type": "application/json-patch+json"},
            )
        resp.raise_for_status()
        if resp.status == 200:
            data = await resp.json()
            return (
                "payload" in data
                and "state" in data["payload"]
                and data["payload"]["state"] == "ok"
            )

        return False

    async def get_device(self, device_id: str) -> Device:
        """Return a device by id."""
        _LOGGER.debug("Fetch device with id %s", device_id)
        async with self.lock, self.throttle:
            resp = await self.auth.request("get", f"devices/{device_id}")
        resp.raise_for_status()
        return Device(await resp.json(), self)

    async def get_firmware_info(self, device: Device) -> FirmwareInfo:
        """Return firmware info for a device."""
        _LOGGER.debug("Fetch firmware info for device %s", device.id)
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "get", f"devices/{device.id}/firmware-info", headers=self.header
            )
        resp.raise_for_status()
        return FirmwareInfo(await resp.json())

    async def get_parameters(self, device: Device) -> list[Parameter]:
        """Return parameters info for a device."""
        _LOGGER.debug("Fetch parameters for device %s", device.id)
        parameter_filters = []

        if len(self.parameter_whitelist) == 0:
            parameter_filters.append([])
            if len(self.additional_parameter) > 0:
                parameter_filters.append(self.additional_parameter)
        else:
            parameter_filters.append(
                [*self.parameter_whitelist, *self.additional_parameter]
            )

        unique_parameters = {}
        seen = set()

        for parameter_filter in parameter_filters:
            query_parameters = {}
            if len(parameter_filter) > 0:
                query_parameters["parameters"] = ",".join(
                    str(parameter_id) for parameter_id in parameter_filter
                )

            async with self.lock, self.throttle:
                resp = await self.auth.request(
                    "get",
                    f"devices/{device.id}/points",
                    headers=self.header,
                    params=query_parameters,
                )
            resp.raise_for_status()
            parameters_data = await resp.json()

            for parameter_data in parameters_data:
                unique_key = (
                    parameter_data["parameterId"],
                    parameter_data["parameterName"],
                )

                if unique_key not in seen:
                    seen.add(unique_key)
                    unique_parameters[unique_key] = Parameter(parameter_data, device)

        return list(unique_parameters.values())

    async def get_zones(self, device_id) -> list[Zone]:
        """Return all smart home zones for a device."""
        _LOGGER.debug("Fetch zones for device %s", device_id)
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "get", f"devices/{device_id}/smart-home-zones", headers=self.header
            )
        resp.raise_for_status()
        return [Zone(zone) for zone in await resp.json()]

    async def patch_parameter(self, device_id, parameter_id: str, value: str) -> bool:
        """Update the value of a parameter for a device."""
        _LOGGER.debug(
            "Patch parameter %s for device %s with value %s",
            parameter_id,
            device_id,
            value,
        )
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "patch",
                f"devices/{device_id}/points",
                data=json.dumps({parameter_id: value}),
                headers={"Content-Type": "application/json-patch+json"},
            )
        resp.raise_for_status()
        return resp.status == 200

    def parse_int_keys(self, dct):
        """Parse object keys into integers."""
        rval = {}
        for key, val in dct.items():
            try:
                # Convert the key to an integer
                int_key = int(key)
                # Assign value to the integer key in the new dict
                rval[int_key] = val
            except ValueError:
                # Couldn't convert key to an integer; Use original key
                rval[key] = val
        return rval
