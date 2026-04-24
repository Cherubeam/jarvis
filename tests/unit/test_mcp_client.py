"""Tests for MCP client connection lifecycle and MCPManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types

from packages.core.settings import MCPServerSettings
from packages.integrations.mcp.client import MCPConnection, MCPManager


def _make_stdio_settings(**overrides) -> MCPServerSettings:
    defaults = dict(
        transport="stdio",
        tool_group="",
        timeout_seconds=30.0,
        command="echo",
        args=["hello"],
    )
    defaults.update(overrides)
    return MCPServerSettings(**defaults)


def _make_sse_settings(**overrides) -> MCPServerSettings:
    defaults = dict(
        transport="sse",
        tool_group="",
        timeout_seconds=30.0,
        url="http://localhost:3000/sse",
    )
    defaults.update(overrides)
    return MCPServerSettings(**defaults)


def _make_mock_session(tools: list[types.Tool] | None = None):
    """Create a mock ClientSession."""
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(
        return_value=types.ListToolsResult(
            tools=tools
            or [
                types.Tool(
                    name="echo",
                    description="Echo input",
                    inputSchema={"type": "object", "properties": {"text": {"type": "string"}}},
                ),
            ],
        )
    )
    session.call_tool = AsyncMock(
        return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text="result")],
            isError=False,
        )
    )
    return session


@pytest.mark.unit
class TestMCPConnection:
    """Tests for MCPConnection."""

    @pytest.mark.asyncio
    async def test_connect_stdio_populates_tools(self):
        settings = _make_stdio_settings()
        conn = MCPConnection("testserver", settings)

        mock_session = _make_mock_session()
        mock_read = MagicMock()
        mock_write = MagicMock()

        with patch(
            "packages.integrations.mcp.client.stdio_client",
        ) as mock_stdio:
            # Make stdio_client an async context manager yielding (read, write)
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            mock_stdio.return_value = mock_cm

            with patch(
                "packages.integrations.mcp.client.ClientSession",
            ) as mock_session_cls:
                session_cm = AsyncMock()
                session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                session_cm.__aexit__ = AsyncMock(return_value=False)
                mock_session_cls.return_value = session_cm

                await conn.connect()

        assert conn.connected is True
        assert len(conn.tools) == 1
        assert conn.tools[0].name == "echo"
        assert conn.session is mock_session

    @pytest.mark.asyncio
    async def test_connect_failure_cleans_up(self):
        settings = _make_stdio_settings()
        conn = MCPConnection("testserver", settings)

        with patch(
            "packages.integrations.mcp.client.stdio_client",
        ) as mock_stdio:
            mock_stdio.side_effect = ConnectionError("server down")

            with pytest.raises(ConnectionError, match="server down"):
                await conn.connect()

        assert conn.connected is False
        assert conn.session is None

    @pytest.mark.asyncio
    async def test_call_tool_when_not_connected(self):
        settings = _make_stdio_settings()
        conn = MCPConnection("testserver", settings)

        with pytest.raises(RuntimeError, match="is not connected"):
            await conn.call_tool("echo", {"text": "hello"})

    @pytest.mark.asyncio
    async def test_disconnect_resets_state(self):
        settings = _make_stdio_settings()
        conn = MCPConnection("testserver", settings)

        # Simulate connected state
        conn._connected = True
        conn.session = _make_mock_session()

        await conn.disconnect()

        assert conn.connected is False
        assert conn.session is None


@pytest.mark.unit
class TestMCPManager:
    """Tests for MCPManager."""

    def test_call_tool_sync_unknown_server(self):
        manager = MCPManager()
        result = manager.call_tool_sync("nonexistent", "tool", {})
        assert result.startswith("Error:")
        assert "nonexistent" in result
        assert "not connected" in result

    def test_call_tool_sync_disconnected_server(self):
        manager = MCPManager()
        conn = MCPConnection("testserver", _make_stdio_settings())
        conn._connected = False
        manager._connections["testserver"] = conn

        result = manager.call_tool_sync("testserver", "tool", {})
        assert result.startswith("Error:")
        assert "not connected" in result

    def test_start_with_failing_server_returns_partial(self):
        """If one server fails to connect, others still work."""
        servers = {
            "good": _make_stdio_settings(tool_group="good_tools"),
            "bad": _make_stdio_settings(tool_group="bad_tools"),
        }

        manager = MCPManager()

        with patch(
            "packages.integrations.mcp.client.MCPConnection",
        ) as MockConn:

            def side_effect(name, settings):
                conn = MagicMock()
                if name == "good":
                    conn.connect = AsyncMock()
                    conn.tools = [
                        types.Tool(
                            name="tool_a",
                            description="Tool A",
                            inputSchema={"type": "object", "properties": {}},
                        ),
                    ]
                    conn.connected = True
                else:
                    conn.connect = AsyncMock(side_effect=ConnectionError("down"))
                conn.name = name
                conn.settings = settings
                return conn

            MockConn.side_effect = side_effect

            result = manager.start(servers)

        assert "good_tools" in result
        assert "bad_tools" not in result
        assert len(result["good_tools"]) == 1

        manager.shutdown()

    def test_shutdown_idempotent(self):
        manager = MCPManager()
        # Should not raise even without start()
        manager.shutdown()
        manager.shutdown()

    def test_shutdown_after_start(self):
        manager = MCPManager()
        manager._start_loop()
        assert manager._loop is not None
        assert manager._thread is not None
        assert manager._thread.is_alive()

        manager.shutdown()

        assert manager._loop is None
        assert manager._thread is None

    def test_make_call_fn_binds_server_name(self):
        manager = MCPManager()
        manager.call_tool_sync = MagicMock(return_value="result")

        call_fn = manager._make_call_fn("myserver")
        result = call_fn("my_tool", {"key": "val"})

        manager.call_tool_sync.assert_called_once_with("myserver", "my_tool", {"key": "val"})
        assert result == "result"
