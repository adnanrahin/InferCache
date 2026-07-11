"""Ollama local LLM adapter."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from infercache.config import CacheConfig
from infercache.core import InferCache
from infercache.integrations.adapters.base import BaseAdapter

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def resolve_ollama_base_url(base_url: str | None = None) -> str:
    """
    Resolve Ollama server URL.

    Priority: explicit base_url → OLLAMA_HOST env → localhost default.
    OLLAMA_HOST may be ``host:port`` or a full URL.
    """
    if base_url:
        return _normalize_ollama_url(base_url)
    env = os.environ.get("OLLAMA_HOST")
    if env:
        return _normalize_ollama_url(env)
    return DEFAULT_OLLAMA_URL


def _normalize_ollama_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


class OllamaAdapter(BaseAdapter):
    """
    Wrap Ollama chat/generate APIs with InferCache.

    Connect to local or remote Ollama via ``base_url`` or ``OLLAMA_HOST`` env var.
    No extra pip packages needed — uses the Ollama HTTP API directly.
    """

    def __init__(
        self,
        cache: InferCache | None = None,
        config: CacheConfig | None = None,
        base_url: str | None = None,
        default_model: str = "llama3.2",
        timeout: float = 120.0,
    ) -> None:
        super().__init__(cache=cache, config=config)
        self.base_url = resolve_ollama_base_url(base_url)
        self.default_model = default_model
        self.timeout = timeout

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode()
        req = Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except URLError as exc:
            raise ConnectionError(
                f"Cannot reach Ollama at {self.base_url}. "
                "Check that Ollama is running and OLLAMA_HOST is set correctly."
            ) from exc

    def _chat_uncached(self, messages: list[dict[str, Any]], model: str, **kwargs: Any) -> str:
        body = {"model": model, "messages": messages, "stream": False, **kwargs}
        result = self._post("/api/chat", body)
        return result.get("message", {}).get("content", "")

    def _generate_uncached(self, prompt: str, model: str, **kwargs: Any) -> str:
        body = {"model": model, "prompt": prompt, "stream": False, **kwargs}
        result = self._post("/api/generate", body)
        return result.get("response", "")

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
        result["provider"] = "ollama"
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
        result["provider"] = "ollama"
        return result

    def list_models(self) -> list[str]:
        """Return model names available in local Ollama."""
        try:
            with urlopen(f"{self.base_url}/api/tags", timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
        except URLError as exc:
            raise ConnectionError(f"Cannot reach Ollama at {self.base_url}") from exc
