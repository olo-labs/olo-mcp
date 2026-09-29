"""Unit tests for environment-based server configuration."""

import pytest

from app.server import _log_level, _port


def test_port_defaults_to_8000(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_PORT", raising=False)
    assert _port() == 8000


def test_port_accepts_valid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_PORT", " 9000 ")
    assert _port() == 9000


@pytest.mark.parametrize("value", ["0", "65536", "-1"])
def test_port_rejects_out_of_range_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("MCP_PORT", value)
    with pytest.raises(ValueError, match="between 1 and 65535"):
        _port()


def test_port_rejects_non_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_PORT", "eight-thousand")
    with pytest.raises(ValueError, match="must be an integer"):
        _port()


def test_log_level_defaults_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert _log_level() == "INFO"


@pytest.mark.parametrize(
    ("configured", "expected"),
    [("debug", "DEBUG"), (" warning ", "WARNING"), ("CRITICAL", "CRITICAL")],
)
def test_log_level_normalizes_valid_values(
    monkeypatch: pytest.MonkeyPatch, configured: str, expected: str
) -> None:
    monkeypatch.setenv("LOG_LEVEL", configured)
    assert _log_level() == expected


def test_log_level_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "verbose")
    with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
        _log_level()
