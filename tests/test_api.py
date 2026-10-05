"""Test account snapshots, endpoint contracts, and metadata cache recovery."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponse, ClientResponseError
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from custom_components.myuplink.api import (
    Device,
    FirmwareInfo,
    MyUplink,
    Parameter,
    Subscription,
    System,
    Zone,
)
from custom_components.myuplink.coordinator import MyUplinkCoordinator
from custom_components.myuplink.sensor import MyUplinkNotificationsSensorEntity


def make_response(data: object, status: int = 200) -> MagicMock:
    """Provide an HTTP response containing synthetic account data."""
    response = MagicMock(spec=ClientResponse)
    response.status = status
    response.json = AsyncMock(return_value=data)
    response.read = AsyncMock(return_value=b"")
    return response


async def test_complete_account_snapshot(
    api: MyUplink,
    system: System,
    device: Device,
    parameter: Parameter,
    zone: Zone,
    coordinator: MyUplinkCoordinator,
) -> None:
    """Associate nested API data with its own device and system."""
    api.additional_parameter = []
    point = {
        **parameter.raw_data,
        "category": "Text not found",
        "parameterName": "Supply\xad temperature",
        "smartHomeCategories": ["Heating"],
    }
    notification = {
        "id": "notification-1",
        "deviceId": device.id,
        "alarmNumber": "42",
        "severity": "2",
        "status": "active",
        "createdDatetime": "2026-09-01T12:00:00Z",
        "header": "Service required",
        "description": "Synthetic service notification",
        "equipName": "Heat pump",
    }
    other_device = {
        **device.raw_data,
        "id": "device-2",
        "firmware": {"currentFwVersion": "2.0", "desiredFwVersion": "2.1"},
    }
    payloads: dict[str, object] = {
        "systems/me?page=1&itemsPerPage=99": {
            "systems": [
                {
                    **system.raw_data,
                    "hasAlarm": True,
                    "devices": [device.raw_data, other_device],
                }
            ]
        },
        f"systems/{system.id}/subscriptions": {"subscriptions": [{"type": "manage"}]},
        f"systems/{system.id}/smart-home-mode": {"smartHomeMode": "Away"},
        f"systems/{system.id}/notifications/active?page=1&itemsPerPage=99": {
            "notifications": [notification]
        },
        f"devices/{device.id}/points": [point],
        "devices/device-2/points": [point],
        f"devices/{device.id}/firmware-info": device.firmware_info.raw_data,
        "devices/device-2/firmware-info": {
            "deviceId": "device-2",
            "firmwareId": "2",
            "currentFwVersion": "2.0",
            "desiredFwVersion": "2.1",
        },
        f"devices/{device.id}/smart-home-zones": [zone.raw_data],
        "devices/device-2/smart-home-zones": [],
    }

    async def request(method: str, path: str, **kwargs: object) -> MagicMock:
        assert method == "get"
        return make_response(payloads[path])

    with patch.object(api.auth, "request", side_effect=request) as transport:
        systems = await api.get_systems()
        assert transport.await_count == 10
    assert api.systems is systems
    loaded = systems[0]
    assert loaded.security_level == "Admin"
    assert loaded.has_alaram
    assert loaded.smart_home_mode == "Away"
    first, second = loaded.devices
    assert first.system is loaded
    assert first.parameters[0].device is first
    assert first.parameters[0].name == "Supply temperature"
    assert first.parameters[0].category == ""
    assert first.parameters[0].timestamp == "2026-09-01T12:00:00Z"
    assert first.parameters[0].smart_home_categories == ["Heating"]
    assert first.parameters[0].zone_id == "zone-1"
    assert first.zones[0].device is first
    assert first.notifications[0].id == "notification-1"
    assert second.notifications == []
    assert second.current_firmware_version == "2.0"
    assert second.desired_firmware_version == "2.1"
    assert second.firmware_info.device_id == second.id
    assert second.firmware_info.firmware_id == 2
    sensor = MyUplinkNotificationsSensorEntity(coordinator, first)
    assert sensor.native_value == 1
    assert sensor.extra_state_attributes == {
        "notifications": [
            {
                "header": "Service required",
                "description": "Synthetic service notification",
                "status": "active",
                "severity": 2,
                "equipment": "Heat pump",
                "alarm_number": 42,
                "created": "2026-09-01T12:00:00Z",
            }
        ]
    }


async def test_failed_snapshot_keeps_cached_account(
    api: MyUplink, system: System
) -> None:
    """Partial endpoint failures do not publish an incomplete account snapshot."""
    api.systems = [system]
    response = make_response({"systems": [system.raw_data]})
    with (
        patch.object(api.auth, "request", return_value=response),
        patch.object(System, "async_fetch_data", side_effect=TimeoutError),
        pytest.raises(TimeoutError),
    ):
        await api.get_systems()
    assert api.systems == [system]


async def test_optional_endpoints_disabled(
    hass: HomeAssistant,
    api: MyUplink,
    system: System,
    device: Device,
    parameter: Parameter,
) -> None:
    """Disabling optional fetching leaves only subscriptions and point reads."""
    hass.config_entries.async_update_entry(
        api.entry,
        options={
            "enable_smart_home_mode": False,
            "enable_smart_home_zone": False,
            "fetch_notifications": False,
            "fetch_firmware": False,
        },
    )
    with (
        patch.object(api, "get_parameters", return_value=[parameter]) as points,
        patch.object(api, "get_premium_manage", return_value=False),
        patch.object(api, "get_notifications") as notifications,
        patch.object(api, "get_firmware_info") as firmware,
        patch.object(api, "get_zones") as zones,
        patch.object(api, "get_smart_home_mode") as mode,
    ):
        await system.async_fetch_data()
    points.assert_awaited_once_with(device)
    notifications.assert_not_awaited()
    firmware.assert_not_awaited()
    zones.assert_not_awaited()
    mode.assert_not_awaited()
    assert not system.premium_manage


@pytest.mark.parametrize(
    ("whitelist", "additional", "expected"),
    [
        pytest.param([], [], [{}], id="all-points"),
        pytest.param([], [123], [{}, {"parameters": "123"}], id="additional-points"),
        pytest.param(
            [123], [456], [{"parameters": "123,456"}], id="whitelisted-points"
        ),
    ],
)
async def test_point_request_filters(
    api: MyUplink,
    device: Device,
    parameter: Parameter,
    whitelist: list[int],
    additional: list[int],
    expected: list[dict[str, str]],
) -> None:
    """Use one combined request when a whitelist is present."""
    api.parameter_whitelist = whitelist
    api.additional_parameter = additional
    with patch.object(
        api.auth, "request", return_value=make_response([parameter.raw_data])
    ) as request:
        points = await api.get_parameters(device)
    assert [call.kwargs["params"] for call in request.await_args_list] == expected
    assert [point.id for point in points] == [123]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param({"subscriptions": [{"type": "manage"}]}, True, id="manage"),
        pytest.param(
            {"subscriptions": [{"type": "history"}]}, False, id="other-subscription"
        ),
        pytest.param({}, False, id="no-subscriptions"),
    ],
)
async def test_subscription_cache(
    api: MyUplink, system: System, data: dict[str, object], expected: bool
) -> None:
    """Reuse permissions for fifteen minutes and refetch at expiry."""
    with (
        patch("custom_components.myuplink.api.monotonic", side_effect=[0, 899, 900]),
        patch.object(api.auth, "request", return_value=make_response(data)) as request,
    ):
        assert await api.get_premium_manage(system) is expected
        assert await api.get_premium_manage(system) is expected
        assert await api.get_premium_manage(system) is expected
    assert request.await_count == 2


async def test_subscription_recovery(
    api: MyUplink, system: System, caplog: pytest.LogCaptureFixture
) -> None:
    """Do not cache failures or keep permission state after a recovered negative result."""
    failure = ClientResponseError(MagicMock(), (), status=500)
    with patch.object(
        api.auth,
        "request",
        side_effect=[failure, make_response({"subscriptions": []})],
    ) as request:
        assert not await api.get_premium_manage(system)
        assert not await api.get_premium_manage(system)
        assert not await api.get_premium_manage(system)
    assert request.await_count == 2
    assert caplog.text.count("subscription lookup failed") == 1
    assert not api._subscription_failures


async def test_firmware_cache(api: MyUplink, device: Device) -> None:
    """Firmware data is reused for one hour while device snapshots are replaced."""
    updated = FirmwareInfo({**device.firmware_info.raw_data, "desiredFwVersion": "1.2"})
    with (
        patch("custom_components.myuplink.api.monotonic", side_effect=[0, 3599, 3600]),
        patch.object(
            api.auth,
            "request",
            side_effect=[
                make_response(device.firmware_info.raw_data),
                make_response(updated.raw_data),
            ],
        ) as request,
    ):
        first = await api.get_firmware_info(device)
        assert await api.get_firmware_info(device) is first
        assert (await api.get_firmware_info(device)).desired_version == "1.2"
    assert request.await_count == 2


async def test_get_device_association(
    api: MyUplink, device: Device, system: System
) -> None:
    """A direct device read retains its owning system rather than the API object."""
    with patch.object(api.auth, "request", return_value=make_response(device.raw_data)):
        result = await api.get_device(device.id, system)
    assert result.system is system
    assert result.name == "NIBE S1255 Home"
    assert result.serial_number == "test-serial"
    assert result.current_firmware_version == "1.0"
    assert result.desired_firmware_version == "?"
    assert not system.has_alaram


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(
            {
                "writable": False,
                "enumValues": [
                    {"value": "0", "text": "Off"},
                    {"value": "1", "text": "On"},
                ],
            },
            Platform.BINARY_SENSOR,
            id="read-only-boolean-enum",
        ),
        pytest.param(
            {"writable": True, "minValue": 0, "maxValue": 1},
            Platform.SWITCH,
            id="writable-boolean-range",
        ),
        pytest.param(
            {"writable": False, "minValue": 0, "maxValue": 1},
            Platform.BINARY_SENSOR,
            id="read-only-boolean-range",
        ),
        pytest.param(
            {"writable": True, "enumValues": [{"value": "1", "text": "Heat"}]},
            Platform.SELECT,
            id="writable-enum",
        ),
        pytest.param({"writable": True}, Platform.NUMBER, id="bounded-number"),
        pytest.param(
            {"writable": True, "minValue": None, "maxValue": None},
            Platform.SENSOR,
            id="unbounded-point",
        ),
        pytest.param({"writable": False}, Platform.SENSOR, id="read-only-point"),
    ],
)
def test_parameter_platform(
    parameter: Parameter, raw: dict[str, object], expected: Platform
) -> None:
    """Derive controls from metadata while retaining read-only sensor behavior."""
    parameter.raw_data.update(raw)
    assert parameter.get_platform() == expected


@pytest.mark.parametrize(
    "writable",
    [
        pytest.param(False, id="force-read-only"),
        pytest.param(True, id="force-writable"),
    ],
)
def test_writable_override(parameter: Parameter, writable: bool) -> None:
    """Apply expert permission corrections only when writes are allowed."""
    api = parameter.device.system.api
    api.writable_override[parameter.id] = writable
    assert parameter.is_writable is writable
    api.writable_without_subscription = False
    parameter.device.system.premium_manage = False
    assert not parameter.is_writable


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        pytest.param("currentFwVersion", " 1.0 ", "1.0", id="strip-current"),
        pytest.param("pendingFwVersion", " 1.1 ", "1.1", id="strip-pending"),
        pytest.param("desiredFwVersion", " 1.2 ", "1.2", id="strip-desired"),
        pytest.param("currentFwVersion", None, None, id="null-current"),
        pytest.param("pendingFwVersion", "", None, id="empty-pending"),
        pytest.param("desiredFwVersion", " ", None, id="blank-desired"),
    ],
)
def test_firmware_versions(field: str, value: str | None, expected: str | None) -> None:
    """Blank or null vendor versions are unavailable, not attribute errors."""
    info = FirmwareInfo({"deviceId": "device-1", "firmwareId": "1", field: value})
    versions = {
        "currentFwVersion": info.current_version,
        "pendingFwVersion": info.pending_version,
        "desiredFwVersion": info.desired_version,
    }
    assert versions[field] == expected


def test_isolated_model_collections(
    api: MyUplink, device: Device, system: System
) -> None:
    """New accounts and devices must never inherit another instance's cached data."""
    other_system = System(dict(system.raw_data), api)
    other_device = Device(dict(device.raw_data), other_system)
    other_device.parameters.append(MagicMock())
    other_device.zones.append(MagicMock())
    other_device.notifications.append(MagicMock())
    other_system.devices.append(other_device)
    assert device.parameters == []
    assert device.zones == []
    assert device.notifications == []
    assert system.devices == [device]
    assert other_system.devices == [other_device]
    assert other_device.firmware_info.current_version is None
    subscription = Subscription(
        {"type": "manage", "validUntil": "2027-01-01T00:00:00+00:00"}
    )
    assert subscription.valid_until == datetime.fromisoformat(
        "2027-01-01T00:00:00+00:00"
    )
