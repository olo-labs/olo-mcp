"""Tests for console-agent environment validation."""

import pytest

from agent_app.config import ConfigurationError, Settings


def valid_environment() -> dict[str, str]:
    return {"OPENAI_API_KEY": "test-key"}


def test_settings_defaults() -> None:
    settings = Settings.from_env(valid_environment())

    assert settings.mcp_url == "http://127.0.0.1:8000/mcp"
    assert settings.openai_model == "gpt-5-mini"
    assert settings.allowed_tools == ("hello", "get_current_time", "calculate")
    assert settings.strict_prompt_guard is True


def test_api_key_is_required() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        Settings.from_env({})


@pytest.mark.parametrize(
    "url",
    ["localhost:8000/mcp", "ftp://localhost/mcp", "http://localhost/tools"],
)
def test_mcp_url_is_validated(url: str) -> None:
    environment = valid_environment() | {"MCP_URL": url}
    with pytest.raises(ConfigurationError, match="MCP_URL"):
        Settings.from_env(environment)


def test_limits_are_validated() -> None:
    environment = valid_environment() | {"TOOL_CALL_LIMIT": "0"}
    with pytest.raises(ConfigurationError, match="TOOL_CALL_LIMIT"):
        Settings.from_env(environment)


def test_boolean_is_validated() -> None:
    environment = valid_environment() | {"STRICT_PROMPT_GUARD": "sometimes"}
    with pytest.raises(ConfigurationError, match="true or false"):
        Settings.from_env(environment)


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("OPENAI_MODEL", " ", "OPENAI_MODEL"),
        ("ALLOWED_MCP_TOOLS", "hello,hello", "duplicates"),
    ],
)
def test_model_and_allowlist_are_validated(
    name: str, value: str, message: str
) -> None:
    environment = valid_environment() | {name: value}
    with pytest.raises(ConfigurationError, match=message):
        Settings.from_env(environment)
