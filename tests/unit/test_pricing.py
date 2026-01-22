"""
Unit tests for pricing module.

Tests model pricing, cost calculation, and API interactions.
"""

import pytest
from unittest.mock import Mock, patch
import requests

# Try new import path first, fall back to old for backward compatibility
try:
    from packages.core.pricing import (
        ModelPricing,
        fetch_all_pricing,
        get_model_pricing,
        calculate_cost_from_litellm,
        format_cost
    )
    PRICING_MODULE = "packages.core.pricing"
except ImportError:
    from pricing import (
        ModelPricing,
        fetch_all_pricing,
        get_model_pricing,
        calculate_cost_from_litellm,
        format_cost
    )
    PRICING_MODULE = "pricing"


@pytest.mark.unit
class TestModelPricing:
    """Tests for ModelPricing dataclass."""

    def test_model_pricing_calculate_cost(self):
        """Test that cost calculation is correct."""
        pricing = ModelPricing(
            prompt_cost=0.000003,  # $3 per 1M tokens
            completion_cost=0.000015,  # $15 per 1M tokens
            model_id="test-model"
        )

        cost = pricing.calculate_cost(1000, 200)

        # (1000 * 0.000003) + (200 * 0.000015) = 0.003 + 0.003 = 0.006
        assert cost == pytest.approx(0.006)

    def test_model_pricing_zero_tokens(self):
        """Test that zero tokens returns zero cost."""
        pricing = ModelPricing(
            prompt_cost=0.000003,
            completion_cost=0.000015,
            model_id="test-model"
        )

        cost = pricing.calculate_cost(0, 0)
        assert cost == 0.0

    def test_model_pricing_large_numbers(self):
        """Test handling of large token counts."""
        pricing = ModelPricing(
            prompt_cost=0.000003,
            completion_cost=0.000015,
            model_id="test-model"
        )

        # 1 million prompt tokens, 500k completion tokens
        cost = pricing.calculate_cost(1_000_000, 500_000)

        # (1M * 0.000003) + (500k * 0.000015) = 3.0 + 7.5 = 10.5
        assert cost == pytest.approx(10.5)


@pytest.mark.unit
class TestFetchAllPricing:
    """Tests for fetch_all_pricing function."""

    def test_fetch_all_pricing_success(self, sample_pricing_data):
        """Test successful fetching and parsing of pricing data."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = sample_pricing_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Clear cache first
            fetch_all_pricing.cache_clear()

            result = fetch_all_pricing()

            # Check API was called
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "openrouter.ai/api/v1/models" in call_args[0][0]

            # Check pricing was parsed correctly
            assert "anthropic/claude-sonnet-4.5" in result
            claude_pricing = result["anthropic/claude-sonnet-4.5"]
            assert claude_pricing.prompt_cost == 0.000003
            assert claude_pricing.completion_cost == 0.000015

    def test_fetch_all_pricing_cached(self, sample_pricing_data):
        """Test that pricing is cached and API is only called once."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = sample_pricing_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Clear cache first
            fetch_all_pricing.cache_clear()

            # First call
            result1 = fetch_all_pricing()
            # Second call
            result2 = fetch_all_pricing()

            # API should only be called once due to caching
            assert mock_get.call_count == 1
            assert result1 == result2

    def test_fetch_all_pricing_api_error(self):
        """Test graceful handling of network errors."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")

            # Clear cache first
            fetch_all_pricing.cache_clear()

            result = fetch_all_pricing()

            # Should return empty dict on error
            assert result == {}


@pytest.mark.unit
class TestGetModelPricing:
    """Tests for get_model_pricing function."""

    def test_get_model_pricing_found(self, sample_pricing_data):
        """Test getting pricing for an existing model."""
        with patch(f'{PRICING_MODULE}.fetch_all_pricing') as mock_fetch:
            mock_fetch.return_value = {
                "anthropic/claude-sonnet-4.5": ModelPricing(
                    prompt_cost=0.000003,
                    completion_cost=0.000015,
                    model_id="anthropic/claude-sonnet-4.5"
                )
            }

            result = get_model_pricing("anthropic/claude-sonnet-4.5")

            assert result is not None
            assert result.model_id == "anthropic/claude-sonnet-4.5"
            assert result.prompt_cost == 0.000003

    def test_get_model_pricing_not_found(self):
        """Test that None is returned for unknown models."""
        with patch(f'{PRICING_MODULE}.fetch_all_pricing') as mock_fetch:
            mock_fetch.return_value = {}

            result = get_model_pricing("unknown-model")

            assert result is None

    def test_get_model_pricing_strips_prefix(self):
        """Test that 'openrouter/' prefix is stripped for lookup."""
        with patch(f'{PRICING_MODULE}.fetch_all_pricing') as mock_fetch:
            mock_fetch.return_value = {
                "anthropic/claude-sonnet-4.5": ModelPricing(
                    prompt_cost=0.000003,
                    completion_cost=0.000015,
                    model_id="anthropic/claude-sonnet-4.5"
                )
            }

            # Pass with openrouter/ prefix
            result = get_model_pricing("openrouter/anthropic/claude-sonnet-4.5")

            # Should still find the model
            assert result is not None
            assert result.model_id == "anthropic/claude-sonnet-4.5"


@pytest.mark.unit
class TestCalculateCostFromLiteLLM:
    """Tests for calculate_cost_from_litellm function."""

    def test_calculate_cost_from_litellm_success(self):
        """Test successful cost calculation via LiteLLM."""
        mock_response = Mock()

        with patch('litellm.completion_cost') as mock_cost:
            mock_cost.return_value = 0.0042

            result = calculate_cost_from_litellm(mock_response)

            assert result == 0.0042
            mock_cost.assert_called_once_with(completion_response=mock_response)

    def test_calculate_cost_from_litellm_error(self):
        """Test graceful handling of errors."""
        mock_response = Mock()

        with patch('litellm.completion_cost') as mock_cost:
            mock_cost.side_effect = Exception("Cost calculation failed")

            result = calculate_cost_from_litellm(mock_response)

            # Should return 0.0 on error
            assert result == 0.0


@pytest.mark.unit
class TestFormatCost:
    """Tests for format_cost function."""

    def test_format_cost_very_small(self):
        """Test formatting of very small costs (< $0.0001)."""
        result = format_cost(0.000042)
        assert result == "$0.000042"

    def test_format_cost_small(self):
        """Test formatting of small costs (< $0.01)."""
        result = format_cost(0.0042)
        assert result == "$0.0042"

    def test_format_cost_medium(self):
        """Test formatting of medium costs (≥ $0.01)."""
        result = format_cost(0.42)
        assert result == "$0.42"

    def test_format_cost_large(self):
        """Test formatting of large costs."""
        result = format_cost(42.567)
        assert result == "$42.57"

    def test_format_cost_zero(self):
        """Test formatting of zero cost."""
        result = format_cost(0.0)
        assert result == "$0.000000"
