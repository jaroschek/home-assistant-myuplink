"""API for myUplink bound to Home Assistant OAuth."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from functools import lru_cache
from http import HTTPStatus
from math import ceil
from time import monotonic
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self, cast

from aiohttp import (
    ClientError,
    ClientResponse,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
)
from homeassistant.const import (
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    API_HOST,
    API_VERSION,
    CONF_ADDITIONAL_PARAMETER,
    CONF_ENABLE_SMART_HOME_MODE,
    CONF_ENABLE_SMART_HOME_ZONE,
    CONF_FETCH_FIRMWARE,
    CONF_FETCH_NOTIFICATIONS,
    CONF_PARAMETER_WHITELIST,
    CONF_PLATFORM_OVERRIDE,
    CONF_WRITABLE_OVERRIDE,
    CONF_WRITABLE_WITHOUT_SUBSCRIPTION,
    DOMAIN,
)
from .models import (
    DeviceData,
    EnumValue,
    FirmwareData,
    NotificationData,
    NotificationsResponse,
    ParameterData,
    SmartHomeModeResponse,
    SubscriptionData,
    SubscriptionsResponse,
    SystemData,
    SystemsResponse,
    WriteValue,
    ZoneData,
)
from .options import parameter_ids, platform_overrides, writable_overrides

if TYPE_CHECKING:
    from .coordinator import MyUplinkConfigEntry

_LOGGER = logging.getLogger(__name__)
SUBSCRIPTION_CACHE_SECONDS = 15 * 60
FIRMWARE_CACHE_SECONDS = 60 * 60


class MyUplinkRateLimitError(Exception):
    """A request must wait until the API rate-limit window resets."""

    def __init__(self, retry_after: float) -> None:
        """Carry the server's backoff to the polling coordinator."""
        super().__init__("myUplink request limit reached")
        self.retry_after = max(1, retry_after)


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
        self.rate_limit_limit: int | None = None
        self.rate_limit_remaining: int | None = None
        self.rate_limit_reset_at: datetime | None = None

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        async with asyncio.timeout(30):
            await self._oauth_session.async_ensure_token_valid()

        return cast(str, self._oauth_session.token["access_token"])

    def _update_rate_limit_headers(self, response: ClientResponse) -> None:
        """Extract and update rate limit headers from response.

        RateLimit-Limit: maximum requests allowed in the current window (e.g., 25)
        RateLimit-Remaining: requests still available in the current window
        RateLimit-Reset: seconds until the current window expires
        """
        limit = self._header_int(response, "RateLimit-Limit")
        if limit is not None:
            self.rate_limit_limit = limit

        remaining = self._header_int(response, "RateLimit-Remaining")
        if remaining is not None:
            self.rate_limit_remaining = remaining

        reset_seconds = self._header_int(response, "RateLimit-Reset")
        if reset_seconds is not None:
            self.rate_limit_reset_at = datetime.now(UTC) + timedelta(
                seconds=reset_seconds
            )
            _LOGGER.debug(
                "Rate limit window: %s/%s remaining, resets in %d seconds",
                self.rate_limit_remaining,
                self.rate_limit_limit,
                reset_seconds,
            )

    def _header_int(self, response: ClientResponse, name: str) -> int | None:
        value = response.headers.get(name)
        if value is None:
            return None
        try:
            return int(value)
        except TypeError, ValueError:
            _LOGGER.debug("Could not parse %s header value: %r", name, value)
            return None

    async def request(self, method: str, path: str, **kwargs: Any) -> ClientResponse:
        """Make an authorized request with rate limit window awareness."""
        headers = kwargs.pop("headers", None)

        if headers is None:
            headers = {}
        else:
            headers = dict(headers)

        access_token = await self.async_get_access_token()
        headers["authorization"] = f"Bearer {access_token}"

        url = f"{API_HOST}/{API_VERSION}/{path}"
        kwargs.setdefault("timeout", ClientTimeout(total=30))

        async with asyncio.timeout(30):
            response = await self._websession.request(
                method, url, **kwargs, headers=headers
            )

        self._update_rate_limit_headers(response)

        if response.status == HTTPStatus.TOO_MANY_REQUESTS:
            retry_after = self._retry_after(response)
            self.rate_limit_remaining = 0
            self.rate_limit_reset_at = datetime.now(UTC) + timedelta(
                seconds=retry_after
            )
            response.release()
            raise MyUplinkRateLimitError(retry_after)

        return response

    def _retry_after(self, response: ClientResponse) -> float:
        """Read Retry-After seconds or HTTP date, then the rate-limit reset."""
        if value := response.headers.get("Retry-After"):
            try:
                return max(1, float(value))
            except ValueError:
                try:
                    return max(
                        1,
                        parsedate_to_datetime(value).timestamp()
                        - datetime.now(UTC).timestamp(),
                    )
                except TypeError, ValueError, OverflowError:
                    pass
        if self.rate_limit_reset_at is not None:
            return max(
                1, (self.rate_limit_reset_at - datetime.now(UTC)).total_seconds()
            )
        return 60


