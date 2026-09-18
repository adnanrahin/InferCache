"""Backward compatibility — use infercache.optimization.tokens instead."""

from infercache.optimization.tokens import (
    count_messages_tokens,
    estimate_tokens,
    normalize_whitespace,
)

__all__ = ["count_messages_tokens", "estimate_tokens", "normalize_whitespace"]
