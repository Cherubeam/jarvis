"""
Integration tests for pricing system.

Tests LiteLLM cost map integration and cost calculation in realistic scenarios.
"""

import pytest
from unittest.mock import Mock, patch
from packages.core.pricing import (
    ModelPricing,
    get_model_pricing,
    calculate_cost_from_litellm,
    format_cost,
)


@pytest.mark.integration
class TestPricingIntegration:
    """Integration tests for pricing system."""

    def test_pricing_fetch_and_calculate(self):
        """Test fetching pricing from LiteLLM cost map and calculating cost."""
        mock_cost_map = {
            "anthropic/claude-sonnet-4.6": {
                "input_cost_per_token": 0.000003,
                "output_cost_per_token": 0.000015,
            }
        }
        with patch('packages.core.pricing._get_litellm_cost_map', return_value=mock_cost_map):
            # Get specific model pricing
            claude_pricing = get_model_pricing("anthropic/claude-sonnet-4.6")
            assert claude_pricing is not None

            # Calculate cost for a request
            prompt_tokens = 1000
            completion_tokens = 500

            cost = claude_pricing.calculate_cost(prompt_tokens, completion_tokens)

            # Expected: (1000 * 0.000003) + (500 * 0.000015) = 0.003 + 0.0075 = 0.0105
            assert cost == pytest.approx(0.0105)

            # Format the cost
            # Note: 0.0105 >= 0.01, so format_cost uses 2 decimals
            formatted = format_cost(cost)
            assert formatted == "$0.01"  # Rounded from 0.0105

    def test_pricing_fallback_to_litellm(self):
        """Test fallback to LiteLLM cost calculation when pricing unavailable."""
        with patch('packages.core.pricing._get_litellm_cost_map', return_value={}):
            # Pricing lookup will return None for unknown model
            pricing = get_model_pricing("anthropic/claude-sonnet-4.6")
            assert pricing is None

        # Now try fallback via LiteLLM completion_cost
        mock_response = Mock()

        with patch('litellm.completion_cost') as mock_cost:
            mock_cost.return_value = 0.0042

            cost = calculate_cost_from_litellm(mock_response)

            assert cost == 0.0042

    def test_pricing_display_format(self):
        """Test cost display formatting in various scenarios."""
        # Create a pricing object
        pricing = ModelPricing(
            prompt_cost=0.000003,
            completion_cost=0.000015,
            model_id="test-model"
        )

        # Test various token counts and their formatted costs
        # Format rules: <0.0001=6 decimals, <0.01=4 decimals, >=0.01=2 decimals
        test_cases = [
            # (prompt_tokens, completion_tokens, expected_format)
            (100, 50, "$0.0011"),      # 0.00105 < 0.01, so 4 decimals -> $0.0011 (rounded)
            (1000, 500, "$0.01"),      # 0.0105 >= 0.01, so 2 decimals -> $0.01 (rounded)
            (10000, 5000, "$0.10"),    # 0.105 >= 0.01, so 2 decimals -> $0.10 (banker's rounding)
            (100000, 50000, "$1.05"),  # 1.05 >= 0.01, so 2 decimals -> $1.05
        ]

        for prompt_tokens, completion_tokens, expected_format in test_cases:
            cost = pricing.calculate_cost(prompt_tokens, completion_tokens)
            formatted = format_cost(cost)

            # Check the formatted string matches expected
            assert formatted == expected_format
