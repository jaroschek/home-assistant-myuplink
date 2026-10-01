"""Typed contracts for myUplink API responses."""

from typing import NotRequired, TypedDict

type Numeric = float | str
type WriteValue = str | float | bool | None


class SubscriptionData(TypedDict):
    """Subscription metadata."""

    type: str
    validUntil: str


class NotificationData(TypedDict):
    """Active device notification."""

    id: str
    alarmNumber: int | str
    deviceId: str
    severity: int | str
    status: str
    createdDatetime: str
    header: str
    description: str
    equipName: str


class FirmwareVersions(TypedDict):
    """Version fields shared by device and firmware responses."""

    currentFwVersion: NotRequired[str | None]
    pendingFwVersion: NotRequired[str | None]
    desiredFwVersion: NotRequired[str | None]


class FirmwareData(FirmwareVersions):
    """Firmware endpoint metadata."""

    deviceId: str
    firmwareId: int | str


class EnumValue(TypedDict):
    """Parameter enum choice."""

    value: str
    text: str


class ParameterData(TypedDict):
    """A point's metadata and current reading."""

    parameterId: int | str
    parameterName: str
    category: str
    parameterUnit: str
    writable: bool
    timestamp: str
    value: float | None
    strVal: str
    smartHomeCategories: list[str]
    minValue: int | None
    maxValue: int | None
    stepValue: NotRequired[int | None]
    enumValues: list[EnumValue]
    scaleValue: Numeric | None
    zoneId: str


class ZoneData(TypedDict):
    """Zone identity, controls, and optional readings."""

    zoneId: int | str
    name: str
    commandOnly: bool
    mode: str
    supportedModes: NotRequired[str | None]
    temperature: NotRequired[Numeric | None]
    setpoint: NotRequired[Numeric | None]
    setpointHeat: NotRequired[Numeric | None]
    setpointCool: NotRequired[Numeric | None]
    setpointRangeMin: NotRequired[Numeric | None]
    setpointRangeMax: NotRequired[Numeric | None]
    isCelsius: NotRequired[bool | None]
    indoorCo2: NotRequired[Numeric | None]
    indoorHumidity: NotRequired[Numeric | None]


class ProductData(TypedDict):
    """Device product identity."""

    name: str
    serialNumber: str


class DeviceData(TypedDict):
    """Device identity and connectivity."""

    id: str
    product: ProductData
    connectionState: str
    firmware: NotRequired[FirmwareVersions]
    currentFwVersion: NotRequired[str]


class SystemData(TypedDict):
    """System identity and its devices."""

    systemId: str
    name: str
    securityLevel: str
    hasAlarm: NotRequired[bool]
    devices: list[DeviceData]


class SystemsResponse(TypedDict):
    """Account system listing."""

    systems: list[SystemData]


class NotificationsResponse(TypedDict):
    """System notification listing."""

    notifications: list[NotificationData]


class SubscriptionsResponse(TypedDict):
    """System subscription listing."""

    subscriptions: NotRequired[list[SubscriptionData]]


class SmartHomeModeResponse(TypedDict):
    """Current system mode."""

    smartHomeMode: str
