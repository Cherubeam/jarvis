"""Tests for packages.agents.pattern_language_expert."""

import pytest
from unittest.mock import MagicMock

from packages.agents.pattern_language_expert.agent import PatternLanguageExpertAgent
from packages.core.tools.base import ToolDefinition


@pytest.mark.unit
class TestPatternLanguageExpertAgent:
    def test_creates_without_tools(self):
        client = MagicMock()
        agent = PatternLanguageExpertAgent(llm_client=client)
        assert agent.config.name == "pattern-language-expert"
        assert agent.config.tools == []

    def test_creates_with_extra_tools(self):
        client = MagicMock()
        dummy_tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            execute=lambda: "ok",
        )
        agent = PatternLanguageExpertAgent(
            llm_client=client, extra_tools=[dummy_tool],
        )
        assert len(agent.config.tools) == 1
        assert agent.config.tools[0].name == "test_tool"

    def test_system_prompt_loaded(self):
        client = MagicMock()
        agent = PatternLanguageExpertAgent(llm_client=client)
        assert "PatternLanguage-Expert" in agent.config.system_prompt
        assert "Vault Tools" in agent.config.system_prompt
