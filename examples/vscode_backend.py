"""
Example: VS Code extension backend or any chat service middleware.

Run: python examples/vscode_backend.py
Then POST to http://127.0.0.1:8765/chat with {"prompt": "..."}
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from infercache import CacheConfig, InferCache

cache = InferCache(CacheConfig(similarity_threshold=0.82, ttl_seconds=7200))


def mock_llm(prompt: str) -> str:
  """Replace with your real LLM call (OpenAI, Ollama, etc.)."""
  return f"[LLM] Processed: {prompt[:80]}..."


class ChatHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/chat":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        prompt = body.get("prompt", "")
        messages = body.get("messages")

        if messages:
            result = cache.get_or_call_messages(messages, lambda m: mock_llm(str(m)))
        else:
            result = cache.get_or_call(prompt, mock_llm)

        payload = {
            "response": result["response"],
            "cache_hit": result.get("cache_hit", False),
            "stats": cache.stats(),
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/stats":
            data = json.dumps(cache.stats(), indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def log_message(self, format: str, *args) -> None:
        pass


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8765), ChatHandler)
    print("InferCache chat proxy on http://127.0.0.1:8765/chat")
    print("GET /stats for metrics")
    server.serve_forever()
