"""
Unit tests for handle_daily_summary().
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call

from packages.core.llm_client import LLMClient, TokenUsage, StreamingResponse
from packages.core.pricing import ModelPricing
from packages.core.stream_handler import StreamResult
from packages.telemetry.metrics import MetricsTracker, ResponseMetrics


def _make_streaming_response(chunks: list[str], usage: TokenUsage | None = None):
    """Create a mock StreamingResponse that yields chunks."""
    if usage is None:
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    mock = MagicMock(spec=StreamingResponse)
    mock.__iter__ = Mock(return_value=iter(chunks))
    mock.usage = usage
    mock.raw_response = Mock()
    return mock


@pytest.mark.unit
class TestDailySummaryMaxTokens:
    """Verify handle_daily_summary passes max_tokens to the LLM client."""

    @patch("apps.cli.main.finish_live_stream")
    @patch("apps.cli.main.make_live_chunk_handler", return_value=lambda chunk: None)
    @patch("apps.cli.main.start_live_stream", return_value=(Mock(), []))
    @patch("apps.cli.main.print_assistant_prefix")
    @patch("apps.cli.main.append_to_daily_note")
    @patch("apps.cli.main.JarvisAgent")
    @patch("apps.cli.main.find_jarvis_callout")
    @patch("apps.cli.main.read_note")
    @patch("apps.cli.main.get_daily_note_path")
    @patch("apps.cli.main.load_vault_config")
    @patch("apps.cli.main.load_filesystem_guard")
    def test_max_tokens_capped_at_4096(
        self,
        mock_fs_guard,
        mock_vault_config,
        mock_daily_path,
        mock_read_note,
        mock_find_callout,
        mock_jarvis_agent,
        mock_append,
        mock_print_prefix,
        mock_start_live,
        mock_make_handler,
        mock_finish_live,
    ):
        """handle_daily_summary must pass max_tokens=4096 to prevent 402 errors."""
        from apps.cli.main import handle_daily_summary
        from packages.integrations.obsidian.callout import CalloutBlock

        # Vault setup
        mock_vault_config.return_value = Mock()
        mock_daily_path.return_value = Mock(name="2026-03-16.md")
        mock_read_note.return_value = "# Daily Note\nSome content"
        mock_find_callout.return_value = CalloutBlock(
            start_line=99, end_line=99, existing_content="",
        )
        mock_jarvis_agent.get_daily_note_instructions.return_value = "Generate summary"
        mock_append.return_value = Mock(success=True, message="Written")

        # LLM client that records calls
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["summary"])

        logger = Mock()
        logger.get_messages_for_api.return_value = []

        metrics_tracker = MetricsTracker()
        pricing = ModelPricing(
            model_id="test-model",
            prompt_cost=0.000003, completion_cost=0.000015,
        )

        handle_daily_summary(
            config={},
            client=client,
            logger=logger,
            system_prompt="You are JARVIS.",
            metrics_tracker=metrics_tracker,
            pricing=pricing,
            model_id="openrouter/anthropic/claude-sonnet-4.6",
        )

        # Assert chat_stream was called with max_tokens=4096
        client.chat_stream.assert_called_once()
        _, kwargs = client.chat_stream.call_args
        assert kwargs.get("max_tokens") == 4096, (
            "handle_daily_summary must cap max_tokens at 4096 to avoid 402 credit errors"
        )


@pytest.mark.unit
class TestDailySummaryDateArgument:
    """Verify handle_daily_summary supports an optional target_date argument."""

    @patch("apps.cli.main.print_error")
    @patch("apps.cli.main.load_filesystem_guard")
    def test_invalid_date_format_shows_error(self, mock_fs_guard, mock_print_error):
        """An invalid date string should print an error and return early."""
        from apps.cli.main import handle_daily_summary

        handle_daily_summary(
            config={},
            client=Mock(spec=LLMClient),
            logger=Mock(),
            system_prompt="You are JARVIS.",
            metrics_tracker=MetricsTracker(),
            pricing=None,
            model_id="test-model",
            target_date="bad-date",
        )

        mock_print_error.assert_called_once()
        assert "bad-date" in mock_print_error.call_args[0][0]
        # load_filesystem_guard should NOT have been called (early return)
        mock_fs_guard.assert_not_called()

    @patch("apps.cli.main.finish_live_stream")
    @patch("apps.cli.main.make_live_chunk_handler", return_value=lambda chunk: None)
    @patch("apps.cli.main.start_live_stream", return_value=(Mock(), []))
    @patch("apps.cli.main.print_assistant_prefix")
    @patch("apps.cli.main.append_to_daily_note")
    @patch("apps.cli.main.JarvisAgent")
    @patch("apps.cli.main.find_jarvis_callout")
    @patch("apps.cli.main.read_note")
    @patch("apps.cli.main.get_daily_note_path")
    @patch("apps.cli.main.load_vault_config")
    @patch("apps.cli.main.load_filesystem_guard")
    def test_target_date_passed_to_vault_functions(
        self,
        mock_fs_guard,
        mock_vault_config,
        mock_daily_path,
        mock_read_note,
        mock_find_callout,
        mock_jarvis_agent,
        mock_append,
        mock_print_prefix,
        mock_start_live,
        mock_make_handler,
        mock_finish_live,
    ):
        """A valid target_date should be forwarded to get_daily_note_path and append_to_daily_note."""
        from apps.cli.main import handle_daily_summary
        from packages.integrations.obsidian.callout import CalloutBlock

        mock_vault_config.return_value = Mock()
        mock_daily_path.return_value = Mock(name="2026-03-18.md")
        mock_read_note.return_value = "# Daily Note\nSome content"
        mock_find_callout.return_value = CalloutBlock(
            start_line=99, end_line=99, existing_content="",
        )
        mock_jarvis_agent.get_daily_note_instructions.return_value = "Generate summary"
        mock_append.return_value = Mock(success=True, message="Written")

        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["summary"])

        logger = Mock()
        logger.get_messages_for_api.return_value = []

        handle_daily_summary(
            config={},
            client=client,
            logger=logger,
            system_prompt="You are JARVIS.",
            metrics_tracker=MetricsTracker(),
            pricing=None,
            model_id="test-model",
            target_date="2026-03-18",
        )

        # get_daily_note_path called with target_date
        mock_daily_path.assert_called_once()
        _, kwargs = mock_daily_path.call_args
        assert kwargs.get("target_date") == "2026-03-18"

        # append_to_daily_note called with date
        mock_append.assert_called_once()
        _, kwargs = mock_append.call_args
        assert kwargs.get("date") == "2026-03-18"

    @patch("apps.cli.main.finish_live_stream")
    @patch("apps.cli.main.make_live_chunk_handler", return_value=lambda chunk: None)
    @patch("apps.cli.main.start_live_stream", return_value=(Mock(), []))
    @patch("apps.cli.main.print_assistant_prefix")
    @patch("apps.cli.main.append_to_daily_note")
    @patch("apps.cli.main.JarvisAgent")
    @patch("apps.cli.main.find_jarvis_callout")
    @patch("apps.cli.main.read_note")
    @patch("apps.cli.main.get_daily_note_path")
    @patch("apps.cli.main.load_vault_config")
    @patch("apps.cli.main.load_filesystem_guard")
    def test_no_date_uses_today(
        self,
        mock_fs_guard,
        mock_vault_config,
        mock_daily_path,
        mock_read_note,
        mock_find_callout,
        mock_jarvis_agent,
        mock_append,
        mock_print_prefix,
        mock_start_live,
        mock_make_handler,
        mock_finish_live,
    ):
        """When target_date is None, vault functions should be called without a date override."""
        from apps.cli.main import handle_daily_summary
        from packages.integrations.obsidian.callout import CalloutBlock

        mock_vault_config.return_value = Mock()
        mock_daily_path.return_value = Mock(name="2026-03-20.md")
        mock_read_note.return_value = "# Daily Note\nSome content"
        mock_find_callout.return_value = CalloutBlock(
            start_line=99, end_line=99, existing_content="",
        )
        mock_jarvis_agent.get_daily_note_instructions.return_value = "Generate summary"
        mock_append.return_value = Mock(success=True, message="Written")

        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["summary"])

        logger = Mock()
        logger.get_messages_for_api.return_value = []

        handle_daily_summary(
            config={},
            client=client,
            logger=logger,
            system_prompt="You are JARVIS.",
            metrics_tracker=MetricsTracker(),
            pricing=None,
            model_id="test-model",
        )

        # get_daily_note_path called with target_date=None (default)
        mock_daily_path.assert_called_once()
        _, kwargs = mock_daily_path.call_args
        assert kwargs.get("target_date") is None

        # append_to_daily_note called with date=None (default)
        mock_append.assert_called_once()
        _, kwargs = mock_append.call_args
        assert kwargs.get("date") is None
