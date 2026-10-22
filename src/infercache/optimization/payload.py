"""Classify a prompt so InferCache can refuse lossy edits on structured text.

InferCache's own detector. Stdlib ``json`` plus cheap regex. It does not
compress, summarize, rewrite, or store a sidecar of the original.
"""

from __future__ import annotations

import json
import re
from enum import Enum

_CODE_FENCE = re.compile(r"^```[A-Za-z0-9_+\-]*\s*$", re.MULTILINE)
_CODE_LINE = re.compile(
    r"^\s*(def |class |function |fn |pub fn |package |import |from .+ import |"
    r"#!/|int main\s*\(|export |const |let |var )",
    re.MULTILINE,
)


class PayloadKind(str, Enum):
    PROSE = "prose"
    JSON = "json"
    CODE = "code"


def classify_payload(text: str) -> PayloadKind:
    """Return the dominant kind of *text* for optimizer policy."""
    sample = (text or "").strip()
    if not sample:
        return PayloadKind.PROSE
    if sample[0] in "{[":
        try:
            json.loads(sample)
            return PayloadKind.JSON
        except (json.JSONDecodeError, ValueError, RecursionError):
            pass
    if _looks_like_code(sample):
        return PayloadKind.CODE
    return PayloadKind.PROSE


def _looks_like_code(sample: str) -> bool:
    if _CODE_FENCE.search(sample):
        return True
    lines = [ln for ln in sample.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    hinted = sum(1 for ln in lines if _CODE_LINE.search(ln))
    if hinted >= 2:
        return True
    punct = sum(sample.count(ch) for ch in "{}();=")
    words = max(1, len(sample.split()))
    return (punct / words) > 0.45


def should_rewrite(text: str) -> bool:
    """True only for prose. JSON and code must stay byte-stable for cache keys."""
    return classify_payload(text) is PayloadKind.PROSE
