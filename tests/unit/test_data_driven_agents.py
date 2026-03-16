"""
Parameterized tests for data-driven agents (meta.yaml-based).

All agents are now data-driven (including writing, tactics, developer).
"""

from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest
import yaml

from packages.agents.base import DataDrivenAgent, agent_from_meta
from packages.agents.registry import discover_agents
from packages.core.llm_client import LLMClient, StreamingResponse, TokenUsage


DATA_DRIVEN_AGENTS = [
    "content_reviewer",
    "developer",
    "navigator",
    "obsidian_note_creator",
    "okr_architect",
    "pattern_language_expert",
    "researcher",
    "simplifier",
    "substack_image_creator",
    "substack_publisher",
    "tactics_coach",
    "writer",
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
        assert len(agent.config.tools) >= 1
        tool_names = [t.name for t in agent.config.tools]
        assert "test_tool" in tool_names


@pytest.mark.unit
class TestDataDrivenAgentsSkillBinding:
    """Verify skill binding via meta.yaml skills: field."""

    def test_agent_with_skills_appends_skill_content(self, tmp_path):
        """meta.yaml with skills: list appends skill content to system prompt."""
        from packages.core.tools.base import ToolDefinition
        from packages.skills.registry import SkillMeta

        # Create agent with skills: field
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(
            yaml.dump({"name": "test", "description": "test", "command": "/test", "skills": ["my-skill"]})
        )
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("You are a test agent." * 5)

        # Create skill
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n\n# My Skill\n\nExpertise content here.")

        skill_registry = {
            "my-skill": SkillMeta(
                name="my-skill", description="test", command="/my-skill",
                path=skill_dir, has_skill_py=False,
            ),
        }

        client = Mock(spec=LLMClient)
        agent = agent_from_meta(
            agent_dir / "meta.yaml", client, "test-model",
            skill_registry=skill_registry,
        )

        assert "# My Skill" in agent.config.system_prompt
        assert "Expertise content here." in agent.config.system_prompt

    def test_agent_without_skills_unchanged(self, tmp_path):
        """meta.yaml without skills: field behaves as before."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(
            yaml.dump({"name": "test", "description": "test", "command": "/test"})
        )
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        base_prompt = "You are a test agent." * 5
        (prompts_dir / "system.md").write_text(base_prompt)

        client = Mock(spec=LLMClient)
        agent = agent_from_meta(agent_dir / "meta.yaml", client, "test-model")

        assert agent.config.system_prompt == base_prompt

    def test_agent_with_skills_but_no_registry_unchanged(self, tmp_path):
        """skills: in meta.yaml but no skill_registry passed — no crash."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(
            yaml.dump({"name": "test", "description": "test", "command": "/test", "skills": ["missing"]})
        )
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        base_prompt = "You are a test agent." * 5
        (prompts_dir / "system.md").write_text(base_prompt)

        client = Mock(spec=LLMClient)
        agent = agent_from_meta(agent_dir / "meta.yaml", client, "test-model")

        assert agent.config.system_prompt == base_prompt


