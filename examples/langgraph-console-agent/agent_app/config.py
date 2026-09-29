"""Validated environment configuration for the console agent."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Raised when agent configuration is missing or unsafe."""


def _integer(
    environment: Mapping[str, str], name: str, default: int, minimum: int
) -> int:
    raw_value = environment.get(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return value


def _float(
    environment: Mapping[str, str], name: str, default: float, minimum: float
) -> float:
    raw_value = environment.get(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return value


def _boolean(environment: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = environment.get(name, str(default)).strip().lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false")


@dataclass(frozen=True, slots=True)
class Settings:
    """All runtime settings, validated once during startup."""

    mcp_url: str
    openai_model: str
    fallback_model: str
    checkpoint_db: Path
    allowed_tools: tuple[str, ...]
    max_input_chars: int
    model_call_limit: int
    tool_call_limit: int
    agent_timeout_seconds: float
    mcp_timeout_seconds: float
    mcp_connect_attempts: int
    require_tool_approval: bool
    strict_prompt_guard: bool
    log_level: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from environment variables without retaining secrets."""
        environment = os.environ if environ is None else environ

        if not environment.get("OPENAI_API_KEY", "").strip():
            raise ConfigurationError("OPENAI_API_KEY is required")

        mcp_url = environment.get("MCP_URL", "http://127.0.0.1:8000/mcp").strip()
        parsed_url = urlsplit(mcp_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ConfigurationError("MCP_URL must be an absolute HTTP(S) URL")
        if not parsed_url.path.rstrip("/").endswith("/mcp"):
            raise ConfigurationError("MCP_URL must point to the /mcp endpoint")

        allowed_tools = tuple(
            name.strip()
            for name in environment.get(
                "ALLOWED_MCP_TOOLS", "hello,get_current_time,calculate"
            ).split(",")
            if name.strip()
        )
        if not allowed_tools:
            raise ConfigurationError("ALLOWED_MCP_TOOLS must contain at least one tool")
        if len(allowed_tools) != len(set(allowed_tools)):
            raise ConfigurationError("ALLOWED_MCP_TOOLS must not contain duplicates")

        openai_model = environment.get("OPENAI_MODEL", "gpt-5-mini").strip()
        if not openai_model:
            raise ConfigurationError("OPENAI_MODEL must not be empty")

        log_level = environment.get("AGENT_LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("AGENT_LOG_LEVEL is invalid")

        return cls(
            mcp_url=mcp_url,
            openai_model=openai_model,
            fallback_model=environment.get(
                "OPENAI_FALLBACK_MODEL", "gpt-5-nano"
            ).strip(),
            checkpoint_db=Path(
                environment.get(
                    "AGENT_CHECKPOINT_DB", ".agent-state/checkpoints.sqlite"
                )
            ),
            allowed_tools=allowed_tools,
            max_input_chars=_integer(environment, "MAX_INPUT_CHARS", 4000, 1),
            model_call_limit=_integer(environment, "MODEL_CALL_LIMIT", 6, 1),
            tool_call_limit=_integer(environment, "TOOL_CALL_LIMIT", 8, 1),
            agent_timeout_seconds=_float(
                environment, "AGENT_TIMEOUT_SECONDS", 120.0, 1.0
            ),
            mcp_timeout_seconds=_float(
                environment, "MCP_TIMEOUT_SECONDS", 15.0, 1.0
            ),
            mcp_connect_attempts=_integer(
                environment, "MCP_CONNECT_ATTEMPTS", 3, 1
            ),
            require_tool_approval=_boolean(
                environment, "REQUIRE_TOOL_APPROVAL", False
            ),
            strict_prompt_guard=_boolean(
                environment, "STRICT_PROMPT_GUARD", True
            ),
            log_level=log_level,
        )
