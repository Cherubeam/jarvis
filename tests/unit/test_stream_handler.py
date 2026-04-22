"""
Unit tests for StreamHandler.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from packages.core.llm_client import LLMClient, StreamingResponse, StreamToolResult, TokenUsage
from packages.core.pricing import ModelPricing
from packages.core.stream_handler import StreamHandler, StreamResult
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
        assert result.usage.total_tokens == 15
        assert result.tool_messages == []

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

    def test_cache_tokens_propagated_to_pricing(self):
        """Cache tokens from TokenUsage are forwarded to pricing.calculate_cost."""
        client = Mock(spec=LLMClient)
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cache_read_tokens=80,
            cache_write_tokens=20,
        )
        client.chat_stream.return_value = _make_streaming_response(["ok"], usage)
        pricing = Mock(spec=ModelPricing)
        pricing.calculate_cost.return_value = 0.01
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        result = handler.stream([{"role": "user", "content": "hi"}])

        pricing.calculate_cost.assert_called_once_with(
            100,
            50,
            cache_read_tokens=80,
            cache_write_tokens=20,
        )
        assert result.cost_usd == 0.01

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

    def test_first_token_recorded_once_for_streaming(self):
        """record_first_token is called exactly once even with multiple chunks."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["a", "b", "c"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = Mock(spec=MetricsTracker)
        tracker.finish_request.return_value = Mock(spec=ResponseMetrics)

        handler = StreamHandler(client, tracker, pricing, "test-model")
        handler.stream([{"role": "user", "content": "hi"}])

        tracker.record_first_token.assert_called_once()

    def test_default_instance_id_is_empty_string(self):
        """Default instance_id is empty string, not None or other value."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["hi"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        assert handler.instance_id == ""

    def test_default_streaming_is_true(self):
        """Default streaming flag is True."""
        client = Mock(spec=LLMClient)
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        assert handler.streaming is True

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

        client.chat_stream.assert_called_once_with(messages, tools=None, max_tokens=None)

    def test_on_chunk_callback_invoked_instead_of_print(self, capsys):
        """When on_chunk is set, it receives chunks and print() is suppressed."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["Hello", " world"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        received = []
        handler = StreamHandler(client, tracker, pricing, "test-model", on_chunk=received.append)
        result = handler.stream([{"role": "user", "content": "hi"}], print_chunks=True)

        assert received == ["Hello", " world"]
        assert result.text == "Hello world"
        # on_chunk takes priority — nothing printed to stdout
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_on_chunk_can_be_set_after_init(self, capsys):
        """on_chunk can be assigned after construction (used by main.py)."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["hi"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        received = []
        handler.on_chunk = received.append
        handler.stream([{"role": "user", "content": "hi"}], print_chunks=True)

        assert received == ["hi"]
        assert capsys.readouterr().out == ""


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


def _make_stream_tool_result(tool_calls, usage=None):
    """Build a StreamToolResult for the agentic loop (streaming tool detection)."""
    if usage is None:
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return StreamToolResult(tool_calls=tool_calls, usage=usage)


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

        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="fetch_url",
            description="fetch",
            parameters={},
            execute=lambda url: f"content of {url}",
        )
        registry = ToolRegistry()
        registry.register(tool)

        # First call: tool call detected via streaming; second: content response
        tool_call = _make_tool_call_obj("tc1", "fetch_url", json.dumps({"url": "https://example.com"}))
        final_stream = _make_streaming_response(["The article says: content of https://example.com"])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result([tool_call]),
            final_stream,
        ]

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "Read https://example.com"}],
            print_chunks=True,
            tool_registry=registry,
        )

        # Tool feedback printed to stdout — exact format
        captured = capsys.readouterr()
        assert "[Tool: fetch_url]" in captured.out

        # Final content — exact text
        assert result.text == "The article says: content of https://example.com"

        # stream_with_tool_detection called twice: tool call then content
        assert client.stream_with_tool_detection.call_count == 2
        # No fallback to chat_stream since we got a streaming response
        client.chat_stream.assert_not_called()

    def test_multi_tool_chain(self, capsys):
        """LLM calls tool A, then tool B, then streams final answer."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool_a = ToolDefinition(name="tool_a", description="a", parameters={}, execute=lambda: "result_a")
        tool_b = ToolDefinition(name="tool_b", description="b", parameters={}, execute=lambda: "result_b")
        registry = ToolRegistry()
        registry.register(tool_a)
        registry.register(tool_b)

        call_a = _make_tool_call_obj("tc1", "tool_a")
        call_b = _make_tool_call_obj("tc2", "tool_b")

        # Use distinct token counts per iteration so we can verify accumulation is a SUM
        usage_a = TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30)
        usage_b = TokenUsage(prompt_tokens=30, completion_tokens=15, total_tokens=45)
        final_usage = TokenUsage(prompt_tokens=40, completion_tokens=20, total_tokens=60)
        final_stream = _make_streaming_response(["final answer"], final_usage)

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result([call_a], usage_a),
            _make_stream_tool_result([call_b], usage_b),
            final_stream,
        ]

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "do things"}],
            print_chunks=True,
            tool_registry=registry,
        )

        assert client.stream_with_tool_detection.call_count == 3
        captured = capsys.readouterr()
        assert "[Tool: tool_a]" in captured.out
        assert "[Tool: tool_b]" in captured.out
        assert result.text == "final answer"

        # Token accumulation must be a SUM across all iterations, not just the last value
        # intermediate: 20+30=50 prompt, 10+15=25 completion; final: 40 prompt, 20 completion
        assert result.usage.prompt_tokens == 20 + 30 + 40
        assert result.usage.completion_tokens == 10 + 15 + 20
        assert result.usage.total_tokens == (20 + 30 + 40) + (10 + 15 + 20)

    def test_on_tool_call_callback_invoked(self, capsys):
        """When on_tool_call is set, it is called instead of plain print()."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="my_tool",
            description="t",
            parameters={},
            execute=lambda: "ok",
        )
        registry = ToolRegistry()
        registry.register(tool)

        call = _make_tool_call_obj("tc1", "my_tool")
        final_stream = _make_streaming_response(["done"])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result([call]),
            final_stream,
        ]

        callback = Mock()
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        handler = StreamHandler(client, tracker, pricing, "test-model", on_tool_call=callback)

        handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        callback.assert_called_once_with("my_tool")
        captured = capsys.readouterr()
        assert "[Tool: my_tool]" not in captured.out

    def test_on_tool_call_default_prints(self, capsys):
        """When on_tool_call is None, the default print() is used."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="my_tool",
            description="t",
            parameters={},
            execute=lambda: "ok",
        )
        registry = ToolRegistry()
        registry.register(tool)

        call = _make_tool_call_obj("tc1", "my_tool")
        final_stream = _make_streaming_response(["done"])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result([call]),
            final_stream,
        ]

        handler = self._make_handler(client)
        handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        captured = capsys.readouterr()
        assert "[Tool: my_tool]" in captured.out

    def test_tool_messages_populated_after_tool_calls(self):
        """StreamResult.tool_messages contains assistant+tool messages from the agentic loop."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="my_tool",
            description="t",
            parameters={},
            execute=lambda: "result_value",
        )
        registry = ToolRegistry()
        registry.register(tool)

        call = _make_tool_call_obj("tc1", "my_tool")
        final_stream = _make_streaming_response(["done"])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result([call]),
            final_stream,
        ]

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        assert len(result.tool_messages) == 2
        # First message is the assistant with tool_calls
        assistant_msg = result.tool_messages[0]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"] is None
        assert len(assistant_msg["tool_calls"]) == 1
        tc = assistant_msg["tool_calls"][0]
        assert tc["id"] == "tc1"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "my_tool"
        assert tc["function"]["arguments"] == "{}"

        # Second message is the tool result
        tool_msg = result.tool_messages[1]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "tc1"
        assert "result_value" in tool_msg["content"]

    def test_tool_messages_empty_when_no_tools(self):
        """StreamResult.tool_messages is empty when no tool_registry is used."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["hi"])

        handler = self._make_handler(client)
        result = handler.stream([{"role": "user", "content": "hello"}])

        assert result.tool_messages == []

    def test_stream_result_delegation_fields_default_none(self):
        """StreamResult delegation fields default to None."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["hi"])

        handler = self._make_handler(client)
        result = handler.stream([{"role": "user", "content": "hello"}])

        assert result.delegate_to is None
        assert result.delegate_task is None

    def test_terminal_tool_skips_streaming(self):
        """When a terminal tool fires, stream() returns without further streaming."""
        import json

        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="delegate_to_agent",
            description="delegate",
            parameters={},
            execute=lambda agent_name, task: f"Delegating to {agent_name}",
            terminal=True,
        )
        registry = ToolRegistry()
        registry.register(tool)

        call = _make_tool_call_obj(
            "tc1",
            "delegate_to_agent",
            json.dumps({"agent_name": "writer", "task": "review blog"}),
        )

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result([call]),
        ]

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "review my blog"}],
            tool_registry=registry,
        )

        # Only one stream_with_tool_detection call — stops after terminal tool
        assert client.stream_with_tool_detection.call_count == 1
        # No further API calls made after terminal tool
        client.chat_stream.assert_not_called()
        # Result has empty text
        assert result.text == ""
        # Tool messages are preserved with correct structure
        assert len(result.tool_messages) == 2
        assert result.tool_messages[0]["role"] == "assistant"
        assert result.tool_messages[0]["content"] is None
        assert result.tool_messages[0]["tool_calls"][0]["id"] == "tc1"
        assert result.tool_messages[0]["tool_calls"][0]["function"]["name"] == "delegate_to_agent"
        assert result.tool_messages[1]["role"] == "tool"
        assert result.tool_messages[1]["tool_call_id"] == "tc1"

    def test_terminal_tool_uses_litellm_fallback_when_no_pricing(self):
        """Terminal tool path falls back to zero cost when pricing is None and no raw_response."""
        import json

        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="delegate_to_agent",
            description="delegate",
            parameters={},
            execute=lambda agent_name, task: f"Delegating to {agent_name}",
            terminal=True,
        )
        registry = ToolRegistry()
        registry.register(tool)

        call = _make_tool_call_obj(
            "tc1",
            "delegate_to_agent",
            json.dumps({"agent_name": "writer", "task": "review blog"}),
        )
        usage = TokenUsage(prompt_tokens=500, completion_tokens=100, total_tokens=600)

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result([call], usage),
        ]

        # No pricing — terminal tool path should still return without error
        tracker = MetricsTracker()
        handler = StreamHandler(client, tracker, None, "test-model")
        result = handler.stream(
            [{"role": "user", "content": "review my blog"}],
            tool_registry=registry,
        )

        # Cost is 0.0 (no pricing, no raw_response available in terminal path)
        assert result.cost_usd == 0.0
        assert result.usage.prompt_tokens == 500
        assert result.usage.completion_tokens == 100

    def test_terminal_tool_emits_usage_report(self):
        """Terminal tool path emits a UsageReport event."""
        import json

        from packages.core.events import UsageReport
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="delegate_to_agent",
            description="delegate",
            parameters={},
            execute=lambda agent_name, task: f"Delegating to {agent_name}",
            terminal=True,
        )
        registry = ToolRegistry()
        registry.register(tool)

        call = _make_tool_call_obj(
            "tc1",
            "delegate_to_agent",
            json.dumps({"agent_name": "writer", "task": "review blog"}),
        )
        usage = TokenUsage(prompt_tokens=200, completion_tokens=50, total_tokens=250)

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result([call], usage),
        ]

        events = []
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")
        tracker = MetricsTracker()
        handler = StreamHandler(
            client,
            tracker,
            pricing,
            "test-model",
            on_event=events.append,
            instance_id="jarvis-1",
        )
        result = handler.stream(
            [{"role": "user", "content": "review my blog"}],
            tool_registry=registry,
        )

        usage_events = [e for e in events if isinstance(e, UsageReport)]
        assert len(usage_events) == 1
        assert usage_events[0].prompt_tokens == 200
        assert usage_events[0].completion_tokens == 50
        assert usage_events[0].total_tokens == 250
        assert usage_events[0].cost_usd == result.cost_usd
        assert usage_events[0].model == "test-model"
        assert usage_events[0].instance_id == "jarvis-1"

    def test_duplicate_parallel_tool_calls_deduplicated(self, capsys):
        """LLM returns 3 identical tool calls; only one is executed."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        call_count = 0

        def _execute():
            nonlocal call_count
            call_count += 1
            return "result"

        tool = ToolDefinition(name="list_blog_posts", description="list", parameters={}, execute=_execute)
        registry = ToolRegistry()
        registry.register(tool)

        # Three identical parallel tool calls
        calls = [
            _make_tool_call_obj("tc1", "list_blog_posts", "{}"),
            _make_tool_call_obj("tc2", "list_blog_posts", "{}"),
            _make_tool_call_obj("tc3", "list_blog_posts", "{}"),
        ]
        final_stream = _make_streaming_response(["done"])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result(calls),
            final_stream,
        ]

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "list posts"}],
            tool_registry=registry,
        )

        # Tool executed only once despite 3 identical calls
        assert call_count == 1
        assert result.text == "done"

    def test_different_parallel_tool_calls_preserved(self, capsys):
        """Two distinct tools in parallel; both execute."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool_a = ToolDefinition(name="tool_a", description="a", parameters={}, execute=lambda: "a_result")
        tool_b = ToolDefinition(name="tool_b", description="b", parameters={}, execute=lambda: "b_result")
        registry = ToolRegistry()
        registry.register(tool_a)
        registry.register(tool_b)

        calls = [
            _make_tool_call_obj("tc1", "tool_a", "{}"),
            _make_tool_call_obj("tc2", "tool_b", "{}"),
        ]
        final_stream = _make_streaming_response(["done"])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result(calls),
            final_stream,
        ]

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "do things"}],
            tool_registry=registry,
        )

        # Both tool calls preserved — assistant message has 2 tool_calls
        first_tool_msg = result.tool_messages[0]
        assert len(first_tool_msg["tool_calls"]) == 2
        assert result.text == "done"

    def test_same_tool_different_args_not_deduplicated(self):
        """Same tool name with different args; both execute."""
        import json

        from packages.core.tools.base import ToolDefinition, ToolRegistry

        results_seen = []

        def _read(post_id):
            results_seen.append(post_id)
            return f"content of {post_id}"

        tool = ToolDefinition(name="read_blog_post", description="read", parameters={}, execute=_read)
        registry = ToolRegistry()
        registry.register(tool)

        calls = [
            _make_tool_call_obj("tc1", "read_blog_post", json.dumps({"post_id": "post-a"})),
            _make_tool_call_obj("tc2", "read_blog_post", json.dumps({"post_id": "post-b"})),
        ]
        final_stream = _make_streaming_response(["done"])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result(calls),
            final_stream,
        ]

        handler = self._make_handler(client)
        handler.stream(
            [{"role": "user", "content": "read posts"}],
            tool_registry=registry,
        )

        # Both calls executed — different args
        assert len(results_seen) == 2

    def test_tools_stripped_when_loop_exhausted(self):
        """When all iterations are consumed, chat_stream is called with tools=None."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(name="my_tool", description="t", parameters={}, execute=lambda: "ok")
        registry = ToolRegistry()
        registry.register(tool)

        # Every iteration returns a tool call — never a content response
        def make_tool_iteration():
            return _make_stream_tool_result([_make_tool_call_obj("tc1", "my_tool", "{}")])

        max_iter = 3
        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [make_tool_iteration() for _ in range(max_iter)]
        client.chat_stream.return_value = _make_streaming_response(["forced text"])

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
            max_iterations=max_iter,
        )

        # Exactly max_iter tool detection calls were made
        assert client.stream_with_tool_detection.call_count == max_iter
        # All iterations consumed — final chat_stream called with tools=None
        client.chat_stream.assert_called_once()
        _, kwargs = client.chat_stream.call_args
        assert kwargs.get("tools") is None
        assert result.text == "forced text"

    def test_default_max_iterations_is_5(self):
        """Without explicit max_iterations, the loop runs up to _MAX_AGENTIC_ITERATIONS=5."""
        from packages.core.stream_handler import _MAX_AGENTIC_ITERATIONS
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        assert _MAX_AGENTIC_ITERATIONS == 5

        tool = ToolDefinition(name="my_tool", description="t", parameters={}, execute=lambda: "ok")
        registry = ToolRegistry()
        registry.register(tool)

        def make_tool_iteration():
            return _make_stream_tool_result([_make_tool_call_obj("tc1", "my_tool", "{}")])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [make_tool_iteration() for _ in range(5)]
        client.chat_stream.return_value = _make_streaming_response(["done"])

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        assert client.stream_with_tool_detection.call_count == 5
        assert result.text == "done"

    def test_max_tokens_passed_to_chat_stream(self):
        """When max_tokens is set, it is forwarded to chat_stream on the simple path."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["ok"])

        handler = self._make_handler(client)
        handler.max_tokens = 16384
        handler.stream([{"role": "user", "content": "hi"}])

        client.chat_stream.assert_called_once_with(
            [{"role": "user", "content": "hi"}],
            tools=None,
            max_tokens=16384,
        )

    def test_max_tokens_passed_to_stream_with_tool_detection(self):
        """When max_tokens is set, it is forwarded to stream_with_tool_detection."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(name="my_tool", description="t", parameters={}, execute=lambda: "ok")
        registry = ToolRegistry()
        registry.register(tool)

        content_stream = _make_streaming_response(["done"])
        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.return_value = content_stream

        handler = self._make_handler(client)
        handler.max_tokens = 8192
        handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        _, kwargs = client.stream_with_tool_detection.call_args
        assert kwargs["max_tokens"] == 8192

    def test_no_tool_call_streams_directly(self):
        """When model returns content (no tools), the streaming response is used directly."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(name="my_tool", description="t", parameters={"type": "object"}, execute=lambda: "ok")
        registry = ToolRegistry()
        registry.register(tool)

        # stream_with_tool_detection returns content (StreamingResponse), not tools
        content_stream = _make_streaming_response(["done"])
        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.return_value = content_stream

        handler = self._make_handler(client)
        result = handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        # Only one call to stream_with_tool_detection, no chat_stream call
        assert client.stream_with_tool_detection.call_count == 1
        client.chat_stream.assert_not_called()
        assert result.text == "done"


# ---------------------------------------------------------------------------
# Credit fallback tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreditFallback:
    """Tests for _try_with_credit_fallback in StreamHandler."""

    def _make_handler(self, client, max_tokens=16384):
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        return StreamHandler(client, tracker, pricing, "test-model", max_tokens=max_tokens)

    def test_402_retries_with_reduced_max_tokens(self, capsys):
        """First call raises InsufficientCreditsError, retry succeeds with reduced tokens."""
        from packages.core.llm_client import InsufficientCreditsError

        client = Mock(spec=LLMClient)
        handler = self._make_handler(client, max_tokens=16384)

        # First call: 402, second call: success
        client.chat_stream.side_effect = [
            InsufficientCreditsError(requested=16384, affordable=8612, original_error=Exception()),
            _make_streaming_response(["ok"]),
        ]

        result = handler.stream([{"role": "user", "content": "hi"}])

        assert handler.max_tokens == 8612
        assert result.text == "ok"
        assert client.chat_stream.call_count == 2
        captured = capsys.readouterr()
        # Check exact format of the warning message
        assert "Credit limit: reduced max_tokens from 16384" in captured.out
        assert "→ 8612" in captured.out

    def test_402_too_few_tokens_raises_runtime_error(self):
        """When affordable tokens < minimum, RuntimeError is raised."""
        from packages.core.llm_client import InsufficientCreditsError

        client = Mock(spec=LLMClient)
        handler = self._make_handler(client, max_tokens=16384)

        client.chat_stream.side_effect = InsufficientCreditsError(
            requested=16384,
            affordable=100,
            original_error=Exception(),
        )

        with pytest.raises(RuntimeError, match="Insufficient OpenRouter credits") as exc_info:
            handler.stream([{"role": "user", "content": "hi"}])

        msg = str(exc_info.value)
        assert "100 tokens affordable" in msg
        assert "minimum 256 needed" in msg
        assert "openrouter.ai/settings/credits" in msg

    def test_prompt_limit_error_raises_runtime_error(self):
        """PromptTokenLimitError is converted to RuntimeError with helpful message."""
        from packages.core.llm_client import PromptTokenLimitError

        client = Mock(spec=LLMClient)
        handler = self._make_handler(client, max_tokens=16384)

        client.chat_stream.side_effect = PromptTokenLimitError(
            prompt_tokens=13391,
            limit=7985,
            original_error=Exception(),
        )

        with pytest.raises(RuntimeError, match="Prompt too large") as exc_info:
            handler.stream([{"role": "user", "content": "hi"}])

        assert "13391" in str(exc_info.value)
        assert "7985" in str(exc_info.value)
        assert "openrouter.ai/settings/keys" in str(exc_info.value)

    def test_reduced_tokens_persist_across_calls(self, capsys):
        """After adjustment, next stream() uses the reduced value."""
        from packages.core.llm_client import InsufficientCreditsError

        client = Mock(spec=LLMClient)
        handler = self._make_handler(client, max_tokens=16384)

        # First stream: 402 then success
        client.chat_stream.side_effect = [
            InsufficientCreditsError(requested=16384, affordable=8612, original_error=Exception()),
            _make_streaming_response(["first"]),
            _make_streaming_response(["second"]),
        ]

        handler.stream([{"role": "user", "content": "hi"}])
        assert handler.max_tokens == 8612

        # Second stream: no error, should use reduced max_tokens
        result = handler.stream([{"role": "user", "content": "hello"}])
        assert result.text == "second"

        # The third chat_stream call should have been made with reduced tokens
        third_call = client.chat_stream.call_args_list[2]
        assert third_call.kwargs.get("max_tokens") == 8612 or third_call[1].get("max_tokens") == 8612


def _make_complete_response(content="", tool_calls=None, prompt_tokens=10, completion_tokens=5):
    """Create a mock LiteLLM ModelResponse for non-streaming complete()."""
    usage = Mock(
        spec=[
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
            "prompt_tokens_details",
        ]
    )
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0
    usage.prompt_tokens_details = None

    choice = Mock()
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    choice.finish_reason = "tool_calls" if tool_calls else "stop"

    response = Mock()
    response.choices = [choice]
    response.usage = usage
    return response


@pytest.mark.unit
class TestStreamHandlerNonStreaming:
    """Tests for non-streaming mode (streaming=False)."""

    def test_simple_nonstreaming_returns_stream_result(self):
        client = Mock(spec=LLMClient)
        client.complete.return_value = _make_complete_response("Hello world")
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model", streaming=False)
        result = handler.stream([{"role": "user", "content": "hi"}])

        assert isinstance(result, StreamResult)
        assert result.text == "Hello world"
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 5
        assert result.usage.total_tokens == 15
        assert result.tool_messages == []
        client.complete.assert_called_once()
        client.chat_stream.assert_not_called()

    def test_nonstreaming_cache_tokens_propagated(self):
        """Cache tokens are extracted and passed to pricing in non-streaming mode."""
        usage = Mock(
            spec=[
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
                "prompt_tokens_details",
            ]
        )
        usage.prompt_tokens = 100
        usage.completion_tokens = 50
        usage.total_tokens = 150
        usage.cache_read_input_tokens = 60
        usage.cache_creation_input_tokens = 15
        usage.prompt_tokens_details = None

        choice = Mock()
        choice.message.content = "ok"
        choice.message.tool_calls = None
        response = Mock()
        response.choices = [choice]
        response.usage = usage

        client = Mock(spec=LLMClient)
        client.complete.return_value = response
        pricing = Mock(spec=ModelPricing)
        pricing.calculate_cost.return_value = 0.02
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model", streaming=False)
        result = handler.stream([{"role": "user", "content": "hi"}])

        pricing.calculate_cost.assert_called_once_with(
            100,
            50,
            cache_read_tokens=60,
            cache_write_tokens=15,
        )
        assert result.cost_usd == 0.02
        assert result.usage.cache_read_tokens == 60
        assert result.usage.cache_write_tokens == 15

    def test_tool_call_then_content(self):
        """Non-streaming agentic loop: tool call → final content."""
        tool_call = Mock()
        tool_call.id = "tc_1"
        tool_call.function.name = "read_note"
        tool_call.function.arguments = '{"path": "test.md"}'

        client = Mock(spec=LLMClient)
        client.complete.side_effect = [
            _make_complete_response(tool_calls=[tool_call]),
            _make_complete_response("Done reading the note."),
        ]
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model", streaming=False)

        # Need a real tool registry
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="read_note",
                description="Read a note",
                parameters={"type": "object", "properties": {}},
                execute=lambda **kwargs: "note content",
            )
        )

        result = handler.stream(
            [{"role": "user", "content": "read test.md"}],
            tool_registry=registry,
        )

        assert result.text == "Done reading the note."
        assert client.complete.call_count == 2

        # Verify tool message structure
        assert len(result.tool_messages) == 2
        assistant_msg = result.tool_messages[0]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"] is None
        assert assistant_msg["tool_calls"][0]["id"] == "tc_1"
        assert assistant_msg["tool_calls"][0]["type"] == "function"
        assert assistant_msg["tool_calls"][0]["function"]["name"] == "read_note"

        tool_msg = result.tool_messages[1]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "tc_1"

        # Verify no double-counting: total = tool call tokens + final response tokens
        # Each call has prompt_tokens=10, completion_tokens=5
        assert result.usage.prompt_tokens == 20  # 10 + 10, not 10 + 10 + 10
        assert result.usage.completion_tokens == 10  # 5 + 5, not 5 + 5 + 5
        assert result.usage.total_tokens == 30  # 15 + 15

    def test_terminal_tool_returns_early(self):
        """Terminal tool fires in non-streaming agentic loop."""
        tool_call = Mock()
        tool_call.id = "tc_1"
        tool_call.function.name = "delegate"
        tool_call.function.arguments = '{"agent": "writer"}'

        client = Mock(spec=LLMClient)
        client.complete.return_value = _make_complete_response(tool_calls=[tool_call])
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model", streaming=False)

        from packages.core.tools.base import ToolDefinition, ToolRegistry

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="delegate",
                description="Delegate to agent",
                parameters={"type": "object", "properties": {}},
                execute=lambda **kwargs: "delegated",
                terminal=True,
            )
        )

        result = handler.stream(
            [{"role": "user", "content": "delegate"}],
            tool_registry=registry,
        )

        assert result.text == ""
        assert client.complete.call_count == 1
        # Tool messages preserved after terminal tool
        assert len(result.tool_messages) == 2
        assert result.tool_messages[0]["role"] == "assistant"
        assert result.tool_messages[0]["tool_calls"][0]["function"]["name"] == "delegate"
        assert result.tool_messages[1]["role"] == "tool"
        assert result.tool_messages[1]["tool_call_id"] == "tc_1"

    def test_usage_report_emitted(self):
        """UsageReport event is emitted in non-streaming mode."""
        client = Mock(spec=LLMClient)
        client.complete.return_value = _make_complete_response("response")
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")
        tracker = MetricsTracker()

        events = []
        handler = StreamHandler(
            client,
            tracker,
            pricing,
            "test-model",
            streaming=False,
            on_event=lambda e: events.append(e),
        )
        handler.stream([{"role": "user", "content": "hi"}])

        from packages.core.events import TextChunk, UsageReport

        usage_events = [e for e in events if isinstance(e, UsageReport)]
        text_events = [e for e in events if isinstance(e, TextChunk)]
        assert len(usage_events) == 1
        assert usage_events[0].prompt_tokens == 10
        assert len(text_events) == 1
        assert text_events[0].text == "response"

    def test_max_tokens_forwarded(self):
        """max_tokens is passed to client.complete()."""
        client = Mock(spec=LLMClient)
        client.complete.return_value = _make_complete_response("ok")
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(
            client,
            tracker,
            pricing,
            "test-model",
            streaming=False,
            max_tokens=4096,
        )
        handler.stream([{"role": "user", "content": "hi"}])

        call_kwargs = client.complete.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 4096 or call_kwargs[1].get("max_tokens") == 4096

    def test_nonstreaming_events_include_instance_id(self):
        """Non-streaming TextChunk and UsageReport events carry instance_id."""
        from packages.core.events import TextChunk, UsageReport

        client = Mock(spec=LLMClient)
        client.complete.return_value = _make_complete_response("response")
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        events = []
        handler = StreamHandler(
            client,
            tracker,
            pricing,
            "test-model",
            streaming=False,
            on_event=events.append,
            instance_id="my-inst",
        )
        handler.stream([{"role": "user", "content": "hi"}])

        text_events = [e for e in events if isinstance(e, TextChunk)]
        usage_events = [e for e in events if isinstance(e, UsageReport)]
        assert len(text_events) == 1
        assert text_events[0].instance_id == "my-inst"
        assert text_events[0].text == "response"
        assert len(usage_events) == 1
        assert usage_events[0].instance_id == "my-inst"
        assert usage_events[0].model == "test-model"

    def test_nonstreaming_first_token_recorded(self):
        """Non-streaming path calls record_first_token exactly once."""
        client = Mock(spec=LLMClient)
        client.complete.return_value = _make_complete_response("ok")
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = Mock(spec=MetricsTracker)
        tracker.finish_request.return_value = Mock(spec=ResponseMetrics)

        handler = StreamHandler(client, tracker, pricing, "test-model", streaming=False)
        handler.stream([{"role": "user", "content": "hi"}])

        tracker.record_first_token.assert_called_once()

    def test_on_before_after_tool_exec_callbacks(self):
        """on_before_tool_exec and on_after_tool_exec are called around tool execution."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(name="my_tool", description="t", parameters={}, execute=lambda: "ok")
        registry = ToolRegistry()
        registry.register(tool)

        call = Mock()
        call.id = "tc1"
        call.function.name = "my_tool"
        call.function.arguments = "{}"

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            StreamToolResult(tool_calls=[call], usage=TokenUsage()),
            _make_streaming_response(["done"]),
        ]

        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        handler = StreamHandler(client, tracker, pricing, "test-model")

        call_order = []
        handler.on_before_tool_exec = lambda: call_order.append("before")
        handler.on_after_tool_exec = lambda: call_order.append("after")

        handler.stream([{"role": "user", "content": "hi"}], tool_registry=registry)

        assert call_order == ["before", "after"]

    def test_nonstreaming_on_before_after_tool_exec_callbacks(self):
        """on_before/after_tool_exec callbacks work in non-streaming mode."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool_call = Mock()
        tool_call.id = "tc1"
        tool_call.function.name = "my_tool"
        tool_call.function.arguments = "{}"

        client = Mock(spec=LLMClient)
        client.complete.side_effect = [
            _make_complete_response(tool_calls=[tool_call]),
            _make_complete_response("done"),
        ]

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="my_tool",
                description="t",
                parameters={"type": "object", "properties": {}},
                execute=lambda **kw: "ok",
            )
        )

        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        handler = StreamHandler(client, tracker, pricing, "test-model", streaming=False)

        call_order = []
        handler.on_before_tool_exec = lambda: call_order.append("before")
        handler.on_after_tool_exec = lambda: call_order.append("after")

        handler.stream([{"role": "user", "content": "hi"}], tool_registry=registry)

        assert call_order == ["before", "after"]

    def test_nonstreaming_dedup_parallel_tool_calls(self):
        """Non-streaming agentic loop deduplicates identical parallel tool calls."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        exec_count = 0

        def _execute(**kw):
            nonlocal exec_count
            exec_count += 1
            return "result"

        tool = ToolDefinition(
            name="list_items",
            description="list",
            parameters={"type": "object", "properties": {}},
            execute=_execute,
        )
        registry = ToolRegistry()
        registry.register(tool)

        # Three identical tool calls
        calls = []
        for i in range(3):
            tc = Mock()
            tc.id = f"tc{i}"
            tc.function.name = "list_items"
            tc.function.arguments = "{}"
            calls.append(tc)

        client = Mock(spec=LLMClient)
        client.complete.side_effect = [
            _make_complete_response(tool_calls=calls),
            _make_complete_response("done"),
        ]

        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        handler = StreamHandler(client, tracker, pricing, "test-model", streaming=False)
        result = handler.stream([{"role": "user", "content": "hi"}], tool_registry=registry)

        assert exec_count == 1
        assert result.text == "done"

    def test_streaming_toggle_uses_different_methods(self):
        """Changing streaming flag mid-session switches client methods."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["streamed"])
        client.complete.return_value = _make_complete_response("completed")
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")

        handler = StreamHandler(client, MetricsTracker(), pricing, "test-model", streaming=True)
        result1 = handler.stream([{"role": "user", "content": "hi"}])
        assert result1.text == "streamed"
        client.chat_stream.assert_called_once()

        handler.streaming = False
        result2 = handler.stream([{"role": "user", "content": "hi"}])
        assert result2.text == "completed"
        client.complete.assert_called_once()


# ==================== Mutation-targeted assertions ====================


@pytest.mark.unit
class TestStreamHandlerMutationTargets:
    """Tests targeting specific surviving mutation patterns across all paths."""

    # --- UsageReport cache token fields (gaps 1 & 4) ---

    def test_streaming_usage_report_all_fields(self):
        """UsageReport event from streaming path carries ALL fields including cache tokens."""
        from packages.core.events import UsageReport

        client = Mock(spec=LLMClient)
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cache_read_tokens=30,
            cache_write_tokens=10,
        )
        client.chat_stream.return_value = _make_streaming_response(["ok"], usage)
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="test")
        tracker = MetricsTracker()

        events = []
        handler = StreamHandler(
            client,
            tracker,
            pricing,
            "test-model",
            on_event=events.append,
            instance_id="stream-inst",
        )
        result = handler.stream([{"role": "user", "content": "hi"}])

        usage_events = [e for e in events if isinstance(e, UsageReport)]
        assert len(usage_events) == 1
        ue = usage_events[0]
        assert ue.prompt_tokens == 100
        assert ue.completion_tokens == 50
        assert ue.total_tokens == 150
        assert ue.cache_read_tokens == 30
        assert ue.cache_write_tokens == 10
        assert ue.cost_usd == result.cost_usd
        assert ue.model == "test-model"
        assert ue.instance_id == "stream-inst"

    def test_nonstreaming_usage_report_all_fields(self):
        """UsageReport from non-streaming _complete_simple carries ALL fields."""
        from packages.core.events import UsageReport

        usage = Mock(
            spec=[
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
                "prompt_tokens_details",
            ]
        )
        usage.prompt_tokens = 200
        usage.completion_tokens = 80
        usage.total_tokens = 280
        usage.cache_read_input_tokens = 50
        usage.cache_creation_input_tokens = 15
        usage.prompt_tokens_details = None

        choice = Mock()
        choice.message.content = "response"
        choice.message.tool_calls = None
        response = Mock()
        response.choices = [choice]
        response.usage = usage

        client = Mock(spec=LLMClient)
        client.complete.return_value = response
        pricing = ModelPricing(prompt_cost=1e-6, completion_cost=2e-6, model_id="my-model")
        tracker = MetricsTracker()

        events = []
        handler = StreamHandler(
            client,
            tracker,
            pricing,
            "my-model",
            streaming=False,
            on_event=events.append,
            instance_id="ns-inst",
        )
        result = handler.stream([{"role": "user", "content": "hi"}])

        usage_events = [e for e in events if isinstance(e, UsageReport)]
        assert len(usage_events) == 1
        ue = usage_events[0]
        assert ue.prompt_tokens == 200
        assert ue.completion_tokens == 80
        assert ue.total_tokens == 280
        assert ue.cache_read_tokens == 50
        assert ue.cache_write_tokens == 15
        assert ue.cost_usd == result.cost_usd
        assert ue.model == "my-model"
        assert ue.instance_id == "ns-inst"

    # --- TokenUsage accumulation arithmetic (gap 7) ---

    def test_streaming_intermediate_usage_accumulated(self):
        """Intermediate tool-call usage is ADDED to final streaming usage."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="my_tool",
            description="t",
            parameters={},
            execute=lambda: "result",
        )
        registry = ToolRegistry()
        registry.register(tool)

        call = Mock()
        call.id = "tc1"
        call.function.name = "my_tool"
        call.function.arguments = "{}"

        # Tool call round: 100 prompt + 20 completion
        tool_usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            cache_read_tokens=10,
            cache_write_tokens=5,
        )
        # Final streaming: 80 prompt + 30 completion
        final_usage = TokenUsage(
            prompt_tokens=80,
            completion_tokens=30,
            total_tokens=110,
            cache_read_tokens=8,
            cache_write_tokens=3,
        )

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            StreamToolResult(tool_calls=[call], usage=tool_usage),
            _make_streaming_response(["done"], final_usage),
        ]

        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        handler = StreamHandler(client, tracker, pricing, "test-model")
        result = handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        # Verify accumulation: tool round + final streaming
        assert result.usage.prompt_tokens == 100 + 80
        assert result.usage.completion_tokens == 20 + 30
        assert result.usage.total_tokens == 120 + 110
        assert result.usage.cache_read_tokens == 10 + 8
        assert result.usage.cache_write_tokens == 5 + 3

    def test_nonstreaming_intermediate_usage_accumulated(self):
        """Non-streaming: intermediate tool usage ADDED to final response usage."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="my_tool",
            description="t",
            parameters={"type": "object", "properties": {}},
            execute=lambda **kw: "ok",
        )
        registry = ToolRegistry()
        registry.register(tool)

        tool_call = Mock()
        tool_call.id = "tc1"
        tool_call.function.name = "my_tool"
        tool_call.function.arguments = "{}"

        # Tool round usage
        tool_usage = Mock(
            spec=[
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
                "prompt_tokens_details",
            ]
        )
        tool_usage.prompt_tokens = 100
        tool_usage.completion_tokens = 20
        tool_usage.total_tokens = 120
        tool_usage.cache_read_input_tokens = 10
        tool_usage.cache_creation_input_tokens = 5
        tool_usage.prompt_tokens_details = None

        tool_choice = Mock()
        tool_choice.message.content = ""
        tool_choice.message.tool_calls = [tool_call]
        tool_response = Mock()
        tool_response.choices = [tool_choice]
        tool_response.usage = tool_usage

        # Final response usage
        final_usage = Mock(
            spec=[
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
                "prompt_tokens_details",
            ]
        )
        final_usage.prompt_tokens = 150
        final_usage.completion_tokens = 40
        final_usage.total_tokens = 190
        final_usage.cache_read_input_tokens = 20
        final_usage.cache_creation_input_tokens = 8
        final_usage.prompt_tokens_details = None

        final_choice = Mock()
        final_choice.message.content = "done"
        final_choice.message.tool_calls = None
        final_response = Mock()
        final_response.choices = [final_choice]
        final_response.usage = final_usage

        client = Mock(spec=LLMClient)
        client.complete.side_effect = [tool_response, final_response]

        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        handler = StreamHandler(client, tracker, pricing, "test-model", streaming=False)
        result = handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        # Tool round (100p, 20c) + final (150p, 40c) via _complete_from_text
        assert result.usage.prompt_tokens == 100 + 150
        assert result.usage.completion_tokens == 20 + 40
        assert result.usage.cache_read_tokens == 10 + 20
        assert result.usage.cache_write_tokens == 5 + 8

    # --- Tool message dict key assertions (gaps 2, 3, 6) ---

    def test_tool_message_structure_exact_keys(self):
        """Tool call assistant messages have exact required dict keys."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="search",
            description="s",
            parameters={},
            execute=lambda: "found it",
        )
        registry = ToolRegistry()
        registry.register(tool)

        call = Mock()
        call.id = "tc_42"
        call.function.name = "search"
        call.function.arguments = "{}"

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            StreamToolResult(tool_calls=[call], usage=TokenUsage()),
            _make_streaming_response(["ok"]),
        ]

        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        handler = StreamHandler(client, tracker, pricing, "test-model")
        result = handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        # Assistant tool-call message
        asst_msg = result.tool_messages[0]
        assert set(asst_msg.keys()) == {"role", "content", "tool_calls"}
        assert asst_msg["role"] == "assistant"
        assert asst_msg["content"] is None

        tc = asst_msg["tool_calls"][0]
        assert set(tc.keys()) == {"id", "type", "function"}
        assert tc["id"] == "tc_42"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "search"
        assert tc["function"]["arguments"] == "{}"

        # Tool result message
        tool_msg = result.tool_messages[1]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "tc_42"
        assert tool_msg["content"] == "found it"

    def test_nonstreaming_tool_message_structure_exact_keys(self):
        """Non-streaming tool call messages have exact required dict keys."""
        from packages.core.tools.base import ToolDefinition, ToolRegistry

        tool = ToolDefinition(
            name="lookup",
            description="l",
            parameters={"type": "object", "properties": {}},
            execute=lambda **kw: "data here",
        )
        registry = ToolRegistry()
        registry.register(tool)

        tool_call = Mock()
        tool_call.id = "tc_99"
        tool_call.function.name = "lookup"
        tool_call.function.arguments = '{"key": "val"}'

        tool_choice = Mock()
        tool_choice.message.content = ""
        tool_choice.message.tool_calls = [tool_call]
        tool_response = Mock()
        tool_response.choices = [tool_choice]
        tool_response.usage = Mock(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            prompt_tokens_details=None,
            spec=[
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
                "prompt_tokens_details",
            ],
        )

        final_choice = Mock()
        final_choice.message.content = "done"
        final_choice.message.tool_calls = None
        final_response = Mock()
        final_response.choices = [final_choice]
        final_response.usage = Mock(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            prompt_tokens_details=None,
            spec=[
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
                "prompt_tokens_details",
            ],
        )

        client = Mock(spec=LLMClient)
        client.complete.side_effect = [tool_response, final_response]

        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()
        handler = StreamHandler(client, tracker, pricing, "test-model", streaming=False)
        result = handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        # Assistant tool-call message
        asst_msg = result.tool_messages[0]
        assert set(asst_msg.keys()) == {"role", "content", "tool_calls"}
        assert asst_msg["role"] == "assistant"
        assert asst_msg["content"] is None

        tc = asst_msg["tool_calls"][0]
        assert set(tc.keys()) == {"id", "type", "function"}
        assert tc["id"] == "tc_99"
        assert tc["type"] == "function"
        assert set(tc["function"].keys()) == {"name", "arguments"}
        assert tc["function"]["name"] == "lookup"
        assert tc["function"]["arguments"] == '{"key": "val"}'

        # Tool result message
        tool_msg = result.tool_messages[1]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "tc_99"
        assert tool_msg["content"] == "data here"

    # --- TextChunk instance_id in streaming path (gap 5) ---

    def test_streaming_text_chunk_instance_id(self):
        """Streaming TextChunk events carry instance_id."""
        from packages.core.events import TextChunk

        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["hello"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        events = []
        handler = StreamHandler(
            client,
            tracker,
            pricing,
            "test-model",
            on_event=events.append,
            instance_id="s-inst",
        )
        handler.stream([{"role": "user", "content": "hi"}])

        text_events = [e for e in events if isinstance(e, TextChunk)]
        assert len(text_events) == 1
        assert text_events[0].text == "hello"
        assert text_events[0].instance_id == "s-inst"

    # --- StreamResult fields exact verification ---

    def test_stream_result_delegate_fields_default_none(self):
        """StreamResult delegate fields default to None when no delegation."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["ok"])
        pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
        tracker = MetricsTracker()

        handler = StreamHandler(client, tracker, pricing, "test-model")
        result = handler.stream([{"role": "user", "content": "hi"}])

        assert result.delegate_to is None
        assert result.delegate_task is None
        assert result.delegate_context is None
