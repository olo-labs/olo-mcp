"""A small MCP server that demonstrates tools over Streamable HTTP."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Literal, TypedDict, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

Number = int | float
Operation = Literal["add", "subtract", "multiply", "divide"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_TIMEZONE = "Asia/Kolkata"
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

logger = logging.getLogger(__name__)


class TimeResult(TypedDict):
    """Structured result returned by ``get_current_time``."""

    datetime: str
    timezone: str


class CalculationResult(TypedDict):
    """Structured result returned by ``calculate``."""

    a: Number
    b: Number
    operation: Operation
    result: Number


def _log_level() -> LogLevel:
    """Read and validate the configured console log level."""
    value = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    if value not in VALID_LOG_LEVELS:
        choices = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ValueError(f"LOG_LEVEL must be one of: {choices}")
    return cast(LogLevel, value)


mcp = MCPServer(
    "simple-mcp-server",
    instructions="A learning server with greeting, time, and calculator tools.",
    version="1.0.0",
    log_level=_log_level(),
)


@mcp.tool()
def hello(name: str) -> str:
    """Return a friendly greeting for the supplied name."""
    logger.info("Tool called: hello")
    clean_name = name.strip()
    if not clean_name:
        logger.warning("Tool hello rejected an empty name")
        raise ToolError("name must not be empty")
    return f"Hello {clean_name}!"


@mcp.tool()
def get_current_time() -> TimeResult:
    """Return the server's current date and time in its configured timezone."""
    logger.info("Tool called: get_current_time")
    timezone_name = os.getenv("TZ", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE

    try:
        current_time = datetime.now(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError as exc:
        logger.error("Configured timezone is unavailable: %s", timezone_name)
        raise ToolError(f"Configured timezone {timezone_name!r} is unavailable") from exc

    return {
        "datetime": current_time.isoformat(timespec="seconds"),
        "timezone": timezone_name,
    }


@mcp.tool()
def calculate(a: Number, b: Number, operation: Operation) -> CalculationResult:
    """Perform add, subtract, multiply, or divide on two numbers."""
    logger.info("Tool called: calculate (%s)", operation)

    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            logger.warning("Tool calculate rejected division by zero")
            raise ToolError("Cannot divide by zero")
        result = a / b
    else:
        # This also protects direct Python callers. MCP clients are rejected by
        # the generated Literal-based tool schema before reaching this branch.
        logger.warning("Tool calculate rejected operation: %s", operation)
        raise ToolError(
            "Unsupported operation. Use add, subtract, multiply, or divide"
        )

    return {"a": a, "b": b, "operation": operation, "result": result}


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> Response:
    """Return a lightweight liveness response outside the MCP protocol."""
    return JSONResponse({"status": "ok"})


def _port() -> int:
    """Read and validate the HTTP listening port."""
    raw_port = os.getenv("MCP_PORT", str(DEFAULT_PORT)).strip()
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("MCP_PORT must be an integer") from exc

    if not 1 <= port <= 65535:
        raise ValueError("MCP_PORT must be between 1 and 65535")
    return port


def main() -> None:
    """Start the MCP server using the Streamable HTTP transport."""
    log_level = _log_level()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )

    host = os.getenv("MCP_HOST", DEFAULT_HOST).strip()
    if not host:
        raise ValueError("MCP_HOST must not be empty")
    port = _port()

    logger.info("Starting simple-mcp-server")
    logger.info("Configured host: %s", host)
    logger.info("Configured port: %s", port)
    logger.info("MCP endpoint: http://%s:%s/mcp", host, port)

    try:
        mcp.run(
            transport="streamable-http",
            host=host,
            port=port,
            streamable_http_path="/mcp",
            json_response=True,
            stateless_http=True,
        )
    except KeyboardInterrupt:
        logger.info("MCP server stopped")
    except Exception:
        logger.exception("MCP server stopped because of a major error")
        raise


if __name__ == "__main__":
    main()
