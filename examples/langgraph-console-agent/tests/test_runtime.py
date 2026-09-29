"""Tests for agent construction helpers without making model API calls."""

from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI

from agent_app.config import Settings
from agent_app.runtime import _middleware, health_url


def _settings(**overrides: str) -> Settings:
    environment = {"OPENAI_API_KEY": "test-key"} | overrides
    return Settings.from_env(environment)


def _tool() -> StructuredTool:
    def hello() -> str:
        return "hello"

    return StructuredTool.from_function(
        hello, name="hello", description="Return a greeting"
    )


def test_health_url_uses_same_origin() -> None:
    assert (
        health_url("https://mcp.example.com:8443/mcp?ignored=yes")
        == "https://mcp.example.com:8443/health"
    )


def test_middleware_stack_constructs_with_pinned_versions() -> None:
    settings = _settings()
    primary = ChatOpenAI(model=settings.openai_model, api_key="test-key")
    fallback = ChatOpenAI(model=settings.fallback_model, api_key="test-key")

    middleware = _middleware(settings, primary, fallback, [_tool()])

    assert len(middleware) == 9


def test_human_approval_middleware_can_be_enabled() -> None:
    settings = _settings(REQUIRE_TOOL_APPROVAL="true")
    primary = ChatOpenAI(model=settings.openai_model, api_key="test-key")
    fallback = ChatOpenAI(model=settings.fallback_model, api_key="test-key")

    middleware = _middleware(settings, primary, fallback, [_tool()])

    assert len(middleware) == 10
