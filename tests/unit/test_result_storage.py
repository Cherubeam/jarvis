"""
Unit tests for result storage and reporting.

Tests the storage, markdown generation, and historical tracking.
"""

import json
import sys
from pathlib import Path

import pytest

# Add golden tests to path
golden_dir = Path(__file__).parent.parent / "golden"
sys.path.insert(0, str(golden_dir))

from evaluator import EvaluationResult, EvaluationScore
from result_storage import ResultStorage, RunSummary


@pytest.fixture
def sample_evaluation_result():
    """Create a sample evaluation result for testing."""
    return EvaluationResult(
        test_name="test_basic_qa",
        timestamp="2026-01-20T15:30:45Z",
        model_tested="anthropic/claude-sonnet-4.5",
        judge_model="anthropic/claude-opus-4.5",
        test_category="reasoning",
        context={"profile": "Test user"},
        user_message="What is 2+2?",
        actual_response="2+2 equals 4.",
        evaluation=EvaluationScore(
            overall_score=0.95,
            dimension_scores={"accurate": 1.0, "concise": 0.9},
            reasoning="Perfect answer",
            passed_criteria=["accurate", "concise"],
            failed_criteria=[],
            forbidden_patterns_found=[],
            content_checks_passed=True,
            themes_present=["mathematics"],
        ),
        passed=True,
        quality_threshold=0.70,
        response_cost_usd=0.007,
        judge_cost_usd=0.011,
        total_cost_usd=0.018,
        response_latency_ms=850,
        judge_latency_ms=1200,
        response_tokens={"prompt": 245, "completion": 12, "total": 257},
        judge_tokens={"prompt": 420, "completion": 185, "total": 605},
    )


@pytest.fixture
def sample_failed_result():
    """Create a sample failed evaluation result."""
    return EvaluationResult(
        test_name="test_ambiguous_query",
        timestamp="2026-01-20T15:31:00Z",
        model_tested="anthropic/claude-sonnet-4.5",
        judge_model="anthropic/claude-opus-4.5",
        test_category="edge_cases",
        context={},
        user_message="What should I do?",
        actual_response="You could do many things.",
        evaluation=EvaluationScore(
            overall_score=0.62,
            dimension_scores={"asks_clarification": 0.5, "offers_suggestions": 0.6},
            reasoning="Did not seek sufficient context",
            passed_criteria=[],
            failed_criteria=["asks_clarification"],
            forbidden_patterns_found=[],
            content_checks_passed=False,
            themes_present=[],
        ),
        passed=False,
        quality_threshold=0.70,
        response_cost_usd=0.008,
        judge_cost_usd=0.012,
        total_cost_usd=0.020,
        response_latency_ms=920,
        judge_latency_ms=1150,
        response_tokens={"prompt": 250, "completion": 30, "total": 280},
        judge_tokens={"prompt": 430, "completion": 190, "total": 620},
    )


