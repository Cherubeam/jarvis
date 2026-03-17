"""
Unit tests for StreamHandler.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.llm_client import LLMClient, StreamToolResult, TokenUsage, StreamingResponse
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
        from packages.core.tools.base import ToolRegistry, ToolDefinition

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

        # Tool feedback printed to stdout
        captured = capsys.readouterr()
        assert "[Tool: fetch_url]" in captured.out

        # Final content
        assert "content of https://example.com" in result.text

        # stream_with_tool_detection called twice: tool call then content
        assert client.stream_with_tool_detection.call_count == 2

    def test_multi_tool_chain(self, capsys):
        """LLM calls tool A, then tool B, then streams final answer."""
        import json
        from packages.core.tools.base import ToolRegistry, ToolDefinition

        tool_a = ToolDefinition(name="tool_a", description="a", parameters={}, execute=lambda: "result_a")
        tool_b = ToolDefinition(name="tool_b", description="b", parameters={}, execute=lambda: "result_b")
        registry = ToolRegistry()
        registry.register(tool_a)
        registry.register(tool_b)

        call_a = _make_tool_call_obj("tc1", "tool_a")
        call_b = _make_tool_call_obj("tc2", "tool_b")
        final_stream = _make_streaming_response(["final answer"])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            _make_stream_tool_result([call_a]),
            _make_stream_tool_result([call_b]),
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

    def test_on_tool_call_callback_invoked(self, capsys):
        """When on_tool_call is set, it is called instead of plain print()."""
        import json
        from packages.core.tools.base import ToolRegistry, ToolDefinition

        tool = ToolDefinition(
            name="my_tool", description="t", parameters={},
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
        import json
        from packages.core.tools.base import ToolRegistry, ToolDefinition

        tool = ToolDefinition(
            name="my_tool", description="t", parameters={},
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
        import json
        from packages.core.tools.base import ToolRegistry, ToolDefinition

        tool = ToolDefinition(
            name="my_tool", description="t", parameters={},
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

        assert len(result.tool_messages) >= 2
        # First message is the assistant with tool_calls
        assert result.tool_messages[0]["role"] == "assistant"
        # Second message is the tool result
        assert result.tool_messages[1]["role"] == "tool"

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
        from packages.core.tools.base import ToolRegistry, ToolDefinition

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
            "tc1", "delegate_to_agent",
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
        # Result has empty text
        assert result.text == ""
        # Tool messages are preserved
        assert len(result.tool_messages) >= 2
        assert result.tool_messages[0]["role"] == "assistant"
        assert result.tool_messages[1]["role"] == "tool"

    def test_duplicate_parallel_tool_calls_deduplicated(self, capsys):
        """LLM returns 3 identical tool calls; only one is executed."""
        from packages.core.tools.base import ToolRegistry, ToolDefinition

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
        from packages.core.tools.base import ToolRegistry, ToolDefinition

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
        from packages.core.tools.base import ToolRegistry, ToolDefinition

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
        from packages.core.tools.base import ToolRegistry, ToolDefinition

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

        # All iterations consumed — final chat_stream called with tools=None
        client.chat_stream.assert_called_once()
        _, kwargs = client.chat_stream.call_args
        assert kwargs.get("tools") is None
        assert result.text == "forced text"

    def test_max_tokens_passed_to_chat_stream(self):
        """When max_tokens is set, it is forwarded to chat_stream on the simple path."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["ok"])

        handler = self._make_handler(client)
        handler.max_tokens = 16384
        handler.stream([{"role": "user", "content": "hi"}])

        client.chat_stream.assert_called_once_with(
            [{"role": "user", "content": "hi"}], tools=None, max_tokens=16384,
        )

    def test_max_tokens_passed_to_stream_with_tool_detection(self):
        """When max_tokens is set, it is forwarded to stream_with_tool_detection."""
        from packages.core.tools.base import ToolRegistry, ToolDefinition

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
        from packages.core.tools.base import ToolRegistry, ToolDefinition

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
        assert "8612" in captured.out

    def test_402_too_few_tokens_raises_runtime_error(self):
        """When affordable tokens < minimum, RuntimeError is raised."""
        from packages.core.llm_client import InsufficientCreditsError

        client = Mock(spec=LLMClient)
        handler = self._make_handler(client, max_tokens=16384)

        client.chat_stream.side_effect = InsufficientCreditsError(
            requested=16384, affordable=100, original_error=Exception(),
        )

        with pytest.raises(RuntimeError, match="Insufficient OpenRouter credits"):
            handler.stream([{"role": "user", "content": "hi"}])

    def test_prompt_limit_error_raises_runtime_error(self):
        """PromptTokenLimitError is converted to RuntimeError with helpful message."""
        from packages.core.llm_client import PromptTokenLimitError

        client = Mock(spec=LLMClient)
        handler = self._make_handler(client, max_tokens=16384)

        client.chat_stream.side_effect = PromptTokenLimitError(
            prompt_tokens=13391, limit=7985, original_error=Exception(),
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
