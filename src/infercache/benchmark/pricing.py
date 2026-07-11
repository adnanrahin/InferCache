"""Approximate provider pricing (USD per 1M tokens) for cost-savings estimates.

Prices change frequently — treat as estimates and override with --input-price /
--output-price when accuracy matters.
"""

from __future__ import annotations

# (input $/1M tokens, output $/1M tokens)
PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    # Anthropic
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    # Bedrock (Anthropic models, on-demand)
    "anthropic.claude-3-5-sonnet": (3.00, 15.00),
    "anthropic.claude-3-5-haiku": (0.80, 4.00),
    # Local models: electricity/GPU amortization is real but ~0 marginal API cost
    "ollama": (0.0, 0.0),
    "local": (0.0, 0.0),
}

DEFAULT_PRICING = (3.00, 15.00)


def get_pricing(model: str) -> tuple[float, float]:
    model_lower = model.lower()
    for key, price in PRICING.items():
        if model_lower.startswith(key) or key in model_lower:
            return price
    return DEFAULT_PRICING


def cost_usd(model: str, input_tokens: int, output_tokens: int,
             input_price: float | None = None, output_price: float | None = None) -> float:
    in_p, out_p = get_pricing(model)
    if input_price is not None:
        in_p = input_price
    if output_price is not None:
        out_p = output_price
    return (input_tokens * in_p + output_tokens * out_p) / 1_000_000
