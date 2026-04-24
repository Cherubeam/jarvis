"""Tests for ``diff_from_defaults`` and ``dereferenced_schema``."""

from __future__ import annotations

from packages.core.settings import (
    MCPServerSettings,
    Settings,
    dereferenced_schema,
    diff_from_defaults,
)


def test_equal_to_defaults_returns_empty() -> None:
    assert diff_from_defaults(Settings()) == {}


def test_scalar_override() -> None:
    s = Settings()
    s.routing.enabled = True  # default is False
    assert diff_from_defaults(s) == {"routing": {"enabled": True}}


def test_nested_scalar_override() -> None:
    s = Settings()
    s.obsidian.daily_notes.path_format = "Journals/%Y-%m-%d"
    assert diff_from_defaults(s) == {
        "obsidian": {"daily_notes": {"path_format": "Journals/%Y-%m-%d"}},
    }


def test_list_replace_wholesale_not_patch() -> None:
    s = Settings()
    s.things3.lists_to_include = ["Today", "Upcoming", "Inbox", "Someday"]
    assert diff_from_defaults(s) == {
        "things3": {"lists_to_include": ["Today", "Upcoming", "Inbox", "Someday"]},
    }


def test_dict_keyed_dynamic_section_preserved() -> None:
    s = Settings()
    s.mcp.enabled = True
    s.mcp.servers = {
        "n8n": MCPServerSettings(
            transport="stdio",
            tool_group="n8n",
            command="npx",
            args=["-y", "n8n-mcp"],
            env={"N8N_API_KEY": "secret-token"},
        ),
    }
    diff = diff_from_defaults(s)
    assert diff["mcp"]["enabled"] is True
    assert diff["mcp"]["servers"]["n8n"]["command"] == "npx"
    assert diff["mcp"]["servers"]["n8n"]["env"] == {"N8N_API_KEY": "secret-token"}


def test_dict_keyed_dynamic_section_deletion_drops() -> None:
    s = Settings()
    s.mcp.servers = {
        "tmp": MCPServerSettings(transport="stdio", command="echo"),
    }
    assert "mcp" in diff_from_defaults(s)
    s.mcp.servers = {}
    assert "mcp" not in diff_from_defaults(s)


def test_resetting_to_default_drops_from_diff() -> None:
    s = Settings()
    s.routing.enabled = True
    assert diff_from_defaults(s) == {"routing": {"enabled": True}}
    s.routing.enabled = False
    assert diff_from_defaults(s) == {}


def test_multiple_sections_independent() -> None:
    s = Settings()
    s.routing.enabled = True
    s.summarization.enabled = True
    s.summarization.keep_recent = 15
    diff = diff_from_defaults(s)
    assert diff == {
        "routing": {"enabled": True},
        "summarization": {"enabled": True, "keep_recent": 15},
    }


def test_round_trip_diff_then_merge_reproduces_original() -> None:
    """Diff → deep_merge onto defaults → validate → produces the same Settings."""
    from packages.core.settings import deep_merge

    s = Settings()
    s.mcp.enabled = True
    s.mcp.servers = {"x": MCPServerSettings(transport="stdio", command="echo")}
    s.obsidian.vault_path = "/tmp/vault"
    s.routing.enabled = True

    diff = diff_from_defaults(s)
    defaults = Settings().model_dump()
    reconstructed = Settings.model_validate(deep_merge(defaults, diff))
    assert reconstructed.model_dump() == s.model_dump()


def test_inline_refs_resolves_mcp_transport() -> None:
    """Schema body for mcp.servers values must be inlined, no $ref remaining."""
    schema = dereferenced_schema()
    assert "$defs" not in schema
    _assert_no_refs(schema)


def test_inline_refs_preserves_transport_enum() -> None:
    """MCPServerSettings.transport is Literal[...] — the enum choices must be inline."""
    schema = dereferenced_schema()
    mcp_schema = schema["properties"]["mcp"]
    servers_values = mcp_schema["properties"]["servers"]["additionalProperties"]
    transport_schema = servers_values["properties"]["transport"]
    # Pydantic renders Literal as {"enum": [...]} or {"const": ...}; both acceptable.
    assert transport_schema.get("enum") == ["stdio", "sse", "streamable_http"]


def _assert_no_refs(node: object) -> None:
    if isinstance(node, dict):
        assert "$ref" not in node, f"unexpected $ref in {node}"
        for value in node.values():
            _assert_no_refs(value)
    elif isinstance(node, list):
        for item in node:
            _assert_no_refs(item)
