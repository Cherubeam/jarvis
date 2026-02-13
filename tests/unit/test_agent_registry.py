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

    def test_discovers_writing_agent(self):
        agents = discover_agents()
        assert "writing" in agents
        assert agents["writing"].command == "/write"

    def test_discovers_research_agent(self):
        agents = discover_agents()
        assert "research" in agents
        assert agents["research"].command == "/research"

    def test_discovers_clarity_agent(self):
        agents = discover_agents()
        assert "clarity" in agents
        assert agents["clarity"].command == "/clarity"

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
            assert meta.agent_class is not None

    def test_all_agent_classes_are_importable(self):
        agents = discover_agents()
        for meta in agents.values():
            # agent_class should be an actual class
            assert isinstance(meta.agent_class, type)


@pytest.mark.unit
class TestGetByCommand:
    """Tests for get_by_command()."""

    def test_finds_write_command(self):
        agents = discover_agents()
        meta = get_by_command("/write", agents)
        assert meta is not None
        assert meta.name == "writing"

    def test_finds_research_command(self):
        agents = discover_agents()
        meta = get_by_command("/research", agents)
        assert meta is not None
        assert meta.name == "research"

    def test_finds_clarity_command(self):
        agents = discover_agents()
        meta = get_by_command("/clarity", agents)
        assert meta is not None
        assert meta.name == "clarity"

    def test_returns_none_for_unknown_command(self):
        agents = discover_agents()
        meta = get_by_command("/nonexistent", agents)
        assert meta is None

    def test_discovers_agents_if_none_passed(self):
        meta = get_by_command("/write")
        assert meta is not None
        assert meta.name == "writing"
