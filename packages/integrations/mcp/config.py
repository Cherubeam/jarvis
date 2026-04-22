"""
MCP server configuration parsing and validation.

Pure data transformation — no I/O, no MCP SDK imports.
"""

from dataclasses import dataclass, field
from typing import Any

_VALID_TRANSPORTS = {"stdio", "sse", "streamable_http"}


@dataclass(frozen=True)
class MCPServerConfig:
    """Validated configuration for one MCP server."""

    name: str
    transport: str  # "stdio" | "sse" | "streamable_http"
    tool_group: str  # tool group name for agent assignment
    timeout_seconds: float = 30.0
    # stdio fields
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None
    # sse / streamable_http fields
    url: str | None = None
    headers: dict[str, str] | None = None


def parse_mcp_config(config: dict[str, Any]) -> list[MCPServerConfig]:
    """Parse the mcp section from the full config dict.

    Returns an empty list if the section is absent or disabled.
    Raises ValueError for invalid server configurations.
    """
    mcp_section = config.get("mcp", {})
    if not mcp_section.get("enabled", False):
        return []

    servers = mcp_section.get("servers", {})
    if not servers:
        return []

    configs: list[MCPServerConfig] = []
    for name, server in servers.items():
        configs.append(_parse_server(name, server))
    return configs


def _parse_server(name: str, server: dict[str, Any]) -> MCPServerConfig:
    """Parse and validate a single server entry."""
    if "__" in name:
        raise ValueError(
            f"MCP server name '{name}' must not contain '__' (reserved as namespace separator in tool names)."
        )

    transport = server.get("transport", "")
    if transport not in _VALID_TRANSPORTS:
        raise ValueError(
            f"MCP server '{name}': invalid transport '{transport}'. "
            f"Must be one of: {', '.join(sorted(_VALID_TRANSPORTS))}."
        )

    if transport == "stdio":
        command = server.get("command")
        if not command:
            raise ValueError(f"MCP server '{name}': stdio transport requires 'command'.")
    else:
        command = None

    if transport in ("sse", "streamable_http"):
        url = server.get("url")
        if not url:
            raise ValueError(f"MCP server '{name}': {transport} transport requires 'url'.")
    else:
        url = None

    return MCPServerConfig(
        name=name,
        transport=transport,
        tool_group=server.get("tool_group", name),
        timeout_seconds=float(server.get("timeout_seconds", 30)),
        command=command,
        args=server.get("args", []),
        env=server.get("env"),
        cwd=server.get("cwd"),
        url=url,
        headers=server.get("headers"),
    )
