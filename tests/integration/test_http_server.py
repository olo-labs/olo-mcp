"""End-to-end tests against a real Streamable HTTP server process."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator

import pytest
from mcp import Client

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@pytest.fixture(scope="module")
def running_server() -> Iterator[str]:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment.update(
        {
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": str(port),
            "TZ": "Asia/Kolkata",
            "LOG_LEVEL": "WARNING",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "app.server"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"MCP server exited during startup:\n{output}")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(0.1)
    else:
        process.terminate()
        process.wait(timeout=5)
        raise RuntimeError("MCP server did not become healthy within 15 seconds")

    try:
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_real_http_health_endpoint(running_server: str) -> None:
    with urllib.request.urlopen(f"{running_server}/health", timeout=3) as response:
        assert response.status == 200
        assert response.read() == b'{"status":"ok"}'


def test_real_http_mcp_discovery_and_calls(running_server: str) -> None:
    async def exercise_server() -> None:
        async with Client(f"{running_server}/mcp") as client:
            listing = await client.list_tools()
            assert {tool.name for tool in listing.tools} == {
                "hello",
                "get_current_time",
                "calculate",
            }

            calculation = await client.call_tool(
                "calculate", {"a": 25, "b": 12, "operation": "multiply"}
            )
            assert not calculation.is_error
            assert calculation.structured_content == {
                "a": 25,
                "b": 12,
                "operation": "multiply",
                "result": 300,
            }

            current_time = await client.call_tool("get_current_time", {})
            assert not current_time.is_error
            assert current_time.structured_content is not None
            assert current_time.structured_content["timezone"] == "Asia/Kolkata"
            assert current_time.structured_content["datetime"].endswith("+05:30")

    asyncio.run(exercise_server())


def test_real_http_mcp_error_result(running_server: str) -> None:
    async def divide_by_zero() -> None:
        async with Client(f"{running_server}/mcp") as client:
            result = await client.call_tool(
                "calculate", {"a": 10, "b": 0, "operation": "divide"}
            )
            assert result.is_error
            assert "Cannot divide by zero" in result.content[0].text

    asyncio.run(divide_by_zero())