class TestResultStorage:
    """Test result storage functionality."""

    def test_initialization_creates_directories(self, tmp_path):
        """Test that initialization creates necessary directories."""
        ResultStorage(tmp_path / "results")

        assert (tmp_path / "results" / "runs").exists()
        assert (tmp_path / "results" / "reports").exists()

    def test_start_run_creates_run_directory(self, tmp_path):
        """Test that start_run creates a timestamped directory."""
        storage = ResultStorage(tmp_path / "results")

        run_id = storage.start_run(model_tested="test-model", judge_model="judge-model")

        assert run_id is not None
        assert (tmp_path / "results" / "runs" / run_id).exists()

    def test_save_result_creates_json_file(self, tmp_path, sample_evaluation_result):
        """Test that save_result creates a JSON file."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        storage.save_result(run_id, sample_evaluation_result)

        result_file = tmp_path / "results" / "runs" / run_id / "test_basic_qa.json"
        assert result_file.exists()

        # Verify JSON is valid
        with open(result_file) as f:
            data = json.load(f)
            assert data["test_name"] == "test_basic_qa"
            assert data["evaluation"]["overall_score"] == 0.95

    def test_calculate_summary_single_result(self, tmp_path, sample_evaluation_result):
        """Test summary calculation with single result."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        summary = storage._calculate_summary(run_id, [sample_evaluation_result])

        assert summary.total_tests == 1
        assert summary.passed_tests == 1
        assert summary.failed_tests == 0
        assert summary.pass_rate == 1.0
        assert summary.average_overall_score == 0.95
        assert summary.total_cost_usd == 0.018

    def test_calculate_summary_multiple_results(self, tmp_path, sample_evaluation_result, sample_failed_result):
        """Test summary calculation with multiple results."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        results = [sample_evaluation_result, sample_failed_result]
        summary = storage._calculate_summary(run_id, results)

        assert summary.total_tests == 2
        assert summary.passed_tests == 1
        assert summary.failed_tests == 1
        assert summary.pass_rate == 0.5
        assert summary.average_overall_score == pytest.approx((0.95 + 0.62) / 2, 0.01)
        assert summary.total_cost_usd == pytest.approx(0.038, 0.001)

    def test_calculate_summary_by_category(self, tmp_path, sample_evaluation_result, sample_failed_result):
        """Test that summary calculates scores by category."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        results = [sample_evaluation_result, sample_failed_result]
        summary = storage._calculate_summary(run_id, results)

        assert "reasoning" in summary.scores_by_category
        assert "edge_cases" in summary.scores_by_category
        assert summary.scores_by_category["reasoning"] == 0.95
        assert summary.scores_by_category["edge_cases"] == 0.62

    def test_calculate_summary_dimension_scores(self, tmp_path, sample_evaluation_result, sample_failed_result):
        """Test aggregation of dimension scores across tests."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        results = [sample_evaluation_result, sample_failed_result]
        summary = storage._calculate_summary(run_id, results)

        assert "accurate" in summary.average_dimension_scores
        assert "concise" in summary.average_dimension_scores
        assert summary.average_dimension_scores["accurate"] == 1.0

    def test_finalize_run_saves_summary(self, tmp_path, sample_evaluation_result):
        """Test that finalize_run saves run_summary.json."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        storage.save_result(run_id, sample_evaluation_result)
        storage.finalize_run(run_id, [sample_evaluation_result])

        summary_file = tmp_path / "results" / "runs" / run_id / "run_summary.json"
        assert summary_file.exists()

        with open(summary_file) as f:
            data = json.load(f)
            assert data["run_id"] == run_id
            assert data["total_tests"] == 1

    def test_finalize_run_generates_markdown_report(self, tmp_path, sample_evaluation_result):
        """Test that finalize_run generates markdown report."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        storage.finalize_run(run_id, [sample_evaluation_result])

        report_file = tmp_path / "results" / "reports" / f"{run_id}.md"
        assert report_file.exists()

        # Verify report content
        with open(report_file) as f:
            content = f.read()
            assert "# Golden Test Evaluation Report" in content
            assert "Executive Summary" in content
            assert "Test Results" in content
            assert "test_basic_qa" in content

    def test_markdown_report_includes_failed_tests(self, tmp_path, sample_evaluation_result, sample_failed_result):
        """Test that markdown report includes failed tests section."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        results = [sample_evaluation_result, sample_failed_result]
        storage.finalize_run(run_id, results)

        report_file = tmp_path / "results" / "reports" / f"{run_id}.md"
        with open(report_file) as f:
            content = f.read()
            assert "## Failed Tests" in content
            assert "test_ambiguous_query" in content
            assert "asks_clarification" in content

    def test_markdown_report_cost_analysis(self, tmp_path, sample_evaluation_result):
        """Test that markdown report includes cost analysis."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        storage.finalize_run(run_id, [sample_evaluation_result])

        report_file = tmp_path / "results" / "reports" / f"{run_id}.md"
        with open(report_file) as f:
            content = f.read()
            assert "## Cost Analysis" in content
            assert "Response Generation" in content
            assert "Judge Evaluation" in content
            assert "$0.007" in content  # Response cost
            assert "$0.011" in content  # Judge cost

    def test_update_history_creates_file(self, tmp_path, sample_evaluation_result):
        """Test that update_history creates history.json."""
        storage = ResultStorage(tmp_path / "results")
        run_id = storage.start_run("test-model", "judge-model")

        summary = storage._calculate_summary(run_id, [sample_evaluation_result])
        storage.update_history(summary)

        assert (tmp_path / "results" / "history.json").exists()

        with open(tmp_path / "results" / "history.json") as f:
            data = json.load(f)
            assert "runs" in data
            assert len(data["runs"]) == 1
            assert data["runs"][0]["run_id"] == run_id

    def test_update_history_appends_runs(self, tmp_path, sample_evaluation_result):
        """Test that update_history appends to existing history."""
        storage = ResultStorage(tmp_path / "results")

        # First run
        run_id_1 = storage.start_run("test-model", "judge-model")
        summary_1 = storage._calculate_summary(run_id_1, [sample_evaluation_result])
        storage.update_history(summary_1)

        # Second run
        run_id_2 = storage.start_run("test-model", "judge-model")
        summary_2 = storage._calculate_summary(run_id_2, [sample_evaluation_result])
        storage.update_history(summary_2)

        # Verify both runs in history
        with open(tmp_path / "results" / "history.json") as f:
            data = json.load(f)
            assert len(data["runs"]) == 2
            assert data["runs"][0]["run_id"] == run_id_1
            assert data["runs"][1]["run_id"] == run_id_2

    def test_get_historical_trends_empty(self, tmp_path):
        """Test getting trends with no history."""
        storage = ResultStorage(tmp_path / "results")

        trends = storage.get_historical_trends()

        assert trends["runs"] == []
        assert trends["trends"] == {}

    def test_get_historical_trends_with_data(self, tmp_path, sample_evaluation_result):
        """Test getting trends with historical data."""
        storage = ResultStorage(tmp_path / "results")

        # Create multiple runs
        for _i in range(3):
            run_id = storage.start_run("test-model", "judge-model")
            summary = storage._calculate_summary(run_id, [sample_evaluation_result])
            storage.update_history(summary)

        trends = storage.get_historical_trends()

        assert len(trends["runs"]) == 3
        assert "quality_over_time" in trends["trends"]
        assert "cost_over_time" in trends["trends"]
        assert "pass_rate_over_time" in trends["trends"]
        assert len(trends["trends"]["quality_over_time"]) == 3

    def test_get_historical_trends_filtered_by_model(self, tmp_path, sample_evaluation_result):
        """Test filtering trends by model."""
        storage = ResultStorage(tmp_path / "results")

        # Create runs with different models
        run_id_1 = storage.start_run("model-a", "judge-model")
        result_1 = sample_evaluation_result
        result_1.model_tested = "model-a"
        summary_1 = storage._calculate_summary(run_id_1, [result_1])
        storage.update_history(summary_1)

        run_id_2 = storage.start_run("model-b", "judge-model")
        result_2 = sample_evaluation_result
        result_2.model_tested = "model-b"
        summary_2 = storage._calculate_summary(run_id_2, [result_2])
        storage.update_history(summary_2)

        # Filter by model-a
        trends = storage.get_historical_trends(model="model-a")

        assert len(trends["runs"]) == 1
        assert trends["runs"][0]["model"] == "model-a"


class TestRunSummary:
    """Test RunSummary dataclass."""

    def test_run_summary_to_dict(self):
        """Test converting RunSummary to dict."""
        summary = RunSummary(
            run_id="2026-01-20_15-30-45",
            timestamp="2026-01-20T15:30:45Z",
            model_tested="test-model",
            judge_model="judge-model",
            total_tests=2,
            passed_tests=1,
            failed_tests=1,
            pass_rate=0.5,
            average_overall_score=0.78,
            total_cost_usd=0.036,
            total_response_cost_usd=0.015,
            total_judge_cost_usd=0.021,
            average_response_latency_ms=900,
            average_judge_latency_ms=1150,
            total_runtime_seconds=10.5,
            total_response_tokens=500,
            total_judge_tokens=1200,
        )

        result_dict = summary.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["run_id"] == "2026-01-20_15-30-45"
        assert result_dict["total_tests"] == 2
        assert result_dict["pass_rate"] == 0.5
