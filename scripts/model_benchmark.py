"""Estimate and optionally run model benchmark evaluations."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.benchmark_costs import estimate_benchmark_costs, get_run_dir
from packages.core.pricing import format_cost

DEFAULT_MODELS = [
    "anthropic/claude-sonnet-4.5",
    "anthropic/claude-opus-4.5",
    "openai/gpt-oss-120b",
    "openai/gpt-5.2",
    "openai/gpt-5.2-codex",
    "openai/gpt-5.2-pro",
    "google/gemini-3-flash-preview",
    "google/gemini-3-pro-preview",
]
DEFAULT_JUDGE_MODEL = "anthropic/claude-opus-4.5"
DEFAULT_RESULTS_DIR = "tests/golden/results"


def _print_estimates(
    estimates: dict,
    judge_model: str,
    run_dir: Path,
) -> None:
    print("\nBenchmark Cost Estimate")
    print(f"Baseline run: {run_dir.name}")
    print(f"Judge model: {judge_model}")

    if not estimates:
        print("No estimates available (missing pricing).")
        return

    print("\nModel | Response | Judge | Total")
    print("--- | --- | --- | ---")
    for model_id, estimate in estimates.items():
        response_cost = format_cost(estimate.response_cost_usd)
        judge_cost = format_cost(estimate.judge_cost_usd)
        total_cost = format_cost(estimate.total_cost_usd)
        print(f"{model_id} | {response_cost} | {judge_cost} | {total_cost}")


def _run_evaluations(models: list[str], judge_model: str, fail_fast: bool) -> None:
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "pytest",
        "tests/golden/",
        "--evaluate",
        "--judge-model",
        judge_model,
    ]

    for model_id in models:
        env = os.environ.copy()
        env["DEFAULT_MODEL"] = model_id
        print(f"\nRunning evaluation for {model_id}...")
        result = subprocess.run(command, check=False, env=env)
        if result.returncode != 0:
            message = f"Evaluation failed for {model_id} (exit {result.returncode})."
            if fail_fast:
                raise subprocess.CalledProcessError(
                    result.returncode,
                    command,
                )
            print(message + " Continuing with next model.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate benchmark costs and optionally run evaluations.")
    parser.add_argument(
        "--models",
        nargs="*",
        default=DEFAULT_MODELS,
        help="Model IDs to benchmark (space-separated).",
    )
    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help="Judge model ID.",
    )
    parser.add_argument(
        "--results-dir",
        default=DEFAULT_RESULTS_DIR,
        help="Path to golden results directory.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Specific run ID to use as baseline.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run golden evaluations after estimating costs.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on the first evaluation failure.",
    )

    args = parser.parse_args()

    estimates, _ = estimate_benchmark_costs(
        models=args.models,
        judge_model=args.judge_model,
        results_dir=args.results_dir,
        run_id=args.run_id,
    )

    run_dir = get_run_dir(args.results_dir, args.run_id)
    _print_estimates(estimates, args.judge_model, run_dir)

    if args.evaluate:
        _run_evaluations(args.models, args.judge_model, args.fail_fast)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
