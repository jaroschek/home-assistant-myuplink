"""Constants for the myUplink integration."""
from __future__ import annotations

from homeassistant.backports.enum import StrEnum
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
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.WATER_HEATER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
]

BINARY_SENSORS = [505, 506, 7086, 10733, 10905, 10906]
SWITCHES = [600]
SELECTS = [500, 517, 544, 601]
NUMBERS = [
    100,
    101,
    200,
    201,
    300,
    301,
    304,
    305,
    307,
    308,
    511,
    512,
    516,
    527,
    545,
    546,
    547,
    548,
]
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
