"""Test parameter identity across changing cloud metadata."""

from unittest.mock import AsyncMock, MagicMock, patch

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


async def test_renamed_duplicate_points(
    api: MyUplink, device: Device, parameter: Parameter
) -> None:
    """Combine renamed points by the same identity used by Home Assistant."""
    api.additional_parameter = []
    response = MagicMock(spec=ClientResponse)
    response.json = AsyncMock(
        return_value=[
            dict(parameter.raw_data),
            {**parameter.raw_data, "parameterName": "Renamed point"},
        ]
    )
    with patch.object(api.auth, "request", new=AsyncMock(return_value=response)):
        parameters = await api.get_parameters(device)
    assert len(parameters) == 1
    assert parameters[0].id == parameter.id
    assert parameters[0].name == "Renamed point"
