"""Generic LLM adapter."""

from __future__ import annotations

from typing import Any, Callable

from infercache.integrations.adapters.base import BaseAdapter


class GenericAdapter(BaseAdapter):
    def complete(
        self,
        prompt: str,
        llm_fn: Callable[[str], str],
        model: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.cache.get_or_call(prompt, llm_fn, model=model, **self.cache_scope(kwargs))

    def chat(
        self,
        messages: list[dict[str, Any]],
        llm_fn: Callable[[list[dict[str, Any]]], str],
        model: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.cache.get_or_call_messages(
            messages, llm_fn, model=model, **self.cache_scope(kwargs)
        )
