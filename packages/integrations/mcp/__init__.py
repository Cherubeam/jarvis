"""MCP client integration — connect JARVIS to external MCP tool servers."""

from packages.integrations.mcp.client import MCPManager
from packages.integrations.mcp.config import parse_mcp_config

__all__ = ["MCPManager", "parse_mcp_config"]
