"""
Handles model pricing and cost calculation.
Uses LiteLLM's built-in cost map — works offline, covers all providers.
"""

import warnings
import litellm
from dataclasses import dataclass
from functools import lru_cache

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

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate total cost in USD for a request."""
        return (prompt_tokens * self.prompt_cost) + (completion_tokens * self.completion_cost)


@lru_cache(maxsize=1)
def _get_litellm_cost_map() -> dict:
    """Load LiteLLM's built-in cost map (cached)."""
    try:
        return litellm.get_model_cost_map(url="")
    except Exception:
        return {}


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
            return ModelPricing(
                prompt_cost=input_cost,
                completion_cost=output_cost,
                model_id=model_id,
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
