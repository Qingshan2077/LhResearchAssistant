"""Estimated DeepSeek API costs in CNY per million tokens."""

from typing import TypedDict


DEEPSEEK_PRICING = {
    "deepseek-v4-flash": {
        "cache_hit_input": 0.02,
        "cache_miss_input": 1.00,
        "output": 2.00,
    },
    "deepseek-v4-pro": {
        "cache_hit_input": 0.025,
        "cache_miss_input": 3.00,
        "output": 6.00,
    },
}


class CostBreakdown(TypedDict):
    cache_hit: float
    cache_miss: float
    output: float


class CostEstimate(TypedDict):
    total: float
    breakdown: CostBreakdown
    currency: str


def estimate_cost(
    model: str,
    cache_hit_tokens: int | None,
    cache_miss_tokens: int | None,
    output_tokens: int,
) -> CostEstimate | None:
    """Estimate a call cost when both the model price and cache data are known."""
    pricing = DEEPSEEK_PRICING.get(model)
    if not pricing or (cache_hit_tokens is None and cache_miss_tokens is None):
        return None

    hit = max(0, cache_hit_tokens or 0) / 1_000_000 * pricing["cache_hit_input"]
    miss = max(0, cache_miss_tokens or 0) / 1_000_000 * pricing["cache_miss_input"]
    output = max(0, output_tokens) / 1_000_000 * pricing["output"]
    return {
        "total": round(hit + miss + output, 6),
        "breakdown": {
            "cache_hit": round(hit, 6),
            "cache_miss": round(miss, 6),
            "output": round(output, 6),
        },
        "currency": "CNY",
    }
