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
        assert reason == "short simple query"
        assert confidence == 0.8

    def test_short_question_routes_to_fast(self):
        preset, reason, confidence = classify_query("What time is it?", _SAMPLE_CONFIG)
        assert preset == "fast"
        assert reason == "short simple query"
        assert confidence == 0.8

    def test_long_query_routes_to_quality(self):
        long_query = "Please explain " + "the details of " * 60
        preset, reason, confidence = classify_query(long_query, _SAMPLE_CONFIG)
        assert preset == "quality"
        assert reason == "complex query detected"
        assert confidence == 0.8

    def test_code_block_routes_to_quality(self):
        query = "Fix this:\n```python\ndef foo(): pass\n```"
        preset, reason, confidence = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "quality"
        assert reason == "code block detected"
        assert confidence == 0.85

    def test_multi_part_and_numbered_list_routes_to_quality(self):
        query = "Additionally, please:\n1. Do this\n2. Do that"
        preset, reason, confidence = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "quality"
        assert reason == "complex query detected"
        assert confidence == 0.8

    def test_medium_query_routes_to_balanced(self):
        query = "Can you explain how the agent framework works in this project and how agents are discovered? " * 3
        preset, reason, confidence = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "balanced"
        assert reason == "moderate complexity"
        assert confidence == 0.6

    def test_developer_agent_always_quality(self):
        preset, reason, confidence = classify_query("hi", _SAMPLE_CONFIG, agent_name="developer")
        assert preset == "quality"
        assert reason == "agent 'developer' always uses quality model"
        assert confidence == 0.95

    def test_writer_agent_always_quality(self):
        preset, reason, confidence = classify_query("hi", _SAMPLE_CONFIG, agent_name="writer")
        assert preset == "quality"
        assert reason == "agent 'writer' always uses quality model"
        assert confidence == 0.95

    def test_researcher_agent_not_forced_to_quality(self):
        preset, reason, _ = classify_query("hi", _SAMPLE_CONFIG, agent_name="researcher")
        assert preset == "fast"  # short query, no special agent override
        assert reason == "short simple query"

    def test_custom_thresholds_respected(self):
        config = {
            **_SAMPLE_CONFIG,
            "routing": {"simple_threshold": 10, "complex_threshold": 50},
        }
        # 15 chars > simple_threshold=10 but < complex_threshold=50 → balanced
        preset, reason, _ = classify_query("A medium query!", config)
        assert preset == "balanced"
        assert reason == "moderate complexity"

    def test_confidence_is_between_0_and_1(self):
        for query in ["hi", "x" * 1000, "```code```"]:
            _, _, confidence = classify_query(query, _SAMPLE_CONFIG)
            assert 0.0 <= confidence <= 1.0

    def test_boundary_at_simple_threshold(self):
        """Query exactly at simple_threshold (200 chars) with no signals → balanced."""
        query = "x" * 200
        preset, reason, _ = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "balanced"
        assert reason == "moderate complexity"

    def test_boundary_below_simple_threshold(self):
        """Query at 199 chars (< 200) with no signals → fast."""
        query = "x" * 199
        preset, reason, _ = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "fast"
        assert reason == "short simple query"

    def test_boundary_at_complex_threshold(self):
        """Query at exactly 800 chars with no signals → balanced (not quality)."""
        query = "x" * 800
        preset, reason, _ = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "balanced"
        assert reason == "moderate complexity"

    def test_boundary_above_complex_threshold(self):
        """Query at 801 chars → quality."""
        query = "x" * 801
        preset, reason, _ = classify_query(query, _SAMPLE_CONFIG)
        assert preset == "quality"
        assert reason == "complex query detected"

    def test_default_thresholds_when_routing_config_missing(self):
        """When routing config is empty, defaults are used (200/800)."""
        config = {"models": _SAMPLE_CONFIG["models"]}
        preset, _, _ = classify_query("hi", config)
        assert preset == "fast"

    def test_all_quality_agents(self):
        """All agents in the quality set route to quality."""
        for agent in ("developer", "writer", "content_reviewer", "substack_publisher"):
            preset, _, _ = classify_query("hi", _SAMPLE_CONFIG, agent_name=agent)
            assert preset == "quality", f"{agent} should route to quality"


@pytest.mark.unit
class TestRouteQuery:
    """Tests for route_query end-to-end."""

    def test_returns_routing_decision(self):
        decision = route_query("hello", _SAMPLE_CONFIG)
        assert isinstance(decision, RoutingDecision)

    def test_fast_preset_resolves_to_fast_model(self):
        decision = route_query("hi", _SAMPLE_CONFIG)
        assert decision.preset == "fast"
        assert decision.resolved.model_id == "openrouter/google/gemini-2.0-flash"
        assert decision.reason == "short simple query"
        assert decision.confidence == 0.8

    def test_quality_preset_resolves_to_quality_model(self):
        decision = route_query("hi", _SAMPLE_CONFIG, agent_name="developer")
        assert decision.preset == "quality"
        assert decision.resolved.model_id == "openrouter/anthropic/claude-opus-4.6"
        assert decision.reason == "agent 'developer' always uses quality model"
        assert decision.confidence == 0.95

    def test_balanced_preset_resolves_to_balanced_model(self):
        query = "Can you explain how the agent framework works in this project and how agents are discovered? " * 3
        decision = route_query(query, _SAMPLE_CONFIG)
        assert decision.preset == "balanced"
        assert decision.resolved.model_id == "openrouter/anthropic/claude-sonnet-4.6"
        assert decision.reason == "moderate complexity"
        assert decision.confidence == 0.6
