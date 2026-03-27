"""
Unit tests for agent-related CLI functionality.

Tests parse_args, _handle_agent_command, and --agent flag behavior.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call, ANY

from apps.cli.main import (
    parse_args, _handle_agent_command, _instantiate_agent,
    _run_agent_session, _make_agent_vault_tools, _assemble_agent_tools,
)
from packages.agents.registry import AgentMeta
from packages.core.llm_client import LLMClient, TokenUsage
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.memory import ConversationLogger
from packages.core.tools.base import ToolDefinition
from packages.telemetry.metrics import ResponseMetrics


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
class TestParseArgs:
    def test_default_no_agent(self):
        args = parse_args([])
        assert args.agent is None

    def test_agent_flag(self):
        args = parse_args(["--agent", "writer"])
        assert args.agent == "writer"

    def test_agent_flag_various_names(self):
        for name in ["writer", "researcher", "simplifier"]:
            args = parse_args(["--agent", name])
            assert args.agent == name


@pytest.mark.unit
class TestAssembleAgentTools:
    """Tests for _assemble_agent_tools helper."""

    def test_shared_tools_always_included(self):
        shared = [Mock(spec=ToolDefinition)]
        meta = AgentMeta(name="test", description="", command="/test")
        result = _assemble_agent_tools(meta, shared, {})
        assert len(result) == 1

    def test_tool_groups_resolved(self):
        shared = [Mock(spec=ToolDefinition)]
        blog = [Mock(spec=ToolDefinition), Mock(spec=ToolDefinition)]
        meta = AgentMeta(name="test", description="", command="/test", tool_groups=("blog_tools",))
        result = _assemble_agent_tools(meta, shared, {"blog_tools": blog})
        assert len(result) == 3

    def test_unknown_tool_group_ignored(self):
        meta = AgentMeta(name="test", description="", command="/test", tool_groups=("nonexistent",))
        result = _assemble_agent_tools(meta, [], {})
        assert len(result) == 0

    def test_agent_only_gets_declared_groups(self):
        """Agent with tool_groups=('blog_tools',) doesn't get dev_tools."""
        blog = [Mock(spec=ToolDefinition)]
        dev = [Mock(spec=ToolDefinition)]
        meta = AgentMeta(name="test", description="", command="/test", tool_groups=("blog_tools",))
        result = _assemble_agent_tools(meta, [], {"blog_tools": blog, "dev_tools": dev})
        assert len(result) == 1
        assert result[0] is blog[0]

    def test_only_tool_groups_whitelist(self):
        """only_tool_groups overrides meta.tool_groups and include_shared=False drops shared."""
        shared = [Mock(spec=ToolDefinition)]
        blog = [Mock(spec=ToolDefinition), Mock(spec=ToolDefinition)]
        dev = [Mock(spec=ToolDefinition)]
        meta = AgentMeta(
            name="test", description="", command="/test",
            tool_groups=("blog_tools", "dev_tools"),
        )
        result = _assemble_agent_tools(
            meta, shared, {"blog_tools": blog, "dev_tools": dev},
            only_tool_groups={"blog_tools"}, include_shared=False,
        )
        # Only blog tools, no shared, no dev
        assert len(result) == 2
        assert result[0] is blog[0]
        assert result[1] is blog[1]


