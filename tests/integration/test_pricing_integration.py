"""
Integration tests for pricing system.

Tests pricing API interaction and cost calculation in realistic scenarios.
"""

import pytest
import requests
from unittest.mock import Mock, patch
from pricing import (
    ModelPricing,
    fetch_all_pricing,
    get_model_pricing,
    calculate_cost_from_litellm,
    format_cost
)


@pytest.mark.integration
class TestPricingIntegration:
    """Integration tests for pricing system."""

    def test_pricing_fetch_and_calculate(self, sample_pricing_data):
        """Test fetching pricing from API and calculating cost."""
        with patch('requests.get') as mock_get:
            # Mock successful API response
            mock_response = Mock()
            mock_response.json.return_value = sample_pricing_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Clear cache
            fetch_all_pricing.cache_clear()

            # Fetch pricing
            pricing_map = fetch_all_pricing()

            # Get specific model pricing
            claude_pricing = pricing_map.get("anthropic/claude-sonnet-4.5")
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
        """Test fallback to LiteLLM cost calculation when OpenRouter unavailable."""
        # Mock OpenRouter API failure with requests.RequestException
        with patch('requests.get') as mock_get:
            # Raise a RequestException instead of generic Exception
            mock_get.side_effect = requests.RequestException("API unavailable")

            # Clear cache
            fetch_all_pricing.cache_clear()

            # Try to get pricing (will fail gracefully and return {})
            pricing_map = fetch_all_pricing()
            assert pricing_map == {}

            # Pricing lookup will return None
            pricing = get_model_pricing("anthropic/claude-sonnet-4.5")
            assert pricing is None

        # Now try fallback via LiteLLM
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
