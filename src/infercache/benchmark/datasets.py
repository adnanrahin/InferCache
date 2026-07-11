"""Benchmark workload generation and loading."""

from __future__ import annotations

import json
import random

# Base questions with paraphrase families — models the ~31% semantic-repeat
# pattern observed in production LLM traffic (see docs/RESEARCH.md).
_FAMILIES: dict[str, list[str]] = {
    "What is the capital of France?": [
        "Tell me France's capital city.",
        "What's the capital city of France?",
        "France capital?",
    ],
    "Explain how HTTP caching works.": [
        "How does HTTP cache work?",
        "Describe HTTP caching mechanisms.",
        "Walk me through HTTP caching.",
    ],
    "Write a Python function to sort a list.": [
        "Python code to sort a list.",
        "Show me how to sort a list in Python.",
        "Give me a list-sorting function in Python.",
    ],
    "Summarize the benefits of semantic caching for LLMs.": [
        "What are advantages of semantic cache for large language models?",
        "Why use semantic caching with LLMs?",
        "Benefits of caching LLM responses semantically?",
    ],
    "How do I reduce OpenAI API costs?": [
        "Ways to lower OpenAI token costs?",
        "Tips for reducing GPT API spending?",
        "How can I cut my OpenAI bill?",
    ],
    "What is a vector database?": [
        "Explain vector databases.",
        "Vector DB — what is it?",
    ],
    "How does JWT authentication work?": [
        "Explain JWT auth flow.",
        "What are JSON web tokens and how do they authenticate?",
    ],
    "Write a SQL query to find duplicate rows.": [
        "SQL for detecting duplicates in a table.",
        "How do I find duplicate records with SQL?",
    ],
}


def synthetic_workload(
    n: int = 200,
    repeat_rate: float = 0.35,
    paraphrase_rate: float = 0.5,
    seed: int | None = 42,
) -> list[str]:
    """
    Generate a prompt stream:
    - repeat_rate fraction are repeats of a known question family
    - within repeats, paraphrase_rate fraction use a paraphrase (semantic hit
      candidates) rather than the identical string (exact hit candidates)
    """
    rng = random.Random(seed)
    bases = list(_FAMILIES.keys())
    prompts: list[str] = []
    for i in range(n):
        if rng.random() < repeat_rate:
            base = rng.choice(bases)
            if rng.random() < paraphrase_rate:
                prompts.append(rng.choice(_FAMILIES[base]))
            else:
                prompts.append(base)
        else:
            prompts.append(f"Unique question #{i}: {rng.randint(10_000, 99_999)}")
    return prompts


def canonical_answer(prompt: str) -> str:
    """Deterministic simulated LLM answer for a prompt (for offline benchmarks)."""
    for base, paras in _FAMILIES.items():
        if prompt == base or prompt in paras:
            return f"Canonical answer for: {base} " + "x" * 400
    return f"Generated response for: {prompt[:60]} " + "y" * 400


def load_jsonl(path: str) -> list[str]:
    """Load prompts from a JSONL file with {"prompt": "..."} per line."""
    prompts = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            prompts.append(obj["prompt"] if isinstance(obj, dict) else str(obj))
    return prompts
