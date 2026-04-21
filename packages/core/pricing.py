"""
Handles model pricing and cost calculation.
Uses LiteLLM's built-in cost map — works offline, covers all providers.
"""

import warnings
import litellm
from dataclasses import dataclass

# Suppress Pydantic serialization warnings from LiteLLM streaming responses
# These occur when LiteLLM tries to serialize streaming response objects during cleanup
# The warnings are harmless but appear during program exit
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.main")


@dataclass
class ModelPricing:
    """Pricing information for a model (costs in USD per token)."""

    prompt_cost: float  # Cost per input token
    completion_cost: float  # Cost per output token
    model_id: str
    cache_read_cost: float | None = (
        None  # Cost per cache-read token (None = derive from prompt_cost)
    )
    cache_write_cost: float | None = (
        None  # Cost per cache-write token (None = derive from prompt_cost)
    )

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> float:
        """Calculate total cost in USD for a request, accounting for cached tokens.

        Cache pricing varies by provider:
          Anthropic: read = 0.1x prompt, write = 1.25x prompt
          OpenAI: read = 0.5x prompt, no write surcharge
        Uses provider-specific rates from LiteLLM cost map when available,
        otherwise defaults to Anthropic rates.
        """
        regular_prompt = max(0, prompt_tokens - cache_read_tokens - cache_write_tokens)
        read_cost = (
            self.cache_read_cost if self.cache_read_cost is not None else self.prompt_cost * 0.1
        )
        write_cost = (
            self.cache_write_cost if self.cache_write_cost is not None else self.prompt_cost * 1.25
        )
        return (
            regular_prompt * self.prompt_cost
            + cache_read_tokens * read_cost
            + cache_write_tokens * write_cost
            + completion_tokens * self.completion_cost
        )


def _get_litellm_cost_map() -> dict:
    """Return LiteLLM's cost map (loaded at import with remote→local fallback)."""
    return litellm.model_cost


def get_model_pricing(model_id: str) -> ModelPricing | None:
    """
    Get pricing for a specific model using LiteLLM's built-in cost data.

    Args:
        model_id: LiteLLM-routable model ID (e.g. "openrouter/anthropic/claude-sonnet-4.6")

    Returns:
        ModelPricing object or None if not found
    """
    cost_map = _get_litellm_cost_map()

    # Try the full model ID first, then progressively stripped prefixes
    candidates = [model_id]
    if "/" in model_id:
        # Strip first prefix: "openrouter/anthropic/claude-sonnet-4.6" -> "anthropic/claude-sonnet-4.6"
        candidates.append(model_id.split("/", 1)[1])
        # Bare model name: "openrouter/anthropic/claude-sonnet-4.6" -> "claude-sonnet-4.6"
        candidates.append(model_id.rsplit("/", 1)[-1])

    for candidate in candidates:
        info = cost_map.get(candidate)
        if info:
            input_cost = info.get("input_cost_per_token", 0)
            output_cost = info.get("output_cost_per_token", 0)
            cache_read = info.get("cache_read_input_token_cost")
            cache_write = info.get("cache_creation_input_token_cost")
            return ModelPricing(
                prompt_cost=input_cost,
                completion_cost=output_cost,
                model_id=model_id,
                cache_read_cost=cache_read,
                cache_write_cost=cache_write,
            )

    return None


def calculate_cost_from_litellm(response) -> float:
    """
    Calculate cost using LiteLLM's built-in cost tracking.
    Useful as a fallback when pricing data isn't available upfront.

    Args:
        response: LiteLLM response object

    Returns:
        Cost in USD, or 0.0 if unable to calculate
    """
    try:
        import warnings

        # Suppress Pydantic serialization warnings from incomplete streaming responses
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            return litellm.completion_cost(completion_response=response)
    except Exception:
        # Silently fail - fallback cost calculation not critical
        return 0.0


def format_cost(cost_usd: float) -> str:
    """Format cost for display. Shows more precision for small amounts."""
    if cost_usd < 0.0001:
        return f"${cost_usd:.6f}"
    elif cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    else:
        return f"${cost_usd:.2f}"
