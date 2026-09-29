"""Tests for the transparent MCP demonstration helpers."""

from agent_app.demo import DEMO_CALLS, _json


def test_demo_covers_every_expected_tool() -> None:
    assert {name for name, _ in DEMO_CALLS} == {
        "hello",
        "get_current_time",
        "calculate",
    }


def test_json_formatter_preserves_payload_fields() -> None:
    rendered = _json({"method": "tools/call", "params": {"name": "hello"}})
    assert '"method": "tools/call"' in rendered
    assert '"name": "hello"' in rendered
