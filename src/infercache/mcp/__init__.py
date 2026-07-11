"""MCP (Model Context Protocol) server exposing InferCache to AI clients."""

from infercache.mcp.server import McpServer, run_stdio_server

__all__ = ["McpServer", "run_stdio_server"]
