"""
Unit tests for the CLI display module.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call

from apps.cli.display import (
    _has_markdown,
    create_prompt_session,
    finish_live_stream,
    make_live_chunk_handler,
    print_startup,
    print_usage_stats,
    print_separator,
    print_tool_feedback,
    print_error,
    print_system,
    print_assistant_prefix,
    print_agent_prefix,
    start_live_stream,
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

    @pytest.mark.parametrize("text", [
        "Here is code:\n```python\nprint('hi')\n```",
        "## Section Title\nSome text",
        "This is **important** text",
        "Items:\n- first\n- second",
        "Steps:\n1. first\n2. second",
        "Use `print()` to output",
    ], ids=["fenced_code", "atx_heading", "bold", "unordered_list", "ordered_list", "inline_code"])
    def test_detects_markdown(self, text):
        assert _has_markdown(text) is True

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
        assert out.startswith("\n"), "should have leading blank line"
        assert "100 tokens" in out
        assert "TTFT:" in out
        assert "Total:" in out

    def test_stats_without_cost(self, capsys):
        result = self._make_result(cost=0.0, tokens=50)
        print_usage_stats(result)
        out = capsys.readouterr().out
        assert out.startswith("\n"), "should have leading blank line"
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
# Live streaming display
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLiveStreamDisplay:
    """Tests for the rich.Live-based streaming display."""

    @patch("apps.cli.display.Live")
    def test_start_live_stream_returns_live_and_buffer(self, MockLive):
        mock_live = MagicMock()
        MockLive.return_value = mock_live

        live, buf = start_live_stream()

        assert live is mock_live
        assert buf == []
        mock_live.start.assert_called_once()

    @patch("apps.cli.display.Live")
    def test_make_live_chunk_handler_accumulates_and_updates(self, MockLive):
        mock_live = MagicMock()
        buf = []
        handler = make_live_chunk_handler(mock_live, buf)

        handler("Hello")
        assert buf == ["Hello"]
        assert mock_live.update.call_count == 1

        handler(" world")
        assert buf == ["Hello", " world"]
        assert mock_live.update.call_count == 2

    @patch("apps.cli.display.Live")
    def test_finish_live_stream_renders_markdown_when_detected(self, MockLive):
        mock_live = MagicMock()
        md_text = "## Title\n\nSome **bold** text"

        finish_live_stream(mock_live, md_text)

        mock_live.update.assert_called_once()
        # The argument should be a Markdown renderable
        from rich.markdown import Markdown
        arg = mock_live.update.call_args[0][0]
        assert isinstance(arg, Markdown)
        mock_live.stop.assert_called_once()

    @patch("apps.cli.display.Live")
    def test_finish_live_stream_skips_markdown_for_plain_text(self, MockLive):
        mock_live = MagicMock()

        finish_live_stream(mock_live, "Just a plain answer.")

        mock_live.update.assert_not_called()
        mock_live.stop.assert_called_once()

    @patch("apps.cli.display.Live")
    def test_finish_live_stream_handles_empty_text(self, MockLive):
        mock_live = MagicMock()

        finish_live_stream(mock_live, "")

        mock_live.update.assert_not_called()
        mock_live.stop.assert_called_once()

    @patch("apps.cli.display.Live")
    def test_finish_live_stream_handles_whitespace_only(self, MockLive):
        mock_live = MagicMock()

        finish_live_stream(mock_live, "   \n  ")

        mock_live.update.assert_not_called()
        mock_live.stop.assert_called_once()


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
