"""Tests for MCP server configuration parsing."""

import pytest

from packages.integrations.mcp.config import MCPServerConfig, parse_mcp_config


@pytest.mark.unit
class TestParseMcpConfig:
    """Tests for parse_mcp_config()."""

    def test_returns_empty_when_section_absent(self):
        assert parse_mcp_config({}) == []

    def test_returns_empty_when_disabled(self):
        config = {"mcp": {"enabled": False, "servers": {"s": {"transport": "stdio", "command": "echo"}}}}
        assert parse_mcp_config(config) == []

    def test_returns_empty_when_no_servers(self):
        config = {"mcp": {"enabled": True, "servers": {}}}
        assert parse_mcp_config(config) == []

    def test_returns_empty_when_servers_key_missing(self):
        config = {"mcp": {"enabled": True}}
        assert parse_mcp_config(config) == []

    def test_parses_stdio_server(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "filesystem": {
                        "transport": "stdio",
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                        "env": {"NODE_ENV": "production"},
                        "cwd": "/home/user",
                        "tool_group": "fs_tools",
                        "timeout_seconds": 45,
                    }
                },
            }
        }
        result = parse_mcp_config(config)
        assert len(result) == 1

        cfg = result[0]
        assert cfg.name == "filesystem"
        assert cfg.transport == "stdio"
        assert cfg.command == "npx"
        assert cfg.args == ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        assert cfg.env == {"NODE_ENV": "production"}
        assert cfg.cwd == "/home/user"
        assert cfg.tool_group == "fs_tools"
        assert cfg.timeout_seconds == 45.0
        assert cfg.url is None
        assert cfg.headers is None

    def test_parses_sse_server(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "github": {
                        "transport": "sse",
                        "url": "http://localhost:3001/sse",
                        "headers": {"Authorization": "Bearer token123"},
                        "timeout_seconds": 60,
                    }
                },
            }
        }
        result = parse_mcp_config(config)
        assert len(result) == 1

        cfg = result[0]
        assert cfg.name == "github"
        assert cfg.transport == "sse"
        assert cfg.url == "http://localhost:3001/sse"
        assert cfg.headers == {"Authorization": "Bearer token123"}
        assert cfg.timeout_seconds == 60.0
        assert cfg.command is None

    def test_parses_streamable_http_server(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "api": {
                        "transport": "streamable_http",
                        "url": "http://localhost:8080/mcp",
                    }
                },
            }
        }
        result = parse_mcp_config(config)
        assert len(result) == 1
        assert result[0].transport == "streamable_http"
        assert result[0].url == "http://localhost:8080/mcp"

    def test_tool_group_defaults_to_server_name(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "myserver": {
                        "transport": "stdio",
                        "command": "echo",
                    }
                },
            }
        }
        result = parse_mcp_config(config)
        assert result[0].tool_group == "myserver"

    def test_default_timeout(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "s": {"transport": "stdio", "command": "echo"},
                },
            }
        }
        result = parse_mcp_config(config)
        assert result[0].timeout_seconds == 30.0

    def test_multiple_servers(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "a": {"transport": "stdio", "command": "cmd_a"},
                    "b": {"transport": "sse", "url": "http://localhost/b"},
                },
            }
        }
        result = parse_mcp_config(config)
        assert len(result) == 2
        names = {c.name for c in result}
        assert names == {"a", "b"}

    def test_invalid_transport_raises_valueerror(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "bad": {"transport": "websocket"},
                },
            }
        }
        with pytest.raises(ValueError, match="invalid transport 'websocket'"):
            parse_mcp_config(config)

    def test_stdio_missing_command_raises_valueerror(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "bad": {"transport": "stdio"},
                },
            }
        }
        with pytest.raises(ValueError, match="requires 'command'"):
            parse_mcp_config(config)

    def test_sse_missing_url_raises_valueerror(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "bad": {"transport": "sse"},
                },
            }
        }
        with pytest.raises(ValueError, match="requires 'url'"):
            parse_mcp_config(config)

    def test_streamable_http_missing_url_raises_valueerror(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "bad": {"transport": "streamable_http"},
                },
            }
        }
        with pytest.raises(ValueError, match="requires 'url'"):
            parse_mcp_config(config)

    def test_server_name_with_double_underscore_raises_valueerror(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "my__server": {"transport": "stdio", "command": "echo"},
                },
            }
        }
        with pytest.raises(ValueError, match="must not contain '__'"):
            parse_mcp_config(config)

    def test_empty_transport_raises_valueerror(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "bad": {"transport": ""},
                },
            }
        }
        with pytest.raises(ValueError, match="invalid transport"):
            parse_mcp_config(config)

    def test_missing_transport_raises_valueerror(self):
        config = {
            "mcp": {
                "enabled": True,
                "servers": {
                    "bad": {"command": "echo"},
                },
            }
        }
        with pytest.raises(ValueError, match="invalid transport"):
            parse_mcp_config(config)


@pytest.mark.unit
class TestMCPServerConfigFrozen:
    """MCPServerConfig is immutable."""

    def test_frozen(self):
        cfg = MCPServerConfig(name="test", transport="stdio", tool_group="test", command="echo")
        with pytest.raises(AttributeError):
            cfg.name = "changed"
