"""
Unit tests for intelligent model routing.
"""

import pytest

from packages.core.model_router import classify_query, route_query, RoutingDecision


_SAMPLE_CONFIG = {
    "models": {
        "default": "openrouter/anthropic/claude-sonnet-4.6",
        "presets": {
            "fast": "openrouter/google/gemini-2.0-flash",
            "quality": "openrouter/anthropic/claude-opus-4.6",
            "balanced": "openrouter/anthropic/claude-sonnet-4.6",
        },
    },
    "routing": {
        "enabled": True,
        "simple_threshold": 200,
        "complex_threshold": 800,
    },
}


@pytest.mark.unit
class TestClassifyQuery:
    """Tests for classify_query heuristics."""

    def test_short_greeting_routes_to_fast(self):
        preset, reason, confidence = classify_query("Hello!", _SAMPLE_CONFIG)
        assert preset == "fast"

    def test_short_question_routes_to_fast(self):
        preset, _, _ = classify_query("What time is it?", _SAMPLE_CONFIG)
        assert preset == "fast"

    def test_long_query_routes_to_quality(self):
        long_query = "Please explain " + "the details of " * 60
        preset, _, _ = classify_query(long_query, _SAMPLE_CONFIG)
        assert preset == "quality"

    def test_code_block_routes_to_quality(self):
        query = "Fix this:\n```python\ndef foo(): pass\n```"
        preset, reason, _ = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "quality"
        assert "code" in reason

    def test_multi_part_and_numbered_list_routes_to_quality(self):
        query = "Additionally, please:\n1. Do this\n2. Do that"
        preset, _, _ = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "quality"

    def test_medium_query_routes_to_balanced(self):
        query = "Can you explain how the agent framework works in this project and how agents are discovered? " * 3
        preset, _, _ = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "balanced"

    def test_developer_agent_always_quality(self):
        preset, reason, _ = classify_query("hi", _SAMPLE_CONFIG, agent_name="developer")
        assert preset == "quality"
        assert "developer" in reason

    def test_writing_agent_always_quality(self):
        preset, _, _ = classify_query("hi", _SAMPLE_CONFIG, agent_name="writing")
        assert preset == "quality"

    def test_research_agent_not_forced_to_quality(self):
        preset, _, _ = classify_query("hi", _SAMPLE_CONFIG, agent_name="research")
        assert preset == "fast"  # short query, no special agent override

    def test_custom_thresholds_respected(self):
        config = {
            **_SAMPLE_CONFIG,
            "routing": {"simple_threshold": 10, "complex_threshold": 50},
        }
        # 15 chars > simple_threshold=10 but < complex_threshold=50 → balanced
        preset, _, _ = classify_query("A medium query!", config)
        assert preset == "balanced"

    def test_confidence_is_between_0_and_1(self):
        for query in ["hi", "x" * 1000, "```code```"]:
            _, _, confidence = classify_query(query, _SAMPLE_CONFIG)
            assert 0.0 <= confidence <= 1.0


@pytest.mark.unit
class TestRouteQuery:
    """Tests for route_query end-to-end."""

    def test_returns_routing_decision(self):
        decision = route_query("hello", _SAMPLE_CONFIG)
        assert isinstance(decision, RoutingDecision)

    def test_fast_preset_resolves_to_fast_model(self):
        decision = route_query("hi", _SAMPLE_CONFIG)
        assert decision.preset == "fast"
        assert "gemini" in decision.resolved.model_id

    def test_quality_preset_resolves_to_quality_model(self):
        decision = route_query("hi", _SAMPLE_CONFIG, agent_name="developer")
        assert decision.preset == "quality"
        assert "opus" in decision.resolved.model_id

    def test_balanced_preset_resolves_to_balanced_model(self):
        query = "Can you explain how the agent framework works in this project and how agents are discovered? " * 3
        decision = route_query(query, _SAMPLE_CONFIG)
        assert decision.preset == "balanced"
        assert "sonnet" in decision.resolved.model_id
