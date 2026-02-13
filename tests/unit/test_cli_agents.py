"""
Unit tests for agent-related CLI functionality.

Tests parse_args, _handle_agent_command, and --agent flag behavior.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from apps.cli.main import parse_args, _handle_agent_command
from packages.agents.registry import AgentMeta
from packages.core.llm_client import LLMClient, TokenUsage
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.memory import ConversationLogger
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
        args = parse_args(["--agent", "writing"])
        assert args.agent == "writing"

    def test_agent_flag_various_names(self):
        for name in ["writing", "research", "clarity"]:
            args = parse_args(["--agent", name])
            assert args.agent == name


@pytest.mark.unit
class TestHandleAgentCommand:
    def _make_mock_agent_class(self, stream_result=None):
        if stream_result is None:
            stream_result = _make_stream_result()
        agent_instance = Mock()
        agent_instance.run.return_value = stream_result
        agent_class = Mock(return_value=agent_instance)
        return agent_class, agent_instance

    def test_returns_false_for_unknown_command(self):
        result = _handle_agent_command(
            "/unknown", "payload", Mock(), Mock(), Mock(), "model", {}
        )
        assert result is False

    def test_returns_true_for_known_command(self):
        agent_class, _ = self._make_mock_agent_class()
        registry = {
            "writing": AgentMeta(
                name="writing",
                description="desc",
                command="/write",
                agent_class=agent_class,
            )
        }

        logger = Mock(spec=ConversationLogger)
        handler = Mock(spec=StreamHandler)

        result = _handle_agent_command(
            "/write", "some text", Mock(), handler, logger, "model", registry
        )
        assert result is True

    def test_shows_usage_when_no_payload(self, capsys):
        agent_class, _ = self._make_mock_agent_class()
        registry = {
            "writing": AgentMeta(
                name="writing",
                description="Refined prose",
                command="/write",
                agent_class=agent_class,
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
        agent_class, agent_instance = self._make_mock_agent_class(stream_result)
        registry = {
            "writing": AgentMeta(
                name="writing",
                description="desc",
                command="/write",
                agent_class=agent_class,
            )
        }

        client = Mock(spec=LLMClient)
        handler = Mock(spec=StreamHandler)
        logger = Mock(spec=ConversationLogger)

        _handle_agent_command(
            "/write", "fix this text", client, handler, logger, "test-model", registry
        )

        # Agent was instantiated
        agent_class.assert_called_once_with(llm_client=client, model="test-model")
        # run() was called with payload
        agent_instance.run.assert_called_once_with(
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
            cost_usd=0.001,
            ttft_ms=50,
            total_latency_ms=200,
        )
