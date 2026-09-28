"""The golden harness takes its pass marks, results dir and model under test from config.

No network: the judge is a mock, and the pytest options/fixtures are read, not run.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

golden_dir = Path(__file__).parent.parent / "golden"
sys.path.insert(0, str(golden_dir))

from evaluator import EvaluationCriteria, JudgeEvaluator, resolve_thresholds

from packages.core.model_resolver import AUTO_MODEL_ID
from packages.core.settings import load_config
from tests.golden.test_golden_conversations import resolve_model_under_test

REPO_ROOT = Path(__file__).resolve().parents[2]


def _judge_scoring(score: float) -> Mock:
    """Mock judge client whose streamed JSON gives every case the same overall score."""
    stream = Mock()
    stream.__iter__ = Mock(
        return_value=iter(
            [
                f'{{"overall_score": {score}, "dimension_scores": {{"accurate": {score}}}, ',
                '"reasoning": "r", "passed_criteria": [], "failed_criteria": []}',
            ]
        )
    )
    stream.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    stream.raw_response = Mock()
    client = Mock()
    client.chat_stream.return_value = stream
    return client


def _evaluate(evaluator: JudgeEvaluator, category: str):
    return evaluator.evaluate_response(
        test_name="t",
        test_category=category,
        context={},
        user_message="q",
        actual_response="a",
        criteria=EvaluationCriteria(qualities={"accurate": True}),
        model_tested="m",
        response_metrics={"latency_ms": 1, "tokens": {}, "cost_usd": 0.0},
    )


class TestResolveThresholds:
    def test_without_cli_flag_uses_config_base_and_categories(self) -> None:
        categories = {"reasoning": 0.75}
        base, per_category = resolve_thresholds(None, 0.70, categories)
        assert base == 0.70
        assert per_category == {"reasoning": 0.75}
        assert per_category is not categories  # a copy, not the settings object

    def test_cli_flag_is_one_mark_for_every_case(self) -> None:
        assert resolve_thresholds(0.80, 0.70, {"reasoning": 0.75}) == (0.80, {})


class TestCategoryThresholds:
    def test_threshold_for_falls_back_to_base(self) -> None:
        evaluator = JudgeEvaluator(
            judge_client=Mock(),
            config={"quality_threshold": 0.70, "category_thresholds": {"reasoning": 0.75}},
        )
        assert evaluator.threshold_for("reasoning") == 0.75
        assert evaluator.threshold_for("tool_use") == 0.70

    def test_no_category_thresholds_key_means_base_only(self) -> None:
        evaluator = JudgeEvaluator(judge_client=Mock(), config={"quality_threshold": 0.70})
        assert evaluator.threshold_for("reasoning") == 0.70

    @pytest.mark.parametrize(
        ("category", "passed", "threshold"), [("reasoning", False, 0.75), ("tool_use", True, 0.70)]
    )
    def test_pass_mark_depends_on_category(self, category: str, passed: bool, threshold: float) -> None:
        evaluator = JudgeEvaluator(
            judge_client=_judge_scoring(0.72),
            config={"quality_threshold": 0.70, "category_thresholds": {"reasoning": 0.75}},
        )
        result = _evaluate(evaluator, category)
        assert result.evaluation.overall_score == pytest.approx(0.72)
        assert result.passed is passed
        assert result.quality_threshold == threshold  # stored per result, used by the agentic re-check


class TestConftestDefaults:
    def test_quality_threshold_flag_defaults_to_unset(self, pytestconfig: pytest.Config) -> None:
        # None, so config's quality_threshold + category_thresholds apply; the flag overrides both
        assert pytestconfig.getoption("--quality-threshold") is None

    def test_judge_model_flag_defaults_to_config(self, pytestconfig: pytest.Config) -> None:
        assert pytestconfig.getoption("--judge-model") == load_config().evaluation.judge_model

    def test_evaluation_config_reads_thresholds_from_config(self, evaluation_config: dict) -> None:
        settings = load_config().evaluation
        assert evaluation_config["quality_threshold"] == settings.quality_threshold
        assert evaluation_config["category_thresholds"] == settings.category_thresholds

    def test_result_storage_uses_results_dir_from_repo_root(self, result_storage) -> None:
        assert result_storage.results_dir == REPO_ROOT / load_config().evaluation.results_dir


class TestModelUnderTest:
    def test_falls_back_to_models_default(self) -> None:
        default = load_config().models.default
        label, model_id = resolve_model_under_test(None, default)
        assert model_id == default  # already LiteLLM form: no second openrouter/ prefix
        assert label == default.removeprefix("openrouter/")

    def test_empty_env_counts_as_unset(self) -> None:
        assert resolve_model_under_test("", "openrouter/openai/gpt-6-luna") == (
            "openai/gpt-6-luna",
            "openrouter/openai/gpt-6-luna",
        )

    def test_env_openrouter_id_gets_prefixed(self) -> None:
        assert resolve_model_under_test("anthropic/claude-opus-5.5", "openrouter/openai/gpt-6-luna") == (
            "anthropic/claude-opus-5.5",
            "openrouter/anthropic/claude-opus-5.5",
        )

    def test_env_litellm_id_kept_and_label_matches_bare_form(self) -> None:
        bare = resolve_model_under_test("openai/gpt-6-luna", "x")
        prefixed = resolve_model_under_test("openrouter/openai/gpt-6-luna", "x")
        assert prefixed == bare

    def test_auto_uses_auto_router(self) -> None:
        assert resolve_model_under_test("auto", "openrouter/openai/gpt-6-luna") == ("auto", AUTO_MODEL_ID)
