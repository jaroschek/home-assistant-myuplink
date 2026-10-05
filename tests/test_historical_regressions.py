"""Protect behavior reported in historical GitHub issues and contributor PRs."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import (
    ClientConnectionError,
    ClientResponse,
    ClientResponseError,
    ContentTypeError,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import PlatformData

from custom_components.myuplink.api import (
    Device,
    MyUplink,
    MyUplinkRateLimitError,
    Parameter,
    System,
)
from custom_components.myuplink.const import DOMAIN
from custom_components.myuplink.coordinator import MyUplinkCoordinator
from custom_components.myuplink.entity import MyUplinkDeviceEntity
from custom_components.myuplink.models import ParameterData
from custom_components.myuplink.number import MyUplinkParameterNumberEntity
from custom_components.myuplink.sensor import (
    MyUplinkParameterSensorEntity,
    async_setup_entry,
)


def response(data: object) -> MagicMock:
    """Create a response without connecting to the cloud."""
    result = MagicMock(spec=ClientResponse)
    result.status = 200
    result.json = AsyncMock(return_value=data)
    result.read = AsyncMock(return_value=b"")
    return result


@pytest.mark.parametrize(
    ("error", "failure_method"),
    [
        pytest.param(
            ClientResponseError(MagicMock(), (), status=500),
            "raise_for_status",
            id="http-500",
        ),
        pytest.param(
            ClientResponseError(MagicMock(), (), status=503),
            "raise_for_status",
            id="http-503",
        ),
        pytest.param(ClientConnectionError(), "json", id="connection"),
        pytest.param(TimeoutError(), "json", id="timeout"),
        pytest.param(ValueError("Invalid JSON"), "json", id="invalid-json"),
        pytest.param(
            ContentTypeError(MagicMock(), (), status=200),
            "json",
            id="invalid-content-type",
        ),
    ],
)
async def test_optional_subscription_failure_keeps_readings(
    hass: HomeAssistant,
    api: MyUplink,
    system: System,
    device: Device,
    parameter: Parameter,
    coordinator: MyUplinkCoordinator,
    error: Exception,
    failure_method: str,
) -> None:
    """Issue #212 / PR #213: an optional lookup cannot block healthy point reads."""
    hass.config_entries.async_update_entry(
        api.entry,
        options={
            "enable_smart_home_mode": False,
            "enable_smart_home_zone": False,
            "fetch_notifications": False,
            "fetch_firmware": False,
        },
    )
    api.additional_parameter = []
    systems = response({"systems": [{**system.raw_data, "devices": [device.raw_data]}]})
    subscriptions = response({})
    getattr(subscriptions, failure_method).side_effect = error
    points = response([parameter.raw_data])
    with patch.object(
        api.auth, "request", side_effect=[systems, subscriptions, points]
    ) as request:
        await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert request.await_count == 3
    assert coordinator.parameters_by_id[(device.id, parameter.id)].value == 20
    assert not coordinator.data[0].premium_manage
    assert not api._subscription_cache


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(MyUplinkRateLimitError(60), id="quota"),
        pytest.param(asyncio.CancelledError(), id="shutdown"),
    ],
)
async def test_subscription_quota_and_cancellation_propagate(
    api: MyUplink, system: System, error: BaseException
) -> None:
    """Preserve the retry window and allow cancelled setup or shutdown to finish."""
    with (
        patch.object(api.auth, "request", side_effect=error),
        pytest.raises(type(error)),
    ):
        await api.get_premium_manage(system)
    assert not api._subscription_failures


async def test_subscription_no_content(api: MyUplink, system: System) -> None:
    """PR #192: HTTP 204 means no Manage subscription and has no JSON body."""
    no_content = response(None)
    no_content.status = 204
    with patch.object(api.auth, "request", return_value=no_content) as request:
        assert not await api.get_premium_manage(system)
        assert not await api.get_premium_manage(system)
    request.assert_awaited_once()
    no_content.json.assert_not_awaited()


async def test_cancelled_rate_limit_pacing_releases_lock(
    api: MyUplink, system: System
) -> None:
    """Issue #84: shutdown cancellation must not issue a request or retain the lock."""
    api.auth.rate_limit_remaining = 5
    api.auth.rate_limit_reset_at = datetime.now(UTC) + timedelta(seconds=60)
    with (
        patch(
            "custom_components.myuplink.api.asyncio.sleep",
            side_effect=asyncio.CancelledError,
        ),
        patch.object(api.auth, "request") as request,
        pytest.raises(asyncio.CancelledError),
    ):
        await api.get_premium_manage(system)
    assert not api.lock.locked()
    request.assert_not_called()


