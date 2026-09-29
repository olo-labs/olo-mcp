"""Tests for the transparent MCP demonstration helpers."""

from io import StringIO
from contextlib import redirect_stdout

from agent_app.demo import DEMO_CALLS, REST_DEMO_CALLS, _json, _show_exchange


def test_demo_covers_every_expected_tool() -> None:
    assert {name for name, _ in DEMO_CALLS} == {
        "hello",
        "get_current_time",
        "calculate",
    }
    assert {(method, path) for method, path, _ in REST_DEMO_CALLS} == {
        ("POST", "/api/tools/hello"),
        ("GET", "/api/tools/get-current-time"),
        ("POST", "/api/tools/calculate"),
    }


def test_json_formatter_preserves_payload_fields() -> None:
    rendered = _json({"method": "tools/call", "params": {"name": "hello"}})
    assert '"method": "tools/call"' in rendered
    assert '"name": "hello"' in rendered


def test_exchange_log_includes_http_method_url_payload_and_response() -> None:
    output = StringIO()
    with redirect_stdout(output):
        _show_exchange(
            "MCP tool: hello",
            http_method="POST",
            url="http://localhost:18001/mcp",
            payload={"method": "tools/call"},
            response={"result": "Hello Anupriya!"},
        )

    rendered = output.getvalue()
    assert "HTTP METHOD: POST" in rendered
    assert "URL: http://localhost:18001/mcp" in rendered
    assert "PAYLOAD:" in rendered
    assert "RESPONSE:" in rendered
