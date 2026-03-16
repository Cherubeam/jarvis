"""
Unit tests for handle_daily_summary().
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

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