@pytest.mark.parametrize(
    ("point_id", "unit", "value", "device_class", "state_class"),
    [
        pytest.param(
            40004,
            "°C",
            16.4,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
            id="issue-161-temperature",
        ),
        pytest.param(
            40083,
            "A",
            0.1,
            SensorDeviceClass.CURRENT,
            SensorStateClass.MEASUREMENT,
            id="issue-147-current",
        ),
        pytest.param(
            147,
            "kWH",
            12406.7,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            id="issue-166-energy",
        ),
        pytest.param(
            25165,
            "kW",
            4.5,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
            id="issue-238-power",
        ),
        pytest.param(
            40782,
            "Hz",
            45,
            SensorDeviceClass.FREQUENCY,
            SensorStateClass.MEASUREMENT,
            id="issue-40-frequency",
        ),
    ],
)
def test_reported_measurements_keep_values_and_statistics(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    point_id: int,
    unit: str,
    value: float,
    device_class: SensorDeviceClass,
    state_class: SensorStateClass,
) -> None:
    """Reported readings are already scaled; scaleValue describes raw bounds."""
    parameter.raw_data.update(
        parameterId=point_id, parameterUnit=unit, value=value, scaleValue=0.1
    )
    entity = MyUplinkParameterSensorEntity(coordinator, device, parameter)
    assert entity.native_value == value
    assert entity.device_class == device_class
    assert entity.state_class == state_class
    assert entity.unique_id == f"myuplink_{device.id}_{point_id}"


@pytest.mark.parametrize(
    "value",
    [pytest.param(0, id="issue-55-zero"), pytest.param(180, id="issue-62-delay")],
)
def test_ctc_duration_with_partial_enum(
    hass: HomeAssistant,
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    value: int,
) -> None:
    """Issues #55 / #62: numeric minutes must not become an enum with only Blocked."""
    parameter.raw_data.update(
        parameterId=62004,
        parameterUnit="min",
        value=value,
        enumValues=[{"value": "241", "text": "Blocked"}],
    )
    entity = MyUplinkParameterSensorEntity(coordinator, device, parameter)
    entity.platform_data = PlatformData(hass, domain="sensor", platform_name=DOMAIN)
    assert entity.state == value
    assert entity.device_class == SensorDeviceClass.DURATION
    assert entity.options is None


async def test_reported_temperature_bounds_and_write(
    coordinator: MyUplinkCoordinator, device: Device, parameter: Parameter
) -> None:
    """Issue #21: 50–300 with scale 0.1 represents 5–30 °C and a 0.5 °C step."""
    parameter.raw_data.update(
        parameterId=47753,
        writable=True,
        minValue=50,
        maxValue=300,
        stepValue=5,
        scaleValue=0.1,
        value=18,
    )
    entity = MyUplinkParameterNumberEntity(coordinator, device, parameter)
    assert (entity.native_min_value, entity.native_max_value, entity.native_step) == (
        5,
        30,
        0.5,
    )
    assert entity.native_value == 18
    with (
        patch.object(
            device.system.api.auth, "request", return_value=response({})
        ) as request,
        patch.object(entity, "async_update"),
    ):
        await entity.async_set_native_value(18.5)
    assert json.loads(request.call_args.kwargs["data"]) == {"47753": 18.5}


@pytest.mark.parametrize(
    "point_id",
    [47050, 47394, 47635, 47669, 47771, 47805, 47839, 47975, 48009, 48043, 48442],
)
def test_unbounded_nibe_switch_overrides(parameter: Parameter, point_id: int) -> None:
    """Issue #122 / PR #125: boolean controls survive missing bounds and enums."""
    parameter.raw_data.update(
        parameterId=point_id, writable=True, minValue=None, maxValue=None, enumValues=[]
    )
    assert parameter.get_platform() == Platform.SWITCH


@pytest.mark.parametrize(
    "point_id",
    [pytest.param(781, id="point-781"), pytest.param(15753, id="point-15753")],
)
async def test_legacy_read_only_overrides(parameter: Parameter, point_id: int) -> None:
    """PR #11: manufacturer metadata must not enable writes to read-only points."""
    parameter.raw_data.update(parameterId=point_id, writable=True)
    assert not parameter.is_writable
    with pytest.raises(ServiceValidationError):
        await parameter.update_parameter(21)


@pytest.mark.parametrize(
    ("point_id", "writable", "expected"),
    [
        pytest.param(505, False, Platform.BINARY_SENSOR, id="pr-4-hoiax-505"),
        pytest.param(506, False, Platform.BINARY_SENSOR, id="pr-4-hoiax-506"),
        pytest.param(600, True, Platform.SWITCH, id="pr-11-hoiax-600"),
        pytest.param(50005, True, Platform.SWITCH, id="issue-77-lowercase"),
    ],
)
def test_lowercase_boolean_controls(
    parameter: Parameter, point_id: int, writable: bool, expected: Platform
) -> None:
    """PR #78: label capitalization cannot turn an off/on control into a select."""
    parameter.raw_data.update(
        parameterId=point_id,
        writable=writable,
        enumValues=[{"value": "0", "text": "off"}, {"value": "1", "text": "on"}],
    )
    assert parameter.get_platform() == expected