@pytest.mark.unit
class TestHandleAgentCommand:
    def test_returns_false_for_unknown_command(self):
        result = _handle_agent_command(
            "/unknown", "payload", Mock(), Mock(), Mock(), "model", {}
        )
        assert result is False

    def test_returns_true_for_known_command(self):
        registry = {
            "writer": AgentMeta(
                name="writer",
                description="desc",
                command="/write",
                meta_path=None,
            )
        }

        logger = Mock(spec=ConversationLogger)
        handler = Mock(spec=StreamHandler)
        handler.streaming = True

        with patch("apps.cli.main.agent_from_meta") as mock_factory:
            mock_agent = Mock()
            mock_agent.run.return_value = _make_stream_result()
            mock_factory.return_value = mock_agent

            result = _handle_agent_command(
                "/write", "some text", Mock(), handler, logger, "model", registry
            )
        assert result is True

    def test_shows_usage_when_no_payload(self, capsys):
        registry = {
            "writer": AgentMeta(
                name="writer",
                description="Refined prose",
                command="/write",
                meta_path=None,
            )
        }

        result = _handle_agent_command(
            "/write", "", Mock(), Mock(), Mock(), "model", registry
        )
        assert result is True
        captured = capsys.readouterr()
        assert "Usage: /write" in captured.out

    def test_routes_to_agent_and_logs(self):
        stream_result = _make_stream_result("polished text")
        registry = {
            "writer": AgentMeta(
                name="writer",
                description="desc",
                command="/write",
                meta_path=None,
            )
        }

        client = Mock(spec=LLMClient)
        handler = Mock(spec=StreamHandler)
        handler.streaming = True
        logger = Mock(spec=ConversationLogger)

        with patch("apps.cli.main.agent_from_meta") as mock_factory:
            mock_agent = Mock()
            mock_agent.run.return_value = stream_result
            mock_factory.return_value = mock_agent

            _handle_agent_command(
                "/write", "fix this text", client, handler, logger, "test-model", registry
            )

            # run() was called with payload
            mock_agent.run.assert_called_once_with(
                "fix this text", handler, print_chunks=True
            )

        # User message logged
        logger.add_message.assert_any_call("user", "/write fix this text")
        # Assistant response logged
        logger.add_message.assert_any_call(
            "assistant",
            "polished text",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cache_read_tokens=0,
            cache_write_tokens=0,
            cost_usd=0.001,
            ttft_ms=50,
            total_latency_ms=200,
            agent_name="writer",
        )

    def test_tool_groups_passed_to_agent(self):
        """Tool groups are assembled and passed to the agent."""
        dummy_tool = ToolDefinition(
            name="search_tactics", description="Search",
            parameters={"type": "object", "properties": {}},
            execute=lambda: "r",
        )

        registry = {
            "tactics": AgentMeta(
                name="tactics", description="desc",
                command="/tactics", meta_path=None,
                tool_groups=("card_search",),
            )
        }

        with patch("apps.cli.main.agent_from_meta") as mock_factory:
            mock_agent = Mock()
            mock_agent.run.return_value = _make_stream_result()
            mock_factory.return_value = mock_agent

            _handle_agent_command(
                "/tactics", "help me pitch", Mock(), Mock(), Mock(), "model",
                registry,
                shared_tools=[],
                tool_groups={"card_search": [dummy_tool]},
            )

            # Verify extra_tools passed to agent_from_meta
            call_kwargs = mock_factory.call_args
            extra = call_kwargs[1].get("extra_tools") or call_kwargs[0][3] if len(call_kwargs[0]) > 3 else call_kwargs[1].get("extra_tools")
            assert extra == [dummy_tool]

    def test_no_payload_starts_session_when_session_provided(self):
        """No-payload + session triggers _run_agent_session instead of usage."""
        registry = {
            "tactics": AgentMeta(
                name="tactics", description="desc",
                command="/tactics", meta_path=None,
            )
        }

        with patch("apps.cli.main._run_agent_session") as mock_session, \
             patch("apps.cli.main.agent_from_meta") as mock_factory:
            mock_factory.return_value = Mock()
            result = _handle_agent_command(
                "/tactics", "", Mock(), Mock(), Mock(), "model",
                registry, session=Mock(),
            )

        assert result is True
        mock_session.assert_called_once()

    def test_no_payload_shows_usage_when_no_session(self, capsys):
        """No-payload + no session falls back to usage text."""
        registry = {
            "tactics": AgentMeta(
                name="tactics", description="Pip Decks coaching",
                command="/tactics", meta_path=None,
            )
        }

        result = _handle_agent_command(
            "/tactics", "", Mock(), Mock(), Mock(), "model",
            registry, session=None,
        )
        assert result is True
        captured = capsys.readouterr()
        assert "Usage: /tactics" in captured.out


