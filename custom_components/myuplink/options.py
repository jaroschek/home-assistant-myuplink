"""Normalize expert options at the configuration boundary."""

import json
from collections.abc import Callable
from typing import cast

from homeassistant.const import Platform

from .const import DEFAULT_PLATFORM_OVERRIDE, DEFAULT_WRITABLE_OVERRIDE

PARAMETER_PLATFORMS = {
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
}


def _decode(value: object, default: object) -> object:
    """Restore defaults for empty or invalid JSON settings."""
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def parameter_ids(value: object) -> list[int]:
    """Accept integer IDs or integer text in a JSON list."""
    data = _decode(value, [])
    if not isinstance(data, list):
        return []
    if any(isinstance(item, bool) or not isinstance(item, (int, str)) for item in data):
        return []
    try:
        return [int(item) for item in data]
    except ValueError:
        return []


def _overrides[T](
    value: object, default: dict[int, T], validate: Callable[[object], T]
) -> dict[int, T]:
    """Require numeric point keys and valid values throughout the mapping."""
    data = _decode(value, None)
    if not isinstance(data, dict):
        return default.copy()
    try:
        return {
            int(key): validate(item)
            for key, item in cast(dict[str, object], data).items()
        }
    except ValueError:
        return default.copy()


def _platform(value: object) -> Platform:
    """Limit overrides to parameter entity platforms."""
    if not isinstance(value, str) or value not in PARAMETER_PLATFORMS:
        raise ValueError("Unsupported parameter platform")
    return Platform(value)


def _writable(value: object) -> bool:
    """Require a boolean writable override."""
    if not isinstance(value, bool):
        raise ValueError("Writable overrides must be boolean")
    return value


def platform_overrides(value: object) -> dict[int, Platform]:
    """Return platform corrections with their defaults."""
    return _overrides(value, DEFAULT_PLATFORM_OVERRIDE, _platform)


def writable_overrides(value: object) -> dict[int, bool]:
    """Return writable corrections with their defaults."""
    return _overrides(value, DEFAULT_WRITABLE_OVERRIDE, _writable)
