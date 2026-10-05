"""Return cached diagnostics without credentials or identifying cloud data."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {
    "data",
    "title",
    "unique_id",
    "entry_id",
    "system_id",
    "device_id",
    "serial_number",
    "name",
    "zone_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Describe only the current cached snapshot, without cloud requests."""
    result = {"config_entry": async_redact_data(entry.as_dict(), TO_REDACT)}
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return result
    result["coordinator"] = {
        "last_update_success": coordinator.last_update_success,
        "poll_interval_seconds": coordinator.update_interval.total_seconds()
        if coordinator.update_interval is not None
        else None,
        "rate_limit": coordinator.api.auth.rate_limit_limit,
        "rate_limit_remaining": coordinator.api.auth.rate_limit_remaining,
    }
    result["systems"] = async_redact_data(
        [
            {
                "system_id": system.id,
                "name": system.name,
                "premium_manage": system.premium_manage,
                "devices": [
                    {
                        "device_id": device.id,
                        "name": device.name,
                        "serial_number": device.serial_number,
                        "connection_state": device.connection_state,
                        "firmware": device.current_firmware_version,
                        "notification_count": len(device.notifications),
                        "parameters": [
                            {
                                "id": parameter.id,
                                "unit": parameter.unit,
                                "platform": parameter.get_platform(),
                                "writable": parameter.is_writable,
                            }
                            for parameter in device.parameters
                        ],
                        "zones": [
                            {
                                "zone_id": zone.id,
                                "name": zone.name,
                                "command_only": zone.is_command_only,
                            }
                            for zone in device.zones
                        ],
                    }
                    for device in system.devices
                ],
            }
            for system in (coordinator.data or [])
        ],
        TO_REDACT,
    )
    return result
