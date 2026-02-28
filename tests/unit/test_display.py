"""
Unit tests for the CLI display module.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from apps.cli.display import (
    _has_markdown,
    create_prompt_session,
    print_startup,
    print_usage_stats,
    print_separator,
    print_tool_feedback,
    print_error,
    print_system,
    render_response,
    print_assistant_prefix,
    print_agent_prefix,
)
from packages.core.stream_handler import StreamResult
from packages.core.llm_client import TokenUsage
from packages.telemetry.metrics import ResponseMetrics


# ---------------------------------------------------------------------------
# _has_markdown detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHasMarkdown:
    """Tests for the markdown detection heuristic."""

    def test_fenced_code_block(self):
        assert _has_markdown("Here is code:\n```python\nprint('hi')\n```") is True

    def test_atx_heading(self):
        assert _has_markdown("## Section Title\nSome text") is True

    def test_bold_text(self):
        assert _has_markdown("This is **important** text") is True

    def test_unordered_list(self):
        assert _has_markdown("Items:\n- first\n- second") is True

    def test_ordered_list(self):
        assert _has_markdown("Steps:\n1. first\n2. second") is True

    def test_inline_code(self):
        assert _has_markdown("Use `print()` to output") is True

    def test_plain_text_no_markdown(self):
        assert _has_markdown("This is just a plain sentence.") is False

    def test_empty_string(self):
        assert _has_markdown("") is False

    def test_numbers_without_list_format(self):
        assert _has_markdown("I have 42 apples") is False


# ---------------------------------------------------------------------------
# print_usage_stats
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPrintUsageStats:
    """Tests for print_usage_stats output."""

    def _make_result(self, cost: float = 0.0, tokens: int = 100) -> StreamResult:
        usage = TokenUsage(prompt_tokens=80, completion_tokens=20, total_tokens=tokens)
        metrics = ResponseMetrics(
            ttft_ms=150.0,
            total_latency_ms=500.0,
            prompt_tokens=80,
            completion_tokens=20,
            cost_usd=cost,
            model="test-model",
        )
        return StreamResult(text="hi", usage=usage, cost_usd=cost, metrics=metrics)

    def test_stats_with_cost(self, capsys):
        result = self._make_result(cost=0.005, tokens=100)
        print_usage_stats(result)
        out = capsys.readouterr().out
        assert "100 tokens" in out
        assert "TTFT:" in out
        assert "Total:" in out

    def test_stats_without_cost(self, capsys):
        result = self._make_result(cost=0.0, tokens=50)
        print_usage_stats(result)
        out = capsys.readouterr().out
        assert "50 tokens" in out
        assert "TTFT:" in out


# ---------------------------------------------------------------------------
# print_startup
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPrintStartup:
    """Tests for the startup banner."""

    def test_startup_with_commands(self, capsys):
        print_startup("JARVIS", "test-model", "(pricing)", ["/write", "/research"])
        out = capsys.readouterr().out
        assert "Personal Assistant" in out
        assert "JARVIS" in out
        assert "test-model" in out
        assert "/write" in out
        assert "/research" in out

    def test_startup_without_commands(self, capsys):
        print_startup("JARVIS", "test-model", "(pricing)", None)
        out = capsys.readouterr().out
        assert "Personal Assistant" in out
        assert "JARVIS" in out
        assert "Commands" not in out


# ---------------------------------------------------------------------------
# create_prompt_session
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreatePromptSession:
    """Tests for prompt_toolkit session creation."""

    def test_session_without_history(self):
        session = create_prompt_session(history_file=None)
        assert session is not None

    def test_session_with_history(self, tmp_path):
        history_file = str(tmp_path / "test_history")
        session = create_prompt_session(history_file=history_file)
        assert session is not None


# ---------------------------------------------------------------------------
# render_response
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRenderResponse:
    """Tests for post-stream markdown rendering."""

    def test_plain_text_no_rerender(self, capsys):
        render_response("Just a plain answer.")
        out = capsys.readouterr().out
        # Plain text should just get a trailing newline, no ANSI escape sequences for cursor movement
        assert "\033[A" not in out

    def test_empty_text(self, capsys):
        render_response("")
        out = capsys.readouterr().out
        assert out == "\n"

    def test_whitespace_only(self, capsys):
        render_response("   \n  ")
        out = capsys.readouterr().out
        assert out == "\n"

    def test_markdown_triggers_rerender(self, capsys):
        md_text = "## Title\n\nSome text with **bold**"
        render_response(md_text)
        out = capsys.readouterr().out
        # Should contain ANSI escape sequences for cursor-up (clearing raw output)
        assert "\033[A" in out


# ---------------------------------------------------------------------------
# Styled print helpers (smoke tests)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStyledHelpers:
    """Smoke tests for styled print functions."""

    def test_print_separator(self, capsys):
        print_separator()
        assert capsys.readouterr().out == "\n"

    def test_print_tool_feedback(self, capsys):
        print_tool_feedback("fetch_url")
        out = capsys.readouterr().out
        assert "fetch_url" in out

    def test_print_error(self, capsys):
        print_error("something broke")
        out = capsys.readouterr().out
        assert "something broke" in out

    def test_print_system(self, capsys):
        print_system("info message")
        out = capsys.readouterr().out
        assert "info message" in out

    def test_print_assistant_prefix(self, capsys):
        print_assistant_prefix("JARVIS")
        out = capsys.readouterr().out
        assert "JARVIS" in out

    def test_print_agent_prefix(self, capsys):
        print_agent_prefix("Writing")
        out = capsys.readouterr().out
        assert "Writing" in out
