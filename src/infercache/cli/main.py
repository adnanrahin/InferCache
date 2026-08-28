"""Command-line interface for InferCache."""

from __future__ import annotations

import argparse
import json
import sys

from infercache import CacheConfig, InferCache, __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="infercache",
        description="InferCache CLI — caching, gateway, MCP server, benchmarks",
    )
    parser.add_argument("--version", action="version", version=f"infercache {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    lookup_p = sub.add_parser("lookup", help="Lookup a prompt in cache")
    lookup_p.add_argument("prompt", help="Prompt text to lookup")
    lookup_p.add_argument("--model", default="", help="Model name for cache key")

    store_p = sub.add_parser("store", help="Store prompt/response pair")
    store_p.add_argument("prompt")
    store_p.add_argument("response")
    store_p.add_argument("--model", default="")

    sub.add_parser("stats", help="Show cache statistics")
    sub.add_parser("clear", help="Clear all cache entries")
    sub.add_parser("demo", help="Watch the cache save a repeated request (no API key needed)")

    bench_p = sub.add_parser("benchmark", help="Measure hit rate, latency, and cost savings")
    bench_p.add_argument("--queries", type=int, default=200)
    bench_p.add_argument("--repeat-rate", type=float, default=0.35)
    bench_p.add_argument("--model", default="gpt-4o-mini", help="Model for pricing estimates")
    bench_p.add_argument("--llm-latency", type=float, default=0.0, help="Simulated LLM latency (s)")
    bench_p.add_argument("--dataset", default=None, help="JSONL file with {'prompt': ...} lines")
    bench_p.add_argument("--output", default=None, help="Write markdown report to file")

    gw_p = sub.add_parser("gateway", help="Run the OpenAI/Anthropic-compatible caching proxy")
    gw_p.add_argument("--host", default="127.0.0.1")
    gw_p.add_argument("--port", type=int, default=8899)
    gw_p.add_argument("--openai-upstream", default="https://api.openai.com")
    gw_p.add_argument("--anthropic-upstream", default="https://api.anthropic.com")
    gw_p.add_argument("--backend", default="sqlite", choices=["memory", "sqlite", "redis"])
    gw_p.add_argument("--sqlite-path", default=None, help="Default: ~/.infercache/cache.db")
    gw_p.add_argument("--redis-url", default=None)
    gw_p.add_argument("--similarity-threshold", type=float, default=None,
                      help="Semantic match threshold (default: config default)")
    gw_p.add_argument("--ttl", type=int, default=None,
                      help="Entry lifetime in seconds (default: 7 days)")
    gw_p.add_argument(
        "--embedding",
        default="tfidf",
        help="Embedding backend: tfidf | hash | minilm (needs infercache[semantic])",
    )
    gw_p.add_argument("--no-vector-index", action="store_true", help="Disable local vector index")

    mcp_p = sub.add_parser("mcp", help="Run the MCP server (stdio) for Cursor/Claude/etc.")
    mcp_p.add_argument("--backend", default="sqlite", choices=["memory", "sqlite", "redis"])
    mcp_p.add_argument("--sqlite-path", default=None, help="Default: ~/.infercache/cache.db")
    mcp_p.add_argument("--similarity-threshold", type=float, default=None,
                       help="Semantic match threshold (default: config default)")
    mcp_p.add_argument(
        "--embedding",
        default="tfidf",
        help="Embedding backend: tfidf | hash | minilm (needs infercache[semantic])",
    )
    mcp_p.add_argument("--no-vector-index", action="store_true", help="Disable local vector index")

    args = parser.parse_args(argv)

    if args.command == "mcp":
        from infercache.mcp import run_stdio_server

        cfg = CacheConfig(
            backend=args.backend,
            embedding_model=args.embedding,
            use_vector_index=not args.no_vector_index,
        )
        if args.similarity_threshold is not None:
            cfg.similarity_threshold = args.similarity_threshold
        if args.sqlite_path:
            cfg.sqlite_path = args.sqlite_path
        run_stdio_server(cache=InferCache(config=cfg))
        return 0

    if args.command == "gateway":
        from infercache.gateway import GatewayConfig, run_gateway

        cache_cfg = CacheConfig(
            backend=args.backend,
            redis_url=args.redis_url,
            embedding_model=args.embedding,
            use_vector_index=not args.no_vector_index,
        )
        if args.similarity_threshold is not None:
            cache_cfg.similarity_threshold = args.similarity_threshold
        if args.ttl is not None:
            cache_cfg.ttl_seconds = args.ttl
        if args.sqlite_path:
            cache_cfg.sqlite_path = args.sqlite_path
        run_gateway(
            GatewayConfig(
                host=args.host,
                port=args.port,
                openai_upstream=args.openai_upstream,
                anthropic_upstream=args.anthropic_upstream,
                cache=cache_cfg,
            )
        )
        return 0

    if args.command == "benchmark":
        from infercache.benchmark import (
            load_jsonl,
            run_cache_benchmark,
            synthetic_workload,
            to_markdown,
        )

        prompts = (
            load_jsonl(args.dataset)
            if args.dataset
            else synthetic_workload(args.queries, args.repeat_rate)
        )
        cache = InferCache()
        result = run_cache_benchmark(
            cache, prompts, model=args.model, llm_latency_s=args.llm_latency
        ).to_dict()
        print(json.dumps(result, indent=2))
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(to_markdown(result))
            print(f"\nReport written to {args.output}")
        return 0

    if args.command == "demo":
        return _run_demo()

    cache = InferCache(config=CacheConfig(backend="sqlite"))

    if args.command == "lookup":
        print(json.dumps(cache.lookup(args.prompt, model=args.model), indent=2))
        return 0

    if args.command == "store":
        cache.store(args.prompt, args.response, model=args.model)
        print("Stored.")
        return 0

    if args.command == "stats":
        print(json.dumps(cache.stats(), indent=2))
        return 0

    if args.command == "clear":
        cache.clear()
        print("Cache cleared.")
        return 0

    return 1


def _run_demo() -> int:
    """Offline walkthrough: the second identical request skips the 'LLM'."""
    import time

    from infercache.optimization.tokens import estimate_tokens

    calls = {"n": 0}

    def pretend_llm(prompt: str) -> str:
        calls["n"] += 1
        time.sleep(0.4)  # stand-in for real API latency
        return "A cache stores answers so repeated questions cost nothing."

    cache = InferCache(config=CacheConfig(backend="memory"))
    prompt = "What is a cache, in one sentence?"

    print("InferCache demo - no API key, nothing leaves this machine\n")
    for label in ("First ask ", "Same ask  "):
        t0 = time.perf_counter()
        result = cache.get_or_call(prompt, pretend_llm, model="demo")
        ms = (time.perf_counter() - t0) * 1000
        status = "HIT  (free)" if result["cache_hit"] else "MISS (paid)"
        print(f"  {label}: {status}  {ms:6.0f} ms   {result['response']}")

    tokens = estimate_tokens(prompt) + estimate_tokens(result["response"])
    print(f"\n  LLM was called {calls['n']} time. The repeat saved ~{tokens} tokens.")
    print("  Point your apps at `infercache gateway` to get this on every request.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
