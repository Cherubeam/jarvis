"""
Parameterized tests for data-driven agents (meta.yaml-based).

These tests replace the per-agent test files that existed before the
architecture simplification. All 6 data-driven agents share the same
test coverage via parametrize.
"""

from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest
import yaml

from packages.agents.base import DataDrivenAgent, agent_from_meta
from packages.agents.registry import discover_agents
from packages.core.llm_client import LLMClient, StreamingResponse, TokenUsage


DATA_DRIVEN_AGENTS = [
    "clarity",
    "research",
    "navigator",
    "obsidian_note_creator",
    "okr_architect",
    "pattern_language_expert",
]

_AGENTS_DIR = Path(__file__).parent.parent.parent / "packages" / "agents"


def _make_streaming_response(chunks: list[str]):
    mock = MagicMock(spec=StreamingResponse)
    mock.__iter__ = Mock(return_value=iter(chunks))
    mock.usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock.raw_response = Mock()
    return mock


@pytest.mark.unit
class TestDataDrivenAgentsMeta:
    """Validate meta.yaml structure for all data-driven agents."""

    @pytest.mark.parametrize("agent_name", DATA_DRIVEN_AGENTS)
    def test_meta_yaml_exists(self, agent_name):
        meta_path = _AGENTS_DIR / agent_name / "meta.yaml"
        assert meta_path.is_file(), f"meta.yaml missing for {agent_name}"

    @pytest.mark.parametrize("agent_name", DATA_DRIVEN_AGENTS)
    def test_meta_yaml_has_required_fields(self, agent_name):
        meta_path = _AGENTS_DIR / agent_name / "meta.yaml"
        with open(meta_path) as f:
            meta = yaml.safe_load(f)
        assert "name" in meta
        assert "description" in meta
        assert "command" in meta
        assert meta["command"].startswith("/")

    @pytest.mark.parametrize("agent_name", DATA_DRIVEN_AGENTS)
    def test_system_prompt_exists(self, agent_name):
        prompt_path = _AGENTS_DIR / agent_name / "prompts" / "system.md"
        assert prompt_path.is_file(), f"system.md missing for {agent_name}"
        content = prompt_path.read_text()
        assert len(content) > 50, f"system.md too short for {agent_name}"


@pytest.mark.unit
class TestDataDrivenAgentsInstantiation:
    """Verify agents can be instantiated from meta.yaml."""

    @pytest.mark.parametrize("agent_name", DATA_DRIVEN_AGENTS)
    def test_agent_instantiates_from_meta(self, agent_name):
        meta_path = _AGENTS_DIR / agent_name / "meta.yaml"
        client = Mock(spec=LLMClient)
        agent = agent_from_meta(meta_path, client, "test-model")

        assert isinstance(agent, DataDrivenAgent)
        assert agent.config.system_prompt
        assert len(agent.config.system_prompt) > 50

    @pytest.mark.parametrize("agent_name", DATA_DRIVEN_AGENTS)
    def test_agent_process_message_streams(self, agent_name):
        meta_path = _AGENTS_DIR / agent_name / "meta.yaml"
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = _make_streaming_response(["response"])
        agent = agent_from_meta(meta_path, client, "test-model")

        response = agent.process_message("test input")
        chunks = list(response)
        assert chunks == ["response"]
        assert len(agent.conversation_history) == 1

    @pytest.mark.parametrize("agent_name", DATA_DRIVEN_AGENTS)
    def test_agent_accepts_extra_tools(self, agent_name):
        from packages.core.tools.base import ToolDefinition

        meta_path = _AGENTS_DIR / agent_name / "meta.yaml"
        client = Mock(spec=LLMClient)
        dummy_tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            execute=lambda: "ok",
        )
        agent = agent_from_meta(
            meta_path, client, "test-model", extra_tools=[dummy_tool],
        )
        assert len(agent.config.tools) == 1
        assert agent.config.tools[0].name == "test_tool"


@pytest.mark.unit
class TestDataDrivenAgentsDiscovery:
    """Verify data-driven agents are found by the registry."""

    @pytest.mark.parametrize("agent_name", DATA_DRIVEN_AGENTS)
    def test_discovered_by_registry(self, agent_name):
        agents = discover_agents()
        with open(_AGENTS_DIR / agent_name / "meta.yaml") as f:
            meta_yaml = yaml.safe_load(f)
        agent_key = meta_yaml["name"]
        assert agent_key in agents, f"{agent_name} not discovered"
        meta = agents[agent_key]
        assert meta.agent_class is None
        assert meta.meta_path is not None
        assert meta.command == meta_yaml["command"]