async def test_hoiax_model_id_does_not_block_other_points(
    hass: HomeAssistant,
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
) -> None:
    """PR #102: the unitless, non-enum model_id point contains text, not a number."""
    model = Parameter(
        cast(
            ParameterData,
            {
                **parameter.raw_data,
                "parameterId": "513",
                "parameterName": "model_id",
                "parameterUnit": "",
                "enumValues": [],
                "value": "18760NE12345",
                "strVal": "18760NE12345",
            },
        ),
        device,
    )
    device.parameters = [model, parameter]
    device.zones = []
    entities: list[Entity] = []
    await async_setup_entry(hass, device.system.api.entry, entities.extend)
    assert [entity.unique_id for entity in entities] == [
        f"myuplink_{device.id}_notifications",
        f"myuplink_{device.id}_{parameter.id}",
    ]


@pytest.mark.parametrize(
    "premium",
    [pytest.param(False, id="without-premium"), pytest.param(True, id="with-premium")],
)
async def test_writes_without_subscription_preserve_default(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    premium: bool,
) -> None:
    """Issues #191 / #196 and PR #193: writable points can work without Manage."""
    device.system.premium_manage = premium
    assert device.system.api.writable_without_subscription
    parameter.raw_data.update(writable=True)
    entity = MyUplinkParameterNumberEntity(coordinator, device, parameter)
    with (
        patch.object(
            device.system.api.auth, "request", return_value=response({})
        ) as request,
        patch.object(entity, "async_update"),
    ):
        await entity.async_set_native_value(21)
    assert json.loads(request.call_args.kwargs["data"]) == {"123": 21}


async def test_subscription_opt_out_rejects_unsubscribed_write(
    parameter: Parameter,
) -> None:
    """PR #193: disabling the override keeps unsubscribed controls read-only."""
    parameter.device.system.premium_manage = False
    parameter.device.system.api.writable_without_subscription = False
    parameter.raw_data["writable"] = True
    assert parameter.get_platform() == Platform.SENSOR
    with (
        patch.object(parameter.device.system.api.auth, "request") as request,
        pytest.raises(ServiceValidationError),
    ):
        await parameter.update_parameter(21)
    request.assert_not_called()


