"""Benchmark runner: replay a prompt stream through InferCache and measure savings."""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from infercache.benchmark.datasets import canonical_answer
from infercache.benchmark.pricing import cost_usd
from infercache.core import InferCache
from infercache.optimization.tokens import estimate_tokens


@dataclass
class BenchmarkResult:
    model: str
    total_requests: int = 0
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    input_tokens_saved: int = 0
    output_tokens_saved: int = 0
    input_tokens_spent: int = 0
    output_tokens_spent: int = 0
    hit_latencies_ms: list[float] = field(default_factory=list)
    miss_latencies_ms: list[float] = field(default_factory=list)
    wall_time_s: float = 0.0
    input_price: float | None = None
    output_price: float | None = None

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.exact_hits + self.semantic_hits) / self.total_requests

    @property
    def cost_saved_usd(self) -> float:
        return cost_usd(
            self.model, self.input_tokens_saved, self.output_tokens_saved,
            self.input_price, self.output_price,
        )

    @property
    def cost_spent_usd(self) -> float:
        return cost_usd(
            self.model, self.input_tokens_spent, self.output_tokens_spent,
            self.input_price, self.output_price,
        )

    @property
    def cost_reduction_pct(self) -> float:
        total = self.cost_saved_usd + self.cost_spent_usd
        if total == 0:
            return 0.0
        return 100.0 * self.cost_saved_usd / total

    def to_dict(self) -> dict[str, Any]:
        def _avg(xs: list[float]) -> float:
            return round(statistics.mean(xs), 2) if xs else 0.0

        def _p95(xs: list[float]) -> float:
            if not xs:
                return 0.0
            xs_sorted = sorted(xs)
            return round(xs_sorted[min(len(xs_sorted) - 1, int(0.95 * len(xs_sorted)))], 2)

        return {
            "model": self.model,
            "total_requests": self.total_requests,
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "tokens": {
                "input_saved": self.input_tokens_saved,
                "output_saved": self.output_tokens_saved,
                "input_spent": self.input_tokens_spent,
                "output_spent": self.output_tokens_spent,
            },
            "cost": {
                "saved_usd": round(self.cost_saved_usd, 6),
                "spent_usd": round(self.cost_spent_usd, 6),
                "reduction_pct": round(self.cost_reduction_pct, 2),
            },
            "latency_ms": {
                "hit_avg": _avg(self.hit_latencies_ms),
                "hit_p95": _p95(self.hit_latencies_ms),
                "miss_avg": _avg(self.miss_latencies_ms),
                "miss_p95": _p95(self.miss_latencies_ms),
            },
            "wall_time_s": round(self.wall_time_s, 2),
        }


def run_cache_benchmark(
    cache: InferCache,
    prompts: list[str],
    model: str = "gpt-4o-mini",
    llm_fn: Callable[[str], str] | None = None,
    llm_latency_s: float = 0.0,
    input_price: float | None = None,
    output_price: float | None = None,
) -> BenchmarkResult:
    """
    Replay prompts through the cache. When llm_fn is None a deterministic
    simulated LLM is used, with optional artificial latency to model real APIs.
    """
    result = BenchmarkResult(model=model, input_price=input_price, output_price=output_price)

    def default_llm(prompt: str) -> str:
        if llm_latency_s > 0:
            time.sleep(llm_latency_s)
        return canonical_answer(prompt)

    fn = llm_fn or default_llm
    start = time.perf_counter()

    for prompt in prompts:
        result.total_requests += 1
        t0 = time.perf_counter()
        out = cache.get_or_call(prompt, fn, model=model)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        in_tokens = estimate_tokens(prompt)
        out_tokens = estimate_tokens(out.get("response", ""))

        if out.get("cache_hit"):
            result.hit_latencies_ms.append(elapsed_ms)
            result.input_tokens_saved += in_tokens
            result.output_tokens_saved += out_tokens
            if out.get("cache_type") == "exact":
                result.exact_hits += 1
            else:
                result.semantic_hits += 1
        else:
            result.miss_latencies_ms.append(elapsed_ms)
            result.misses += 1
            result.input_tokens_spent += in_tokens
            result.output_tokens_spent += out_tokens

    result.wall_time_s = time.perf_counter() - start
    return result
