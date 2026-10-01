"""Local Home Assistant fixtures for the myUplink regression tests."""

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import jwt
import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import frame

from custom_components.myuplink import async_setup_entry
from custom_components.myuplink.api import (
    AsyncConfigEntryAuth,
    Device,
    FirmwareInfo,
    MyUplink,
    Parameter,
    System,
    Zone,
)
from custom_components.myuplink.config_flow import OAuth2FlowHandler
from custom_components.myuplink.const import (
    CONF_ADDITIONAL_PARAMETER,
    CONF_DISCONNECTED_AVAILABLE,
    CONF_ENABLE_SMART_HOME_MODE,
    CONF_ENABLE_SMART_HOME_ZONE,
    CONF_EXPERT_MODE,
    CONF_FETCH_FIRMWARE,
    CONF_FETCH_NOTIFICATIONS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SCOPES,
)
from custom_components.myuplink.coordinator import MyUplinkCoordinator


@pytest.fixture
async def hass(tmp_path: Path) -> AsyncGenerator[HomeAssistant]:
    """Provide Home Assistant without starting integrations or writing config."""
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    frame.async_setup(instance)
    loader.async_setup(instance)
    dr.async_setup(instance)
    await dr.async_load(instance)
    await er.async_load(instance)
    with patch.object(instance.config_entries, "_async_schedule_save"):
        yield instance
        await instance.async_stop()


@pytest.fixture
def entry(hass: HomeAssistant) -> ConfigEntry:
    """Provide a registered OAuth entry with existing expert options."""
    config_entry = ConfigEntry(
        domain=DOMAIN,
        title="myUplink",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": jwt.encode(
                    {"sub": "test-account"},
                    "test-secret-for-myuplink-regression-tests",
                    algorithm="HS256",
                ),
                "refresh_token": "test-refresh-token",
                "scope": " ".join(SCOPES),
                "expires_at": 0,
            },
            "other_data": "preserved",
        },
        options={
            CONF_ENABLE_SMART_HOME_MODE: True,
            CONF_ENABLE_SMART_HOME_ZONE: True,
            CONF_FETCH_FIRMWARE: True,
            CONF_FETCH_NOTIFICATIONS: True,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_DISCONNECTED_AVAILABLE: False,
            CONF_EXPERT_MODE: False,
            CONF_ADDITIONAL_PARAMETER: "[12345]",
        },
        source="user",
        version=1,
        minor_version=2,
        unique_id="test-account",
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )
    hass.config_entries._entries[config_entry.entry_id] = config_entry  # noqa: SLF001
    return config_entry


@pytest.fixture
def options_input(entry: ConfigEntry) -> dict[str, bool | int]:
    """Provide the general options separately from existing expert options."""
    options = dict(entry.options)
    del options[CONF_ADDITIONAL_PARAMETER]
    return options


@pytest.fixture(autouse=True)
def mock_flow_handler() -> Generator[None]:
    """Load the custom flow instead of Home Assistant's built-in integration."""
    with patch(
        "homeassistant.config_entries._async_get_flow_handler",
        return_value=OAuth2FlowHandler,
    ):
        yield


@pytest.fixture
async def setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the entry without making API requests or loading platforms."""
    with (
        patch(
            "custom_components.myuplink.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch("custom_components.myuplink.config_entry_oauth2_flow.OAuth2Session"),
        patch("custom_components.myuplink.aiohttp_client.async_get_clientsession"),
        patch("custom_components.myuplink.AsyncConfigEntryAuth", autospec=True),
        patch("custom_components.myuplink.MyUplinkCoordinator", autospec=True),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch("custom_components.myuplink.async_setup_services"),
    ):
        assert await async_setup_entry(hass, entry)


@pytest.fixture
def api(entry: ConfigEntry) -> MyUplink:
    """Provide the real client with mocked transport."""
    return MyUplink(AsyncConfigEntryAuth(MagicMock(), MagicMock()), "en-GB", entry)


@pytest.fixture
def system(api: MyUplink) -> System:
    """Provide a synthetic heating system."""
    return System(
        {
            "systemId": "system-1",
            "name": "Home",
            "securityLevel": "Admin",
            "devices": [],
        },
        api,
    )


@pytest.fixture
def device(system: System) -> Device:
    """Provide a connected device and cached firmware."""
    result = Device(
        {
            "id": "device-1",
            "connectionState": "Connected",
            "product": {"name": "NIBE S1255", "serialNumber": "test-serial"},
            "currentFwVersion": "1.0",
        },
        system,
    )
    result.firmware_info = FirmwareInfo(
        {
            "deviceId": result.id,
            "firmwareId": 1,
            "currentFwVersion": "1.0",
            "desiredFwVersion": "1.1",
        }
    )
    result.parameters = []
    result.zones = []
    result.notifications = []
    system.devices = [result]
    return result


@pytest.fixture
def parameter(device: Device) -> Parameter:
    """Provide a readable temperature point."""
    result = Parameter(
        {
            "parameterId": "123",
            "parameterName": "Supply temperature",
            "category": "Heating",
            "parameterUnit": "°C",
            "writable": False,
            "value": 20.0,
            "strVal": "20",
            "timestamp": "2026-09-01T12:00:00Z",
            "smartHomeCategories": [],
            "minValue": 0,
            "maxValue": 60,
            "stepValue": 1,
            "enumValues": [],
            "scaleValue": 1,
            "zoneId": "zone-1",
        },
        device,
    )
    device.parameters = [result]
    return result


@pytest.fixture
def zone(device: Device) -> Zone:
    """Provide a readable and controllable smart-home zone."""
    result = Zone(
        {
            "zoneId": "1",
            "name": "Living room",
            "commandOnly": False,
            "supportedModes": "off,auto,heat,cool,heatcool",
            "mode": "heat",
            "temperature": 20,
            "setpoint": 21,
            "setpointHeat": 21,
            "setpointCool": 24,
            "setpointRangeMin": 5,
            "setpointRangeMax": 30,
            "isCelsius": True,
            "indoorCo2": 500,
            "indoorHumidity": 40,
        },
        device,
    )
    device.zones = [result]
    return result


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    system: System,
    device: Device,
    parameter: Parameter,
    zone: Zone,
) -> MyUplinkCoordinator:
    """Provide cached coordinator data without scheduling cloud updates."""
    result = MyUplinkCoordinator(hass, system.api.entry, system.api)
    system.devices = [device]
    device.parameters = [parameter]
    device.zones = [zone]
    result.async_set_updated_data([system])
    system.api.entry.runtime_data = result
    return result