async def test_rejected_write_keeps_sensor_availability(
    coordinator: MyUplinkCoordinator, device: Device, parameter: Parameter
) -> None:
    """Issue #191: a rejected command must not invalidate a successful snapshot."""
    parameter.raw_data["writable"] = True
    entity = MyUplinkParameterNumberEntity(coordinator, device, parameter)
    sensor = MyUplinkParameterSensorEntity(coordinator, device, parameter)
    failure = response({})
    failure.raise_for_status.side_effect = ClientResponseError(
        MagicMock(), (), status=500
    )
    with (
        patch.object(device.system.api.auth, "request", return_value=failure),
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_set_native_value(21)
    assert coordinator.last_update_success
    assert sensor.available
    assert sensor.native_value == 20


@pytest.mark.parametrize(
    "point_id",
    [406, 500, 517, 544, 549, 601, 1965, 14950, 55000, 55027, 62005, 62017, 62246],
)
def test_contributor_enum_keys_are_strings(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    point_id: int,
) -> None:
    """Issue #10 / PRs #3, #7, #219: translated IDs stay strings and keep API states."""
    parameter.raw_data.update(
        parameterId=point_id,
        parameterUnit="",
        enumValues=[{"value": "3", "text": "Eco"}, {"value": "4", "text": "Normal"}],
        value=4,
        strVal="Normal",
    )
    entity = MyUplinkParameterSensorEntity(coordinator, device, parameter)
    assert entity.translation_key == str(point_id)
    assert entity.native_value == "Normal"
    assert entity.options == ["Eco", "Normal"]
    strings = json.loads(
        (
            Path(__file__).parents[1] / "custom_components/myuplink/strings.json"
        ).read_text()
    )
    assert strings["entity"]["sensor"][str(point_id)]["state"]


async def test_many_devices_with_rate_limit_headroom(
    api: MyUplink, system: System, device: Device, coordinator: MyUplinkCoordinator
) -> None:
    """Issues #15 / #246 / #247 and PR #248: startup does not sleep per request."""
    many_devices = [{**device.raw_data, "id": f"device-{index}"} for index in range(6)]
    api.auth.rate_limit_remaining = 25
    api.auth.rate_limit_reset_at = datetime.now(UTC) + timedelta(seconds=60)
    api.additional_parameter = []
    with (
        patch.object(
            api.auth,
            "request",
            side_effect=[
                response({"systems": [{**system.raw_data, "devices": many_devices}]}),
                response({"subscriptions": []}),
                response({"smartHomeMode": "Home"}),
                response({"notifications": []}),
                *[
                    item
                    for _ in many_devices
                    for item in (
                        response([]),
                        response({"deviceId": "unused", "firmwareId": "1"}),
                        response([]),
                    )
                ],
            ],
        ) as request,
        patch("custom_components.myuplink.api.asyncio.sleep") as sleep,
    ):
        await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert len(coordinator.devices_by_id) == 6
    assert request.await_count == 22
    sleep.assert_not_called()


@pytest.mark.parametrize(
    ("language", "point_id", "state", "label"),
    [
        pytest.param("nb", 406, "Eco", "Øko", id="hoiax-mode"),
        pytest.param("nb", 500, "Vacation", "Ferie", id="hoiax-operation"),
        pytest.param("nb", 549, "Cheap", "Billig", id="hoiax-price"),
        pytest.param("nb", 1965, "Defrosting", "Avrimer", id="nibe-defrosting"),
        pytest.param("nb", 14950, "Heating", "Varmer", id="nibe-heating"),
        pytest.param("nb", 55000, "Hot water", "Varmtvann", id="nibe-hot-water"),
        pytest.param("nb", 55027, "Blocked", "Blokkert", id="nibe-blocked"),
        pytest.param("de", 1965, "Off", "Aus", id="german-off"),
        pytest.param("de", 14950, "Hot water", "Brauchwasser", id="german-hot-water"),
        pytest.param("de", 55000, "Cooling", "Kühlung", id="german-cooling"),
        pytest.param("de", 55027, "Active", "Aktiv", id="german-active"),
    ],
)
def test_legacy_api_labels_remain_translatable(
    coordinator: MyUplinkCoordinator,
    device: Device,
    parameter: Parameter,
    language: str,
    point_id: int,
    state: str,
    label: str,
) -> None:
    """The 1.8 translations resolve against API text states, including spaces."""
    parameter.raw_data.update(
        parameterId=point_id,
        parameterUnit="",
        enumValues=[{"value": "3", "text": state}],
        value=3,
        strVal=state,
    )
    entity = MyUplinkParameterSensorEntity(coordinator, device, parameter)
    translation = json.loads(
        (
            Path(__file__).parents[1]
            / f"custom_components/myuplink/translations/{language}.json"
        ).read_text()
    )
    assert entity.native_value == state
    assert (
        translation["entity"]["sensor"][entity.translation_key]["state"][
            entity.native_value
        ]
        == label
    )


def test_single_word_hoiax_model(
    coordinator: MyUplinkCoordinator, device: Device
) -> None:
    """PR #5: a one-word product is a model, not a manufacturer."""
    device.raw_data["product"]["name"] = "18760NE12345"
    device.system.raw_data["name"] = "18760NE12345"
    entity = MyUplinkDeviceEntity(coordinator, device)
    assert entity.device_info["manufacturer"] is None
    assert entity.device_info["model"] == "18760NE12345"


async def test_two_systems_keep_point_ownership(
    hass: HomeAssistant,
    api: MyUplink,
    system: System,
    device: Device,
    parameter: Parameter,
    coordinator: MyUplinkCoordinator,
) -> None:
    """Issue #97: the same point ID on two systems belongs to distinct devices."""
    hass.config_entries.async_update_entry(
        api.entry,
        options={
            "enable_smart_home_mode": False,
            "enable_smart_home_zone": False,
            "fetch_notifications": False,
            "fetch_firmware": False,
        },
    )
    api.additional_parameter = []
    second_device = {**device.raw_data, "id": "device-2"}
    second_system = {
        **system.raw_data,
        "systemId": "system-2",
        "devices": [second_device],
    }
    with patch.object(
        api.auth,
        "request",
        side_effect=[
            response(
                {
                    "systems": [
                        {**system.raw_data, "devices": [device.raw_data]},
                        second_system,
                    ]
                }
            ),
            response({"subscriptions": []}),
            response([parameter.raw_data]),
            response({"subscriptions": []}),
            response([parameter.raw_data]),
        ],
    ):
        await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert set(coordinator.systems_by_id) == {"system-1", "system-2"}
    assert set(coordinator.parameters_by_id) == {("device-1", 123), ("device-2", 123)}
    assert (
        coordinator.parameters_by_id[("device-1", 123)].device.system.id == "system-1"
    )
    assert (
        coordinator.parameters_by_id[("device-2", 123)].device.system.id == "system-2"
    )