class Subscription:
    """Class that represents the subscription in the myUplink API."""

    def __init__(self, raw_data: SubscriptionData) -> None:
        """Initialize a subscription object."""
        self.raw_data = raw_data

    @property
    def type(self) -> str:
        """Return the subscription type."""
        return self.raw_data["type"]

    @property
    def valid_until(self) -> datetime:
        """Return datetime value of 'validUntil'."""
        return datetime.fromisoformat(self.raw_data["validUntil"])


class Notification:
    """Class that represents the notificationobject in the myUplink API."""

    def __init__(self, raw_data: NotificationData) -> None:
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

    def __init__(self, raw_data: FirmwareData) -> None:
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
    def current_version(self) -> str | None:
        """Return the current firmware version of the device."""
        version = self.raw_data.get("currentFwVersion")
        return version.strip() or None if version is not None else None

    @property
    def pending_version(self) -> str | None:
        """Return the pending firmware version of the device."""
        version = self.raw_data.get("pendingFwVersion")
        return version.strip() or None if version is not None else None

    @property
    def desired_version(self) -> str | None:
        """Return the desired firmware version of the device."""
        version = self.raw_data.get("desiredFwVersion")
        return version.strip() or None if version is not None else None


class Parameter:
    """Class that represents a parameter object in the myUplink API."""

    def __init__(self, raw_data: ParameterData, device: Device) -> None:
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
        if (
            self.device.system.premium_manage
            or self.device.system.api.writable_without_subscription
        ):
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
    def min_value(self) -> int | None:
        """Return the min value of the parameter."""
        return self.raw_data["minValue"]

    @property
    def max_value(self) -> int | None:
        """Return the max value of the parameter."""
        return self.raw_data["maxValue"]

    @property
    def step_value(self) -> int | None:
        """Return the step value of the parameter."""
        return self.raw_data.get("stepValue", 1)

    @property
    def enum_values(self) -> list[EnumValue]:
        """Return the enum values of the parameter."""
        return self.raw_data["enumValues"]

    @property
    def enum_text(self) -> str | None:
        """Return the enum text matching the current value.

        The ``strVal`` returned by the API does not always match one of the
        enum option texts (e.g. it may carry a unit or a different format), so
        map the raw value onto its ``enumValues`` entry to obtain the matching
        option text. Returns ``None`` when the value has no matching entry.
        """
        raw_value = self.raw_data["value"]
        value_strings = {str(raw_value)}
        if isinstance(raw_value, float) and raw_value.is_integer():
            value_strings.add(str(int(raw_value)))
        for enum_value in self.enum_values:
            if enum_value.get("value") in value_strings:
                return enum_value["text"]
        return None

    @property
    def scale_value(self) -> float:
        """Return the scale value of the parameter."""
        if self.raw_data["scaleValue"]:
            return float(self.raw_data["scaleValue"])

        return 1.0

    @property
    def zone_id(self) -> str:
        """Return the zone id of the parameter."""
        return self.raw_data["zoneId"]

    async def update_parameter(self, value: WriteValue) -> None:
        """Set parameter value if writable."""
        if not self.is_writable:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="parameter_not_writable"
            )
        await self.device.system.api.patch_parameter(
            self.device.id, str(self.id), value
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

        if (
            self.max_value is not None or self.min_value is not None
        ) and self.is_writable:
            return Platform.NUMBER

        return Platform.SENSOR

    @staticmethod
    @lru_cache(maxsize=128)
    def get_unit(parameter_unit: str) -> str:
        """Try to get the correct home assistant unit."""
        aliases = {
            "day": "d",
            "days": "d",
            "hour": "h",
            "hours": "h",
            "hrs": "h",
            "sec": "s",
            "l/m": "L/min",
            "m3/h": "m³/h",
        }
        if parameter_unit.lower() in aliases:
            return aliases[parameter_unit.lower()]
        units = [
            str(unit)
            for unit_type in (
                UnitOfEnergy,
                UnitOfFrequency,
                UnitOfPower,
                UnitOfTemperature,
                UnitOfTime,
                UnitOfElectricCurrent,
                UnitOfElectricPotential,
                UnitOfPressure,
                UnitOfVolumeFlowRate,
            )
            for unit in unit_type
        ]
        if parameter_unit in units:
            return parameter_unit
        matches = [unit for unit in units if parameter_unit.lower() == unit.lower()]
        if len(matches) == 1:
            return matches[0]
        return parameter_unit


class Zone:
    """Class that represents a zone object in the myUplink API."""

    def __init__(self, raw_data: ZoneData, device: Device) -> None:
        """Initialize a zone object."""
        self.raw_data = raw_data
        self.device = device

    @property
    def id(self) -> int:
        """Return the ID of the zone."""
        return int(self.raw_data["zoneId"])

    @property
    def name(self) -> str:
        """Return the name of the zone."""
        return self.raw_data["name"]

    @property
    def is_command_only(self) -> bool:
        """Return if the zone is command only."""
        return bool(self.raw_data["commandOnly"])

    @property
    def supported_modes(self) -> str | None:
        """Return the supported modes of the zone."""
        return self.raw_data.get("supportedModes")

    @property
    def mode(self) -> str:
        """Return the current mode of the zone."""
        return self.raw_data["mode"]

    @property
    def temperature(self) -> float | None:
        """Return the current temperature of the zone."""
        value = self.raw_data.get("temperature")
        return float(value) if value is not None else None

    @property
    def setpoint(self) -> float | None:
        """Return the target temperature of the zone."""
        value = self.raw_data.get("setpoint")
        return float(value) if value is not None else None

    @property
    def setpoint_heating(self) -> float | None:
        """Return the heating setpoint value of the zone."""
        value = self.raw_data.get("setpointHeat")
        return float(value) if value is not None else None

    @property
    def setpoint_cooling(self) -> float | None:
        """Return the cooling setpoint value of the zone."""
        value = self.raw_data.get("setpointCool")
        return float(value) if value is not None else None

    @property
    def setpoint_range_min(self) -> int | None:
        """Return the minimum temperature range of the zone."""
        value = self.raw_data.get("setpointRangeMin")
        return int(value) if value is not None else None

    @property
    def setpoint_range_max(self) -> int | None:
        """Return the maximum temperature range of the zone."""
        value = self.raw_data.get("setpointRangeMax")
        return int(value) if value is not None else None

    @property
    def is_celsius(self) -> bool:
        """Return if the temperature in the zone is specified as celsius (true) or fahrenheit (false)."""
        return (
            bool(self.raw_data.get("isCelsius"))
            if self.raw_data.get("isCelsius") is not None
            else True
        )

    @property
    def indoor_co2(self) -> int | None:
        """Return the indoor co2 level of the zone."""
        value = self.raw_data.get("indoorCo2")
        return int(value) if value is not None else None

    @property
    def indoor_humidity(self) -> float | None:
        """Return the indoor humidity of the zone."""
        value = self.raw_data.get("indoorHumidity")
        return float(value) if value is not None else None

    async def update_zone_property(self, property_name: str, value: WriteValue) -> None:
        """Patch zone if writable."""
        if self.is_command_only:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="zone_command_only"
            )
        await self.device.system.api.patch_zone_property(
            self.device.id, str(self.id), property_name, value
        )
        cast(dict[str, WriteValue], self.raw_data)[property_name] = value