@pytest.mark.unit
class TestRunAgentSession:
    """Tests for the _run_agent_session helper."""

    @patch("apps.cli.main.prompt_user")
    def test_exit_returns_to_jarvis(self, mock_prompt, capsys):
        """Typing /exit breaks the session loop."""
        mock_prompt.side_effect = ["/exit"]
        agent = Mock()
        logger = Mock(spec=ConversationLogger)
        handler = Mock(spec=StreamHandler)
        handler.streaming = True

        _run_agent_session(agent, "tactics", handler, logger, Mock())

        agent.run.assert_not_called()
        captured = capsys.readouterr()
        assert "Entering tactics session" in captured.out
        assert "Returning to JARVIS" in captured.out

    @patch("apps.cli.main.prompt_user")
    def test_back_returns_to_jarvis(self, mock_prompt, capsys):
        """/back also exits the session."""
        mock_prompt.side_effect = ["/back"]
        agent = Mock()

        _run_agent_session(agent, "tactics", Mock(), Mock(), Mock())

        agent.run.assert_not_called()

    @patch("apps.cli.main.finish_live_stream")
    @patch("apps.cli.main.start_live_stream", return_value=(Mock(), Mock()))
    @patch("apps.cli.main.make_live_chunk_handler", return_value=Mock())
    @patch("apps.cli.main.prompt_user")
    def test_multi_turn_conversation(
        self, mock_prompt, mock_chunk, mock_start, mock_finish, capsys
    ):
        """Multiple turns accumulate history and log messages."""
        mock_prompt.side_effect = ["hello", "follow up", "/exit"]

        result1 = _make_stream_result("response 1")
        result2 = _make_stream_result("response 2")
        agent = Mock()
        agent.run.side_effect = [result1, result2]
        logger = Mock(spec=ConversationLogger)
        handler = Mock(spec=StreamHandler)
        handler.streaming = True

        _run_agent_session(agent, "tactics", handler, logger, Mock())

        # Agent was called twice
        assert agent.run.call_count == 2

        # First call: empty history (messages_override=[])
        first_call = agent.run.call_args_list[0]
        assert first_call[0][0] == "hello"
        assert first_call[1]["messages_override"] == []

        # Second call: history contains the first exchange
        second_call = agent.run.call_args_list[1]
        assert second_call[0][0] == "follow up"
        assert len(second_call[1]["messages_override"]) == 2
        assert second_call[1]["messages_override"][0]["content"] == "hello"
        assert second_call[1]["messages_override"][1]["content"] == "response 1"

        # All messages logged
        assert logger.add_message.call_count == 4  # 2 user + 2 assistant

    @patch("apps.cli.main.prompt_user")
    def test_empty_input_skipped(self, mock_prompt):
        """Empty input lines are ignored."""
        mock_prompt.side_effect = ["", "", "/exit"]
        agent = Mock()

        _run_agent_session(agent, "tactics", Mock(), Mock(), Mock())

        agent.run.assert_not_called()

    @patch("apps.cli.main.prompt_user")
    def test_eof_exits_session(self, mock_prompt, capsys):
        """EOFError (Ctrl-D) cleanly exits the session."""
        mock_prompt.side_effect = EOFError

        _run_agent_session(Mock(), "tactics", Mock(), Mock(), Mock())

        captured = capsys.readouterr()
        assert "Returning to JARVIS" in captured.out


@pytest.mark.unit
class TestRunAgentSessionHandoff:
    """Tests for context and prior_session handoff in _run_agent_session."""

    @patch("apps.cli.main.prompt_user")
    def test_returns_session_history(self, mock_prompt, capsys):
        """_run_agent_session returns the session history list."""
        mock_prompt.side_effect = ["/exit"]
        result = _run_agent_session(Mock(), "test", Mock(), Mock(), Mock())
        assert isinstance(result, list)
        assert result == []

    @patch("apps.cli.main.finish_live_stream")
    @patch("apps.cli.main.start_live_stream", return_value=(Mock(), Mock()))
    @patch("apps.cli.main.make_live_chunk_handler", return_value=Mock())
    @patch("apps.cli.main.prompt_user")
    def test_returns_history_with_messages(
        self, mock_prompt, mock_chunk, mock_start, mock_finish
    ):
        """Session with messages returns populated history."""
        mock_prompt.side_effect = ["hello", "/exit"]
        agent = Mock()
        agent.run.return_value = _make_stream_result("reply")

        result = _run_agent_session(agent, "test", Mock(), Mock(), Mock())

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "hello"}
        assert result[1] == {"role": "assistant", "content": "reply"}

    @patch("apps.cli.main.prompt_user")
    def test_context_prepends_exchange(self, mock_prompt, capsys):
        """context param prepends a context exchange to session_history."""
        mock_prompt.side_effect = ["/exit"]
        result = _run_agent_session(
            Mock(), "test", Mock(), Mock(), Mock(),
            context="User wants formal tone",
        )
        assert len(result) == 2
        assert "[Context from JARVIS]" in result[0]["content"]
        assert "formal tone" in result[0]["content"]
        assert result[1]["role"] == "assistant"

    @patch("apps.cli.main.prompt_user")
    def test_prior_session_prepended(self, mock_prompt, capsys):
        """prior_session messages appear at the start of session_history."""
        mock_prompt.side_effect = ["/exit"]
        prior = [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ]
        result = _run_agent_session(
            Mock(), "test", Mock(), Mock(), Mock(),
            prior_session=prior,
        )
        assert len(result) == 2
        assert result[0]["content"] == "previous question"
        assert result[1]["content"] == "previous answer"

    @patch("apps.cli.main.prompt_user")
    def test_prior_session_and_context_combined(self, mock_prompt, capsys):
        """Both prior_session and context are included, prior first."""
        mock_prompt.side_effect = ["/exit"]
        prior = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        result = _run_agent_session(
            Mock(), "test", Mock(), Mock(), Mock(),
            context="some context",
            prior_session=prior,
        )
        # prior_session (2) + context exchange (2) = 4
        assert len(result) == 4
        assert result[0]["content"] == "q1"
        assert result[1]["content"] == "a1"
        assert "[Context from JARVIS]" in result[2]["content"]


