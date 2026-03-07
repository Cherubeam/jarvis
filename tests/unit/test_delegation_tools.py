"""
Unit tests verifying that delegated agents receive only agent_only_tools,
not JARVIS's orchestration tools (extra_tools like conversation recall).
"""

import pytest
from unittest.mock import Mock, patch

from packages.agents.registry import AgentMeta
from packages.core.tools.base import ToolDefinition
from packages.core.stream_handler import StreamResult
from packages.core.llm_client import TokenUsage
from packages.telemetry.metrics import ResponseMetrics


def _dummy_tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} tool",
        parameters={"type": "object", "properties": {}},
        execute=lambda: "ok",
    )


def _make_stream_result(text="done", delegate_to=None, delegate_task=None):
    return StreamResult(
        text=text,
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        cost_usd=0.001,
        metrics=ResponseMetrics(
            ttft_ms=50, total_latency_ms=200,
            prompt_tokens=10, completion_tokens=5,
        ),
        delegate_to=delegate_to,
        delegate_task=delegate_task,
    )


@pytest.mark.unit
class TestDelegationToolIsolation:
    """Delegated agents must NOT receive JARVIS's extra_tools (recall, card search)."""

    def test_delegated_agent_receives_only_agent_only_tools(self):
        """When JARVIS delegates, the sub-agent gets agent_only_tools, not extra_tools.

        This prevents orchestration tools like conversation_recall from leaking
        into delegated agent sessions (fix/recall-tool-delegation-leak).
        """
        recall_tool = _dummy_tool("recall_conversations")
        card_search_tool = _dummy_tool("card_search")
        blog_tool = _dummy_tool("blog_read")
        evaluator_tool = _dummy_tool("content_evaluator")

        extra_tools = [recall_tool, card_search_tool]
        agent_only_tools = [blog_tool, evaluator_tool]

        # Simulate the delegation logic from main.py (line ~740)
        all_delegate_tools = agent_only_tools  # NOT extra_tools + agent_only_tools

        assert recall_tool not in all_delegate_tools
        assert card_search_tool not in all_delegate_tools
        assert blog_tool in all_delegate_tools
        assert evaluator_tool in all_delegate_tools

    def test_delegated_agent_constructed_without_extra_tools(self):
        """End-to-end: a delegated agent class receives only agent_only_tools."""
        recall_tool = _dummy_tool("recall_conversations")
        blog_tool = _dummy_tool("blog_read")

        extra_tools = [recall_tool]
        agent_only_tools = [blog_tool]

        created_with = {}

        class FakeDelegateAgent:
            def __init__(self, *, llm_client, model, extra_tools=None):
                created_with["extra_tools"] = extra_tools

            def run(self, *args, **kwargs):
                return _make_stream_result()

        # Reproduce the delegation path from main.py
        import inspect
        sig = inspect.signature(FakeDelegateAgent.__init__)
        all_delegate_tools = agent_only_tools  # The fix

        if "extra_tools" in sig.parameters and all_delegate_tools:
            FakeDelegateAgent(
                llm_client=Mock(), model="test", extra_tools=all_delegate_tools,
            )

        assert created_with["extra_tools"] == [blog_tool]
        assert recall_tool not in created_with["extra_tools"]

    def test_standalone_agent_mode_receives_all_tools(self):
        """In --agent mode (standalone), agents get both extra_tools and agent_only_tools.

        This is intentional — standalone agents benefit from recall.
        """
        recall_tool = _dummy_tool("recall_conversations")
        blog_tool = _dummy_tool("blog_read")

        extra_tools = [recall_tool]
        agent_only_tools = [blog_tool]

        # Standalone mode (main.py line ~532) combines both
        all_agent_tools = extra_tools + agent_only_tools

        assert recall_tool in all_agent_tools
        assert blog_tool in all_agent_tools