class Device:
    """Class that represents a device object in the myUplink API."""

    def __init__(self, raw_data: DeviceData, system: System) -> None:
        """Initialize a device object."""
        self.raw_data = raw_data
        self.system = system
        self.firmware_info = FirmwareInfo({"deviceId": self.id, "firmwareId": 0})
        self.notifications: list[Notification] = []
        self.parameters: list[Parameter] = []
        self.zones: list[Zone] = []

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
            return self.raw_data["firmware"].get("currentFwVersion") or "N/A"
        return self.raw_data.get("currentFwVersion", "N/A")

    @property
    def desired_firmware_version(self) -> str:
        """Return the desired firmware version of the device."""
        if "firmware" in self.raw_data:
            return self.raw_data["firmware"].get("desiredFwVersion") or "?"
        return "?"

    async def async_fetch_data(self) -> None:
        """Fetch data from myUplink API."""
        self.parameters = await self.system.api.get_parameters(self)
        if self.system.api.entry.options.get(CONF_FETCH_FIRMWARE, True):
            self.firmware_info = await self.system.api.get_firmware_info(self)
        if self.system.api.entry.options.get(CONF_ENABLE_SMART_HOME_ZONE, True):
            self.zones = await self.system.api.get_zones(self)


class System:
    """Class that represents a system object in the myUplink API."""

    def __init__(self, raw_data: SystemData, api: MyUplink) -> None:
        """Initialize a system object."""
        self.raw_data = raw_data
        self.api = api
        self.devices: list[Device] = []
        self.smart_home_mode = "Default"
        self.premium_manage = True

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
        return self.raw_data.get("hasAlarm", False)

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

    async def update_smart_home_mode(self, value: str) -> None:
        """Put smart home mode for system."""
        await self.api.put_smart_home_mode(self.id, str(value))


