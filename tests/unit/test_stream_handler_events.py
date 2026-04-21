"""Unit tests for StreamHandler event emission."""

import json
import pytest
from unittest.mock import Mock, MagicMock

from packages.core.events import (
    TextChunk,
    ToolCallStarted,
    ToolResult as ToolResultEvent,
    UsageReport,
)
from packages.core.llm_client import LLMClient, StreamToolResult, TokenUsage, StreamingResponse
from packages.core.pricing import ModelPricing
from packages.core.stream_handler import StreamHandler
from packages.telemetry.metrics import MetricsTracker


def _make_streaming_response(chunks, usage=None):
    if usage is None:
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock = MagicMock(spec=StreamingResponse)
    mock.__iter__ = Mock(return_value=iter(chunks))
    mock.usage = usage
    mock.raw_response = Mock()
    return mock


def _make_handler(client, on_event=None, instance_id=""):
    pricing = ModelPricing(prompt_cost=0, completion_cost=0, model_id="test")
    tracker = MetricsTracker()
    return StreamHandler(
        client,
        tracker,
        pricing,
        "test-model",
        on_event=on_event,
        instance_id=instance_id,
    )


def _make_tool_call_obj(call_id, name, args="{}"):
    call = Mock()
    call.id = call_id
    call.function.name = name
    call.function.arguments = args
    return call


@pytest.mark.unit
class TestStreamHandlerEvents:
    def test_text_chunk_events_emitted(self):
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["Hello", " world"])

        events = []
        handler = _make_handler(client, on_event=events.append, instance_id="writer-1")
        handler.stream([{"role": "user", "content": "hi"}])

        text_events = [e for e in events if isinstance(e, TextChunk)]
        assert len(text_events) == 2
        assert text_events[0].text == "Hello"
        assert text_events[0].instance_id == "writer-1"
        assert text_events[1].text == " world"

    def test_usage_report_emitted(self):
        client = Mock(spec=LLMClient)
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        client.chat_stream.return_value = _make_streaming_response(["ok"], usage)

        events = []
        handler = _make_handler(client, on_event=events.append, instance_id="test-inst")
        handler.stream([{"role": "user", "content": "hi"}])

        usage_events = [e for e in events if isinstance(e, UsageReport)]
        assert len(usage_events) == 1
        assert usage_events[0].prompt_tokens == 100
        assert usage_events[0].completion_tokens == 50
        assert usage_events[0].total_tokens == 150
        assert usage_events[0].model == "test-model"
        assert usage_events[0].instance_id == "test-inst"

    def test_tool_call_events_emitted(self):
        from packages.core.tools.base import ToolRegistry, ToolDefinition

        tool = ToolDefinition(
            name="my_tool",
            description="t",
            parameters={},
            execute=lambda: "result",
        )
        registry = ToolRegistry()
        registry.register(tool)

        call = _make_tool_call_obj("tc1", "my_tool")
        final_stream = _make_streaming_response(["done"])

        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            StreamToolResult(tool_calls=[call], usage=TokenUsage()),
            final_stream,
        ]

        events = []
        handler = _make_handler(client, on_event=events.append, instance_id="test-1")
        handler.stream(
            [{"role": "user", "content": "hi"}],
            tool_registry=registry,
        )

        tool_events = [e for e in events if isinstance(e, ToolCallStarted)]
        assert len(tool_events) == 1
        assert tool_events[0].tool_name == "my_tool"
        assert tool_events[0].tool_call_id == "tc1"
        assert tool_events[0].arguments == "{}"
        assert tool_events[0].instance_id == "test-1"

        # Verify ToolResult event was also emitted
        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert len(result_events) == 1
        assert result_events[0].result == "result"
        assert result_events[0].tool_call_id == "tc1"
        assert result_events[0].instance_id == "test-1"

    def test_no_events_when_callback_not_set(self):
        """When on_event is None, no events are emitted (no error)."""
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["hi"])

        handler = _make_handler(client, on_event=None)
        result = handler.stream([{"role": "user", "content": "hi"}])
        assert result.text == "hi"
