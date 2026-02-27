"""
Unit tests for execute_tool_calls().
"""

import json
import pytest
from unittest.mock import Mock

from packages.core.tools.base import ToolDefinition, ToolRegistry
from packages.core.tools.executor import execute_tool_calls


def _make_registry(*tools: ToolDefinition) -> ToolRegistry:
    registry = ToolRegistry()
    for t in tools:
        registry.register(t)
    return registry


def _make_tool_call(call_id: str, name: str, args: dict) -> Mock:
    call = Mock()
    call.id = call_id
    call.function.name = name
    call.function.arguments = json.dumps(args)
    return call


@pytest.mark.unit
class TestExecuteToolCalls:
    def test_executes_known_tool(self):
        tool = ToolDefinition(
            name="greet",
            description="Greet",
            parameters={},
            execute=lambda name: f"Hello, {name}!",
        )
        registry = _make_registry(tool)
        call = _make_tool_call("c1", "greet", {"name": "Alice"})

        results = execute_tool_calls([call], registry)

        assert len(results) == 1
        assert results[0]["role"] == "tool"
        assert results[0]["tool_call_id"] == "c1"
        assert results[0]["content"] == "Hello, Alice!"

    def test_unknown_tool_returns_error_string(self):
        registry = _make_registry()
        call = _make_tool_call("c2", "unknown_tool", {})

        results = execute_tool_calls([call], registry)

        assert results[0]["content"].startswith("Error: Unknown tool")
        assert "unknown_tool" in results[0]["content"]

    def test_exception_in_tool_returns_error_string(self):
        def bad_execute(**kwargs):
            raise ValueError("boom")

        tool = ToolDefinition(
            name="bad",
            description="breaks",
            parameters={},
            execute=bad_execute,
        )
        registry = _make_registry(tool)
        call = _make_tool_call("c3", "bad", {})

        results = execute_tool_calls([call], registry)

        assert results[0]["content"].startswith("Error executing tool")
        assert "boom" in results[0]["content"]

    def test_multiple_tool_calls_all_executed(self):
        tool = ToolDefinition(
            name="double",
            description="doubles",
            parameters={},
            execute=lambda n: str(int(n) * 2),
        )
        registry = _make_registry(tool)
        calls = [
            _make_tool_call("c4", "double", {"n": "3"}),
            _make_tool_call("c5", "double", {"n": "7"}),
        ]

        results = execute_tool_calls(calls, registry)

        assert len(results) == 2
        assert results[0]["content"] == "6"
        assert results[1]["content"] == "14"

    def test_arguments_as_dict_not_string(self):
        """If arguments is already a dict (not JSON string), it should still work."""
        tool = ToolDefinition(
            name="echo",
            description="echo",
            parameters={},
            execute=lambda msg: msg,
        )
        registry = _make_registry(tool)
        call = Mock()
        call.id = "c6"
        call.function.name = "echo"
        call.function.arguments = {"msg": "direct dict"}  # dict, not JSON string

        results = execute_tool_calls([call], registry)
        assert results[0]["content"] == "direct dict"

    def test_empty_tool_calls_returns_empty_list(self):
        registry = _make_registry()
        assert execute_tool_calls([], registry) == []
