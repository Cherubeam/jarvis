"""
Unit tests for promoted agents (Pattern Language Expert, OKR Architect).
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
class TestPatternLanguageExpertAgent:
    def test_init_loads_system_prompt(self):
        from packages.agents.pattern_language_expert.agent import PatternLanguageExpertAgent
        client = Mock(spec=LLMClient)
        agent = PatternLanguageExpertAgent(llm_client=client)
        assert "patternlanguage-expert" in agent.config.system_prompt.lower()
        assert agent.name == "pattern-language-expert"

    def test_process_message_streams(self):
        from packages.agents.pattern_language_expert.agent import PatternLanguageExpertAgent
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["pattern draft"])
        agent = PatternLanguageExpertAgent(llm_client=client)

        response = agent.process_message("Turn this practice into a pattern")
        chunks = list(response)
        assert chunks == ["pattern draft"]
        assert len(agent.conversation_history) == 1

    def test_meta_export(self):
        from packages.agents.pattern_language_expert import AGENT_META
        assert AGENT_META["name"] == "pattern-language-expert"
        assert AGENT_META["command"] == "/pattern-language-expert"


@pytest.mark.unit
class TestOKRArchitectAgent:
    def test_init_loads_system_prompt(self):
        from packages.agents.okr_architect.agent import OKRArchitectAgent
        client = Mock(spec=LLMClient)
        agent = OKRArchitectAgent(llm_client=client)
        assert "okr-architect" in agent.config.system_prompt.lower()
        assert agent.name == "okr-architect"

    def test_process_message_streams(self):
        from packages.agents.okr_architect.agent import OKRArchitectAgent
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["draft okrs"])
        agent = OKRArchitectAgent(llm_client=client)

        response = agent.process_message("Help me write OKRs for Q3")
        chunks = list(response)
        assert chunks == ["draft okrs"]
        assert len(agent.conversation_history) == 1

    def test_meta_export(self):
        from packages.agents.okr_architect import AGENT_META
        assert AGENT_META["name"] == "okr-architect"
        assert AGENT_META["command"] == "/okr-architect"
