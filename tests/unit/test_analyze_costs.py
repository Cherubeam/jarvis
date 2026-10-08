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
    caching_by_model,
    classify_length,
    classify_model,
    classify_source,
    format_caching,
    format_full_report,
    format_sessions,
    format_spend,
    format_table,
    iso_week,
    sessions_by_week,
    spend_by_month,
    turn_model,
    usage_source,
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
        assert classify_source(_make_conversation(tags=["imported", "chatgpt"])) == "imported/chatgpt"

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


# --- usage reports (AON-01 measurement) ---


def _turn(
    cost: float,
    *,
    source: str | None = "billed",
    prompt: int = 1000,
    cache_read: int = 0,
    model: str | None = None,
    timestamp: str = "2026-10-08T10:00:00",
) -> dict:
    metadata: dict = {}
    if source:
        metadata["usage_source"] = source
    if model:
        metadata["model"] = model
    return {
        "role": "assistant",
        "timestamp": timestamp,
        "metadata": metadata,
        "usage": {"prompt_tokens": prompt, "cache_read_tokens": cache_read, "cost_usd": cost},
    }


def _session(
    turns: list[dict],
    *,
    start: str = "2026-10-08T09:00:00",
    client: str = "cli",
    import_source: str | None = None,
    with_user: bool = True,
) -> dict:
    messages: list[dict] = []
    for turn in turns:
        if with_user:
            messages.append({"role": "user", "content": "hi"})
        messages.append(turn)
    if with_user and not turns:
        messages.append({"role": "user", "content": "hi"})
    return {
        "session_start": start,
        "tags": [],
        "model": {"id": "openrouter/openai/gpt-6-luna"},
        "environment": {"client": client},
        "metadata": {"import_source": import_source} if import_source else {},
        "messages": messages,
    }


class TestImportSource:
    def test_metadata_import_source_wins_over_missing_tags(self):
        conv = _session([], import_source="claude_code")
        assert classify_source(conv) == "imported/claude_code"


class TestUsageHelpers:
    def test_iso_week(self):
        assert iso_week("2026-10-08T21:30:10") == "2026-W41"
        assert iso_week("2026-01-01T00:00:00") == "2026-W01"

    def test_usage_source(self):
        assert usage_source(_turn(0.1, source="billed")) == "billed"
        assert usage_source(_turn(0.1, source="estimated")) == "estimated"
        assert usage_source(_turn(0.1, source=None)) == "legacy"

    def test_turn_model_prefers_logged_model(self):
        conv = _session([])
        assert turn_model(conv, _turn(0.1, model="openrouter/anthropic/claude-opus-5.5")) == (
            "openrouter/anthropic/claude-opus-5.5"
        )
        assert turn_model(conv, _turn(0.1)) == "openrouter/openai/gpt-6-luna (session)"


class TestSessionsByWeek:
    def test_counts_native_sessions_per_week_and_client(self):
        convs = [
            _session([_turn(0.1)], start="2026-10-06T09:00:00", client="cli"),
            _session([_turn(0.1)], start="2026-10-08T09:00:00", client="gui"),
            _session([_turn(0.1)], start="2026-10-12T09:00:00", client="cli"),
            _session([_turn(0.1)], start="2026-10-08T09:00:00", import_source="claude"),
            _session([], start="2026-10-08T09:00:00", with_user=False),
        ]

        assert sessions_by_week(convs) == {"2026-W41": {"cli": 1, "gui": 1}, "2026-W42": {"cli": 1}}

    def test_format_has_total_line(self):
        table = format_sessions({"2026-W41": {"cli": 2, "gui": 1}})
        assert "| 2026-W41 | 2 | 1 | 3 |" in table
        assert "3 sessions in 1 active weeks" in table


class TestSpendByMonth:
    def test_splits_cost_by_usage_source_and_month(self):
        convs = [
            _session(
                [
                    _turn(0.5, source=None, timestamp="2026-09-10T10:00:00"),
                    _turn(0.25, source="billed", timestamp="2026-10-01T10:00:00"),
                    _turn(0.125, source="estimated", timestamp="2026-10-02T10:00:00"),
                ]
            ),
            _session([_turn(9.0)], import_source="chatgpt"),
        ]

        months = spend_by_month(convs)

        assert sorted(months) == ["2026-09", "2026-10"]
        assert (months["2026-09"].legacy, months["2026-09"].turns) == (0.5, 1)
        assert (months["2026-10"].billed, months["2026-10"].estimated, months["2026-10"].turns) == (0.25, 0.125, 2)
        assert months["2026-10"].total == 0.375

    def test_format_shows_dash_for_zero(self):
        table = format_spend(spend_by_month([_session([_turn(0.25, timestamp="2026-10-01T10:00:00")])]))
        assert "| 2026-10 | 1 | $0.25 | – | – | $0.25 |" in table


class TestCachingByModel:
    def test_billed_turns_only_with_read_share_and_later_turns(self):
        opus = "openrouter/anthropic/claude-opus-5.5"
        convs = [
            _session(
                [
                    _turn(0.25, prompt=1000, cache_read=0, model=opus),
                    _turn(0.125, prompt=3000, cache_read=2000, model=opus),
                    _turn(0.5, source="estimated", prompt=5000, model=opus),
                    _turn(0.0625, prompt=1000, cache_read=0, model=opus),
                ]
            )
        ]

        stats = caching_by_model(convs)[opus]

        assert (stats.turns, stats.prompt_tokens, stats.cache_read_tokens) == (3, 5000, 2000)
        assert stats.read_share == 0.4
        assert (stats.later_turns, stats.later_turns_with_reads) == (2, 1)
        assert stats.cost == 0.4375

    def test_format_without_billed_turns(self):
        assert "| (no billed turns yet) |" in format_caching({})

    def test_format_row(self):
        table = format_caching(caching_by_model([_session([_turn(0.25, prompt=1000, cache_read=500, model="m")])]))
        assert "| m | 1 | 1,000 | 500 | 50% | 0/0 | $0.25 |" in table


class TestFullReportUsage:
    def test_usage_reports_in_full_report(self):
        report = format_full_report([_session([_turn(0.25)])], ["sessions", "spend", "caching"])
        assert "### Native sessions per week" in report
        assert "### Native spend per month" in report
        assert "### Prompt caching (billed native turns)" in report
