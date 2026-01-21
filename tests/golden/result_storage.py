"""
Result storage and reporting for LLM-as-judge evaluations.

This module handles persistence of evaluation results, generation of
markdown reports, and tracking of historical trends.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluator import EvaluationResult


@dataclass
class RunSummary:
    """
    Summary of a complete evaluation run.

    Aggregates metrics across all tests in a run including
    pass rates, average scores, costs, and performance.
    """

    run_id: str
    timestamp: str
    model_tested: str
    judge_model: str

    # Results
    total_tests: int
    passed_tests: int
    failed_tests: int
    pass_rate: float

    # Aggregated scores
    average_overall_score: float

    # Performance
    total_cost_usd: float
    total_response_cost_usd: float
    total_judge_cost_usd: float
    average_response_latency_ms: float
    average_judge_latency_ms: float
    total_runtime_seconds: float

    # Token usage
    total_response_tokens: int
    total_judge_tokens: int

    # Fields with defaults must come last
    average_dimension_scores: dict[str, float] = field(default_factory=dict)
    scores_by_category: dict[str, float] = field(default_factory=dict)
    test_results: list[str] = field(default_factory=list)  # Filenames

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)


class ResultStorage:
    """
    Manages storage and retrieval of evaluation results.

    Handles:
    - Creating run directories
    - Saving individual test results as JSON
    - Finalizing runs with summary calculation
    - Generating markdown reports
    - Tracking historical trends
    """

    def __init__(self, results_dir: Path | str):
        """
        Initialize result storage.

        Args:
            results_dir: Base directory for results (e.g., tests/golden/results)
        """
        self.results_dir = Path(results_dir)
        self.runs_dir = self.results_dir / "runs"
        self.reports_dir = self.results_dir / "reports"
        self.history_file = self.results_dir / "history.json"

        # Create directories
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def start_run(self, model_tested: str, judge_model: str) -> str:
        """
        Start a new evaluation run.

        Creates a timestamped directory for the run.

        Args:
            model_tested: Model identifier for the model being tested
            judge_model: Model identifier for the judge

        Returns:
            run_id (timestamp-based string like "2026-01-20_15-30-45")
        """
        # Create run ID from timestamp
        run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Create run directory
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        return run_id

    def save_result(self, run_id: str, result: EvaluationResult):
        """
        Save individual test result to JSON.

        Args:
            run_id: Run identifier
            result: EvaluationResult to save
        """
        run_dir = self.runs_dir / run_id
        result_file = run_dir / f"{result.test_name}.json"

        # Convert to dict and save
        with open(result_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

    def finalize_run(
        self,
        run_id: str,
        results: list[EvaluationResult],
    ) -> RunSummary:
        """
        Finalize run: calculate summary, save, generate report.

        Args:
            run_id: Run identifier
            results: List of all EvaluationResults from the run

        Returns:
            RunSummary with aggregated metrics
        """
        if not results:
            raise ValueError("Cannot finalize run with no results")

        # Calculate summary metrics
        summary = self._calculate_summary(run_id, results)

        # Save run summary JSON
        run_dir = self.runs_dir / run_id
        summary_file = run_dir / "run_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary.to_dict(), f, indent=2)

        # Generate markdown report
        self.generate_markdown_report(run_id, summary, results)

        # Update historical tracking
        self.update_history(summary)

        return summary

    def _calculate_summary(
        self, run_id: str, results: list[EvaluationResult]
    ) -> RunSummary:
        """Calculate aggregated metrics from results."""
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.passed)
        failed_tests = total_tests - passed_tests
        pass_rate = passed_tests / total_tests if total_tests > 0 else 0.0

        # Average scores
        average_overall = (
            sum(r.evaluation.overall_score for r in results) / total_tests
        )

        # Scores by category
        category_scores = {}
        category_counts = {}
        for r in results:
            cat = r.test_category
            if cat not in category_scores:
                category_scores[cat] = 0.0
                category_counts[cat] = 0
            category_scores[cat] += r.evaluation.overall_score
            category_counts[cat] += 1

        for cat in category_scores:
            category_scores[cat] /= category_counts[cat]

        # Dimension scores (across all tests)
        all_dimensions = {}
        dimension_counts = {}
        for r in results:
            for dim, score in r.evaluation.dimension_scores.items():
                if dim not in all_dimensions:
                    all_dimensions[dim] = 0.0
                    dimension_counts[dim] = 0
                all_dimensions[dim] += score
                dimension_counts[dim] += 1

        average_dimension_scores = {
            dim: all_dimensions[dim] / dimension_counts[dim]
            for dim in all_dimensions
        }

        # Costs
        total_cost = sum(r.total_cost_usd for r in results)
        total_response_cost = sum(r.response_cost_usd for r in results)
        total_judge_cost = sum(r.judge_cost_usd for r in results)

        # Latency
        avg_response_latency = (
            sum(r.response_latency_ms for r in results) / total_tests
        )
        avg_judge_latency = sum(r.judge_latency_ms for r in results) / total_tests

        # Tokens
        total_response_tokens = sum(
            r.response_tokens.get("total", 0) for r in results
        )
        total_judge_tokens = sum(r.judge_tokens.get("total", 0) for r in results)

        # Filenames
        test_filenames = [f"{r.test_name}.json" for r in results]

        return RunSummary(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            model_tested=results[0].model_tested if results else "unknown",
            judge_model=results[0].judge_model if results else "unknown",
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            pass_rate=pass_rate,
            average_overall_score=average_overall,
            average_dimension_scores=average_dimension_scores,
            scores_by_category=category_scores,
            total_cost_usd=total_cost,
            total_response_cost_usd=total_response_cost,
            total_judge_cost_usd=total_judge_cost,
            average_response_latency_ms=avg_response_latency,
            average_judge_latency_ms=avg_judge_latency,
            total_runtime_seconds=0.0,  # Calculated externally if needed
            total_response_tokens=total_response_tokens,
            total_judge_tokens=total_judge_tokens,
            test_results=test_filenames,
        )

    def generate_markdown_report(
        self,
        run_id: str,
        summary: RunSummary,
        results: list[EvaluationResult],
    ):
        """
        Generate human-readable markdown report.

        Creates a comprehensive report with:
        - Executive summary
        - Per-test results table
        - Failed tests detail
        - Cost analysis
        - Performance metrics
        - Recommendations
        """
        report_path = self.reports_dir / f"{run_id}.md"

        with open(report_path, "w") as f:
            # Header
            f.write("# Golden Test Evaluation Report\n\n")
            f.write(f"**Date**: {run_id.replace('_', ' ')}\n")
            f.write(f"**Model Tested**: {summary.model_tested}\n")
            f.write(f"**Judge Model**: {summary.judge_model}\n\n")
            f.write("---\n\n")

            # Executive Summary
            f.write("## Executive Summary\n\n")
            f.write(
                f"**Overall Pass Rate**: {summary.passed_tests}/{summary.total_tests} "
                f"({summary.pass_rate*100:.1f}%)\n"
            )
            f.write(
                f"**Average Quality Score**: {summary.average_overall_score:.2f} / 1.0\n"
            )
            f.write(
                f"**Total Cost**: ${summary.total_cost_usd:.3f} "
                f"(${summary.total_response_cost_usd:.3f} model + "
                f"${summary.total_judge_cost_usd:.3f} judge)\n\n"
            )

            # Score breakdown by category
            f.write("### Score Breakdown by Category\n")
            for cat, score in sorted(summary.scores_by_category.items()):
                cat_results = [r for r in results if r.test_category == cat]
                cat_passed = sum(1 for r in cat_results if r.passed)
                cat_total = len(cat_results)
                status = "" if cat_passed == cat_total else " ⚠️"
                f.write(
                    f"- {cat}: {score:.2f} ({cat_passed}/{cat_total} passed){status}\n"
                )
            f.write("\n---\n\n")

            # Test Results Table
            f.write("## Test Results\n\n")
            f.write("| Test | Category | Score | Pass | Cost | Latency |\n")
            f.write("|------|----------|-------|------|------|---------|\n")
            for r in results:
                status = "✅" if r.passed else "❌"
                f.write(
                    f"| {r.test_name} | {r.test_category} | {r.evaluation.overall_score:.2f} | "
                    f"{status} | ${r.total_cost_usd:.3f} | {r.response_latency_ms:.0f}ms |\n"
                )
            f.write("\n---\n\n")

            # Failed Tests Detail
            failed_results = [r for r in results if not r.passed]
            if failed_results:
                f.write("## Failed Tests\n\n")
                for r in failed_results:
                    f.write(f"### {r.test_name} (Score: {r.evaluation.overall_score:.2f})\n\n")
                    f.write(f"**Category**: {r.test_category}\n")
                    f.write(f"**User Query**: {r.user_message}\n\n")

                    # Issues identified
                    f.write("**Issues Identified**:\n")
                    for crit in r.evaluation.failed_criteria:
                        score = r.evaluation.dimension_scores.get(crit, 0.0)
                        f.write(f"- ❌ `{crit}`: {score:.1f}\n")

                    if r.evaluation.forbidden_patterns_found:
                        f.write("\n**Forbidden Patterns Found**:\n")
                        for pattern in r.evaluation.forbidden_patterns_found:
                            f.write(f"- 🚫 \"{pattern}\"\n")

                    f.write(f"\n**Judge Reasoning**:\n")
                    f.write(f"> {r.evaluation.reasoning}\n\n")

                    f.write("---\n\n")

            # Cost Analysis
            f.write("## Cost Analysis\n\n")
            response_pct = (summary.total_response_cost_usd / summary.total_cost_usd * 100) if summary.total_cost_usd > 0 else 0
            f.write(
                f"**Response Generation**: ${summary.total_response_cost_usd:.3f} "
                f"({response_pct:.0f}%)\n"
            )
            f.write(
                f"- Average per test: ${summary.total_response_cost_usd/summary.total_tests:.3f}\n"
            )
            f.write(
                f"- Token usage: {summary.total_response_tokens:,} total "
                f"({summary.total_response_tokens//summary.total_tests:,} avg per test)\n\n"
            )

            judge_pct = (summary.total_judge_cost_usd / summary.total_cost_usd * 100) if summary.total_cost_usd > 0 else 0
            f.write(
                f"**Judge Evaluation**: ${summary.total_judge_cost_usd:.3f} "
                f"({judge_pct:.0f}%)\n"
            )
            f.write(
                f"- Average per test: ${summary.total_judge_cost_usd/summary.total_tests:.3f}\n"
            )
            f.write(
                f"- Token usage: {summary.total_judge_tokens:,} total "
                f"({summary.total_judge_tokens//summary.total_tests:,} avg per test)\n\n"
            )

            # Performance Metrics
            f.write("\n---\n\n")
            f.write("## Performance Metrics\n\n")
            f.write("**Response Latency**:\n")
            f.write(f"- Average: {summary.average_response_latency_ms:.0f}ms\n\n")

            f.write("**Judge Latency**:\n")
            f.write(f"- Average: {summary.average_judge_latency_ms:.0f}ms\n\n")

            # Recommendations
            f.write("---\n\n")
            f.write("## Recommendations\n\n")
            if failed_results:
                # Find most common failure category
                failure_cats = {}
                for r in failed_results:
                    cat = r.test_category
                    failure_cats[cat] = failure_cats.get(cat, 0) + 1
                worst_cat = max(failure_cats.items(), key=lambda x: x[1])[0]
                f.write(f"1. **Focus Area**: Improve {worst_cat} handling\n")

            lowest_score = min(results, key=lambda r: r.evaluation.overall_score)
            f.write(
                f"2. **Quality Gate**: Consider threshold of {summary.average_overall_score - 0.05:.2f} "
                f"(current lowest: {lowest_score.evaluation.overall_score:.2f} in {lowest_score.test_name})\n"
            )

            judge_cost_ratio = (
                summary.total_judge_cost_usd / summary.total_response_cost_usd
                if summary.total_response_cost_usd > 0 else 0
            )
            if judge_cost_ratio > 1.5:
                savings = (
                    summary.total_judge_cost_usd * 0.6
                )  # Estimate 60% savings with cheaper judge
                f.write(
                    f"3. **Cost Optimization**: Consider using Sonnet 4 as judge for ~${savings:.2f} savings per run\n"
                )

    def update_history(self, summary: RunSummary):
        """
        Append run to historical tracking.

        Maintains history.json with all past runs for trend analysis.
        """
        # Load existing history
        if self.history_file.exists():
            with open(self.history_file, "r") as f:
                history = json.load(f)
        else:
            history = {"runs": []}

        # Append new run
        history["runs"].append(
            {
                "run_id": summary.run_id,
                "timestamp": summary.timestamp,
                "model": summary.model_tested,
                "pass_rate": summary.pass_rate,
                "average_score": summary.average_overall_score,
                "total_cost": summary.total_cost_usd,
            }
        )

        # Save updated history
        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2)

    def get_historical_trends(self, model: str | None = None) -> dict:
        """
        Get quality and cost trends over time.

        Args:
            model: Optional model filter

        Returns:
            Dict with trend data
        """
        if not self.history_file.exists():
            return {"runs": [], "trends": {}}

        with open(self.history_file, "r") as f:
            history = json.load(f)

        runs = history.get("runs", [])

        # Filter by model if specified
        if model:
            runs = [r for r in runs if r["model"] == model]

        # Calculate trends
        if runs:
            trends = {
                "quality_over_time": [r["average_score"] for r in runs],
                "cost_over_time": [r["total_cost"] for r in runs],
                "pass_rate_over_time": [r["pass_rate"] for r in runs],
            }
        else:
            trends = {}

        return {"runs": runs, "trends": trends}
