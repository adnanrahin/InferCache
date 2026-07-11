"""Backward compatibility — use infercache.integrations.wrapper instead."""

from infercache.integrations.wrapper import cached_llm_call, configure, get_default_cache

__all__ = ["cached_llm_call", "configure", "get_default_cache"]
