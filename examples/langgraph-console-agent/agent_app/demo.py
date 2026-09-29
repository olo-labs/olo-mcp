"""Transparent MCP API demonstration followed by one guarded agent turn."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agent_app.config import ConfigurationError, Settings
from agent_app.logging_config import configure_logging
from agent_app.runtime import build_runtime, health_url

DEFAULT_PROMPT = (
    "Use every available MCP tool: greet Anupriya, report the current server "
    "time, and calculate 25 times 12."
)

DEMO_CALLS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("hello", {"name": "Anupriya"}),
    ("get_current_time", {}),
    ("calculate", {"a": 25, "b": 12, "operation": "multiply"}),
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show every MCP request/response, then run a sample agent prompt"
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    return parser.parse_args()


def _json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _show_exchange(
    title: str, *, url: str, payload: dict[str, Any], response: Any
) -> None:
    print(f"\n=== {title} ===")
    print(f"URL: {url}")
    print("PAYLOAD:")
    print(_json(payload))
    print("RESPONSE:")
    print(_json(response))


async def _show_all_mcp_apis(mcp_url: str) -> None:
    endpoint_health = health_url(mcp_url)
    async with httpx.AsyncClient(timeout=15) as http_client:
        health_response = await http_client.get(endpoint_health)
        health_response.raise_for_status()
        _show_exchange(
            "Health API",
            url=endpoint_health,
            payload={"method": "GET"},
            response=health_response.json(),
        )

    async with streamable_http_client(mcp_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            _show_exchange(
                "MCP tool discovery",
                url=mcp_url,
                payload={"jsonrpc": "2.0", "method": "tools/list", "params": {}},
                response=tools_response,
            )

            exposed_names = {tool.name for tool in tools_response.tools}
            expected_names = {name for name, _ in DEMO_CALLS}
            missing = expected_names - exposed_names
            if missing:
                raise RuntimeError(
                    "MCP server is missing expected tools: " + ", ".join(sorted(missing))
                )

            for name, arguments in DEMO_CALLS:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
                result = await session.call_tool(name, arguments)
                _show_exchange(
                    f"MCP tool: {name}",
                    url=mcp_url,
                    payload=payload,
                    response=result,
                )


async def _run() -> int:
    project_directory = Path(__file__).resolve().parents[1]
    load_dotenv(project_directory / ".env")
    arguments = _arguments()
    mcp_url = os.environ.get("MCP_URL", "http://localhost:18001/mcp")

    try:
        await _show_all_mcp_apis(mcp_url)
    except Exception as exc:
        print(f"\nMCP API demonstration failed: {exc}", file=sys.stderr)
        return 1

    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        print(f"\nAgent configuration error: {exc}", file=sys.stderr)
        print(
            "The MCP exchanges completed, but OPENAI_API_KEY is required for "
            "the sample agent prompt.",
            file=sys.stderr,
        )
        return 2

    configure_logging(settings.log_level)
    print("\n=== LangGraph agent ===")
    print(f"INPUT: {arguments.prompt}")
    try:
        async with build_runtime(settings) as runtime:
            output = await runtime.invoke(arguments.prompt, f"sample-{uuid4().hex}")
    except Exception as exc:
        print(f"Agent request failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"OUTPUT: {output}")
    return 0


def main() -> None:
    """Run the demonstration and return its status to the batch file."""
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
