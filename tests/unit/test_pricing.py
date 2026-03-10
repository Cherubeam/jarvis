"""
Unit tests for pricing module.

Tests model pricing, cost calculation, and LiteLLM cost map integration.
"""

import pytest
from unittest.mock import Mock, patch

try:
    from packages.core.pricing import (
        ModelPricing,
        get_model_pricing,
        calculate_cost_from_litellm,
        format_cost,
        _get_litellm_cost_map,
    )
    PRICING_MODULE = "packages.core.pricing"
except ImportError:
    from pricing import (
        ModelPricing,
        get_model_pricing,
        calculate_cost_from_litellm,
        format_cost,
        _get_litellm_cost_map,
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
class TestGetModelPricing:
    """Tests for get_model_pricing function using LiteLLM cost map."""

    def test_get_model_pricing_found(self):
        """Test getting pricing for an existing model."""
        mock_cost_map = {
            "anthropic/claude-sonnet-4.6": {
                "input_cost_per_token": 0.000003,
                "output_cost_per_token": 0.000015,
            }
        }
        with patch(f'{PRICING_MODULE}._get_litellm_cost_map', return_value=mock_cost_map):
            result = get_model_pricing("anthropic/claude-sonnet-4.6")

        assert result is not None
        assert result.prompt_cost == 0.000003
        assert result.completion_cost == 0.000015

    def test_get_model_pricing_not_found(self):
        """Test that None is returned for unknown models."""
        with patch(f'{PRICING_MODULE}._get_litellm_cost_map', return_value={}):
            result = get_model_pricing("unknown-model")
        assert result is None

    def test_get_model_pricing_strips_provider_prefix(self):
        """Test that provider prefix is stripped for lookup as fallback."""
        mock_cost_map = {
            "anthropic/claude-sonnet-4.6": {
                "input_cost_per_token": 0.000003,
                "output_cost_per_token": 0.000015,
            }
        }
        with patch(f'{PRICING_MODULE}._get_litellm_cost_map', return_value=mock_cost_map):
            # Pass with openrouter/ prefix — should strip and find
            result = get_model_pricing("openrouter/anthropic/claude-sonnet-4.6")

        assert result is not None
        assert result.model_id == "openrouter/anthropic/claude-sonnet-4.6"

    def test_get_model_pricing_tries_full_id_first(self):
        """Test that full model ID is tried before stripping prefix."""
        mock_cost_map = {
            "openrouter/anthropic/claude-sonnet-4.6": {
                "input_cost_per_token": 0.000001,
                "output_cost_per_token": 0.000002,
            },
            "anthropic/claude-sonnet-4.6": {
                "input_cost_per_token": 0.000003,
                "output_cost_per_token": 0.000015,
            },
        }
        with patch(f'{PRICING_MODULE}._get_litellm_cost_map', return_value=mock_cost_map):
            result = get_model_pricing("openrouter/anthropic/claude-sonnet-4.6")

        # Should use the full ID match
        assert result is not None
        assert result.prompt_cost == 0.000001


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
        """Test formatting of medium costs (>= $0.01)."""
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
