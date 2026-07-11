"""
InferCache MCP server — stdio transport, JSON-RPC 2.0, zero dependencies.

Exposes the cache as MCP tools so any MCP client (Cursor, Claude Desktop,
Claude Code, Windsurf, ...) can check the cache before spending tokens and
store answers afterwards.

Protocol: newline-delimited JSON-RPC over stdin/stdout, per the MCP spec
(https://modelcontextprotocol.io). Implemented directly so no SDK is required.

Run:  infercache mcp   (or: python -m infercache.mcp)
"""

from __future__ import annotations

import json
import sys
from typing import Any

from infercache import __version__
from infercache.config import CacheConfig
from infercache.core import InferCache

PROTOCOL_VERSION = "2024-11-05"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "cache_lookup",
        "description": (
            "Look up a prompt in the local InferCache before calling an LLM. "
            "Returns the cached response if an exact or semantically similar "
            "prompt was answered before. Use this FIRST to avoid spending tokens."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The prompt to look up"},
                "model": {"type": "string", "description": "Model name scoping the cache", "default": ""},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "cache_store",
        "description": (
            "Store a prompt/response pair in the local InferCache after an LLM "
            "call, so future identical or similar prompts are answered for free."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "response": {"type": "string"},
                "model": {"type": "string", "default": ""},
            },
            "required": ["prompt", "response"],
        },
    },
    {
        "name": "cache_stats",
        "description": "Get cache statistics: hit rate, tokens saved, estimated cost reduction.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cache_feedback",
        "description": (
            "Report whether a cached answer was correct for a prompt. Tunes the "
            "adaptive similarity thresholds (reduces future false hits)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "was_correct": {"type": "boolean"},
            },
            "required": ["prompt", "was_correct"],
        },
    },
    {
        "name": "cache_clear",
        "description": "Delete all entries from the local cache.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class McpServer:
    """Transport-agnostic MCP message handler (testable without stdio)."""

    def __init__(self, cache: InferCache | None = None) -> None:
        # SQLite default so the cache persists across editor/agent restarts
        self.cache = cache or InferCache(config=CacheConfig(backend="sqlite"))

    # ---------- JSON-RPC dispatch ----------

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC message. Returns a response dict, or None for notifications."""
        method = message.get("method", "")
        msg_id = message.get("id")

        if method.startswith("notifications/"):
            return None

        try:
            if method == "initialize":
                result = self._initialize()
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                result = self._tools_call(message.get("params", {}))
            else:
                return self._error(msg_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            return self._error(msg_id, -32603, f"Internal error: {exc}")

        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    def _initialize(self) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "infercache", "version": __version__},
        }

    # ---------- tools ----------

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name", "")
        args = params.get("arguments", {}) or {}

        if name == "cache_lookup":
            payload = self._tool_lookup(args)
        elif name == "cache_store":
            payload = self._tool_store(args)
        elif name == "cache_stats":
            payload = self.cache.stats()
        elif name == "cache_feedback":
            payload = self._tool_feedback(args)
        elif name == "cache_clear":
            self.cache.clear()
            payload = {"cleared": True}
        else:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }

        return {
            "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
            "isError": False,
        }

    def _tool_lookup(self, args: dict[str, Any]) -> dict[str, Any]:
        result = self.cache.lookup(args["prompt"], model=args.get("model", ""))
        return {
            "cache_hit": result.get("cache_hit", False),
            "cache_type": result.get("cache_type"),
            "response": result.get("response"),
        }

    def _tool_store(self, args: dict[str, Any]) -> dict[str, Any]:
        self.cache.store(args["prompt"], args["response"], model=args.get("model", ""))
        return {"stored": True}

    def _tool_feedback(self, args: dict[str, Any]) -> dict[str, Any]:
        self.cache.feedback(args["prompt"], bool(args["was_correct"]))
        return {"recorded": True}


def run_stdio_server(cache: InferCache | None = None) -> None:
    """Serve MCP over stdin/stdout (newline-delimited JSON-RPC)."""
    server = McpServer(cache=cache)
    # stderr is safe for logs; stdout is reserved for protocol messages
    print(f"infercache MCP server v{__version__} ready (stdio)", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle_message(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
