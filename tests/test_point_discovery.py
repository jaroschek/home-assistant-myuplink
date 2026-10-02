"""Test parameter identity across changing cloud metadata."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponse
from homeassistant.const import Platform

from custom_components.myuplink.api import Device, MyUplink, Parameter
from custom_components.myuplink.coordinator import MyUplinkCoordinator


def test_platform_stable_until_reload(
    coordinator: MyUplinkCoordinator, parameter: Parameter
) -> None:
    """A changed writable flag must not create a second platform's entity."""
    assert coordinator.parameter_platform(parameter) == Platform.SENSOR
    parameter.raw_data["writable"] = True
    assert parameter.get_platform() == Platform.NUMBER
    assert coordinator.parameter_platform(parameter) == Platform.SENSOR


@pytest.mark.parametrize(
    ("additional", "payloads", "expected_name"),
    [
        pytest.param(
            [], [[{}, {}]], "Supply temperature", id="pr-108-exact-duplicates"
        ),
        pytest.param(
            [],
            [[{}, {"parameterName": "Renamed point"}]],
            "Renamed point",
            id="renamed-duplicates",
        ),
        pytest.param(
            [123], [[{}], [{}]], "Supply temperature", id="duplicates-across-requests"
        ),
        pytest.param(
            [123],
            [[{}], [{"parameterName": "Renamed point"}]],
            "Renamed point",
            id="renamed-across-requests",
        ),
        pytest.param(
            [123],
            [
                [{"parameterId": 123}],
                [{"parameterId": "123", "parameterName": "Renamed point"}],
            ],
            "Renamed point",
            id="normalized-point-ids",
        ),
    ],
)
async def test_duplicate_points_by_entity_identity(
    api: MyUplink,
    device: Device,
    parameter: Parameter,
    additional: list[int],
    payloads: list[list[dict[str, str | int]]],
    expected_name: str,
) -> None:
    """PR #108: deduplicate by entity identity even when API labels change."""
    api.additional_parameter = additional
    responses = []
    for payload in payloads:
        response = MagicMock(spec=ClientResponse)
        response.json = AsyncMock(
            return_value=[{**parameter.raw_data, **point} for point in payload]
        )
        responses.append(response)
    with patch.object(api.auth, "request", side_effect=responses) as request:
        parameters = await api.get_parameters(device)
    assert request.await_count == len(payloads)
    assert len(parameters) == 1
    assert parameters[0].id == parameter.id
    assert parameters[0].name == expected_name
