"""
MCP client connection lifecycle and async/sync bridge.

Manages MCP server connections on a background asyncio event loop,
exposing synchronous call_tool_sync() for JARVIS's ToolDefinition.execute.
"""

import asyncio
import logging
import threading
from collections.abc import Callable
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any

from mcp import ClientSession, types
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

from packages.core.settings import MCPServerSettings
from packages.core.tools.base import ToolDefinition
from packages.integrations.mcp.bridge import format_call_result, mcp_tools_to_tool_definitions

logger = logging.getLogger(__name__)


class MCPConnection:
    """Manages a single MCP server connection and its async resources."""

    def __init__(self, name: str, settings: MCPServerSettings):
        self.name = name
        self.settings = settings
        self.session: ClientSession | None = None
        self._tools: list[types.Tool] = []
        self._connected: bool = False
        self._exit_stack = AsyncExitStack()

    @property
    def tools(self) -> list[types.Tool]:
        """Tools discovered from this server."""
        return self._tools

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Open transport, initialize session, discover tools."""
        try:
            transport = await self._open_transport()
            read_stream, write_stream, *_ = transport

            session = await self._exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()

            result = await session.list_tools()
            self._tools = result.tools
            self.session = session
            self._connected = True

            logger.info(
                "MCP server '%s' connected — %d tool(s) discovered.",
                self.name,
                len(self._tools),
            )
        except Exception:
            await self._exit_stack.aclose()
            raise

    async def _open_transport(self) -> Any:
        """Open the appropriate transport based on settings."""
        s = self.settings
        if s.transport == "stdio":
            assert s.command is not None, "stdio transport requires `command`"
            params = StdioServerParameters(
                command=s.command,
                args=s.args,
                env=s.env,
                cwd=s.cwd,
            )
            return await self._exit_stack.enter_async_context(stdio_client(params))
        elif s.transport == "sse":
            assert s.url is not None, "sse transport requires `url`"
            return await self._exit_stack.enter_async_context(
                sse_client(
                    url=s.url,
                    headers=s.headers,
                )
            )
        elif s.transport == "streamable_http":
            assert s.url is not None, "streamable_http transport requires `url`"
            return await self._exit_stack.enter_async_context(
                streamablehttp_client(
                    url=s.url,
                    headers=s.headers,
                )
            )
        else:
            raise ValueError(f"Unknown transport: {s.transport}")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        """Call a tool on this server."""
        if self.session is None or not self._connected:
            raise RuntimeError(f"MCP server '{self.name}' is not connected. Restart JARVIS to reconnect.")
        return await self.session.call_tool(
            name,
            arguments=arguments,
            read_timeout_seconds=timedelta(seconds=self.settings.timeout_seconds),
        )

    async def disconnect(self) -> None:
        """Gracefully close the session and transport."""
        self._connected = False
        self.session = None
        await self._exit_stack.aclose()


class MCPManager:
    """Manages all MCP server connections and the background async event loop.

    This is the single public entry point used by main.py.
    """

    def __init__(self) -> None:
        self._connections: dict[str, MCPConnection] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def start(self, servers: dict[str, MCPServerSettings]) -> dict[str, list[ToolDefinition]]:
        """Start the background event loop, connect to all servers, return tool groups.

        Returns a dict of {tool_group_name: [ToolDefinition, ...]} ready to
        merge into main.py's tool_groups dict.

        Servers that fail to connect are logged and skipped (graceful degradation).
        """
        self._start_loop()

        tool_groups: dict[str, list[ToolDefinition]] = {}

        for name, server in servers.items():
            conn = MCPConnection(name, server)
            try:
                self._run_async(conn.connect())
                self._connections[name] = conn

                # Bridge MCP tools → ToolDefinition
                call_fn = self._make_call_fn(name)
                definitions = mcp_tools_to_tool_definitions(
                    name,
                    conn.tools,
                    call_fn,
                )
                if definitions:
                    tool_group_name = server.tool_group or name
                    tool_groups[tool_group_name] = definitions

            except Exception as e:
                logger.warning(
                    "MCP server '%s' failed to connect: %s",
                    name,
                    e,
                )

        return tool_groups

    def call_tool_sync(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> str:
        """Synchronous wrapper: submit async call_tool to the background loop."""
        conn = self._connections.get(server_name)
        if conn is None or not conn.connected:
            return f"Error: MCP server '{server_name}' is not connected. Restart JARVIS to reconnect."
        try:
            result = self._run_async(conn.call_tool(tool_name, arguments))
            return format_call_result(result)
        except Exception as e:
            return (
                f"Error calling MCP tool '{tool_name}' on '{server_name}': {e}. "
                "Do not retry this tool with the same arguments — "
                "try a different tool or approach."
            )

    def shutdown(self) -> None:
        """Disconnect all servers and stop the background event loop."""
        if self._loop is None:
            return

        for name, conn in self._connections.items():
            try:
                self._run_async(conn.disconnect())
            except Exception as e:
                logger.warning("MCP server '%s' disconnect error: %s", name, e)

        self._connections.clear()
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None

    def _start_loop(self) -> None:
        """Start a background thread with a running asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            daemon=True,
            name="mcp-event-loop",
        )
        self._thread.start()

    def _run_async(self, coro: Any) -> Any:
        """Submit a coroutine to the background loop and block until complete."""
        if self._loop is None:
            raise RuntimeError("MCP event loop is not running.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=120)

    def _make_call_fn(self, server_name: str) -> Callable[[str, dict[str, Any]], str]:
        """Create a bound call_fn for a specific server (used by bridge)."""

        def call_fn(tool_name: str, arguments: dict[str, Any]) -> str:
            return self.call_tool_sync(server_name, tool_name, arguments)

        return call_fn
