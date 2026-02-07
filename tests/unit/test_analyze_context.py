"""Tests for scripts/analyze_context.py analysis functions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path for script imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scripts.analyze_context import (
    AnalysisResult,
    ContextFileStats,
    analyze_context_utilization,
    check_context_referenced,
    extract_keywords,
    format_report,
)


# --- extract_keywords ---


class TestExtractKeywords:
    def test_basic_extraction(self):
        text = "Software engineering and machine learning projects"
        keywords = extract_keywords(text)
        assert "software" in keywords
        assert "engineering" in keywords
        assert "machine" in keywords
        assert "learning" in keywords
        assert "projects" in keywords

    def test_filters_short_words(self):
        text = "I am a big fan of AI and ML"
        keywords = extract_keywords(text, min_length=4)
        # "fan" is only 3 chars, should be excluded
        assert "fan" not in keywords

    def test_filters_stop_words(self):
        text = "this is about what they have been doing with their projects"
        keywords = extract_keywords(text)
        assert "this" not in keywords
        assert "about" not in keywords
        assert "they" not in keywords
        assert "have" not in keywords
        assert "their" not in keywords
        assert "doing" in keywords
        assert "projects" in keywords

    def test_lowercases_words(self):
        text = "Python Django FastAPI"
        keywords = extract_keywords(text)
        assert "python" in keywords
        assert "django" in keywords
        assert "fastapi" in keywords

    def test_empty_text(self):
        assert extract_keywords("") == set()

    def test_custom_min_length(self):
        text = "AI ML NLP deep learning"
        keywords = extract_keywords(text, min_length=3)
        assert "deep" in keywords
        assert "learning" in keywords
        # "NLP" is 3 chars, included with min_length=3
        assert "nlp" in keywords


# --- check_context_referenced ---


class TestCheckContextReferenced:
    def test_referenced_above_threshold(self):
        keywords = {"python", "django", "fastapi", "backend", "engineering"}
        response = "I work with Python and Django for backend development, plus FastAPI."
        assert check_context_referenced(keywords, response, threshold=3) is True

    def test_not_referenced_below_threshold(self):
        keywords = {"python", "django", "fastapi", "backend", "engineering"}
        response = "The weather is nice today."
        assert check_context_referenced(keywords, response, threshold=3) is False

    def test_exact_threshold(self):
        keywords = {"python", "django", "fastapi"}
        response = "I use Python and Django regularly."
        # matches: python, django (2) — below threshold of 3
        assert check_context_referenced(keywords, response, threshold=3) is False

    def test_empty_keywords(self):
        assert check_context_referenced(set(), "some response", threshold=1) is False

    def test_case_insensitive(self):
        keywords = {"python", "django"}
        response = "PYTHON and DJANGO are great frameworks."
        assert check_context_referenced(keywords, response, threshold=2) is True

    def test_threshold_of_one(self):
        keywords = {"python"}
        response = "I love Python programming."
        assert check_context_referenced(keywords, response, threshold=1) is True


# --- ContextFileStats ---


class TestContextFileStats:
    def test_avg_size_bytes(self):
        stats = ContextFileStats(path="test.md", times_loaded=3, total_size_bytes=300)
        assert stats.avg_size_bytes == 100

    def test_avg_size_bytes_zero_loads(self):
        stats = ContextFileStats(path="test.md", times_loaded=0, total_size_bytes=0)
        assert stats.avg_size_bytes == 0

    def test_utilization_pct(self):
        stats = ContextFileStats(
            path="test.md",
            conversations_referenced=3,
            total_conversations_loaded=10,
        )
        assert stats.utilization_pct == 30.0

    def test_utilization_pct_zero(self):
        stats = ContextFileStats(path="test.md", total_conversations_loaded=0)
        assert stats.utilization_pct == 0.0


# --- AnalysisResult ---


class TestAnalysisResult:
    def test_context_overhead_pct(self):
        result = AnalysisResult(
            total_context_tokens_estimate=100, total_prompt_tokens=1000
        )
        assert result.context_overhead_pct == 10.0

    def test_context_overhead_pct_zero_tokens(self):
        result = AnalysisResult(total_prompt_tokens=0)
        assert result.context_overhead_pct == 0.0


# --- analyze_context_utilization ---


class TestAnalyzeContextUtilization:
    def _make_conversation(
        self,
        *,
        with_context: bool = True,
        files_loaded: list | None = None,
        assistant_text: str = "I help with Python and Django development.",
        prompt_tokens: int = 1000,
    ) -> dict:
        """Build a minimal conversation dict for testing."""
        conv: dict = {
            "schema_version": "1.0.0",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello"}],
                },
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": assistant_text}],
                },
            ],
            "metrics": {"total_prompt_tokens": prompt_tokens},
        }
        if with_context:
            conv["context"] = {
                "files_loaded": files_loaded
                or [
                    {
                        "path": "data/context/profile.md",
                        "hash": "sha256:abc123",
                        "size_bytes": 500,
                    }
                ]
            }
        else:
            conv["context"] = None
        return conv

    def test_counts_conversations(self):
        convs = [self._make_conversation(), self._make_conversation(with_context=False)]
        result = analyze_context_utilization(convs)
        assert result.total_conversations == 2
        assert result.conversations_with_context == 1

    def test_file_stats_populated(self):
        convs = [self._make_conversation()]
        result = analyze_context_utilization(convs)
        assert "data/context/profile.md" in result.file_stats
        stats = result.file_stats["data/context/profile.md"]
        assert stats.times_loaded == 1
        assert stats.total_size_bytes == 500

    def test_multiple_conversations_same_file(self):
        convs = [self._make_conversation(), self._make_conversation()]
        result = analyze_context_utilization(convs)
        stats = result.file_stats["data/context/profile.md"]
        assert stats.times_loaded == 2
        assert stats.total_size_bytes == 1000

    def test_prompt_tokens_accumulated(self):
        convs = [
            self._make_conversation(prompt_tokens=500),
            self._make_conversation(prompt_tokens=700),
        ]
        result = analyze_context_utilization(convs)
        assert result.total_prompt_tokens == 1200

    def test_context_tokens_estimated(self):
        convs = [
            self._make_conversation(
                files_loaded=[
                    {"path": "a.md", "hash": "x", "size_bytes": 400},
                ]
            )
        ]
        result = analyze_context_utilization(convs)
        # 400 bytes / 4 = 100 tokens
        assert result.total_context_tokens_estimate == 100

    def test_no_conversations(self):
        result = analyze_context_utilization([])
        assert result.total_conversations == 0
        assert result.conversations_with_context == 0

    def test_conversations_without_context_skipped(self):
        convs = [self._make_conversation(with_context=False)]
        result = analyze_context_utilization(convs)
        assert result.conversations_with_context == 0
        assert len(result.file_stats) == 0

    def test_context_reference_detection_with_dir(self, tmp_path):
        """When context_dir is provided and files exist, references are detected."""
        # Create a context file
        ctx_file = tmp_path / "profile.md"
        ctx_file.write_text("Python Django FastAPI backend engineering projects")

        convs = [
            self._make_conversation(
                files_loaded=[
                    {"path": str(ctx_file), "hash": "x", "size_bytes": 100}
                ],
                assistant_text="I work extensively with Python and Django for backend engineering projects.",
            )
        ]
        result = analyze_context_utilization(convs, context_dir=tmp_path)
        stats = result.file_stats[str(ctx_file)]
        assert stats.conversations_referenced == 1

    def test_string_content_handled(self):
        """Messages with string content (old format) are handled."""
        conv = {
            "schema_version": "1.0.0",
            "context": {
                "files_loaded": [
                    {"path": "p.md", "hash": "x", "size_bytes": 100}
                ]
            },
            "messages": [
                {"role": "assistant", "content": "Some response text"},
            ],
            "metrics": {"total_prompt_tokens": 500},
        }
        result = analyze_context_utilization([conv])
        assert result.conversations_with_context == 1


# --- format_report ---


class TestFormatReport:
    def test_report_contains_summary(self):
        result = AnalysisResult(
            total_conversations=10,
            conversations_with_context=5,
            total_context_tokens_estimate=500,
            total_prompt_tokens=5000,
        )
        report = format_report(result)
        assert "# Context Utilization Report" in report
        assert "Total conversations**: 10" in report
        assert "Conversations with context**: 5" in report
        assert "50.0%" in report  # context coverage

    def test_report_contains_file_table(self):
        result = AnalysisResult(
            total_conversations=10,
            conversations_with_context=5,
            file_stats={
                "profile.md": ContextFileStats(
                    path="profile.md",
                    times_loaded=5,
                    total_size_bytes=2500,
                    conversations_referenced=3,
                    total_conversations_loaded=5,
                )
            },
        )
        report = format_report(result)
        assert "profile.md" in report
        assert "60%" in report  # utilization
        assert "500 bytes" in report  # avg size

    def test_report_no_files(self):
        result = AnalysisResult(total_conversations=5, conversations_with_context=0)
        report = format_report(result)
        assert "Unique context files**: 0" in report

    def test_report_zero_conversations(self):
        result = AnalysisResult(total_conversations=0)
        report = format_report(result)
        assert "N/A" in report
