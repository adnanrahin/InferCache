"""Cache key generation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def make_exact_key(prompt: str, model: str = "", **kwargs: Any) -> str:
    payload = json.dumps(
        {"prompt": prompt, "model": model, **kwargs},
        sort_keys=True,
        separators=(",", ":"),
    )
    # blake2b is faster than sha256 and 16 bytes is plenty for a local cache
    return hashlib.blake2b(payload.encode(), digest_size=16).hexdigest()
