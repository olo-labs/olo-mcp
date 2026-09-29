"""Integration tests through the official MCP client and ASGI application."""

import asyncio

import httpx2
import pytest
from mcp import Client

from app.server import mcp

pytestmark = pytest.mark.integration


def test_health_route() -> None:
    async def request_health() -> tuple[int, dict[str, str]]:
        app = mcp.streamable_http_app(
            host="127.0.0.1", json_response=True, stateless_http=True
        )
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            response = await client.get("/health")
            return response.status_code, response.json()

    status, body = asyncio.run(request_health())
    assert status == 200
    assert body == {"status": "ok"}


def test_client_discovers_tools_and_generated_schemas() -> None:
    async def discover() -> dict[str, dict[str, object]]:
        async with Client(mcp) as client:
            result = await client.list_tools()
            return {tool.name: tool.input_schema for tool in result.tools}

    schemas = asyncio.run(discover())

    assert set(schemas) == {"hello", "get_current_time", "calculate"}
    assert schemas["hello"]["required"] == ["name"]
    assert schemas["get_current_time"]["properties"] == {}
    operation_schema = schemas["calculate"]["properties"]["operation"]  # type: ignore[index]
    assert operation_schema["enum"] == ["add", "subtract", "multiply", "divide"]  # type: ignore[index]


def test_client_calls_tools_and_receives_structured_results() -> None:
    async def call_tools() -> tuple[object, object]:
        async with Client(mcp) as client:
            greeting = await client.call_tool("hello", {"name": "Rahul"})
            calculation = await client.call_tool(
                "calculate", {"a": 25, "b": 12, "operation": "multiply"}
            )
            return greeting, calculation

    greeting, calculation = asyncio.run(call_tools())

    assert not greeting.is_error  # type: ignore[union-attr]
    assert greeting.structured_content == {"result": "Hello Rahul!"}  # type: ignore[union-attr]
    assert not calculation.is_error  # type: ignore[union-attr]
    assert calculation.structured_content == {  # type: ignore[union-attr]
        "a": 25,
        "b": 12,
        "operation": "multiply",
        "result": 300,
    }


def test_client_receives_expected_tool_errors() -> None:
    async def call_invalid_tools() -> tuple[object, object]:
        async with Client(mcp) as client:
            zero = await client.call_tool(
                "calculate", {"a": 10, "b": 0, "operation": "divide"}
            )
            invalid = await client.call_tool(
                "calculate", {"a": 10, "b": 2, "operation": "power"}
            )
            return zero, invalid

    zero, invalid = asyncio.run(call_invalid_tools())

    assert zero.is_error  # type: ignore[union-attr]
    assert "Cannot divide by zero" in zero.content[0].text  # type: ignore[union-attr]
    assert invalid.is_error  # type: ignore[union-attr]
    assert "operation" in invalid.content[0].text  # type: ignore[union-attr]
