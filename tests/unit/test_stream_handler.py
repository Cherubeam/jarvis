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

        client.chat_stream.assert_called_once_with(messages, tools=None)


# ---------------------------------------------------------------------------
# Agentic loop tests
# ---------------------------------------------------------------------------

def _make_tool_call_obj(call_id: str, name: str, args: str = "{}"):
    """Build a mock tool call object matching LiteLLM's shape."""
    call = Mock()
    call.id = call_id
    call.function.name = name
    call.function.arguments = args
    return call


def _make_complete_response(finish_reason: str, tool_calls=None, content: str = ""):
    """Build a mock non-streaming completion response."""
    choice = Mock()
    choice.finish_reason = finish_reason
    choice.message.tool_calls = tool_calls or []
    choice.message.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": [],
    }
    response = Mock()
    response.choices = [choice]
    response.usage = None
    return response


@pytest.mark.unit
class TestStreamHandlerAgenticLoop:
    """Tests for the agentic tool-calling loop in StreamHandler.stream()."""

    def _make_handler(self, client):
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        return StreamHandler(client, tracker, pricing, "test-model")

    def test_no_tool_registry_uses_simple_path(self):
        """When tool_registry is None, stream() skips the agentic loop."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["hi"])

        handler = self._make_handler(client)
        result = handler.stream([{"role": "user", "content": "hello"}], tool_registry=None)

        client.complete.assert_not_called()
        assert result.text == "hi"

    def test_empty_registry_uses_simple_path(self):
        """When tool_registry has no tools, stream() skips the agentic loop."""
        from packages.core.tools.base import ToolRegistry
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["hi"])

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "hello"}],
            tool_registry=ToolRegistry(),
        )

        client.complete.assert_not_called()
        assert result.text == "hi"

    def test_tool_call_then_final_answer(self, capsys):
        """One tool call followed by a final streaming answer."""
        import json
        from packages.core.tools.base import ToolRegistry, ToolDefinition

        # Registry with one tool
        tool = ToolDefinition(
            name="fetch_url",
            description="fetch",
            parameters={},
            execute=lambda url: f"content of {url}",
        )
        registry = ToolRegistry()
        registry.register(tool)

        # LLM first responds with a tool call, second with stop
        tool_call = _make_tool_call_obj("tc1", "fetch_url", json.dumps({"url": "https://example.com"}))
        first_response = _make_complete_response("tool_calls", tool_calls=[tool_call])
        second_response = _make_complete_response("stop")

        client = Mock(spec=LLMClient)
        client.complete.side_effect = [first_response, second_response]
        client.chat_stream.return_value = _make_streaming_response(["The article says: content of https://example.com"])

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "Read https://example.com"}],
            print_chunks=True,
            tool_registry=registry,
        )

        # Tool feedback printed to stdout
        captured = capsys.readouterr()
        assert "[Tool: fetch_url]" in captured.out

        # Final streamed content printed too
        assert "content of https://example.com" in captured.out

        # complete() called twice: tool_calls then stop
        assert client.complete.call_count == 2

        # chat_stream() called with tools parameter
        client.chat_stream.assert_called_once()
        call_kwargs = client.chat_stream.call_args[1]
        assert call_kwargs.get("tools") is not None

        # Messages include the tool result
        streamed_messages = client.chat_stream.call_args[0][0]
        assert any(m.get("role") == "tool" for m in streamed_messages)

        assert result.text == "The article says: content of https://example.com"

    def test_multi_tool_chain(self, capsys):
        """LLM calls tool A, then tool B, then stops."""
        import json
        from packages.core.tools.base import ToolRegistry, ToolDefinition

        tool_a = ToolDefinition(name="tool_a", description="a", parameters={}, execute=lambda: "result_a")
        tool_b = ToolDefinition(name="tool_b", description="b", parameters={}, execute=lambda: "result_b")
        registry = ToolRegistry()
        registry.register(tool_a)
        registry.register(tool_b)

        call_a = _make_tool_call_obj("tc1", "tool_a")
        call_b = _make_tool_call_obj("tc2", "tool_b")
        resp1 = _make_complete_response("tool_calls", tool_calls=[call_a])
        resp2 = _make_complete_response("tool_calls", tool_calls=[call_b])
        resp3 = _make_complete_response("stop")

        client = Mock(spec=LLMClient)
        client.complete.side_effect = [resp1, resp2, resp3]
        client.chat_stream.return_value = _make_streaming_response(["final answer"])

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "do things"}],
            print_chunks=True,
            tool_registry=registry,
        )

        assert client.complete.call_count == 3
        captured = capsys.readouterr()
        assert "[Tool: tool_a]" in captured.out
        assert "[Tool: tool_b]" in captured.out
        assert result.text == "final answer"

    def test_tools_passed_to_streaming_call(self):
        """chat_stream() receives the tools parameter after the agentic loop."""
        from packages.core.tools.base import ToolRegistry, ToolDefinition

        tool = ToolDefinition(name="my_tool", description="t", parameters={"type": "object"}, execute=lambda: "ok")
        registry = ToolRegistry()
        registry.register(tool)

        stop_response = _make_complete_response("stop")
        client = Mock(spec=LLMClient)
        client.complete.side_effect = [stop_response]
        client.chat_stream.return_value = _make_streaming_response(["done"])

        handler = self._make_handler(client)
        handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        # chat_stream should receive tools kwarg matching the registry format
        call_kwargs = client.chat_stream.call_args[1]
        assert call_kwargs["tools"] == registry.to_litellm_format()