@pytest.mark.unit
class TestPromptIncludes:
    """Verify prompt_includes substitution in agent_from_meta."""

    def test_prompt_includes_replaces_placeholders(self, tmp_path):
        """prompt_includes: field replaces {placeholder} in system prompt."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(yaml.dump({
            "name": "test", "description": "test", "command": "/test",
            "prompt_includes": {"voice": "my-voice", "rules": "my-rules"},
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("Voice: {voice}\n\nRules: {rules}")
        (prompts_dir / "my-voice.md").write_text("Speak plainly.")
        (prompts_dir / "my-rules.md").write_text("No fluff.")

        agent = agent_from_meta(agent_dir / "meta.yaml", Mock(spec=LLMClient), "m")

        assert "Speak plainly." in agent.config.system_prompt
        assert "No fluff." in agent.config.system_prompt
        assert "{voice}" not in agent.config.system_prompt
        assert "{rules}" not in agent.config.system_prompt

    def test_prompt_includes_override_blanks_before_expansion(self, tmp_path):
        """prompt_includes_override={\"x\": \"\"} blanks {x} before normal file expansion."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(yaml.dump({
            "name": "test", "description": "test", "command": "/test",
            "prompt_includes": {"greeting": "hello", "farewell": "bye"},
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("A: {greeting}\n\nB: {farewell}")
        (prompts_dir / "hello.md").write_text("Hello world")
        (prompts_dir / "bye.md").write_text("Goodbye world")

        agent = agent_from_meta(
            agent_dir / "meta.yaml", Mock(spec=LLMClient), "m",
            prompt_includes_override={"greeting": ""},
        )

        # {greeting} should be blanked (empty string), not expanded from file
        assert "Hello world" not in agent.config.system_prompt
        assert "A: \n" in agent.config.system_prompt
        # {farewell} should still be expanded normally
        assert "Goodbye world" in agent.config.system_prompt

    def test_prompt_includes_override_replaces_filename(self, tmp_path):
        """prompt_includes_override={\"x\": \"alt\"} replaces the file for {x}."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(yaml.dump({
            "name": "test", "description": "test", "command": "/test",
            "prompt_includes": {"greeting": "hello"},
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("Say: {greeting}")
        (prompts_dir / "hello.md").write_text("Hello world")
        (prompts_dir / "alt-hello.md").write_text("Alternative greeting")

        agent = agent_from_meta(
            agent_dir / "meta.yaml", Mock(spec=LLMClient), "m",
            prompt_includes_override={"greeting": "alt-hello"},
        )

        assert "Alternative greeting" in agent.config.system_prompt
        assert "Hello world" not in agent.config.system_prompt

    def test_writer_agent_prompt_includes_work(self):
        """Writer agent's prompt_includes resolve voice-profile and anti-patterns from shared dir."""
        meta_path = _AGENTS_DIR / "writer" / "meta.yaml"
        agent = agent_from_meta(meta_path, Mock(spec=LLMClient), "test-model")

        # voice-profile and anti-patterns should be substituted
        assert "{voice_profile}" not in agent.config.system_prompt
        assert "{anti_patterns}" not in agent.config.system_prompt
        # Content from the included files should be present
        assert len(agent.config.system_prompt) > 200


@pytest.mark.unit
class TestMaxIterations:
    """Verify max_iterations is read from meta.yaml and passed through."""

    def test_max_iterations_read_from_meta(self, tmp_path):
        """max_iterations in meta.yaml is set on AgentConfig."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(yaml.dump({
            "name": "test", "description": "test", "command": "/test",
            "max_iterations": 20,
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("You are a test agent." * 5)

        agent = agent_from_meta(agent_dir / "meta.yaml", Mock(spec=LLMClient), "m")
        assert agent.config.max_iterations == 20

    def test_max_iterations_none_by_default(self, tmp_path):
        """Agents without max_iterations have None."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(yaml.dump({
            "name": "test", "description": "test", "command": "/test",
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("You are a test agent." * 5)

        agent = agent_from_meta(agent_dir / "meta.yaml", Mock(spec=LLMClient), "m")
        assert agent.config.max_iterations is None

    def test_developer_agent_has_max_iterations(self):
        """Developer agent's meta.yaml sets max_iterations=20."""
        meta_path = _AGENTS_DIR / "developer" / "meta.yaml"
        agent = agent_from_meta(meta_path, Mock(spec=LLMClient), "test-model")
        assert agent.config.max_iterations == 20

    def test_max_iterations_passed_to_stream_handler(self, tmp_path):
        """DataDrivenAgent.run() passes max_iterations to stream_handler.stream()."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(yaml.dump({
            "name": "test", "description": "test", "command": "/test",
            "max_iterations": 15,
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("You are a test agent." * 5)

        from packages.core.stream_handler import StreamResult
        from packages.telemetry.metrics import ResponseMetrics

        agent = agent_from_meta(agent_dir / "meta.yaml", Mock(spec=LLMClient), "m")
        handler = Mock()
        handler.stream.return_value = StreamResult(
            text="ok",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            cost_usd=0.0,
            metrics=ResponseMetrics(ttft_ms=10, total_latency_ms=100, prompt_tokens=1, completion_tokens=1),
        )

        agent.run("hello", handler)

        handler.stream.assert_called_once()
        call_kwargs = handler.stream.call_args[1]
        assert call_kwargs["max_iterations"] == 15

    def test_no_max_iterations_not_passed(self, tmp_path):
        """Agents without max_iterations don't pass the kwarg."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(yaml.dump({
            "name": "test", "description": "test", "command": "/test",
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("You are a test agent." * 5)

        from packages.core.stream_handler import StreamResult
        from packages.telemetry.metrics import ResponseMetrics

        agent = agent_from_meta(agent_dir / "meta.yaml", Mock(spec=LLMClient), "m")
        handler = Mock()
        handler.stream.return_value = StreamResult(
            text="ok",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            cost_usd=0.0,
            metrics=ResponseMetrics(ttft_ms=10, total_latency_ms=100, prompt_tokens=1, completion_tokens=1),
        )

        agent.run("hello", handler)

        call_kwargs = handler.stream.call_args[1]
        assert "max_iterations" not in call_kwargs


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
        assert meta.meta_path is not None
        assert meta.command == meta_yaml["command"]
