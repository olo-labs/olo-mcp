"""Unit tests for the MCP tool functions."""

from datetime import datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.server import calculate, get_current_time, hello


def test_hello() -> None:
    assert hello("Rahul") == "Hello Rahul!"


def test_hello_trims_surrounding_whitespace() -> None:
    assert hello("  Rahul  ") == "Hello Rahul!"


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_hello_rejects_empty_names(name: str) -> None:
    with pytest.raises(ToolError, match="name must not be empty"):
        hello(name)


@pytest.mark.parametrize(
    ("a", "b", "operation", "expected"),
    [
        (10, 5, "add", 15),
        (10, 5, "subtract", 5),
        (10, 5, "multiply", 50),
        (10, 5, "divide", 2),
        (2.5, 1.25, "add", 3.75),
        (-3, 2, "multiply", -6),
    ],
)
def test_calculate_supported_operations(
    a: int | float,
    b: int | float,
    operation: str,
    expected: int | float,
) -> None:
    result = calculate(a, b, operation)  # type: ignore[arg-type]

    assert result == {
        "a": a,
        "b": b,
        "operation": operation,
        "result": expected,
    }


@pytest.mark.parametrize("zero", [0, 0.0])
def test_calculate_rejects_division_by_zero(zero: int | float) -> None:
    with pytest.raises(ToolError, match="Cannot divide by zero"):
        calculate(10, zero, "divide")


def test_calculate_rejects_invalid_operation() -> None:
    with pytest.raises(ToolError, match="Unsupported operation"):
        calculate(10, 5, "power")  # type: ignore[arg-type]


def test_current_time_uses_configured_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TZ", "Asia/Kolkata")
    result = get_current_time()

    parsed = datetime.fromisoformat(result["datetime"])
    assert result["timezone"] == "Asia/Kolkata"
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 5.5 * 60 * 60


def test_current_time_uses_default_for_blank_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TZ", "   ")

    assert get_current_time()["timezone"] == "Asia/Kolkata"


def test_current_time_rejects_unknown_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TZ", "Not/A-Timezone")

    with pytest.raises(ToolError, match="is unavailable"):
        get_current_time()
