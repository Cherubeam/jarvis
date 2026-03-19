"""Unit tests for the events module."""

import pytest

from packages.core.events import (
    TextChunk,
    ToolCallStarted,
    ToolResult,
    UsageReport,
    DelegationRequested,
    AgentStarted,
    AgentFinished,
)


@pytest.mark.unit
class TestEvents:
    """Tests for typed event dataclasses."""

    def test_text_chunk_creation(self):
        chunk = TextChunk(text="Hello", instance_id="writer-1")
        assert chunk.text == "Hello"
        assert chunk.instance_id == "writer-1"

    def test_text_chunk_defaults(self):
        chunk = TextChunk(text="Hi")
        assert chunk.instance_id == ""

    def test_text_chunk_is_frozen(self):
        chunk = TextChunk(text="Hello")
        with pytest.raises(AttributeError):
            chunk.text = "World"

    def test_tool_call_started(self):
        event = ToolCallStarted(
            tool_name="read_note",
            tool_call_id="tc1",
            arguments='{"path": "test.md"}',
            instance_id="researcher-1",
        )
        assert event.tool_name == "read_note"
        assert event.tool_call_id == "tc1"

    def test_tool_result(self):
        event = ToolResult(
            tool_name="read_note",
            result="Note contents",
            tool_call_id="tc1",
        )
        assert event.result == "Note contents"

    def test_usage_report(self):
        event = UsageReport(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
            model="test-model",
        )
        assert event.total_tokens == 150
        assert event.cost_usd == 0.001

    def test_delegation_requested(self):
        event = DelegationRequested(
            target_agent="writer",
            task="Write a blog post",
            context="About AI",
        )
        assert event.target_agent == "writer"

    def test_agent_started(self):
        event = AgentStarted(
            instance_id="writer-1",
            role="writer",
            task="Write article",
        )
        assert event.instance_id == "writer-1"

    def test_agent_finished_defaults(self):
        event = AgentFinished(instance_id="writer-1", role="writer")
        assert event.status == "completed"
        assert event.error == ""
        assert event.cost_usd == 0.0

    def test_agent_finished_with_error(self):
        event = AgentFinished(
            instance_id="writer-1",
            role="writer",
            status="failed",
            error="Budget exceeded",
        )
        assert event.status == "failed"
        assert event.error == "Budget exceeded"
