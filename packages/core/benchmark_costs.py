"""
Estimate model benchmarking costs using LiteLLM pricing data.
"""

from dataclasses import dataclass
from pathlib import Path
import json
import warnings

from packages.core.pricing import get_model_pricing, ModelPricing


@dataclass
class TokenTotals:
    """Token totals for a full golden test run."""

    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class BenchmarkTokenBaseline:
    """Baseline token usage for response + judge."""

    response: TokenTotals
    judge: TokenTotals


@dataclass
class BenchmarkCostEstimate:
    """Estimated costs for running the golden suite on a model."""

    model_id: str
    response_cost_usd: float
    judge_cost_usd: float
    total_cost_usd: float
    response_tokens: TokenTotals
    judge_tokens: TokenTotals


def _run_has_results(run_dir: Path) -> bool:
    return any(path.name != "run_summary.json" for path in run_dir.glob("*.json"))


def _find_latest_run_dir(results_dir: Path) -> Path | None:
    runs_dir = results_dir / "runs"
    if not runs_dir.exists():
        return None

    run_dirs = [path for path in runs_dir.iterdir() if path.is_dir() and _run_has_results(path)]
    if not run_dirs:
        return None

    return sorted(run_dirs, key=lambda path: path.name)[-1]


def get_run_dir(results_dir: Path | str, run_id: str | None = None) -> Path:
    """Resolve the golden test run directory to use as a baseline."""
    results_path = Path(results_dir)
    if run_id:
        run_dir = results_path / "runs" / run_id
    else:
        run_dir = _find_latest_run_dir(results_path)

    if run_dir is None or not run_dir.exists():
        raise ValueError("No golden test runs found. Run golden tests first to create a baseline.")

    return run_dir


def _load_run_token_totals(run_dir: Path) -> BenchmarkTokenBaseline:
    response_prompt = 0
    response_completion = 0
    judge_prompt = 0
    judge_completion = 0

    json_files = [path for path in run_dir.glob("*.json") if path.name != "run_summary.json"]
    if not json_files:
        raise ValueError(f"No test result JSON files found in {run_dir}")

    for json_file in json_files:
        with open(json_file) as file_handle:
            data = json.load(file_handle)

        response_tokens = data.get("response_tokens", {})
        judge_tokens = data.get("judge_tokens", {})

        response_prompt += int(response_tokens.get("prompt", 0))
        response_completion += int(response_tokens.get("completion", 0))
        judge_prompt += int(judge_tokens.get("prompt", 0))
        judge_completion += int(judge_tokens.get("completion", 0))

    return BenchmarkTokenBaseline(
        response=TokenTotals(
            prompt_tokens=response_prompt,
            completion_tokens=response_completion,
        ),
        judge=TokenTotals(
            prompt_tokens=judge_prompt,
            completion_tokens=judge_completion,
        ),
    )


def _calculate_cost(tokens: TokenTotals, pricing: ModelPricing) -> float:
    return (tokens.prompt_tokens * pricing.prompt_cost) + (
        tokens.completion_tokens * pricing.completion_cost
    )


def estimate_benchmark_costs(
    models: list[str],
    judge_model: str,
    results_dir: Path | str = "tests/golden/results",
    run_id: str | None = None,
) -> tuple[dict[str, BenchmarkCostEstimate], BenchmarkTokenBaseline]:
    """
    Estimate the cost of benchmarking models against the golden suite.

    Args:
        models: List of model IDs to estimate.
        judge_model: Model ID used as the judge.
        results_dir: Directory containing golden test results.
        run_id: Optional run ID to use instead of latest.

    Returns:
        Tuple of (estimates_by_model, token_baseline).
    """
    run_dir = get_run_dir(results_dir, run_id)
    token_baseline = _load_run_token_totals(run_dir)

    judge_pricing = get_model_pricing(judge_model)
    if not judge_pricing:
        warnings.warn(
            f"Pricing unavailable for judge model {judge_model}.",
            RuntimeWarning,
        )
        return {}, token_baseline

    estimates: dict[str, BenchmarkCostEstimate] = {}
    for model_id in models:
        model_pricing = get_model_pricing(model_id)
        if not model_pricing:
            warnings.warn(
                f"Pricing unavailable for model {model_id}; skipping.",
                RuntimeWarning,
            )
            continue

        response_cost = _calculate_cost(token_baseline.response, model_pricing)
        judge_cost = _calculate_cost(token_baseline.judge, judge_pricing)
        total_cost = response_cost + judge_cost

        estimates[model_id] = BenchmarkCostEstimate(
            model_id=model_id,
            response_cost_usd=response_cost,
            judge_cost_usd=judge_cost,
            total_cost_usd=total_cost,
            response_tokens=token_baseline.response,
            judge_tokens=token_baseline.judge,
        )

    return estimates, token_baseline
