"""Unit tests for benchmark cost estimation."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from packages.core import benchmark_costs
from packages.core.pricing import ModelPricing


def _write_result(
    run_dir: Path,
    name: str,
    response_prompt: int,
    response_completion: int,
    judge_prompt: int,
    judge_completion: int,
) -> None:
    data = {
        "test_name": name,
        "response_tokens": {
            "prompt": response_prompt,
            "completion": response_completion,
            "total": response_prompt + response_completion,
        },
        "judge_tokens": {
            "prompt": judge_prompt,
            "completion": judge_completion,
            "total": judge_prompt + judge_completion,
        },
    }
    with open(run_dir / f"{name}.json", "w") as file_handle:
        json.dump(data, file_handle)


def _write_run_summary(run_dir: Path) -> None:
    with open(run_dir / "run_summary.json", "w") as file_handle:
        json.dump({"run_id": run_dir.name}, file_handle)


def test_get_run_dir_latest(tmp_path: Path):
    results_dir = tmp_path / "results"
    runs_dir = results_dir / "runs"
    first_run = runs_dir / "2026-01-20_09-55-04"
    second_run = runs_dir / "2026-01-21_09-59-53"
    first_run.mkdir(parents=True)
    second_run.mkdir(parents=True)

    latest = benchmark_costs.get_run_dir(results_dir)
    assert latest.name == "2026-01-21_09-59-53"


def test_get_run_dir_specific(tmp_path: Path):
    results_dir = tmp_path / "results"
    run_dir = results_dir / "runs" / "2026-01-21_09-59-53"
    run_dir.mkdir(parents=True)

    resolved = benchmark_costs.get_run_dir(results_dir, "2026-01-21_09-59-53")
    assert resolved == run_dir


def test_estimate_benchmark_costs_calculates(tmp_path: Path, monkeypatch):
    results_dir = tmp_path / "results"
    run_dir = results_dir / "runs" / "2026-01-21_09-59-53"
    run_dir.mkdir(parents=True)
    _write_result(run_dir, "basic_qa", 100, 50, 200, 100)
    _write_result(run_dir, "context_recall", 120, 30, 180, 80)
    _write_run_summary(run_dir)

    pricing_map = {
        "anthropic/claude-opus-4.5": ModelPricing(
            prompt_cost=0.000015,
            completion_cost=0.000075,
            model_id="anthropic/claude-opus-4.5",
        ),
        "anthropic/claude-sonnet-4.5": ModelPricing(
            prompt_cost=0.000003,
            completion_cost=0.000015,
            model_id="anthropic/claude-sonnet-4.5",
        ),
    }

    monkeypatch.setattr(benchmark_costs, "fetch_all_pricing", lambda: pricing_map)

    estimates, baseline = benchmark_costs.estimate_benchmark_costs(
        models=["anthropic/claude-sonnet-4.5"],
        judge_model="anthropic/claude-opus-4.5",
        results_dir=results_dir,
    )

    assert baseline.response.prompt_tokens == 220
    assert baseline.response.completion_tokens == 80
    assert baseline.judge.prompt_tokens == 380
    assert baseline.judge.completion_tokens == 180

    estimate = estimates["anthropic/claude-sonnet-4.5"]
    expected_response_cost = (220 * 0.000003) + (80 * 0.000015)
    expected_judge_cost = (380 * 0.000015) + (180 * 0.000075)
    assert estimate.response_cost_usd == pytest.approx(expected_response_cost)
    assert estimate.judge_cost_usd == pytest.approx(expected_judge_cost)
    assert estimate.total_cost_usd == pytest.approx(
        expected_response_cost + expected_judge_cost
    )


def test_estimate_benchmark_costs_warns_on_missing_pricing(
    tmp_path: Path,
    monkeypatch,
):
    results_dir = tmp_path / "results"
    run_dir = results_dir / "runs" / "2026-01-21_09-59-53"
    run_dir.mkdir(parents=True)
    _write_result(run_dir, "basic_qa", 10, 5, 20, 10)

    pricing_map = {
        "anthropic/claude-opus-4.5": ModelPricing(
            prompt_cost=0.000015,
            completion_cost=0.000075,
            model_id="anthropic/claude-opus-4.5",
        ),
    }

    monkeypatch.setattr(benchmark_costs, "fetch_all_pricing", lambda: pricing_map)

    with warnings.catch_warnings(record=True) as caught:
        estimates, _ = benchmark_costs.estimate_benchmark_costs(
            models=["anthropic/claude-sonnet-4.5"],
            judge_model="anthropic/claude-opus-4.5",
            results_dir=results_dir,
        )

    assert estimates == {}
    assert any(
        "Pricing unavailable for model" in str(warning.message) for warning in caught
    )
