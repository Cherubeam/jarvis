"""
Unit tests for the delegation tool and DelegationState.
"""

import pytest
from packages.core.tools.base import ToolDefinition
from packages.core.tools.delegate import DelegationState, make_delegate_tool


AVAILABLE_AGENTS = [
    {"name": "writing", "description": "Writing and content creation"},
    {"name": "research", "description": "Research and analysis"},
]


@pytest.mark.unit
class TestDelegationState:

    def test_defaults_to_none(self):
        state = DelegationState()
        assert state.agent_name is None
        assert state.task is None
        assert state.context is None


@pytest.mark.unit
class TestDelegateTool:

    def test_factory_returns_tool_definition(self):
        state = DelegationState()
        tool = make_delegate_tool(AVAILABLE_AGENTS, state)

        assert isinstance(tool, ToolDefinition)
        assert tool.name == "delegate_to_agent"
        assert tool.parameters["properties"]["agent_name"]["enum"] == ["writing", "research"]
        assert tool.parameters["required"] == ["agent_name", "task"]

    def test_execute_sets_state(self):
        state = DelegationState()
        tool = make_delegate_tool(AVAILABLE_AGENTS, state)

        result = tool.execute(agent_name="writing", task="Review my blog post")

        assert state.agent_name == "writing"
        assert state.task == "Review my blog post"
        assert "Delegating to writing" in result

    def test_execute_unknown_agent_returns_error(self):
        state = DelegationState()
        tool = make_delegate_tool(AVAILABLE_AGENTS, state)

        result = tool.execute(agent_name="unknown", task="do stuff")

        assert state.agent_name is None
        assert state.task is None
        assert "Unknown agent" in result
        assert "writing" in result

    def test_terminal_flag_is_true(self):
        state = DelegationState()
        tool = make_delegate_tool(AVAILABLE_AGENTS, state)

        assert tool.terminal is True

    def test_enum_constraint_matches_agents(self):
        state = DelegationState()
        agents = [{"name": "a", "description": "A agent"}]
        tool = make_delegate_tool(agents, state)

        assert tool.parameters["properties"]["agent_name"]["enum"] == ["a"]

    def test_context_param_stored_on_state(self):
        state = DelegationState()
        tool = make_delegate_tool(AVAILABLE_AGENTS, state)

        tool.execute(agent_name="writing", task="Write post", context="User prefers formal tone")

        assert state.context == "User prefers formal tone"

    def test_missing_context_defaults_to_none(self):
        state = DelegationState()
        tool = make_delegate_tool(AVAILABLE_AGENTS, state)

        tool.execute(agent_name="writing", task="Write post")

        assert state.context is None

    def test_empty_context_defaults_to_none(self):
        state = DelegationState()
        tool = make_delegate_tool(AVAILABLE_AGENTS, state)

        tool.execute(agent_name="writing", task="Write post", context="")

        assert state.context is None

    def test_context_in_tool_schema(self):
        state = DelegationState()
        tool = make_delegate_tool(AVAILABLE_AGENTS, state)

        assert "context" in tool.parameters["properties"]
        assert tool.parameters["properties"]["context"]["type"] == "string"
