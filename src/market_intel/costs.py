from __future__ import annotations

from typing import Any

from market_intel.config import Settings
from market_intel.models import CostEstimate, RunCost

DISCOVERY_SEARCH_CALLS = 3
RESEARCH_SEARCH_CALLS_PER_COMPETITOR = 6


def estimate_run_cost(top_n: int, settings: Settings) -> CostEstimate:
    """Estimate a normal run before any billable provider is called."""
    ydc_calls = DISCOVERY_SEARCH_CALLS + RESEARCH_SEARCH_CALLS_PER_COMPETITOR * top_n
    llm_calls = top_n + 2  # discovery, one extraction per competitor, synthesis
    input_tokens = 15_000 + 8_000 * top_n
    output_tokens = 3_500 + 3_000 * top_n
    ydc_cost = ydc_calls * settings.ydc_cost_per_1000_calls / 1_000
    llm_cost = (
        input_tokens * settings.llm_input_cost_per_million
        + output_tokens * settings.llm_output_cost_per_million
    ) / 1_000_000
    return CostEstimate(
        ydc_calls=ydc_calls,
        ydc_cost_usd=round(ydc_cost, 6),
        llm_calls=llm_calls,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        llm_cost_usd=round(llm_cost, 6),
        total_cost_usd=round(ydc_cost + llm_cost, 6),
        assumptions=[
            "Estimate only; actual LLM cost depends on generated and cached tokens.",
            f"Uses {settings.openai_model} rates configured in .env.",
            "Retries may increase provider calls.",
        ],
    )


def calculate_run_cost(
    settings: Settings,
    search_usage: dict[str, Any],
    llm_usage: dict[str, Any],
) -> RunCost:
    calls = int(search_usage.get("calls", 0))
    llm_calls = int(llm_usage.get("calls", 0))
    input_tokens = int(llm_usage.get("input_tokens", 0))
    cached_tokens = int(llm_usage.get("cached_input_tokens", 0))
    output_tokens = int(llm_usage.get("output_tokens", 0))
    uncached_tokens = max(0, input_tokens - cached_tokens)
    ydc_cost = calls * settings.ydc_cost_per_1000_calls / 1_000
    llm_cost = (
        uncached_tokens * settings.llm_input_cost_per_million
        + cached_tokens * settings.llm_cached_input_cost_per_million
        + output_tokens * settings.llm_output_cost_per_million
    ) / 1_000_000
    return RunCost(
        ydc_calls=calls,
        ydc_cost_usd=round(ydc_cost, 6),
        llm_calls=llm_calls,
        input_tokens=input_tokens,
        cached_input_tokens=cached_tokens,
        output_tokens=output_tokens,
        llm_cost_usd=round(llm_cost, 6),
        total_cost_usd=round(ydc_cost + llm_cost, 6),
    )


def usage_snapshot(provider: object) -> dict[str, Any]:
    snapshot = getattr(provider, "usage_snapshot", None)
    return snapshot() if callable(snapshot) else {}

