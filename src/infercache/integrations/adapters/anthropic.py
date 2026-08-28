"""Anthropic adapter."""

from __future__ import annotations

from typing import Any

from infercache.config import CacheConfig
from infercache.core import InferCache
from infercache.integrations.adapters.base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    def __init__(
        self,
        client: Any | None = None,
        cache: InferCache | None = None,
        config: CacheConfig | None = None,
        default_model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        super().__init__(cache=cache, config=config)
        self._client = client
        self.default_model = default_model

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ImportError("Install infercache[anthropic] for Anthropic adapter") from exc
        self._client = Anthropic()
        return self._client

    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        model = model or self.default_model

        def call(msgs: list[dict[str, Any]]) -> str:
            client = self._get_client()
            # cache_control marks the static system prefix for Anthropic's
            # provider-side prompt cache; applied only to what goes upstream
            prepared = self.cache.optimizer.build_cache_control_blocks(msgs)
            non_system = [m for m in prepared if m.get("role") != "system"]
            kwargs_copy = dict(kwargs)
            system_val = system
            if system_val is None:
                for m in prepared:
                    if m.get("role") == "system":
                        system_val = m.get("content")
                        break
            if system_val:
                kwargs_copy["system"] = system_val
            resp = client.messages.create(model=model, messages=non_system, **kwargs_copy)
            return "".join(getattr(b, "text", str(b)) for b in resp.content)

        result = self.cache.get_or_call_messages(messages, call, model=model)
        result["provider"] = "anthropic"
        return result
