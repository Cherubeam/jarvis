"""Tests for MCP tool bridging (MCP types → ToolDefinition)."""

import pytest
from unittest.mock import MagicMock

from mcp import types

from packages.integrations.mcp.bridge import (
    format_call_result,
    mcp_tools_to_tool_definitions,
)


def _make_mcp_tool(
    name: str = "read_file",
    description: str = "Read a file",
    input_schema: dict | None = None,
) -> types.Tool:
    """Create an MCP Tool for testing."""
    return types.Tool(
        name=name,
        description=description,
        inputSchema=input_schema
        or {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )


@pytest.mark.unit
class TestMcpToolsToToolDefinitions:
    """Tests for mcp_tools_to_tool_definitions()."""

    def test_converts_single_tool(self):
        tool = _make_mcp_tool()
        call_fn = MagicMock(return_value="file content")

        result = mcp_tools_to_tool_definitions("filesystem", [tool], call_fn)

        assert len(result) == 1
        td = result[0]
        assert td.name == "mcp_filesystem__read_file"
        assert td.description == "Read a file"
        assert td.parameters == tool.inputSchema
        assert td.terminal is False

    def test_namespacing_with_different_server_names(self):
        tool = _make_mcp_tool(name="list_issues")
        call_fn = MagicMock()

        result = mcp_tools_to_tool_definitions("github", [tool], call_fn)

        assert result[0].name == "mcp_github__list_issues"

    def test_multiple_tools(self):
        tools = [
            _make_mcp_tool(name="read_file"),
            _make_mcp_tool(name="write_file"),
            _make_mcp_tool(name="list_dir"),
        ]
        call_fn = MagicMock()

        result = mcp_tools_to_tool_definitions("fs", tools, call_fn)

        assert len(result) == 3
        names = [td.name for td in result]
        assert names == ["mcp_fs__read_file", "mcp_fs__write_file", "mcp_fs__list_dir"]

    def test_empty_tools_list(self):
        call_fn = MagicMock()
        result = mcp_tools_to_tool_definitions("server", [], call_fn)
        assert result == []

    def test_execute_closure_calls_call_fn_with_correct_args(self):
        tool = _make_mcp_tool(name="read_file")
        call_fn = MagicMock(return_value="content")

        result = mcp_tools_to_tool_definitions("fs", [tool], call_fn)
        td = result[0]

        output = td.execute(path="/tmp/test.txt")

        call_fn.assert_called_once_with("read_file", {"path": "/tmp/test.txt"})
        assert output == "content"

    def test_execute_closure_passes_multiple_kwargs(self):
        tool = _make_mcp_tool(name="write_file")
        call_fn = MagicMock(return_value="ok")

        result = mcp_tools_to_tool_definitions("fs", [tool], call_fn)
        td = result[0]

        td.execute(path="/tmp/out.txt", content="hello")

        call_fn.assert_called_once_with("write_file", {"path": "/tmp/out.txt", "content": "hello"})

    def test_description_fallback_when_none(self):
        tool = _make_mcp_tool(name="mystery", description=None)
        # Override description to None since _make_mcp_tool always sets it
        tool.description = None
        call_fn = MagicMock()

        result = mcp_tools_to_tool_definitions("srv", [tool], call_fn)

        assert "mystery" in result[0].description
        assert "srv" in result[0].description

    def test_input_schema_passed_through(self):
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        }
        tool = _make_mcp_tool(name="search", input_schema=schema)
        call_fn = MagicMock()

        result = mcp_tools_to_tool_definitions("srv", [tool], call_fn)

        assert result[0].parameters == schema


@pytest.mark.unit
class TestFormatCallResult:
    """Tests for format_call_result()."""

    def test_text_content(self):
        result = types.CallToolResult(
            content=[types.TextContent(type="text", text="hello world")],
            isError=False,
        )
        assert format_call_result(result) == "hello world"

    def test_multiple_text_blocks(self):
        result = types.CallToolResult(
            content=[
                types.TextContent(type="text", text="line 1"),
                types.TextContent(type="text", text="line 2"),
            ],
            isError=False,
        )
        assert format_call_result(result) == "line 1\nline 2"

    def test_error_result(self):
        result = types.CallToolResult(
            content=[types.TextContent(type="text", text="file not found")],
            isError=True,
        )
        assert format_call_result(result) == "Error: file not found"

    def test_empty_content(self):
        result = types.CallToolResult(content=[], isError=False)
        assert format_call_result(result) == "(empty result)"

    def test_empty_content_with_error(self):
        result = types.CallToolResult(content=[], isError=True)
        assert format_call_result(result) == "Error: (empty result)"

    def test_image_content(self):
        result = types.CallToolResult(
            content=[types.ImageContent(type="image", data="abc", mimeType="image/png")],
            isError=False,
        )
        assert format_call_result(result) == "[Image: image/png]"

    def test_audio_content(self):
        result = types.CallToolResult(
            content=[types.AudioContent(type="audio", data="abc", mimeType="audio/mp3")],
            isError=False,
        )
        assert format_call_result(result) == "[Audio: audio/mp3]"

    def test_mixed_content(self):
        result = types.CallToolResult(
            content=[
                types.TextContent(type="text", text="Screenshot:"),
                types.ImageContent(type="image", data="abc", mimeType="image/png"),
            ],
            isError=False,
        )
        assert format_call_result(result) == "Screenshot:\n[Image: image/png]"
