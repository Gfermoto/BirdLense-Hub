"""Tests for MCP server bootstrap and transport selection."""

from __future__ import annotations

import sys
import types


def test_main_uses_streamable_http_transport(monkeypatch):
    sys.modules["httpx"] = types.SimpleNamespace(AsyncClient=lambda *a, **k: object())
    sys.modules["yaml"] = types.SimpleNamespace(safe_load=lambda _: {"paths": {}})
    sys.modules["fastmcp"] = types.SimpleNamespace(FastMCP=object)
    sys.modules["fastmcp.server"] = types.SimpleNamespace()
    sys.modules["fastmcp.server.providers"] = types.SimpleNamespace()
    sys.modules["fastmcp.server.providers.openapi"] = types.SimpleNamespace(
        RouteMap=lambda **kwargs: kwargs,
        MCPType=types.SimpleNamespace(TOOL="tool"),
    )
    import birdlense_mcp as mod

    calls = {}

    class DummyMcp:
        def run(self, **kwargs):
            calls["kwargs"] = kwargs

    monkeypatch.setattr(mod, "create_mcp_server", lambda: DummyMcp())
    monkeypatch.setattr(sys, "argv", ["birdlense_mcp.py", "--transport", "http"])

    mod.main()

    assert calls["kwargs"]["transport"] == "streamable-http"
    assert calls["kwargs"]["host"] == "127.0.0.1"
    assert calls["kwargs"]["port"] == 8001
