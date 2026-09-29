"""Opt-in protocol test against the real Dockerized MCP server."""

import asyncio
import os
from pathlib import Path

import pytest
from langchain_mcp_adapters.client import MultiServerMCPClient

from agent_app.config import Settings
from agent_app.runtime import build_runtime


@pytest.mark.integration
def test_discovers_calls_and_builds_agent_for_dockerized_mcp_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.environ.get("RUN_MCP_DOCKER_INTEGRATION") != "1":
        pytest.skip("set RUN_MCP_DOCKER_INTEGRATION=1 with the MCP container running")

    async def exercise_server() -> None:
        mcp_url = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")
        client = MultiServerMCPClient(
            {
                "simple_mcp": {
                    "transport": "streamable_http",
                    "url": mcp_url,
                    "timeout": 10,
                }
            },
            handle_tool_errors=True,
        )
        tools = await client.get_tools()
        by_name = {tool.name: tool for tool in tools}
        assert set(by_name) == {"hello", "get_current_time", "calculate"}

        result = await by_name["calculate"].ainvoke(
            {"a": 25, "b": 12, "operation": "multiply"}
        )
        assert "300" in str(result)

        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        settings = Settings.from_env(
            {
                "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
                "MCP_URL": mcp_url,
                "AGENT_CHECKPOINT_DB": str(tmp_path / "checkpoints.sqlite"),
            }
        )
        async with build_runtime(settings) as runtime:
            assert set(runtime.tool_names) == {
                "hello",
                "get_current_time",
                "calculate",
            }

    asyncio.run(exercise_server())
