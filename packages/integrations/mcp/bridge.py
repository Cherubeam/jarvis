"""
Bridge between MCP server tools and JARVIS ToolDefinition.

Pure data transformation — converts MCP Tool objects to ToolDefinition
instances and formats MCP CallToolResult into plain strings.
"""

from collections.abc import Callable

from mcp import types

from packages.core.tools.base import ToolDefinition


def mcp_tools_to_tool_definitions(
    server_name: str,
    mcp_tools: list[types.Tool],
    call_fn: Callable[[str, dict], str],
) -> list[ToolDefinition]:
    """Convert MCP Tool objects to JARVIS ToolDefinition instances.

    Args:
        server_name: Used for namespacing tool names (prefix).
        mcp_tools: Tools discovered via session.list_tools().
        call_fn: Synchronous callable(tool_name, arguments) -> str
                 that executes the tool (bound to MCPManager.call_tool_sync).

    Returns:
        List of ToolDefinition instances with namespaced names.
    """
    definitions: list[ToolDefinition] = []
    for tool in mcp_tools:
        namespaced_name = f"mcp_{server_name}__{tool.name}"
        execute = _make_execute_fn(call_fn, tool.name)
        definitions.append(
            ToolDefinition(
                name=namespaced_name,
                description=tool.description or f"MCP tool '{tool.name}' from server '{server_name}'.",  # pragma: no mutate
                parameters=tool.inputSchema,
                execute=execute,
            )
        )
    return definitions


def _make_execute_fn(
    call_fn: Callable[[str, dict], str],
    tool_name: str,
) -> Callable[..., str]:
    """Create an execute closure for a single MCP tool."""

    def execute(**kwargs) -> str:
        return call_fn(tool_name, kwargs)

    return execute


def format_call_result(result: types.CallToolResult) -> str:
    """Convert an MCP CallToolResult to a plain string for JARVIS.

    Handles text, image, and audio content blocks. Errors are prefixed
    with 'Error:' to match JARVIS's existing tool error convention.
    """
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, types.TextContent):
            parts.append(block.text)
        elif isinstance(block, types.ImageContent):
            parts.append(f"[Image: {block.mimeType}]")
        elif isinstance(block, types.AudioContent):
            parts.append(f"[Audio: {block.mimeType}]")
        else:
            parts.append(f"[Unsupported content: {type(block).__name__}]")

    text = "\n".join(parts) if parts else "(empty result)"

    if result.isError:
        return f"Error: {text}"
    return text
