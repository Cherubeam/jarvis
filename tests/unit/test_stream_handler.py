"""
Unit tests for StreamHandler.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.llm_client import LLMClient, TokenUsage, StreamingResponse
from packages.core.pricing import ModelPricing
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
class TestStreamHandler:
    """Tests for StreamHandler.stream()."""

    def test_stream_returns_stream_result(self):
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["Hello", " world"])
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        result = handler.stream([{"role": "user", "content": "hi"}])

        assert isinstance(result, StreamResult)
        assert result.text == "Hello world"
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 5

    def test_stream_calculates_cost_with_pricing(self):
        client = Mock(spec=LLMClient)
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        client.chat_stream.return_value = _make_streaming_response(["ok"], usage)
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        result = handler.stream([{"role": "user", "content": "hi"}])

        expected_cost = 100 * 1e-6 + 50 * 2e-6
        assert result.cost_usd == pytest.approx(expected_cost)

    def test_stream_uses_litellm_fallback_when_no_pricing(self):
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["ok"])
        tracker = MetricsTracker()

        with patch("packages.core.stream_handler.calculate_cost_from_litellm", return_value=0.005) as mock_calc:
            handler = StreamHandler(client, tracker, None, "test-model")
            result = handler.stream([{"role": "user", "content": "hi"}])

        mock_calc.assert_called_once()
        assert result.cost_usd == 0.005

    def test_stream_prints_chunks_when_requested(self, capsys):
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["Hello", " world"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        handler.stream([{"role": "user", "content": "hi"}], print_chunks=True)

        captured = capsys.readouterr()
        assert captured.out == "Hello world"

    def test_stream_does_not_print_by_default(self, capsys):
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["Hello"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        handler.stream([{"role": "user", "content": "hi"}])

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_stream_records_metrics(self):
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["ok"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        result = handler.stream([{"role": "user", "content": "hi"}])

        assert result.metrics.prompt_tokens == 10
        assert result.metrics.completion_tokens == 5
        assert result.metrics.model == "test-model"
        assert len(tracker.responses) == 1

    def test_stream_empty_response(self):
        client = Mock(spec=LLMClient)
        usage = TokenUsage(prompt_tokens=5, completion_tokens=0, total_tokens=5)
        client.chat_stream.return_value = _make_streaming_response([], usage)
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        result = handler.stream([{"role": "user", "content": "hi"}])

        assert result.text == ""

    def test_stream_passes_messages_to_client(self):
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["ok"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
        ]

        handler = StreamHandler(client, tracker, pricing, "test-model")
        handler.stream(messages)

        client.chat_stream.assert_called_once_with(messages)
