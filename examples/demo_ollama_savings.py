"""
Demo: InferCache + Ollama — see tokens SPENT vs tokens SAVED.

Run:
  conda activate infer_cache
  set OLLAMA_HOST=192.168.1.248:11434
  set OLLAMA_MODEL=qwen3.5:latest
  python examples/demo_ollama_savings.py

What you'll see:
  - Call 1: miss  → Ollama runs (tokens spent)
  - Call 2: exact hit → no Ollama (tokens saved)
  - Call 3: paraphrase → semantic hit if similar enough (tokens saved)
  - Final report: spent vs saved totals
"""

from __future__ import annotations

import os
import time

from infercache import CacheConfig, InferCache
from infercache.integrations.adapters import OllamaAdapter
from infercache.optimization.tokens import estimate_tokens

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "192.168.1.248:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:latest")


def main() -> None:
    print("=" * 60)
    print("InferCache × Ollama — token savings demo")
    print("=" * 60)

    cache = InferCache(
        CacheConfig(
            backend="sqlite",
            similarity_threshold=0.55,
            ttl_seconds=3600,
        )
    )
    adapter = OllamaAdapter(cache=cache, base_url=OLLAMA_URL, default_model=MODEL)

    print(f"\nOllama : {adapter.base_url}")
    print(f"Model  : {MODEL}")
    try:
        models = adapter.list_models()
        print(f"Models : {models}")
        if models and MODEL not in models and not any(MODEL in m for m in models):
            print(f"\nWARNING: '{MODEL}' not in server list. Set OLLAMA_MODEL to one of the above.")
    except ConnectionError as exc:
        print(f"\nERROR: cannot reach Ollama — {exc}")
        print("Fix: start Ollama on that host, or set OLLAMA_HOST correctly.")
        return

    prompts = [
        ("1. First ask (MISS — pays tokens)", "Explain what a cache is in one short sentence."),
        ("2. Same ask again (EXACT HIT — free)", "Explain what a cache is in one short sentence."),
        ("3. Paraphrase (SEMANTIC HIT if similar)", "In one sentence, what does caching mean?"),
        ("4. New ask (MISS — pays tokens)", "Name one benefit of caching LLM responses."),
        ("5. Repeat new ask (EXACT HIT — free)", "Name one benefit of caching LLM responses."),
    ]

    spent = 0
    saved = 0
    results = []

    print("\n" + "-" * 60)
    for label, prompt in prompts:
        messages = [{"role": "user", "content": prompt}]
        t0 = time.perf_counter()
        out = adapter.chat(messages)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        in_tok = estimate_tokens(prompt)
        out_tok = estimate_tokens(out.get("response", ""))
        total_tok = in_tok + out_tok
        hit = bool(out.get("cache_hit"))

        if hit:
            saved += total_tok
            path = "CACHE HIT (no Ollama call)"
        else:
            spent += total_tok
            path = "CACHE MISS → Ollama"

        results.append((label, hit, total_tok, elapsed_ms, out.get("response", "")[:80]))

        print(f"\n{label}")
        print(f"  Path     : {path}")
        print(f"  Tokens   : ~{total_tok} (in≈{in_tok}, out≈{out_tok})")
        print(f"  Latency  : {elapsed_ms:.0f} ms")
        print(f"  Reply    : {out.get('response', '')[:120]!r}")

    total = spent + saved
    pct = (100.0 * saved / total) if total else 0.0

    print("\n" + "=" * 60)
    print("TOKEN REPORT")
    print("=" * 60)
    print(f"  Tokens SPENT  (Ollama called) : ~{spent}")
    print(f"  Tokens SAVED  (served locally): ~{saved}")
    print(f"  Total tokens in this demo     : ~{total}")
    print(f"  Savings rate                  : {pct:.1f}%")
    print()
    print("Cache stats:", cache.stats())
    print()
    print("How to read this:")
    print("  - SPENT  = tokens that actually went to Ollama")
    print("  - SAVED  = tokens you did NOT send because of a cache hit")
    print("  - Without InferCache, SPENT would equal TOTAL")
    print("=" * 60)


if __name__ == "__main__":
    main()
