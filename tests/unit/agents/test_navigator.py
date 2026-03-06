"""
Unit tests for the Navigator agent.
"""

import pytest
from unittest.mock import Mock, MagicMock

from packages.core.llm_client import LLMClient, StreamingResponse, TokenUsage


def _make_streaming_response(chunks: list[str]):
    mock = MagicMock(spec=StreamingResponse)
    mock.__iter__ = Mock(return_value=iter(chunks))
    mock.usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock.raw_response = Mock()
    return mock


@pytest.mark.unit
class TestNavigatorAgent:
    def test_init_loads_system_prompt(self):
        from packages.agents.navigator.agent import NavigatorAgent

        client = Mock(spec=LLMClient)
        agent = NavigatorAgent(llm_client=client)
        assert "navigator" in agent.config.system_prompt.lower()
        assert agent.name == "navigator"

    def test_system_prompt_contains_review_cadences(self):
        from packages.agents.navigator.agent import NavigatorAgent

        client = Mock(spec=LLMClient)
        agent = NavigatorAgent(llm_client=client)
        prompt = agent.config.system_prompt
        assert "Weekly Review" in prompt
        assert "Monthly Review" in prompt
        assert "Quarterly Review" in prompt
        assert "Yearly Review" in prompt

    def test_system_prompt_contains_philosophical_pillars(self):
        from packages.agents.navigator.agent import NavigatorAgent

        client = Mock(spec=LLMClient)
        agent = NavigatorAgent(llm_client=client)
        prompt = agent.config.system_prompt
        assert "Ikigai" in prompt
        assert "Stoic" in prompt
        assert "GTD" in prompt

    def test_process_message_streams(self):
        from packages.agents.navigator.agent import NavigatorAgent

        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["reflection"])
        agent = NavigatorAgent(llm_client=client)

        response = agent.process_message("I want to do a weekly review")
        chunks = list(response)
        assert chunks == ["reflection"]
        assert len(agent.conversation_history) == 1

    def test_process_message_builds_conversation_history(self):
        from packages.agents.navigator.agent import NavigatorAgent

        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["response 1"])
        agent = NavigatorAgent(llm_client=client)

        agent.process_message("First message")
        assert len(agent.conversation_history) == 1
        assert agent.conversation_history[0]["content"] == "First message"

    def test_meta_export(self):
        from packages.agents.navigator import AGENT_META

        assert AGENT_META["name"] == "navigator"
        assert AGENT_META["command"] == "/navigator"
        assert "agent_class" in AGENT_META
