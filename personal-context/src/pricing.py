"""
Handles model pricing and cost calculation.
Fetches pricing from OpenRouter API and calculates costs per request.
"""

import requests
from dataclasses import dataclass
from functools import lru_cache


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
def fetch_all_pricing() -> dict[str, ModelPricing]:
    """
    Fetch pricing for all models from OpenRouter.
    Cached to avoid repeated API calls during a session.
    """
    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        pricing_map = {}
        for model in data.get("data", []):
            model_id = model.get("id")
            pricing = model.get("pricing", {})

            if model_id and pricing:
                pricing_map[model_id] = ModelPricing(
                    prompt_cost=float(pricing.get("prompt", 0)),
                    completion_cost=float(pricing.get("completion", 0)),
                    model_id=model_id,
                )

        return pricing_map

    except (requests.RequestException, ValueError) as e:
        print(f"Warning: Could not fetch pricing data: {e}")
        return {}


def get_model_pricing(model_id: str) -> ModelPricing | None:
    """Get pricing for a specific model."""
    pricing_map = fetch_all_pricing()
    return pricing_map.get(model_id)


def format_cost(cost_usd: float) -> str:
    """Format cost for display. Shows more precision for small amounts."""
    if cost_usd < 0.0001:
        return f"${cost_usd:.6f}"
    elif cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    else:
        return f"${cost_usd:.2f}"