class Throttle:
    """Throttling requests to API with rate limit window awareness.

    The throttle respects the 25 requests per minute limit by:
    1. Tracking RateLimit-Remaining in the current window
    2. When RateLimit-Remaining = 0, waiting until RateLimit-Reset window expires
    3. Otherwise, maintaining a minimum delay of 60/25 = 2.4 seconds between requests
    """

    MIN_DELAY_SECONDS = 60 / 25
    # Start pacing requests only once the window has this many or fewer
    # requests left; above this, fire requests back-to-back.
    LOW_REMAINING_THRESHOLD = 5

    def __init__(self, auth: AsyncConfigEntryAuth) -> None:
        """Initialize throttle."""
        self._auth = auth
        self._last_request_time = datetime.now(UTC)

    async def __aenter__(self) -> Self:
        """Enter async throttle - apply delay before making request."""
        now = datetime.now(UTC)

        if (
            self._auth.rate_limit_reset_at
            and self._auth.rate_limit_remaining is not None
        ):
            if self._auth.rate_limit_remaining <= 0:
                wait_seconds = (self._auth.rate_limit_reset_at - now).total_seconds()
                if wait_seconds > 0:
                    raise MyUplinkRateLimitError(wait_seconds)

        # Only pace requests when the rate-limit window is running low.
        # With plenty of headroom there is no need to insert a fixed delay
        # before every call; doing so serializes startup and can overrun
        # Home Assistant's setup timeout on accounts with several devices.
        remaining = self._auth.rate_limit_remaining
        if remaining is not None and remaining <= self.LOW_REMAINING_THRESHOLD:
            time_since_last_request = (now - self._last_request_time).total_seconds()
            if time_since_last_request < self.MIN_DELAY_SECONDS:
                delay = self.MIN_DELAY_SECONDS - time_since_last_request
                _LOGGER.debug(
                    "Rate limit low (%d remaining): waiting %.2f seconds",
                    remaining,
                    delay,
                )
                await asyncio.sleep(delay)

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async throttle - record request time."""
        self._last_request_time = datetime.now(UTC)


class MyUplink:
    """Class to communicate with the myUplink API."""

    def __init__(
        self, auth: AsyncConfigEntryAuth, language_code: str, entry: MyUplinkConfigEntry
    ) -> None:
        """Initialize the API and store the auth so we can make requests."""
        self.auth = auth
        self.entry = entry
        self.lock = asyncio.Lock()
        self.throttle = Throttle(auth)
        self._subscription_failures: set[str] = set()
        self._premium_manage: dict[str, bool] = {}
        self._subscription_cache: dict[str, tuple[float, bool]] = {}
        self._firmware_cache: dict[str, tuple[float, FirmwareInfo]] = {}
        self.systems: list[System] = []

        self.header = {"Accept-Language": language_code}

        self.writable_without_subscription = entry.options.get(
            CONF_WRITABLE_WITHOUT_SUBSCRIPTION, True
        )

        self.parameter_whitelist = parameter_ids(
            entry.options.get(CONF_PARAMETER_WHITELIST)
        )
        self.additional_parameter = parameter_ids(
            entry.options.get(CONF_ADDITIONAL_PARAMETER)
        )
        self.platform_override = platform_overrides(
            entry.options.get(CONF_PLATFORM_OVERRIDE)
        )
        self.writable_override = writable_overrides(
            entry.options.get(CONF_WRITABLE_OVERRIDE)
        )

    async def get_systems(self) -> list[System]:
        """Return all systems."""
        _LOGGER.debug("Fetch systems")
        async with self.lock, self.throttle:
            resp = await self.auth.request("get", "systems/me?page=1&itemsPerPage=99")
        resp.raise_for_status()
        data = cast(SystemsResponse, await resp.json())
        systems = [System(system_data, self) for system_data in data["systems"]]

        _LOGGER.debug("Update systems")
        for system in systems:
            await system.async_fetch_data()

        self.systems = systems
        return systems

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
        data = cast(NotificationsResponse, await resp.json())
        return [Notification(notification) for notification in data["notifications"]]

    async def get_premium_manage(self, system: System) -> bool:
        """Check for a premium subscription to allow writing values."""
        now = monotonic()
        if cached := self._subscription_cache.get(system.id):
            if now - cached[0] < SUBSCRIPTION_CACHE_SECONDS:
                return cached[1]
        _LOGGER.debug("Fetch subscriptions for system %s", system.id)

        try:
            async with self.lock, self.throttle:
                resp = await self.auth.request(
                    "get", f"systems/{system.id}/subscriptions"
                )

            resp.raise_for_status()

            if resp.status == 200:
                data = cast(SubscriptionsResponse, await resp.json())
                for subscription in data.get("subscriptions", []):
                    if Subscription(subscription).type == "manage":
                        self._subscription_failures.discard(system.id)
                        self._premium_manage[system.id] = True
                        self._subscription_cache[system.id] = (now, True)
                        return True

        except ClientResponseError as err:
            if err.status != HTTPStatus.INTERNAL_SERVER_ERROR:
                raise
            # This optional endpoint sometimes fails while point reads still work.
            if system.id not in self._subscription_failures:
                _LOGGER.warning(
                    "myUplink subscription lookup failed; retaining known permissions"
                )
                self._subscription_failures.add(system.id)
            return self._premium_manage.get(system.id, False)

        self._subscription_failures.discard(system.id)
        self._premium_manage[system.id] = False
        self._subscription_cache[system.id] = (now, False)
        return False

    async def get_smart_home_mode(self, system: System) -> str:
        """Return smart home mode by system id."""
        _LOGGER.debug("Fetch smart home mode for system %s", system.id)
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "get", f"systems/{system.id}/smart-home-mode"
            )
        resp.raise_for_status()
        data = cast(SmartHomeModeResponse, await resp.json())
        return data["smartHomeMode"]

    async def put_smart_home_mode(self, system_id: str, value: str) -> None:
        """Set the smart home mode for a system."""
        _LOGGER.debug(
            "Put smart home mode for system %s with value %s",
            system_id,
            value,
        )
        resp = await self._async_write(
            "put",
            f"systems/{system_id}/smart-home-mode",
            data=json.dumps({"smartHomeMode": value}),
            headers={"Content-Type": "application/json-patch+json"},
        )
        if resp.status == 200:
            try:
                data: object = await resp.json()
            except (ClientError, TimeoutError, ValueError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="write_rejected"
                ) from err
            payload = data.get("payload") if isinstance(data, dict) else None
            if not isinstance(payload, dict) or payload.get("state") != "ok":
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="write_rejected"
                )

    async def get_device(self, device_id: str, system: System) -> Device:
        """Return a device by id."""
        _LOGGER.debug("Fetch device with id %s", device_id)
        async with self.lock, self.throttle:
            resp = await self.auth.request("get", f"devices/{device_id}")
        resp.raise_for_status()
        return Device(cast(DeviceData, await resp.json()), system)

    async def get_firmware_info(self, device: Device) -> FirmwareInfo:
        """Return firmware info for a device."""
        now = monotonic()
        if cached := self._firmware_cache.get(device.id):
            if now - cached[0] < FIRMWARE_CACHE_SECONDS:
                return cached[1]
        _LOGGER.debug("Fetch firmware info for device %s", device.id)
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "get", f"devices/{device.id}/firmware-info", headers=self.header
            )
        resp.raise_for_status()
        info = FirmwareInfo(cast(FirmwareData, await resp.json()))
        self._firmware_cache[device.id] = (now, info)
        return info

    async def get_parameters(self, device: Device) -> list[Parameter]:
        """Return parameters info for a device."""
        _LOGGER.debug("Fetch parameters for device %s", device.id)
        parameter_filters: list[list[int]] = []

        if len(self.parameter_whitelist) == 0:
            parameter_filters.append([])
            if len(self.additional_parameter) > 0:
                parameter_filters.append(self.additional_parameter)
        else:
            parameter_filters.append(
                [*self.parameter_whitelist, *self.additional_parameter]
            )

        unique_parameters: dict[int, Parameter] = {}

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
            parameters_data = cast(list[ParameterData], await resp.json())

            for parameter_data in parameters_data:
                parameter = Parameter(parameter_data, device)
                unique_parameters[parameter.id] = parameter

        return list(unique_parameters.values())

    async def get_zones(self, device: Device) -> list[Zone]:
        """Return all smart home zones for a device."""
        _LOGGER.debug("Fetch zones for device %s", device.id)
        async with self.lock, self.throttle:
            resp = await self.auth.request(
                "get", f"devices/{device.id}/smart-home-zones", headers=self.header
            )
        resp.raise_for_status()
        return [Zone(zone, device) for zone in cast(list[ZoneData], await resp.json())]

    async def patch_parameter(
        self, device_id: str, parameter_id: str, value: WriteValue
    ) -> None:
        """Update the value of a parameter for a device."""
        _LOGGER.debug(
            "Patch parameter %s for device %s with value %s",
            parameter_id,
            device_id,
            value,
        )
        await self._async_write(
            "patch",
            f"devices/{device_id}/points",
            data=json.dumps({parameter_id: value}),
            headers={"Content-Type": "application/json-patch+json"},
        )

    async def patch_zone_property(
        self, device_id: str, zone_id: str, property_name: str, value: WriteValue
    ) -> None:
        """Update the value of a zone property for a device."""
        _LOGGER.debug(
            "Patch property %s for zone %s of device %s with value %s",
            property_name,
            zone_id,
            device_id,
            value,
        )
        await self._async_write(
            "patch",
            f"devices/{device_id}/zones/{zone_id}",
            data=json.dumps({property_name: value}),
            headers={"Content-Type": "application/json-patch+json"},
        )

    async def _async_write(
        self, method: str, path: str, **kwargs: Any
    ) -> ClientResponse:
        """Report every failed write consistently across actions and platforms."""
        try:
            async with self.lock, self.throttle:
                response = await self.auth.request(method, path, **kwargs)
            response.raise_for_status()
            await response.read()
        except MyUplinkRateLimitError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                translation_placeholders={"seconds": str(ceil(err.retry_after))},
            ) from err
        except ClientResponseError as err:
            if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                self.entry.async_start_reauth(self.entry.runtime_data.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"status": str(err.status)},
            ) from err
        except (ClientError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="connection_error"
            ) from err
        if not 200 <= response.status < 300:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="write_rejected"
            )
        return response
