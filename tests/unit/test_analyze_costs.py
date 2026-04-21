"""Tests for scripts/analyze_costs.py analysis functions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scripts.analyze_costs import (
    GroupStats,
    aggregate_conversation,
    analyze_by_group,
    classify_length,
    classify_model,
    classify_source,
    format_full_report,
    format_table,
)

# --- Helpers ---


def _make_conversation(
    *,
    tags: list[str] | None = None,
    model_id: str | None = "anthropic/claude-sonnet-4.5",
    msg_count: int = 4,
    cost: float = 0.01,
    tokens: int = 1000,
    prompt_tokens: int = 800,
    completion_tokens: int = 200,
    avg_latency_ms: float = 0.0,
) -> dict:
    messages = [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": [{"type": "text", "text": f"msg {i}"}],
        }
        for i in range(msg_count)
    ]
    conv: dict = {
        "schema_version": "1.0.0",
        "tags": tags or [],
        "model": {"id": model_id, "provider": "openrouter", "parameters": {}} if model_id else None,
        "messages": messages,
        "metrics": {
            "total_cost_usd": cost,
            "total_tokens": tokens,
            "total_prompt_tokens": prompt_tokens,
            "total_completion_tokens": completion_tokens,
            "average_latency_ms": avg_latency_ms,
        },
    }
    return conv


# --- classify_source ---


class TestClassifySource:
    def test_native(self):
        assert classify_source(_make_conversation(tags=[])) == "native"

    def test_imported_chatgpt(self):
        assert (
            classify_source(_make_conversation(tags=["imported", "chatgpt"])) == "imported/chatgpt"
        )

    def test_imported_claude(self):
        assert classify_source(_make_conversation(tags=["imported", "claude"])) == "imported/claude"

    def test_imported_other(self):
        assert classify_source(_make_conversation(tags=["imported"])) == "imported/other"

    def test_no_tags(self):
        conv = _make_conversation()
        conv["tags"] = []
        assert classify_source(conv) == "native"


# --- classify_model ---


class TestClassifyModel:
    def test_with_model(self):
        assert classify_model(_make_conversation(model_id="openai/gpt-4o")) == "openai/gpt-4o"

    def test_no_model(self):
        assert classify_model(_make_conversation(model_id=None)) == "unknown"

    def test_model_not_dict(self):
        conv = _make_conversation()
        conv["model"] = "some-string"
        assert classify_model(conv) == "unknown"


# --- classify_length ---


class TestClassifyLength:
    def test_short(self):
        assert classify_length(_make_conversation(msg_count=1)) == "short (1-3)"
        assert classify_length(_make_conversation(msg_count=3)) == "short (1-3)"

    def test_medium(self):
        assert classify_length(_make_conversation(msg_count=4)) == "medium (4-10)"
        assert classify_length(_make_conversation(msg_count=10)) == "medium (4-10)"

    def test_long(self):
        assert classify_length(_make_conversation(msg_count=11)) == "long (11+)"
        assert classify_length(_make_conversation(msg_count=50)) == "long (11+)"

    def test_zero_messages(self):
        conv = _make_conversation()
        conv["messages"] = []
        assert classify_length(conv) == "short (1-3)"


# --- GroupStats ---


class TestGroupStats:
    def test_avg_cost(self):
        stats = GroupStats(count=4, total_cost=0.20)
        assert stats.avg_cost == pytest.approx(0.05)

    def test_avg_cost_zero(self):
        stats = GroupStats(count=0)
        assert stats.avg_cost == 0.0

    def test_avg_tokens(self):
        stats = GroupStats(count=3, total_tokens=900)
        assert stats.avg_tokens == 300

    def test_avg_latency(self):
        stats = GroupStats(latency_count=2, total_latency_ms=400.0)
        assert stats.avg_latency_ms == 200.0

    def test_avg_latency_no_data(self):
        stats = GroupStats(latency_count=0)
        assert stats.avg_latency_ms == 0.0


# --- aggregate_conversation ---


class TestAggregateConversation:
    def test_aggregates_metrics(self):
        stats = GroupStats()
        conv = _make_conversation(cost=0.05, tokens=1500, prompt_tokens=1200, completion_tokens=300)
        aggregate_conversation(stats, conv)
        assert stats.count == 1
        assert stats.total_cost == 0.05
        assert stats.total_tokens == 1500
        assert stats.total_prompt_tokens == 1200
        assert stats.total_completion_tokens == 300

    def test_aggregates_latency(self):
        stats = GroupStats()
        conv = _make_conversation(avg_latency_ms=500.0)
        aggregate_conversation(stats, conv)
        assert stats.latency_count == 1
        assert stats.total_latency_ms == 500.0

    def test_skips_zero_latency(self):
        stats = GroupStats()
        conv = _make_conversation(avg_latency_ms=0.0)
        aggregate_conversation(stats, conv)
        assert stats.latency_count == 0

    def test_multiple_aggregations(self):
        stats = GroupStats()
        aggregate_conversation(stats, _make_conversation(cost=0.01, tokens=100))
        aggregate_conversation(stats, _make_conversation(cost=0.02, tokens=200))
        assert stats.count == 2
        assert stats.total_cost == pytest.approx(0.03)
        assert stats.total_tokens == 300


# --- analyze_by_group ---


class TestAnalyzeByGroup:
    def test_group_by_source(self):
        convs = [
            _make_conversation(tags=["imported", "chatgpt"]),
            _make_conversation(tags=["imported", "chatgpt"]),
            _make_conversation(tags=[]),
        ]
        groups = analyze_by_group(convs, "source")
        assert groups["imported/chatgpt"].count == 2
        assert groups["native"].count == 1

    def test_group_by_model(self):
        convs = [
            _make_conversation(model_id="anthropic/claude-sonnet-4.5"),
            _make_conversation(model_id="openai/gpt-4o"),
        ]
        groups = analyze_by_group(convs, "model")
        assert "anthropic/claude-sonnet-4.5" in groups
        assert "openai/gpt-4o" in groups

    def test_group_by_length(self):
        convs = [
            _make_conversation(msg_count=2),
            _make_conversation(msg_count=8),
            _make_conversation(msg_count=20),
        ]
        groups = analyze_by_group(convs, "length")
        assert groups["short (1-3)"].count == 1
        assert groups["medium (4-10)"].count == 1
        assert groups["long (11+)"].count == 1

    def test_invalid_group_by(self):
        with pytest.raises(ValueError, match="Unknown group_by"):
            analyze_by_group([], "invalid")

    def test_empty_conversations(self):
        groups = analyze_by_group([], "source")
        assert groups == {}


# --- format_table ---


class TestFormatTable:
    def test_table_structure(self):
        groups = {
            "native": GroupStats(count=5, total_cost=0.05, total_tokens=5000),
        }
        table = format_table(groups, "source")
        assert "### Costs by source" in table
        assert "native" in table
        assert "| Source |" in table

    def test_latency_display(self):
        groups = {
            "native": GroupStats(
                count=2,
                total_cost=0.02,
                total_tokens=2000,
                total_latency_ms=1000.0,
                latency_count=2,
            ),
        }
        table = format_table(groups, "source")
        assert "500 ms" in table

    def test_no_latency_shows_na(self):
        groups = {"native": GroupStats(count=1, total_cost=0.01, total_tokens=1000)}
        table = format_table(groups, "source")
        assert "n/a" in table


# --- format_full_report ---


class TestFormatFullReport:
    def test_report_header(self):
        convs = [_make_conversation()]
        report = format_full_report(convs, ["source"])
        assert "# Cost Analysis Report" in report
        assert "Total conversations**: 1" in report

    def test_report_multiple_groups(self):
        convs = [_make_conversation()]
        report = format_full_report(convs, ["source", "model", "length"])
        assert "Costs by source" in report
        assert "Costs by model" in report
        assert "Costs by length" in report

    def test_report_total_cost(self):
        convs = [
            _make_conversation(cost=0.01),
            _make_conversation(cost=0.02),
        ]
        report = format_full_report(convs, ["source"])
        assert "Total cost" in report
