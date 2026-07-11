"""Backward compatibility — use infercache.integrations.adapters instead."""

from infercache.integrations.adapters import (
    AnthropicAdapter,
    BaseAdapter,
    GenericAdapter,
    OllamaAdapter,
    OpenAIAdapter,
)

__all__ = ["AnthropicAdapter", "BaseAdapter", "GenericAdapter", "OllamaAdapter", "OpenAIAdapter"]
