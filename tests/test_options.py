"""Test expert option normalization without weakening API contracts."""

import pytest
from homeassistant.const import Platform

from custom_components.myuplink.const import (
    DEFAULT_PLATFORM_OVERRIDE,
    DEFAULT_WRITABLE_OVERRIDE,
)
from custom_components.myuplink.options import (
    parameter_ids,
    platform_overrides,
    writable_overrides,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("[123, 456]", [123, 456], id="integer-ids"),
        pytest.param('["123", "456"]', [123, 456], id="text-ids"),
        pytest.param("[]", [], id="empty-list"),
        pytest.param(None, [], id="unset"),
        pytest.param("", [], id="empty-text"),
        pytest.param(" ", [], id="blank-text"),
        pytest.param("invalid", [], id="invalid-json"),
        pytest.param("{}", [], id="wrong-structure"),
        pytest.param("[true]", [], id="boolean-is-not-an-id"),
        pytest.param("[1.5]", [], id="fraction-is-not-an-id"),
        pytest.param('["invalid"]', [], id="invalid-id-text"),
    ],
)
def test_parameter_ids(value: object, expected: list[int]) -> None:
    """Malformed lists restore defaults instead of causing request failures."""
    assert parameter_ids(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="unset"),
        pytest.param("invalid", id="invalid-json"),
        pytest.param("[]", id="wrong-structure"),
        pytest.param('{"invalid": "sensor"}', id="invalid-id"),
        pytest.param('{"123": "climate"}', id="unsupported-platform"),
        pytest.param('{"123": false}', id="wrong-value-type"),
    ],
)
def test_invalid_platform_override(value: object) -> None:
    """Only parameter entity platforms are accepted."""
    result = platform_overrides(value)
    assert result == DEFAULT_PLATFORM_OVERRIDE
    assert result is not DEFAULT_PLATFORM_OVERRIDE


def test_valid_platform_override() -> None:
    """Integer point keys and platform enum values are ready for entity lookup."""
    assert platform_overrides('{"123": "sensor", "456": "switch"}') == {
        123: Platform.SENSOR,
        456: Platform.SWITCH,
    }
    assert platform_overrides("{}") == {}


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="unset"),
        pytest.param("[]", id="wrong-structure"),
        pytest.param('{"invalid": false}', id="invalid-id"),
        pytest.param('{"123": "false"}', id="text-is-not-a-boolean"),
        pytest.param('{"123": 0}', id="integer-is-not-a-boolean"),
    ],
)
def test_invalid_writable_override(value: object) -> None:
    """Do not silently turn string or integer values into permissions."""
    assert writable_overrides(value) == DEFAULT_WRITABLE_OVERRIDE


def test_valid_writable_override() -> None:
    """An explicit empty mapping clears the default corrections."""
    assert writable_overrides('{"123": false, "456": true}') == {
        123: False,
        456: True,
    }
    assert writable_overrides("{}") == {}
