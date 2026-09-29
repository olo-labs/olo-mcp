"""Deterministic guardrails around the model-driven agent loop."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool


class GuardrailViolation(ValueError):
    """Raised when deterministic input or tool policy rejects a request."""


_SECRET_EXTRACTION_PATTERNS = (
    re.compile(
        r"\b(?:show|print|reveal|return|exfiltrate)\b.{0,80}"
        r"\b(?:api[- ]?key|secret|environment variables?|system prompt)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bignore\b.{0,40}\b(?:previous|prior|system)\b.{0,40}"
        r"\b(?:instruction|message|prompt)s?\b",
        re.IGNORECASE | re.DOTALL,
    ),
)


def validate_user_input(text: str, *, max_chars: int, strict: bool) -> str:
    """Reject malformed, oversized, or obvious instruction-extraction input."""
    clean_text = text.strip()
    if not clean_text:
        raise GuardrailViolation("Input must not be empty")
    if len(clean_text) > max_chars:
        raise GuardrailViolation(f"Input exceeds the {max_chars}-character limit")
    if "\x00" in clean_text:
        raise GuardrailViolation("Input contains a null byte")
    if strict and any(pattern.search(clean_text) for pattern in _SECRET_EXTRACTION_PATTERNS):
        raise GuardrailViolation(
            "Input was blocked by the prompt-injection and secret-extraction guardrail"
        )
    return clean_text


def select_allowed_tools(
    discovered_tools: Iterable[BaseTool], allowed_names: Iterable[str]
) -> list[BaseTool]:
    """Return only explicitly allow-listed MCP tools and require all to exist."""
    allowed = set(allowed_names)
    discovered = {tool.name: tool for tool in discovered_tools}
    missing = allowed - discovered.keys()
    if missing:
        missing_names = ", ".join(sorted(missing))
        raise GuardrailViolation(f"MCP server is missing allowed tools: {missing_names}")
    return [discovered[name] for name in allowed_names]


def final_message_text(result: dict[str, Any]) -> str:
    """Extract displayable text from the agent's final message without traces."""
    messages = result.get("messages", [])
    if not messages:
        return "The agent completed without a text response."

    message = messages[-1]
    content = message.content if isinstance(message, BaseMessage) else message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
        if text_parts:
            return "\n".join(text_parts)
    return "The agent completed without a text response."
