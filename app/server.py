"""A small MCP server that demonstrates tools over Streamable HTTP."""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime
from typing import Any, Literal, TypedDict, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

Number = int | float
Operation = Literal["add", "subtract", "multiply", "divide"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_TIMEZONE = "Asia/Kolkata"
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
SWAGGER_UI_VERSION = "5.33.0"

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


def _error(message: str, status_code: int = 400) -> JSONResponse:
    """Return the stable error shape used by the documented REST adapters."""
    return JSONResponse({"error": message}, status_code=status_code)


async def _json_object(request: Request) -> dict[str, Any] | JSONResponse:
    """Read one JSON object or return a client-safe validation response."""
    try:
        payload = await request.json()
    except (ValueError, UnicodeDecodeError):
        return _error("Request body must be valid JSON")
    if not isinstance(payload, dict):
        return _error("Request body must be a JSON object")
    return payload


@mcp.custom_route("/api/tools/hello", methods=["POST"])
async def hello_api(request: Request) -> Response:
    """HTTP adapter for the ``hello`` MCP tool."""
    payload = await _json_object(request)
    if isinstance(payload, JSONResponse):
        return payload
    name = payload.get("name")
    if not isinstance(name, str):
        return _error("name must be a string")
    try:
        return JSONResponse({"result": hello(name)})
    except ToolError as exc:
        return _error(str(exc))


@mcp.custom_route("/api/tools/get-current-time", methods=["GET"])
async def get_current_time_api(_request: Request) -> Response:
    """HTTP adapter for the ``get_current_time`` MCP tool."""
    try:
        return JSONResponse(get_current_time())
    except ToolError as exc:
        return _error(str(exc), status_code=500)


@mcp.custom_route("/api/tools/calculate", methods=["POST"])
async def calculate_api(request: Request) -> Response:
    """HTTP adapter for the ``calculate`` MCP tool."""
    payload = await _json_object(request)
    if isinstance(payload, JSONResponse):
        return payload

    a = payload.get("a")
    b = payload.get("b")
    operation = payload.get("operation")
    if isinstance(a, bool) or not isinstance(a, (int, float)):
        return _error("a must be a number")
    if isinstance(b, bool) or not isinstance(b, (int, float)):
        return _error("b must be a number")
    if operation not in {"add", "subtract", "multiply", "divide"}:
        return _error("operation must be add, subtract, multiply, or divide")

    try:
        result = calculate(a, b, cast(Operation, operation))
    except ToolError as exc:
        return _error(str(exc))
    return JSONResponse(result)


OPENAPI_SCHEMA: dict[str, Any] = {
    "openapi": "3.1.0",
    "info": {
        "title": "Simple MCP Server HTTP API",
        "version": "1.0.0",
        "description": (
            "Swagger documentation for health checks and REST adapters over the "
            "same functions exposed as MCP tools. MCP clients should use /mcp."
        ),
    },
    "servers": [{"url": "/"}],
    "tags": [
        {"name": "Operations", "description": "Server health and metadata"},
        {"name": "Tool adapters", "description": "HTTP adapters for MCP tools"},
        {"name": "MCP", "description": "Native MCP protocol transport"},
    ],
    "paths": {
        "/health": {
            "get": {
                "tags": ["Operations"],
                "summary": "Check server health",
                "operationId": "health",
                "responses": {
                    "200": {
                        "description": "Server is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"}
                            }
                        },
                    }
                },
            }
        },
        "/api/tools/hello": {
            "post": {
                "tags": ["Tool adapters"],
                "summary": "Return a greeting",
                "operationId": "hello",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/HelloRequest"},
                            "example": {"name": "Anupriya"},
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Greeting",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HelloResponse"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                },
            }
        },
        "/api/tools/get-current-time": {
            "get": {
                "tags": ["Tool adapters"],
                "summary": "Return the configured server time",
                "operationId": "getCurrentTime",
                "responses": {
                    "200": {
                        "description": "Current server time",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TimeResponse"}
                            }
                        },
                    }
                },
            }
        },
        "/api/tools/calculate": {
            "post": {
                "tags": ["Tool adapters"],
                "summary": "Perform a calculation",
                "operationId": "calculate",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CalculationRequest"},
                            "example": {"a": 25, "b": 12, "operation": "multiply"},
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Calculation result",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CalculationResponse"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                },
            }
        },
        "/mcp": {
            "post": {
                "tags": ["MCP"],
                "summary": "Exchange an MCP Streamable HTTP message",
                "description": (
                    "Native MCP clients manage initialization, request IDs, and "
                    "content negotiation. Prefer an MCP SDK instead of Swagger "
                    "for this protocol endpoint."
                ),
                "operationId": "mcpMessage",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "additionalProperties": True}
                        }
                    },
                },
                "responses": {
                    "200": {"description": "MCP JSON response"},
                    "202": {"description": "MCP notification accepted"},
                },
            }
        },
    },
    "components": {
        "schemas": {
            "HealthResponse": {
                "type": "object",
                "required": ["status"],
                "properties": {"status": {"type": "string", "example": "ok"}},
            },
            "HelloRequest": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name"],
                "properties": {"name": {"type": "string", "minLength": 1}},
            },
            "HelloResponse": {
                "type": "object",
                "required": ["result"],
                "properties": {"result": {"type": "string"}},
            },
            "TimeResponse": {
                "type": "object",
                "required": ["datetime", "timezone"],
                "properties": {
                    "datetime": {"type": "string", "format": "date-time"},
                    "timezone": {"type": "string"},
                },
            },
            "CalculationRequest": {
                "type": "object",
                "additionalProperties": False,
                "required": ["a", "b", "operation"],
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                    },
                },
            },
            "CalculationResponse": {
                "allOf": [
                    {"$ref": "#/components/schemas/CalculationRequest"},
                    {
                        "type": "object",
                        "required": ["result"],
                        "properties": {"result": {"type": "number"}},
                    },
                ]
            },
            "ErrorResponse": {
                "type": "object",
                "required": ["error"],
                "properties": {"error": {"type": "string"}},
            },
        },
        "responses": {
            "BadRequest": {
                "description": "Invalid request",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                },
            }
        },
    },
}


@mcp.custom_route("/openapi.json", methods=["GET"])
async def openapi_schema(_request: Request) -> Response:
    """Return the OpenAPI document consumed by Swagger UI."""
    return JSONResponse(OPENAPI_SCHEMA)


@mcp.custom_route("/docs", methods=["GET"])
async def swagger_ui(_request: Request) -> Response:
    """Serve Swagger UI with pinned assets and a restrictive CSP."""
    nonce = secrets.token_urlsafe(18)
    asset_root = f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Simple MCP Server API</title>
  <link rel="stylesheet" href="{asset_root}/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="{asset_root}/swagger-ui-bundle.js"></script>
  <script nonce="{nonce}">
    SwaggerUIBundle({{
      url: "/openapi.json",
      dom_id: "#swagger-ui",
      deepLinking: true,
      displayRequestDuration: true,
      persistAuthorization: false
    }});
  </script>
</body>
</html>"""
    csp = (
        "default-src 'none'; "
        f"script-src https://cdn.jsdelivr.net 'nonce-{nonce}'; "
        "style-src https://cdn.jsdelivr.net 'unsafe-inline'; "
        "img-src data: https://validator.swagger.io; "
        "connect-src 'self'"
    )
    return HTMLResponse(html, headers={"Content-Security-Policy": csp})


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
    logger.info("Swagger UI: http://%s:%s/docs", host, port)

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
