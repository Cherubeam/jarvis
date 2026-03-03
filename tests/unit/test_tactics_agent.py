"""
Unit tests for TacticsAgent.
"""

import pytest
from unittest.mock import Mock, MagicMock

from packages.core.llm_client import LLMClient, StreamingResponse, TokenUsage
from packages.core.tools.base import ToolDefinition


def _make_streaming_response(chunks: list[str]):
    mock = MagicMock(spec=StreamingResponse)
    mock.__iter__ = Mock(return_value=iter(chunks))
    mock.usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock.raw_response = Mock()
    return mock


@pytest.mark.unit
class TestTacticsAgent:

    def test_init_loads_system_prompt(self):
        from packages.agents.tactics.agent import TacticsAgent
        client = Mock(spec=LLMClient)
        agent = TacticsAgent(llm_client=client)
        assert "tactics coach" in agent.config.system_prompt.lower()
        assert agent.name == "tactics"

    def test_process_message_streams(self):
        from packages.agents.tactics.agent import TacticsAgent
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["try The Hero tactic"])
        agent = TacticsAgent(llm_client=client)

        response = agent.process_message("help me pitch my startup")
        chunks = list(response)
        assert chunks == ["try The Hero tactic"]
        assert len(agent.conversation_history) == 1

    def test_meta_export(self):
        from packages.agents.tactics import AGENT_META
        assert AGENT_META["name"] == "tactics"
        assert AGENT_META["command"] == "/tactics"
        assert "Pip Decks" in AGENT_META["description"]

    def test_extra_tools_registered(self):
        from packages.agents.tactics.agent import TacticsAgent
        client = Mock(spec=LLMClient)

        dummy_tool = ToolDefinition(
            name="search_tactics",
            description="Search tactics",
            parameters={"type": "object", "properties": {}},
            execute=lambda: "result",
        )
        agent = TacticsAgent(llm_client=client, extra_tools=[dummy_tool])

        assert not agent.tool_registry.is_empty()
        assert agent.tool_registry.get("search_tactics") is dummy_tool

    def test_no_tools_when_extra_tools_is_none(self):
        from packages.agents.tactics.agent import TacticsAgent
        client = Mock(spec=LLMClient)
        agent = TacticsAgent(llm_client=client)
        assert agent.tool_registry.is_empty()

    def test_agent_discovered_by_registry(self):
        from packages.agents.registry import discover_agents
        agents = discover_agents()
        assert "tactics" in agents
        meta = agents["tactics"]
        assert meta.command == "/tactics"
