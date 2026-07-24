"""
InferCache Gateway — caching reverse proxy (OpenAI + Anthropic wire formats).

On cache miss with stream=true, upstream SSE is piped through live while the
full answer is collected and stored for later hits.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from infercache.config import CacheConfig
from infercache.core import InferCache
from infercache.optimization.tokens import estimate_tokens

FORWARD_HEADERS = (
    "authorization",
    "x-api-key",
    "anthropic-version",
    "anthropic-beta",
    "openai-organization",
)


@dataclass
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 8899
    openai_upstream: str = "https://api.openai.com"
    anthropic_upstream: str = "https://api.anthropic.com"
    upstream_timeout: float = 300.0
    cache: CacheConfig = field(default_factory=lambda: CacheConfig(backend="sqlite"))


class _GatewayState:
    def __init__(self, config: GatewayConfig) -> None:
        self.config = config
        self.cache = InferCache(config=config.cache)
        self.lock = threading.RLock()
        self.started_at = time.time()


def _messages_cache_repr(body: dict[str, Any]) -> str:
    key_fields = {
        "model": body.get("model", ""),
        "messages": body.get("messages", []),
        "system": body.get("system"),
        "tools": body.get("tools"),
    }
    return json.dumps(key_fields, sort_keys=True)


def _extract_openai_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    return message.get("content") or ""


def _extract_anthropic_text(response: dict[str, Any]) -> str:
    blocks = response.get("content", [])
    return "".join(b.get("text", "") for b in blocks if isinstance(b, dict))


def _openai_response(model: str, text: str, cached: bool) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "infercache": {"cache_hit": cached},
    }


def _anthropic_response(model: str, text: str, cached: bool) -> dict[str, Any]:
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "infercache": {"cache_hit": cached},
    }


def _sse_chunks_openai(model: str, text: str, chunk_size: int = 80):
    msg_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    for i in range(0, len(text), chunk_size):
        piece = text[i : i + chunk_size]
        chunk = {
            "id": msg_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk)}\n\n".encode()
    final = {
        "id": msg_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final)}\n\n".encode()
    yield b"data: [DONE]\n\n"


def _parse_openai_sse_delta(line: str) -> str:
    if not line.startswith("data: "):
        return ""
    payload = line[6:].strip()
    if payload == "[DONE]":
        return ""
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    choices = obj.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    return delta.get("content") or ""


def make_handler(state: _GatewayState):
    class GatewayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            pass

        def _read_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_sse(self, chunks: Iterator[bytes]) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            for chunk in chunks:
                self.wfile.write(chunk)
                self.wfile.flush()

        def _forward_headers(self) -> dict[str, str]:
            headers = {"Content-Type": "application/json"}
            for name in FORWARD_HEADERS:
                value = self.headers.get(name)
                if value:
                    headers[name] = value
            return headers

        def _call_upstream(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
            body = dict(body)
            body["stream"] = False
            req = Request(
                url,
                data=json.dumps(body).encode(),
                headers=self._forward_headers(),
                method="POST",
            )
            try:
                with urlopen(req, timeout=state.config.upstream_timeout) as resp:
                    return json.loads(resp.read().decode())
            except HTTPError as exc:
                detail = exc.read().decode(errors="replace")
                raise RuntimeError(f"Upstream {exc.code}: {detail[:500]}") from exc
            except URLError as exc:
                raise RuntimeError(f"Cannot reach upstream {url}: {exc.reason}") from exc

        def _stream_upstream_openai(
            self, url: str, body: dict[str, Any]
        ) -> tuple[Iterator[bytes], list[str]]:
            """Pipe upstream SSE to client; return collected text pieces."""
            body = dict(body)
            body["stream"] = True
            req = Request(
                url,
                data=json.dumps(body).encode(),
                headers=self._forward_headers(),
                method="POST",
            )
            collected: list[str] = []

            def gen() -> Iterator[bytes]:
                try:
                    with urlopen(req, timeout=state.config.upstream_timeout) as resp:
                        while True:
                            raw = resp.readline()
                            if not raw:
                                break
                            yield raw
                            try:
                                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                            except Exception:
                                continue
                            piece = _parse_openai_sse_delta(line)
                            if piece:
                                collected.append(piece)
                except HTTPError as exc:
                    detail = exc.read().decode(errors="replace")
                    err = {"error": f"Upstream {exc.code}: {detail[:300]}"}
                    yield f"data: {json.dumps(err)}\n\n".encode()
                    yield b"data: [DONE]\n\n"

            return gen(), collected

        def _user_scope(self) -> str:
            return self.headers.get("X-InferCache-User", "")

        def do_GET(self) -> None:
            if self.path in ("/health", "/"):
                self._send_json(
                    {
                        "status": "ok",
                        "uptime_s": round(time.time() - state.started_at, 1),
                        "openai_upstream": state.config.openai_upstream,
                        "anthropic_upstream": state.config.anthropic_upstream,
                        "embedding_model": state.cache.config.embedding_model,
                    }
                )
            elif self.path == "/stats":
                with state.lock:
                    self._send_json(state.cache.stats())
            else:
                self._send_json({"error": "not found"}, status=404)

        def do_POST(self) -> None:
            try:
                if self.path in ("/v1/chat/completions", "/chat/completions"):
                    self._handle_chat_completions()
                elif self.path == "/v1/messages":
                    self._handle_anthropic_messages()
                elif self.path == "/cache/clear":
                    with state.lock:
                        state.cache.clear()
                    self._send_json({"cleared": True})
                else:
                    self._send_json({"error": f"unsupported path {self.path}"}, status=404)
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=502)
            except Exception as exc:
                self._send_json({"error": f"gateway error: {exc}"}, status=500)

        def _handle_chat_completions(self) -> None:
            body = self._read_body()
            model = body.get("model", "")
            stream = bool(body.get("stream"))
            cache_repr = _messages_cache_repr(body)
            user = self._user_scope()

            with state.lock:
                cached = state.cache.lookup(cache_repr, model=model, optimize=False, user=user)

            if cached.get("cache_hit"):
                text = cached["response"]
                if stream:
                    self._send_sse(_sse_chunks_openai(model, text))
                else:
                    self._send_json(_openai_response(model, text, cached=True))
                return

            upstream_url = f"{state.config.openai_upstream.rstrip('/')}/v1/chat/completions"

            if stream:
                gen, collected = self._stream_upstream_openai(upstream_url, body)
                self._send_sse(gen)
                text = "".join(collected)
                with state.lock:
                    state.cache.metrics.record_miss(
                        estimate_tokens(cache_repr) + estimate_tokens(text)
                    )
                    if text:
                        state.cache.store(cache_repr, text, model=model, user=user)
                return

            upstream = self._call_upstream(upstream_url, body)
            text = _extract_openai_text(upstream)
            with state.lock:
                state.cache.metrics.record_miss(
                    estimate_tokens(cache_repr) + estimate_tokens(text)
                )
                if text:
                    state.cache.store(cache_repr, text, model=model, user=user)
            upstream.setdefault("infercache", {})["cache_hit"] = False
            self._send_json(upstream)

        def _handle_anthropic_messages(self) -> None:
            body = self._read_body()
            model = body.get("model", "")
            cache_repr = _messages_cache_repr(body)
            user = self._user_scope()

            with state.lock:
                cached = state.cache.lookup(cache_repr, model=model, optimize=False, user=user)

            if cached.get("cache_hit"):
                self._send_json(_anthropic_response(model, cached["response"], cached=True))
                return

            upstream_url = f"{state.config.anthropic_upstream.rstrip('/')}/v1/messages"
            upstream = self._call_upstream(upstream_url, body)
            text = _extract_anthropic_text(upstream)
            with state.lock:
                state.cache.metrics.record_miss(
                    estimate_tokens(cache_repr) + estimate_tokens(text)
                )
                if text:
                    state.cache.store(cache_repr, text, model=model, user=user)
            upstream.setdefault("infercache", {})["cache_hit"] = False
            self._send_json(upstream)

    return GatewayHandler


def create_gateway(config: GatewayConfig | None = None) -> ThreadingHTTPServer:
    config = config or GatewayConfig()
    state = _GatewayState(config)
    server = ThreadingHTTPServer((config.host, config.port), make_handler(state))
    server.infercache_state = state  # type: ignore[attr-defined]
    return server


def run_gateway(config: GatewayConfig | None = None) -> None:
    config = config or GatewayConfig()
    server = create_gateway(config)
    print(f"InferCache Gateway listening on http://{config.host}:{config.port}")
    print(f"  OpenAI-compatible : POST /v1/chat/completions -> {config.openai_upstream}")
    print(f"  Anthropic         : POST /v1/messages         -> {config.anthropic_upstream}")
    print(f"  Stats             : GET  /stats")
    print(f"  Storage           : {config.cache.backend}")
    print(f"  Embeddings        : {config.cache.embedding_model}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