@pytest.mark.unit
class TestInstantiateAgent:
    """Tests for the _instantiate_agent helper (all data-driven)."""

    def test_data_driven_agent_from_meta_path(self, tmp_path):
        """Uses agent_from_meta() to create DataDrivenAgent."""
        import yaml as _yaml

        # Create a minimal meta.yaml + system prompt
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        meta_path = agent_dir / "meta.yaml"
        meta_path.write_text(_yaml.dump({
            "name": "test-agent",
            "description": "A test agent",
            "command": "/test-agent",
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("You are a test agent." * 5)

        meta = AgentMeta(
            name="test-agent", description="A test agent",
            command="/test-agent", meta_path=meta_path,
        )
        client = Mock(spec=LLMClient)
        agent = _instantiate_agent(meta, client, "test-model")

        from packages.agents.base import DataDrivenAgent
        assert isinstance(agent, DataDrivenAgent)
        assert agent.config.name == "test-agent"

    def test_data_driven_agent_receives_extra_tools(self, tmp_path):
        """Data-driven agents get extra_tools passed through."""
        import yaml as _yaml

        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        meta_path = agent_dir / "meta.yaml"
        meta_path.write_text(_yaml.dump({
            "name": "test-agent",
            "description": "desc",
            "command": "/test",
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("You are a test agent." * 5)

        dummy_tool = ToolDefinition(
            name="test_tool", description="test",
            parameters={"type": "object", "properties": {}},
            execute=lambda: "ok",
        )

        meta = AgentMeta(
            name="test-agent", description="desc",
            command="/test", meta_path=meta_path,
        )
        agent = _instantiate_agent(meta, Mock(spec=LLMClient), "model", [dummy_tool])
        assert len(agent.config.tools) == 1

    def test_delegation_keeps_meta_max_iterations(self, tmp_path):
        """Delegated agent keeps its meta.yaml max_iterations."""
        import yaml as _yaml

        agent_dir = tmp_path / "writer"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(_yaml.dump({
            "name": "writer",
            "description": "Writing agent",
            "command": "/write",
            "max_iterations": 2,
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("You are a writing agent." * 5)

        meta = AgentMeta(
            name="writer", description="Writing agent",
            command="/write", meta_path=agent_dir / "meta.yaml",
        )

        agent = _instantiate_agent(meta, Mock(spec=LLMClient), "test-model")
        assert agent.config.max_iterations == 2

    def test_handle_agent_command_with_data_driven_agent(self, tmp_path):
        """_handle_agent_command works with data-driven agents."""
        import yaml as _yaml

        agent_dir = tmp_path / "clarity"
        agent_dir.mkdir()
        (agent_dir / "meta.yaml").write_text(_yaml.dump({
            "name": "clarity", "description": "Explains things", "command": "/clarity",
        }))
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.md").write_text("You explain things clearly." * 5)

        meta = AgentMeta(
            name="clarity", description="Explains things",
            command="/clarity",
            meta_path=agent_dir / "meta.yaml",
        )
        registry = {"clarity": meta}

        with patch("apps.cli.main.agent_from_meta") as mock_factory:
            mock_agent = Mock()
            mock_agent.run.return_value = _make_stream_result()
            mock_factory.return_value = mock_agent

            result = _handle_agent_command(
                "/clarity", "explain this", Mock(), Mock(), Mock(),
                "model", registry,
            )

        assert result is True
        mock_factory.assert_called_once()


@pytest.mark.unit
class TestMakeAgentVaultTools:
    """Tests for _make_agent_vault_tools helper."""

    def test_returns_empty_when_no_vault_config(self):
        meta = AgentMeta(name="test", description="", command="/test", vault_writing="patterns")
        result = _make_agent_vault_tools(meta, {}, None)
        assert result == []

    def test_returns_empty_when_no_vault_writing(self):
        meta = AgentMeta(name="test", description="", command="/test", vault_writing=None)
        result = _make_agent_vault_tools(meta, {}, Mock())
        assert result == []

    def test_returns_empty_when_target_dir_empty(self):
        meta = AgentMeta(name="test", description="", command="/test", vault_writing="patterns")
        config = {"obsidian": {"writing": {"patterns": {"target_dir": "", "template_path": ""}}}}
        result = _make_agent_vault_tools(meta, config, Mock())
        assert result == []

    def test_returns_empty_when_config_section_missing(self):
        meta = AgentMeta(name="test", description="", command="/test", vault_writing="nonexistent")
        config = {"obsidian": {"writing": {}}}
        result = _make_agent_vault_tools(meta, config, Mock())
        assert result == []

    @patch("packages.core.tools.vault_write_tools.make_vault_write_tools")
    def test_calls_factory_with_correct_args(self, mock_factory):
        """Calls make_vault_write_tools with target_dir and template_path from config."""
        mock_factory.return_value = [Mock()]
        meta = AgentMeta(name="test", description="", command="/test", vault_writing="slip_box")
        config = {
            "obsidian": {
                "writing": {
                    "slip_box": {
                        "target_dir": "04 – Slip Box",
                        "template_path": "Templates/Permanent Note.md",
                    }
                }
            }
        }
        vault_config = Mock()

        result = _make_agent_vault_tools(meta, config, vault_config)

        assert len(result) == 1
        mock_factory.assert_called_once()
        call_kwargs = mock_factory.call_args
        assert call_kwargs[1]["target_dir"] == "04 – Slip Box"
        assert call_kwargs[1]["template_path"] == "Templates/Permanent Note.md"

    @patch("packages.core.tools.vault_write_tools.make_vault_write_tools")
    def test_patterns_config_routed_correctly(self, mock_factory):
        """vault_writing='patterns' reads obsidian.writing.patterns section."""
        mock_factory.return_value = [Mock(), Mock()]
        meta = AgentMeta(name="test", description="", command="/test", vault_writing="patterns")
        config = {
            "obsidian": {
                "writing": {
                    "patterns": {
                        "target_dir": "02 – Areas/02 – Patterns",
                        "template_path": "Templates/Permanent Note.md",
                    }
                }
            }
        }
        result = _make_agent_vault_tools(meta, config, Mock())
        assert len(result) == 2
        assert mock_factory.call_args[1]["target_dir"] == "02 – Areas/02 – Patterns"


@pytest.mark.unit
class TestJarvisAgentPromptLoading:
    """Tests for JarvisAgent.load_prompt and get_daily_note_instructions."""

    def test_load_daily_note_entry_prompt(self):
        """JarvisAgent.load_prompt('daily_note_entry') returns the prompt content."""
        from packages.agents.jarvis.agent import JarvisAgent

        content = JarvisAgent.load_prompt("daily_note_entry")
        assert "Daily Note" in content
        assert "DO NOT" in content

    def test_get_daily_note_instructions(self):
        """JarvisAgent.get_daily_note_instructions() returns the daily note prompt."""
        from packages.agents.jarvis.agent import JarvisAgent

        content = JarvisAgent.get_daily_note_instructions()
        assert len(content) > 0
        assert "Daily Note" in content
        assert "DO NOT" in content
        assert "bullet" in content.lower()
        assert "OUTPUT ONLY" in content

    def test_load_general_writing_prompt(self):
        """JarvisAgent.load_prompt('general_writing') returns the writing conventions."""
        from packages.agents.jarvis.agent import JarvisAgent

        content = JarvisAgent.load_prompt("general_writing")
        assert "Obsidian" in content
