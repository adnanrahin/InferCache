"""llama.cpp (llama-server) adapter — OpenAI-compatible local HTTP API."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from infercache.config import CacheConfig
from infercache.core import InferCache
from infercache.integrations.adapters.base import BaseAdapter

DEFAULT_LLAMACPP_URL = "http://127.0.0.1:8080"


def resolve_llamacpp_base_url(base_url: str | None = None) -> str:
    """
    Resolve llama-server URL.

    Priority: explicit base_url → LLAMACPP_HOST / LLAMA_CPP_BASE_URL env → localhost:8080.
    Host may be ``host:port`` or a full URL.
    """
    if base_url:
        return _normalize_url(base_url)
    env = os.environ.get("LLAMACPP_HOST") or os.environ.get("LLAMA_CPP_BASE_URL")
    if env:
        return _normalize_url(env)
    return DEFAULT_LLAMACPP_URL


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


class LlamaCppAdapter(BaseAdapter):
    """
    Wrap llama.cpp ``llama-server`` with InferCache.

    Talks to the OpenAI-compatible endpoints (``/v1/chat/completions``,
    ``/v1/completions``, ``/v1/models``). No extra pip packages required.

    Start a server first::

        llama-server -m model.gguf --port 8080

    Then::

        adapter = LlamaCppAdapter(default_model="local")
        adapter.chat([{"role": "user", "content": "Hello"}])
    """

    def __init__(
        self,
        cache: InferCache | None = None,
        config: CacheConfig | None = None,
        base_url: str | None = None,
        default_model: str = "local",
        timeout: float = 300.0,
        api_key: str | None = None,
    ) -> None:
        super().__init__(cache=cache, config=config)
        self.base_url = resolve_llamacpp_base_url(base_url)
        self.default_model = default_model or os.environ.get("LLAMACPP_MODEL", "local")
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("LLAMACPP_API_KEY")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(
            f"{self.base_url}{path}",
            data=data,
            headers=self._headers(),
            method=method,
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode()
                return json.loads(body) if body else {}
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise ConnectionError(
                f"llama-server {exc.code} at {self.base_url}{path}: {detail}"
            ) from exc
        except URLError as exc:
            raise ConnectionError(
                f"Cannot reach llama-server at {self.base_url}. "
                "Start it with: llama-server -m model.gguf --port 8080"
            ) from exc

    def _chat_uncached(self, messages: list[dict[str, Any]], model: str, **kwargs: Any) -> str:
        body = {"model": model, "messages": messages, "stream": False, **kwargs}
        result = self._request("POST", "/v1/chat/completions", body)
        choices = result.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        return msg.get("content") or ""

    def _generate_uncached(self, prompt: str, model: str, **kwargs: Any) -> str:
        # Prefer chat completions — most GGUF instruct models expect ChatML.
        return self._chat_uncached([{"role": "user", "content": prompt}], model, **kwargs)

    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        model = model or self.default_model
        optimized = self.cache.optimizer.build_cache_control_blocks(
            self.cache.optimizer.optimize_messages(messages)[0]
        )

        def call(msgs: list[dict[str, Any]]) -> str:
            return self._chat_uncached(msgs, model, **kwargs)

        result = self.cache.get_or_call_messages(optimized, call, model=model)
        result["provider"] = "llamacpp"
        return result

    def complete(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        model = model or self.default_model

        def call(p: str) -> str:
            return self._generate_uncached(p, model, **kwargs)

        result = self.cache.get_or_call(prompt, call, model=model)
        result["provider"] = "llamacpp"
        return result

    def list_models(self) -> list[str]:
        """Return model ids from ``GET /v1/models``."""
        data = self._request("GET", "/v1/models")
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]

    def health(self) -> bool:
        """Return True if ``GET /health`` reports ok."""
        try:
            data = self._request("GET", "/health")
            status = str(data.get("status", "")).lower()
            return status in ("ok", "healthy", "") or bool(data)
        except ConnectionError:
            return False
