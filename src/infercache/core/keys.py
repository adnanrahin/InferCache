"""Cache key generation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def make_exact_key(prompt: str, model: str = "", **kwargs: Any) -> str:
    payload = json.dumps({"prompt": prompt, "model": model, **kwargs}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
