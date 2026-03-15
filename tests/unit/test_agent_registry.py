"""
Unit tests for agent registry.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from packages.agents.registry import discover_agents, get_by_command, AgentMeta


@pytest.mark.unit
class TestDiscoverAgents:
    """Tests for discover_agents()."""

    @pytest.mark.parametrize("name,command", [
        ("writing", "/write"),
        ("research", "/research"),
        ("clarity", "/clarity"),
        ("tactics", "/tactics"),
        ("developer", "/develop"),
    ])
    def test_discovers_agent(self, name, command):
        agents = discover_agents()
        assert name in agents
        assert agents[name].command == command

    def test_excludes_jarvis(self):
        agents = discover_agents()
        assert "jarvis" not in agents

    def test_excludes_pycache(self):
        agents = discover_agents()
        assert "__pycache__" not in agents

    def test_returns_agent_meta_instances(self):
        agents = discover_agents()
        for meta in agents.values():
            assert isinstance(meta, AgentMeta)
            assert meta.name
            assert meta.description
            assert meta.command.startswith("/")

    def test_all_agents_are_data_driven(self):
        agents = discover_agents()
        for meta in agents.values():
            assert meta.meta_path is not None
            assert meta.meta_path.is_file()

    def test_vault_writing_extracted_from_meta_yaml(self):
        agents = discover_agents()
        assert agents["pattern-language-expert"].vault_writing == "patterns"
        assert agents["obsidian-note-creator"].vault_writing == "slip_box"

    def test_vault_writing_none_when_not_declared(self):
        agents = discover_agents()
        assert agents["clarity"].vault_writing is None
        assert agents["research"].vault_writing is None

    def test_tool_groups_extracted_from_meta_yaml(self):
        agents = discover_agents()
        assert agents["writing"].tool_groups == ("blog_tools", "content_evaluator", "suggest_improvements")
        assert agents["developer"].tool_groups == ("dev_tools",)
        assert agents["tactics"].tool_groups == ("card_search",)

    def test_skills_extracted_from_meta_yaml(self):
        agents = discover_agents()
        assert agents["writing"].skills == ("technical-humanist-image-architect",)
        assert agents["pattern-language-expert"].skills == ("pattern-language-expert",)

    def test_tool_groups_empty_when_not_declared(self):
        agents = discover_agents()
        assert agents["clarity"].tool_groups == ()
        assert agents["research"].tool_groups == ()


@pytest.mark.unit
class TestGetByCommand:
    """Tests for get_by_command()."""

    @pytest.mark.parametrize("command,expected_name", [
        ("/write", "writing"),
        ("/research", "research"),
        ("/clarity", "clarity"),
    ])
    def test_finds_command(self, command, expected_name):
        agents = discover_agents()
        meta = get_by_command(command, agents)
        assert meta is not None
        assert meta.name == expected_name

    def test_returns_none_for_unknown_command(self):
        agents = discover_agents()
        meta = get_by_command("/nonexistent", agents)
        assert meta is None

    def test_discovers_agents_if_none_passed(self):
        meta = get_by_command("/write")
        assert meta is not None
        assert meta.name == "writing"
