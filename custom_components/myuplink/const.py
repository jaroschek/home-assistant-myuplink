"""Constants for the myUplink integration."""
from __future__ import annotations

from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "myuplink"

OAUTH2_AUTHORIZE = "https://api.myuplink.com/oauth/authorize"
OAUTH2_TOKEN = "https://api.myuplink.com/oauth/token"

SCOPES = [
    "READSYSTEM",
    "WRITESYSTEM",
    "offline_access",
]

API_HOST = "https://api.myuplink.com"
API_VERSION = "v2"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.WATER_HEATER,
]

DEFAULT_SCAN_INTERVAL = 300
MIN_SCAN_INTERVAL = 5

PLATFORM_OVERRIDE = {10733: Platform.BINARY_SENSOR, 44703: Platform.BINARY_SENSOR}
WRITABLE_OVERRIDE = {781: False, 15753: False}
WATER_HEATERS = ["18760NE"]


class CustomUnits(StrEnum):
    """Custom units."""

    DEGREE_MINUTES = "DM"
    POWER_WS = "Ws"
    VOLUME_LM = "l/m"
    TIME_DAY = "day"
    TIME_DAYS = "days"
    TIME_HOUR = "hour"
    TIME_HOURS = "hours"
