"""
Unit tests for the evaluation system.

Tests the evaluator logic with mocked judge responses.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add golden tests to path
golden_dir = Path(__file__).parent.parent / "golden"
sys.path.insert(0, str(golden_dir))

from evaluator import (
    EvaluationCriteria,
    JudgeEvaluator,
)
from judge_prompts import build_judge_prompt, format_context, format_criteria


class TestEvaluationCriteria:
    """Test criteria extraction and handling."""

    def test_basic_criteria_creation(self):
        """Test creating criteria with basic qualities."""
        criteria = EvaluationCriteria(
            qualities={"accurate": True, "concise": True},
            forbidden_patterns=["I don't know"],
        )

        assert criteria.qualities["accurate"] is True
        assert criteria.qualities["concise"] is True
        assert "I don't know" in criteria.forbidden_patterns

    def test_criteria_with_all_fields(self):
        """Test criteria with all optional fields."""
        criteria = EvaluationCriteria(
            qualities={"technical_depth": "high"},
            forbidden_patterns=["bad phrase"],
            expected_content=["Paris"],
            expected_themes=["geography"],
            min_length=100,
            max_length=500,
        )

        assert criteria.qualities["technical_depth"] == "high"
        assert criteria.min_length == 100
        assert criteria.max_length == 500
        assert "Paris" in criteria.expected_content


class TestJudgePrompts:
    """Test judge prompt building."""

    def test_format_criteria_boolean(self):
        """Test formatting boolean criteria."""
        qualities = {"accurate": True, "verbose": False}
        formatted = format_criteria(qualities)

        assert "accurate" in formatted
        assert "must be present" in formatted
        assert "verbose" in formatted
        assert "must not be present" in formatted

    def test_format_criteria_string(self):
        """Test formatting string criteria."""
        qualities = {"technical_depth": "high", "tone": "professional"}
        formatted = format_criteria(qualities)

        assert "technical_depth: high" in formatted
        assert "tone: professional" in formatted

    def test_format_context(self):
        """Test formatting context dict."""
        context = {
            "profile": "Software engineer",
            "preferences": "Be concise",
        }
        formatted = format_context(context)

        assert "PROFILE" in formatted
        assert "Software engineer" in formatted
        assert "PREFERENCES" in formatted
        assert "Be concise" in formatted

    def test_build_judge_prompt_reasoning(self):
        """Test building prompt for reasoning category."""
        messages = build_judge_prompt(
            category="reasoning",
            context={},
            user_message="What is 2+2?",
            actual_response="2+2 equals 4",
            criteria_qualities={"accurate": True},
            forbidden_patterns=[],
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "What is 2+2?" in messages[1]["content"]
        assert "2+2 equals 4" in messages[1]["content"]

    def test_build_judge_prompt_with_forbidden_patterns(self):
        """Test prompt building with forbidden patterns."""
        messages = build_judge_prompt(
            category="personalization",
            context={"preferences": "Be direct"},
            user_message="Explain APIs",
            actual_response="APIs are interfaces...",
            criteria_qualities={"direct": True},
            forbidden_patterns=["I'd be happy to", "Of course!"],
        )

        content = messages[1]["content"]
        assert "FORBIDDEN PATTERNS" in content
        assert "I'd be happy to" in content
        assert "Of course!" in content


class TestJudgeEvaluator:
    """Test judge evaluation logic."""

    @pytest.fixture
    def mock_judge_client(self):
        """Mock LLMClient for judge."""
        client = Mock()

        # Mock streaming response with valid JSON
        mock_stream = Mock()
        mock_stream.__iter__ = Mock(
            return_value=iter(
                [
                    '{"overall_score": 0.9, "dimension_scores": {"accurate": 1.0, "concise": 0.8}, ',
                    '"reasoning": "Test reasoning", "passed_criteria": ["accurate"], "failed_criteria": []}',
                ]
            )
        )
        mock_stream.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        mock_stream.raw_response = Mock()

        client.chat_stream.return_value = mock_stream
        return client

    def test_basic_evaluation(self, mock_judge_client):
        """Test basic evaluation flow."""
        evaluator = JudgeEvaluator(
            judge_client=mock_judge_client, config={"quality_threshold": 0.70}
        )

        criteria = EvaluationCriteria(qualities={"accurate": True})

        result = evaluator.evaluate_response(
            test_name="test",
            test_category="reasoning",
            context={},
            user_message="Test?",
            actual_response="Test response",
            criteria=criteria,
            model_tested="test-model",
            response_metrics={
                "latency_ms": 100,
                "tokens": {"prompt": 50, "completion": 25, "total": 75},
                "cost_usd": 0.005,
            },
        )

        assert result.passed is True
        assert result.evaluation.overall_score >= 0.70
        assert result.test_name == "test"
        assert result.test_category == "reasoning"

    def test_forbidden_patterns_detected(self, mock_judge_client):
        """Test forbidden pattern detection."""
        evaluator = JudgeEvaluator(
            judge_client=mock_judge_client, config={"quality_threshold": 0.70}
        )

        criteria = EvaluationCriteria(
            qualities={}, forbidden_patterns=["bad phrase", "terrible words"]
        )

        result = evaluator.evaluate_response(
            test_name="test",
            test_category="personalization",
            context={},
            user_message="Test?",
            actual_response="This contains bad phrase in it",
            criteria=criteria,
            model_tested="test-model",
            response_metrics={
                "latency_ms": 100,
                "tokens": {},
                "cost_usd": 0.005,
            },
        )

        assert "bad phrase" in result.evaluation.forbidden_patterns_found
        assert result.passed is False  # Forbidden patterns cause failure

    def test_multiple_forbidden_patterns(self, mock_judge_client):
        """Test detection of multiple forbidden patterns."""
        evaluator = JudgeEvaluator(
            judge_client=mock_judge_client, config={"quality_threshold": 0.70}
        )

        criteria = EvaluationCriteria(qualities={}, forbidden_patterns=["bad", "terrible"])

        result = evaluator.evaluate_response(
            test_name="test",
            test_category="personalization",
            context={},
            user_message="Test?",
            actual_response="This is bad and terrible",
            criteria=criteria,
            model_tested="test-model",
            response_metrics={
                "latency_ms": 100,
                "tokens": {},
                "cost_usd": 0.005,
            },
        )

        assert "bad" in result.evaluation.forbidden_patterns_found
        assert "terrible" in result.evaluation.forbidden_patterns_found
        assert len(result.evaluation.forbidden_patterns_found) == 2

    def test_expected_content_check(self, mock_judge_client):
        """Test expected content detection."""
        evaluator = JudgeEvaluator(
            judge_client=mock_judge_client, config={"quality_threshold": 0.70}
        )

        criteria = EvaluationCriteria(qualities={}, expected_content=["Paris", "France"])

        result = evaluator.evaluate_response(
            test_name="test",
            test_category="reasoning",
            context={},
            user_message="What is the capital of France?",
            actual_response="Paris is the capital of France.",
            criteria=criteria,
            model_tested="test-model",
            response_metrics={
                "latency_ms": 100,
                "tokens": {},
                "cost_usd": 0.005,
            },
        )

        assert result.evaluation.content_checks_passed is True

    def test_missing_expected_content(self, mock_judge_client):
        """Test missing expected content."""
        evaluator = JudgeEvaluator(
            judge_client=mock_judge_client, config={"quality_threshold": 0.70}
        )

        criteria = EvaluationCriteria(qualities={}, expected_content=["Paris", "France"])

        result = evaluator.evaluate_response(
            test_name="test",
            test_category="reasoning",
            context={},
            user_message="What is the capital of France?",
            actual_response="I don't know.",
            criteria=criteria,
            model_tested="test-model",
            response_metrics={
                "latency_ms": 100,
                "tokens": {},
                "cost_usd": 0.005,
            },
        )

        assert result.evaluation.content_checks_passed is False

    def test_fallback_on_judge_failure(self):
        """Test fallback evaluation when judge fails."""
        # Mock client that raises exception
        mock_client = Mock()
        mock_client.chat_stream.side_effect = Exception("API error")

        evaluator = JudgeEvaluator(judge_client=mock_client, config={"quality_threshold": 0.70})

        criteria = EvaluationCriteria(qualities={"accurate": True})

        result = evaluator.evaluate_response(
            test_name="test",
            test_category="reasoning",
            context={},
            user_message="Test?",
            actual_response="Test response",
            criteria=criteria,
            model_tested="test-model",
            response_metrics={
                "latency_ms": 100,
                "tokens": {},
                "cost_usd": 0.005,
            },
        )

        # Should still return a result (fallback)
        assert result is not None
        assert "failed" in result.evaluation.reasoning.lower()
        assert result.judge_cost_usd == 0.0  # No judge call succeeded

    def test_parse_valid_json_response(self):
        """Test parsing valid JSON from judge."""
        evaluator = JudgeEvaluator(judge_client=Mock(), config={"quality_threshold": 0.70})

        json_response = """{
            "overall_score": 0.85,
            "dimension_scores": {"accurate": 0.9, "concise": 0.8},
            "reasoning": "Good response",
            "passed_criteria": ["accurate", "concise"],
            "failed_criteria": []
        }"""

        parsed = evaluator._parse_judge_response(json_response)

        assert parsed["overall_score"] == 0.85
        assert parsed["dimension_scores"]["accurate"] == 0.9
        assert parsed["reasoning"] == "Good response"
        assert "accurate" in parsed["passed_criteria"]

    def test_parse_malformed_json_fallback(self):
        """Test fallback parsing for malformed JSON."""
        evaluator = JudgeEvaluator(judge_client=Mock(), config={"quality_threshold": 0.70})

        # Malformed JSON with score in text
        bad_response = "The overall score is 0.75 based on the criteria"

        parsed = evaluator._parse_judge_response(bad_response)

        assert "overall_score" in parsed
        assert 0.0 <= parsed["overall_score"] <= 1.0
        assert "Fallback parsing" in parsed["reasoning"]

    def test_result_to_dict_serialization(self, mock_judge_client):
        """Test EvaluationResult can be serialized to dict."""
        evaluator = JudgeEvaluator(
            judge_client=mock_judge_client, config={"quality_threshold": 0.70}
        )

        criteria = EvaluationCriteria(qualities={"accurate": True})

        result = evaluator.evaluate_response(
            test_name="test",
            test_category="reasoning",
            context={"profile": "Test user"},
            user_message="Test?",
            actual_response="Test response",
            criteria=criteria,
            model_tested="test-model",
            response_metrics={
                "latency_ms": 100,
                "tokens": {"prompt": 50, "completion": 25, "total": 75},
                "cost_usd": 0.005,
            },
        )

        # Convert to dict for JSON serialization
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["test_name"] == "test"
        assert isinstance(result_dict["evaluation"], dict)
        assert "overall_score" in result_dict["evaluation"]
