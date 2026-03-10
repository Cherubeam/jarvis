"""Generate benchmark report tables from golden test runs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import warnings
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.pricing import get_model_pricing, format_cost, ModelPricing


@dataclass
class TokenTotals:
    prompt: int
    completion: int

    @property
    def total(self) -> int:
        return self.prompt + self.completion


@dataclass
class RunStats:
    run_id: str
    model: str
    judge_model: str
    total_tests: int
    pass_rate: float
    average_score: float
    avg_response_latency_ms: float
    avg_judge_latency_ms: float
    response_tokens: TokenTotals
    judge_tokens: TokenTotals
    estimated_cost_usd: float | None


def _load_token_totals(run_dir: Path) -> tuple[TokenTotals, TokenTotals, int]:
    response_prompt = 0
    response_completion = 0
    judge_prompt = 0
    judge_completion = 0
    total_tests = 0

    for json_file in run_dir.glob("*.json"):
        if json_file.name == "run_summary.json":
            continue

        with open(json_file) as file_handle:
            data = json.load(file_handle)

        response_tokens = data.get("response_tokens", {})
        judge_tokens = data.get("judge_tokens", {})

        response_prompt += int(response_tokens.get("prompt", 0))
        response_completion += int(response_tokens.get("completion", 0))
        judge_prompt += int(judge_tokens.get("prompt", 0))
        judge_completion += int(judge_tokens.get("completion", 0))
        total_tests += 1

    return (
        TokenTotals(prompt=response_prompt, completion=response_completion),
        TokenTotals(prompt=judge_prompt, completion=judge_completion),
        total_tests,
    )


def _estimate_cost(
    model: str,
    judge_model: str,
    response_tokens: TokenTotals,
    judge_tokens: TokenTotals,
) -> float | None:
    model_pricing = get_model_pricing(model)
    judge_pricing = get_model_pricing(judge_model)
    if not model_pricing or not judge_pricing:
        if not model_pricing:
            warnings.warn(
                f"Pricing unavailable for model {model}; cost omitted.",
                RuntimeWarning,
            )
        if not judge_pricing:
            warnings.warn(
                f"Pricing unavailable for judge {judge_model}; cost omitted.",
                RuntimeWarning,
            )
        return None

    response_cost = (response_tokens.prompt * model_pricing.prompt_cost) + (
        response_tokens.completion * model_pricing.completion_cost
    )
    judge_cost = (judge_tokens.prompt * judge_pricing.prompt_cost) + (
        judge_tokens.completion * judge_pricing.completion_cost
    )
    return response_cost + judge_cost


def _load_run_stats(results_dir: Path) -> list[RunStats]:
    runs_dir = results_dir / "runs"
    if not runs_dir.exists():
        raise ValueError(f"Runs directory not found: {runs_dir}")

    stats: list[RunStats] = []

    for summary_file in runs_dir.glob("*/run_summary.json"):
        run_dir = summary_file.parent
        with open(summary_file) as file_handle:
            summary = json.load(file_handle)

        response_tokens, judge_tokens, total_tests = _load_token_totals(run_dir)
        estimated_cost = _estimate_cost(
            summary["model_tested"],
            summary["judge_model"],
            response_tokens,
            judge_tokens,
        )

        stats.append(
            RunStats(
                run_id=summary["run_id"],
                model=summary["model_tested"],
                judge_model=summary["judge_model"],
                total_tests=summary.get("total_tests", total_tests),
                pass_rate=summary.get("pass_rate", 0.0),
                average_score=summary.get("average_overall_score", 0.0),
                avg_response_latency_ms=summary.get("average_response_latency_ms", 0.0),
                avg_judge_latency_ms=summary.get("average_judge_latency_ms", 0.0),
                response_tokens=response_tokens,
                judge_tokens=judge_tokens,
                estimated_cost_usd=estimated_cost,
            )
        )

    if not stats:
        raise ValueError("No run summaries found in results directory.")

    return stats


def _latest_runs_by_model(stats: list[RunStats]) -> list[RunStats]:
    latest: dict[str, RunStats] = {}
    for run in stats:
        current = latest.get(run.model)
        if current is None or run.run_id > current.run_id:
            latest[run.model] = run

    return sorted(latest.values(), key=lambda item: item.model)


def _format_latency(value_ms: float) -> str:
    if value_ms <= 0:
        return "n/a"
    return f"{value_ms:.0f} ms"


def _format_cost(cost: float | None) -> str:
    if cost is None:
        return "n/a"
    return format_cost(cost)


def _build_report_section(runs: list[RunStats]) -> str:
    if not runs:
        return "No benchmark runs found."

    judge_models = sorted({run.judge_model for run in runs})
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"Generated: {generated_at}",
        f"Judge model(s): {', '.join(judge_models)}",
        "",
        "| Model | Run | Avg score | Pass rate | Avg response latency | Avg judge latency | Response tokens | Judge tokens | Est. total cost |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for run in runs:
        lines.append(
            " | ".join(
                [
                    run.model,
                    run.run_id,
                    f"{run.average_score:.3f}",
                    f"{run.pass_rate:.0%}",
                    _format_latency(run.avg_response_latency_ms),
                    _format_latency(run.avg_judge_latency_ms),
                    str(run.response_tokens.total),
                    str(run.judge_tokens.total),
                    _format_cost(run.estimated_cost_usd),
                ]
            )
        )

    return "\n".join(lines)


def _update_marked_section(content: str, replacement: str) -> str:
    start_marker = "<!-- BENCHMARK_TABLE_START -->"
    end_marker = "<!-- BENCHMARK_TABLE_END -->"

    if start_marker not in content or end_marker not in content:
        raise ValueError("Benchmark markers not found in target document.")

    before, remainder = content.split(start_marker, maxsplit=1)
    _, after = remainder.split(end_marker, maxsplit=1)

    return "".join(
        [
            before,
            start_marker,
            "\n",
            replacement.strip(),
            "\n",
            end_marker,
            after,
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate benchmark report section for docs/research/models.md."
    )
    parser.add_argument(
        "--results-dir",
        default="tests/golden/results",
        help="Path to golden results directory.",
    )
    parser.add_argument(
        "--output-file",
        default="docs/research/models.md",
        help="Markdown file to update.",
    )
    parser.add_argument(
        "--include-all-runs",
        action="store_true",
        help="Include all runs instead of latest per model.",
    )

    args = parser.parse_args()
    results_dir = Path(args.results_dir)
    output_file = Path(args.output_file)

    stats = _load_run_stats(results_dir)
    runs = stats if args.include_all_runs else _latest_runs_by_model(stats)
    report_section = _build_report_section(runs)

    with open(output_file) as file_handle:
        content = file_handle.read()

    updated = _update_marked_section(content, report_section)
    with open(output_file, "w") as file_handle:
        file_handle.write(updated)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
