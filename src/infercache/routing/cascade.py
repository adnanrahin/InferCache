"""Model cascade: try cheap models first, escalate when unsure (FrugalGPT-style)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from infercache.core.engine import InferCache
from infercache.optimization.tokens import estimate_tokens

EscalateFn = Callable[[str], bool]
LLMFn = Callable[[str], str]


def default_escalate(response: str) -> bool:
    """Heuristic: escalate if answer looks uncertain or too thin."""
    text = (response or "").strip()
    if len(text) < 40:
        return True
    uncertain = (
        r"\b(i('m| am) not sure|cannot determine|insufficient|unclear|"
        r"i don't know|as an ai|need more (info|context))\b"
    )
    return bool(re.search(uncertain, text, re.I))


@dataclass
class CascadeStage:
    model: str
    llm_fn: LLMFn


class ModelCascade:
    """
    FrugalGPT-inspired cascade:
      1) Check cache for any stage model
      2) Call cheapest stage
      3) Escalate to next stage only if escalate_if(response) is True
    """

    def __init__(
        self,
        cache: InferCache,
        stages: list[CascadeStage],
        escalate_if: EscalateFn | None = default_escalate,
    ) -> None:
        if not stages:
            raise ValueError("Cascade requires at least one stage")
        self.cache = cache
        self.stages = stages
        self.escalate_if = escalate_if

    def complete(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        for stage in self.stages:
            hit = self.cache.lookup(prompt, model=stage.model, **kwargs)
            if hit.get("cache_hit"):
                hit["model_used"] = stage.model
                hit["cascade_stage"] = stage.model
                hit["escalated"] = False
                return hit

        optimized = self.cache.optimizer.optimize_prompt(prompt)[0]

        for i, stage in enumerate(self.stages):
            response = stage.llm_fn(optimized)
            tokens = estimate_tokens(optimized) + estimate_tokens(response)
            self.cache.metrics.record_miss(tokens)

            is_last = i == len(self.stages) - 1
            accepted = is_last or self.escalate_if is None or not self.escalate_if(response)
            if not accepted:
                # Rejected answers must never become cache hits
                continue

            if response and response.strip():
                self.cache.store(prompt, response, model=stage.model, **kwargs)
            return {
                "response": response,
                "cache_hit": False,
                "optimized_prompt": optimized,
                "model_used": stage.model,
                "cascade_stage": stage.model,
                "escalated": i > 0,
                "stages_tried": i + 1,
            }

        raise RuntimeError("unreachable: last stage always returns")
