"""Prompt optimization: compression, prefix structuring, history pruning."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Sequence

from infercache.config import CacheConfig
from infercache.optimization.tokens import count_messages_tokens, estimate_tokens, normalize_whitespace


class PromptOptimizer:
    """Reduces input tokens while preserving semantic structure."""

    FILLER_PATTERNS = [
        r"\b(please|kindly|could you|would you|I would like you to)\b",
        r"\b(very|really|quite|actually|basically|essentially)\b",
        r"\b(in order to|for the purpose of)\b",
    ]

    def __init__(self, config: CacheConfig | None = None) -> None:
        self.config = config or CacheConfig()

    def optimize_messages(
        self, messages: Sequence[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int, int]:
        msgs = [deepcopy(m) for m in messages]
        before = count_messages_tokens(msgs)

        if self.config.enable_history_pruning:
            msgs = self._prune_history(msgs)
        if self.config.enable_prompt_compression:
            msgs = self._compress_messages(msgs)
        if self.config.enable_prefix_optimization:
            msgs = self._reorder_for_prefix_cache(msgs)

        after = count_messages_tokens(msgs)
        return msgs, before, after

    def optimize_prompt(self, prompt: str) -> tuple[str, int, int]:
        before = estimate_tokens(prompt)
        text = prompt
        if self.config.enable_prompt_compression:
            text = self._compress_text(text)
        text = normalize_whitespace(text)
        after = estimate_tokens(text)
        return text, before, after

    def _prune_history(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(messages) <= self.config.max_history_messages:
            return messages
        system = [m for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]
        keep = rest[-(self.config.max_history_messages - len(system)) :]
        return system + keep

    def _compress_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        target_ratio = self.config.compression_ratio
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str) and msg.get("role") != "system":
                compressed = self._compress_text(content, target_ratio)
                if estimate_tokens(compressed) < estimate_tokens(content):
                    msg["content"] = compressed
        return messages

    def _compress_text(self, text: str, target_ratio: float | None = None) -> str:
        ratio = target_ratio or self.config.compression_ratio
        text = normalize_whitespace(text)

        for pattern in self.FILLER_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) <= 2:
            return text.strip()

        scored: list[tuple[float, str]] = []
        for sent in sentences:
            if not sent.strip():
                continue
            scored.append((self._sentence_importance(sent), sent))

        scored.sort(key=lambda x: x[0], reverse=True)
        keep_count = max(1, int(len(scored) * ratio))
        kept = sorted(scored[:keep_count], key=lambda x: sentences.index(x[1]) if x[1] in sentences else 0)
        return " ".join(s for _, s in kept).strip()

    def _sentence_importance(self, sentence: str) -> float:
        score = len(sentence.split()) * 0.1
        if re.search(r"\b(must|should|important|key|error|fail|require)\b", sentence, re.I):
            score += 2.0
        if re.search(r"\b\d+\b", sentence):
            score += 1.0
        if sentence.strip().endswith("?"):
            score += 1.5
        return score

    def _reorder_for_prefix_cache(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        system_static: list[dict[str, Any]] = []
        system_dynamic: list[dict[str, Any]] = []
        other: list[dict[str, Any]] = []

        for msg in messages:
            if msg.get("role") != "system":
                other.append(msg)
                continue
            content = msg.get("content", "")
            if isinstance(content, str) and estimate_tokens(content) >= self.config.static_prefix_min_tokens:
                system_static.append(msg)
            else:
                system_dynamic.append(msg)

        return system_static + system_dynamic + other

    def build_cache_control_blocks(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = deepcopy(messages)
        static_idx = -1
        for i, msg in enumerate(result):
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str) and estimate_tokens(content) >= self.config.static_prefix_min_tokens:
                    static_idx = i
        if static_idx >= 0:
            msg = result[static_idx]
            if isinstance(msg.get("content"), str):
                msg["content"] = [
                    {
                        "type": "text",
                        "text": msg["content"],
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
        return result
