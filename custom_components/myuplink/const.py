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

PLATFORM_OVERRIDE = {
    10733: Platform.BINARY_SENSOR,
    44703: Platform.BINARY_SENSOR,
    47050: Platform.SWITCH,
    47394: Platform.SWITCH,
    47635: Platform.SWITCH,
    47669: Platform.SWITCH,
    47771: Platform.SWITCH,
    47805: Platform.SWITCH,
    47839: Platform.SWITCH,
    47975: Platform.SWITCH,
    48009: Platform.SWITCH,
    48043: Platform.SWITCH,
    48442: Platform.SWITCH,
}

WRITABLE_OVERRIDE = {
    781: False,
    1755: False,
    1959: False,
    1961: False,
    1963: False,
    15753: False,
}

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
