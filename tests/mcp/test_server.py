"""MCP server tests (direct message handling, no stdio needed)."""

import json

from infercache import CacheConfig, InferCache
from infercache.mcp import McpServer


def _make_server() -> McpServer:
    return McpServer(cache=InferCache(config=CacheConfig(backend="memory")))


def _call_tool(server: McpServer, name: str, arguments: dict) -> dict:
    response = server.handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    payload = response["result"]["content"][0]["text"]
    return json.loads(payload)


def test_initialize():
    server = _make_server()
    resp = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp["result"]["serverInfo"]["name"] == "infercache"
    assert "protocolVersion" in resp["result"]


def test_tools_list():
    server = _make_server()
    resp = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in resp["result"]["tools"]]
    assert "cache_lookup" in names
    assert "cache_store" in names
    assert "cache_stats" in names


def test_store_then_lookup_roundtrip():
    server = _make_server()
    stored = _call_tool(server, "cache_store", {"prompt": "What is MCP?", "response": "A protocol."})
    assert stored["stored"] is True

    hit = _call_tool(server, "cache_lookup", {"prompt": "What is MCP?"})
    assert hit["cache_hit"] is True
    assert hit["response"] == "A protocol."


def test_lookup_miss():
    server = _make_server()
    miss = _call_tool(server, "cache_lookup", {"prompt": "never stored"})
    assert miss["cache_hit"] is False


def test_notifications_return_none():
    server = _make_server()
    assert server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_method_errors():
    server = _make_server()
    resp = server.handle_message({"jsonrpc": "2.0", "id": 9, "method": "bogus/method"})
    assert "error" in resp
