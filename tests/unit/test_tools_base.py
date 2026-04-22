"""
Unit tests for ToolDefinition and ToolRegistry.
"""

import pytest

from packages.core.tools.base import ToolDefinition, ToolRegistry


def _make_tool(name: str = "my_tool", fn=None) -> ToolDefinition:
    if fn is None:

        def fn(x):
            return f"result:{x}"

    return ToolDefinition(
        name=name,
        description=f"A test tool called {name}",
        parameters={
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        },
        execute=fn,
    )


@pytest.mark.unit
class TestToolDefinition:
    def test_to_litellm_format_structure(self):
        tool = _make_tool("greet")
        fmt = tool.to_litellm_format()

        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "greet"
        assert fmt["function"]["description"] == "A test tool called greet"
        assert "properties" in fmt["function"]["parameters"]

    def test_execute_calls_function(self):
        tool = _make_tool("echo", fn=lambda x: f"echo:{x}")
        assert tool.execute(x="hello") == "echo:hello"


@pytest.mark.unit
class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = _make_tool("alpha")
        registry.register(tool)

        retrieved = registry.get("alpha")
        assert retrieved is tool

    def test_get_returns_none_for_unknown(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_is_empty_true_when_no_tools(self):
        registry = ToolRegistry()
        assert registry.is_empty() is True

    def test_is_empty_false_after_register(self):
        registry = ToolRegistry()
        registry.register(_make_tool("t"))
        assert registry.is_empty() is False

    def test_to_litellm_format_returns_list(self):
        registry = ToolRegistry()
        registry.register(_make_tool("a"))
        registry.register(_make_tool("b"))
        fmt = registry.to_litellm_format()

        assert len(fmt) == 2
        names = {entry["function"]["name"] for entry in fmt}
        assert names == {"a", "b"}

    def test_to_litellm_format_empty_registry(self):
        registry = ToolRegistry()
        assert registry.to_litellm_format() == []

    def test_register_overwrites_same_name(self):
        registry = ToolRegistry()
        tool1 = _make_tool("dup", fn=lambda: "first")
        tool2 = _make_tool("dup", fn=lambda: "second")
        registry.register(tool1)
        registry.register(tool2)

        assert registry.get("dup") is tool2
