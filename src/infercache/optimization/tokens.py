"""Token counting and estimation utilities."""

from __future__ import annotations

import re
from typing import Any, Sequence


def estimate_tokens(text: str) -> int:
    """Estimate token count without external tokenizer (≈4 chars/token for English)."""
    if not text:
        return 0
    words = len(text.split())
    chars = len(text)
    return max(1, int((chars / 4 + words * 0.75) / 2))


def count_messages_tokens(messages: Sequence[dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += estimate_tokens(part.get("text", ""))
        total += 4
    return total


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
