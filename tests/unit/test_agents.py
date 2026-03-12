"""
Unit tests for specialized agents (Writing, Research, Clarity).
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
class TestWritingAgent:
    def test_init_loads_system_prompt(self):
        from packages.agents.writing.agent import WritingAgent
        client = Mock(spec=LLMClient)
        agent = WritingAgent(llm_client=client)
        assert "writing specialist" in agent.config.system_prompt.lower()
        assert "burstiness" in agent.config.system_prompt.lower()
        assert "banned vocabulary" in agent.config.system_prompt.lower()
        assert agent.name == "writing"

    def test_prompt_has_no_raw_placeholders(self):
        from packages.agents.writing.agent import WritingAgent
        client = Mock(spec=LLMClient)
        agent = WritingAgent(llm_client=client)
        assert "{voice_profile}" not in agent.config.system_prompt
        assert "{anti_patterns}" not in agent.config.system_prompt

    def test_process_message_streams(self):
        from packages.agents.writing.agent import WritingAgent
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["revised text"])
        agent = WritingAgent(llm_client=client)

        response = agent.process_message("fix my prose")
        chunks = list(response)
        assert chunks == ["revised text"]
        assert len(agent.conversation_history) == 1

    def test_meta_export(self):
        from packages.agents.writing import AGENT_META
        assert AGENT_META["name"] == "writing"
        assert AGENT_META["command"] == "/write"


