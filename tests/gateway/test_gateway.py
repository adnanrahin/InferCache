"""Gateway integration tests: real HTTP through a mock upstream."""

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from infercache.config import CacheConfig
from infercache.gateway import GatewayConfig, create_gateway

UPSTREAM_CALLS = {"count": 0}


class MockUpstreamHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        UPSTREAM_CALLS["count"] += 1
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        payload = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "model": "mock-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Mock upstream answer"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def gateway_url():
    UPSTREAM_CALLS["count"] = 0

    upstream = HTTPServer(("127.0.0.1", 0), MockUpstreamHandler)
    upstream_port = upstream.server_address[1]
    threading.Thread(target=upstream.serve_forever, daemon=True).start()

    gw_config = GatewayConfig(
        host="127.0.0.1",
        port=0,
        openai_upstream=f"http://127.0.0.1:{upstream_port}",
        cache=CacheConfig(backend="memory"),
    )
    gateway = create_gateway(gw_config)
    gw_port = gateway.server_address[1]
    threading.Thread(target=gateway.serve_forever, daemon=True).start()

    yield f"http://127.0.0.1:{gw_port}"

    gateway.shutdown()
    upstream.shutdown()


def _post_chat(url: str, prompt: str) -> dict:
    body = json.dumps(
        {
            "model": "mock-model",
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()
    req = urllib.request.Request(
        f"{url}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def test_gateway_miss_then_hit(gateway_url):
    r1 = _post_chat(gateway_url, "What is the gateway test?")
    assert r1["choices"][0]["message"]["content"] == "Mock upstream answer"
    assert r1["infercache"]["cache_hit"] is False
    assert UPSTREAM_CALLS["count"] == 1

    r2 = _post_chat(gateway_url, "What is the gateway test?")
    assert r2["choices"][0]["message"]["content"] == "Mock upstream answer"
    assert r2["infercache"]["cache_hit"] is True
    assert UPSTREAM_CALLS["count"] == 1  # upstream NOT called again


def test_gateway_stats_endpoint(gateway_url):
    _post_chat(gateway_url, "stats probe")
    with urllib.request.urlopen(f"{gateway_url}/stats", timeout=10) as resp:
        stats = json.loads(resp.read().decode())
    assert "hit_rate" in stats
    assert stats["total_requests"] >= 1


def test_gateway_health(gateway_url):
    with urllib.request.urlopen(f"{gateway_url}/health", timeout=10) as resp:
        health = json.loads(resp.read().decode())
    assert health["status"] == "ok"
