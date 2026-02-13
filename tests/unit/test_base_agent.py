"""
Unit tests for BaseAgent — run() and load_prompt().
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse, TokenUsage
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.pricing import ModelPricing
from packages.telemetry.metrics import MetricsTracker, ResponseMetrics


class ConcreteAgent(BaseAgent):
    """Minimal concrete agent for testing."""

    def process_message(self, message, context=None):
        self.add_to_history("user", message)
        return self.llm_client.chat_stream(self.get_messages_for_api())


def _make_stream_result(text: str = "response") -> StreamResult:
    return StreamResult(
        text=text,
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        cost_usd=0.001,
        metrics=ResponseMetrics(
            ttft_ms=50, total_latency_ms=200,
            prompt_tokens=10, completion_tokens=5,
        ),
    )


@pytest.mark.unit
class TestBaseAgentRun:
    """Tests for BaseAgent.run()."""

    def _make_agent(self) -> ConcreteAgent:
        config = AgentConfig(
            name="test",
            description="test agent",
            model="test-model",
            system_prompt="You are a test agent.",
        )
        client = Mock(spec=LLMClient)
        return ConcreteAgent(config, client)

    def test_run_with_messages_override(self):
        agent = self._make_agent()
        handler = Mock(spec=StreamHandler)
        handler.stream.return_value = _make_stream_result()

        history = [{"role": "user", "content": "earlier"}]
        result = agent.run("hello", handler, messages_override=history)

        # Should build: [system, *history, user message]
        call_args = handler.stream.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a test agent."
        assert messages[1] == {"role": "user", "content": "earlier"}
        assert messages[2] == {"role": "user", "content": "hello"}
        assert result.text == "response"

    def test_run_without_messages_override_uses_internal_history(self):
        agent = self._make_agent()
        handler = Mock(spec=StreamHandler)
        handler.stream.return_value = _make_stream_result()

        result = agent.run("hello", handler)

        # Should add to internal history and use it
        call_args = handler.stream.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[1] == {"role": "user", "content": "hello"}
        assert len(agent.conversation_history) == 1

    def test_run_does_not_modify_internal_history_with_override(self):
        agent = self._make_agent()
        handler = Mock(spec=StreamHandler)
        handler.stream.return_value = _make_stream_result()

        agent.run("hello", handler, messages_override=[])
        assert len(agent.conversation_history) == 0

    def test_run_passes_print_chunks(self):
        agent = self._make_agent()
        handler = Mock(spec=StreamHandler)
        handler.stream.return_value = _make_stream_result()

        agent.run("hello", handler, print_chunks=True)
        handler.stream.assert_called_once()
        assert handler.stream.call_args[1]["print_chunks"] is True

    def test_run_returns_stream_result(self):
        agent = self._make_agent()
        handler = Mock(spec=StreamHandler)
        expected = _make_stream_result("test output")
        handler.stream.return_value = expected

        result = agent.run("hello", handler)
        assert result is expected


@pytest.mark.unit
class TestBaseAgentLoadPrompt:
    """Tests for BaseAgent.load_prompt()."""

    def test_load_prompt_from_agent_directory(self, tmp_path):
        """Test that load_prompt reads from prompts/ relative to agent file."""
        # The writing agent has a real system.md prompt — test via it
        from packages.agents.writing.agent import WritingAgent
        prompt = WritingAgent.load_prompt("system")
        assert "writing specialist" in prompt.lower()

    def test_load_prompt_missing_file_raises(self):
        from packages.agents.writing.agent import WritingAgent
        with pytest.raises(FileNotFoundError):
            WritingAgent.load_prompt("nonexistent")

    def test_each_agent_has_system_prompt(self):
        """All three agents should load their system prompt without error."""
        from packages.agents.writing.agent import WritingAgent
        from packages.agents.research.agent import ResearchAgent
        from packages.agents.clarity.agent import ClarityAgent

        for cls in [WritingAgent, ResearchAgent, ClarityAgent]:
            prompt = cls.load_prompt("system")
            assert len(prompt) > 50
