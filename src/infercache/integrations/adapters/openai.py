"""OpenAI adapter."""

from __future__ import annotations

from typing import Any

from infercache.config import CacheConfig
from infercache.core import InferCache
from infercache.integrations.adapters.base import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    def __init__(
        self,
        client: Any | None = None,
        cache: InferCache | None = None,
        config: CacheConfig | None = None,
        default_model: str = "gpt-4o-mini",
    ) -> None:
        super().__init__(cache=cache, config=config)
        self._client = client
        self.default_model = default_model

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("Install infercache[openai] for OpenAI adapter") from exc
        self._client = OpenAI()
        return self._client

    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        model = model or self.default_model

        def call(msgs: list[dict[str, Any]]) -> str:
            client = self._get_client()
            resp = client.chat.completions.create(model=model, messages=msgs, **kwargs)
            return resp.choices[0].message.content or ""

        result = self.cache.get_or_call_messages(messages, call, model=model)
        result["provider"] = "openai"
        return result
