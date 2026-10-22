"""Sampling fields that change the answer and therefore the cache identity.

Shared by the gateway and provider adapters so a temperature=0 call can never
serve a temperature=1 answer. Keys are InferCache's own list, aligned with
OpenAI/Anthropic request bodies.
"""

from __future__ import annotations

from typing import Any, Mapping

SAMPLING_KEYS: frozenset[str] = frozenset(
    {
        "temperature",
        "top_p",
        "top_k",
        "max_tokens",
        "max_completion_tokens",
        "seed",
        "stop",
        "stop_sequences",
        "n",
        "response_format",
        "frequency_penalty",
        "presence_penalty",
        "tool_choice",
    }
)


def sampling_scope(body: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the sampling fields present on *body*."""
    return {key: body[key] for key in SAMPLING_KEYS if key in body}
