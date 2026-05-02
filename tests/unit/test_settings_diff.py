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


# ---------------------------------------------------------------------------
# _inline_refs — direct unit tests (cycle / missing-def / shape preservation)


def test_inline_refs_replaces_ref_with_target() -> None:
    from packages.core.settings import _inline_refs

    defs = {"Color": {"type": "string", "enum": ["red", "blue"]}}
    node = {"$ref": "#/$defs/Color"}
    assert _inline_refs(node, defs) == {"type": "string", "enum": ["red", "blue"]}


def test_inline_refs_recurses_into_target() -> None:
    """A $ref pointing at another node containing a $ref must be expanded."""
    from packages.core.settings import _inline_refs

    defs = {
        "A": {"$ref": "#/$defs/B"},
        "B": {"type": "integer"},
    }
    node = {"$ref": "#/$defs/A"}
    assert _inline_refs(node, defs) == {"type": "integer"}


def test_inline_refs_recurses_into_dict_values() -> None:
    from packages.core.settings import _inline_refs

    defs = {"Color": {"type": "string"}}
    node = {"properties": {"shade": {"$ref": "#/$defs/Color"}}}
    assert _inline_refs(node, defs) == {"properties": {"shade": {"type": "string"}}}


def test_inline_refs_recurses_into_list_items() -> None:
    from packages.core.settings import _inline_refs

    defs = {"X": {"const": 7}}
    node = [{"$ref": "#/$defs/X"}, {"plain": "value"}]
    assert _inline_refs(node, defs) == [{"const": 7}, {"plain": "value"}]


def test_inline_refs_returns_scalars_unchanged() -> None:
    from packages.core.settings import _inline_refs

    assert _inline_refs("string", {}) == "string"
    assert _inline_refs(42, {}) == 42
    assert _inline_refs(None, {}) is None
    assert _inline_refs(True, {}) is True


def test_inline_refs_breaks_cycle_by_returning_ref_dict() -> None:
    """Self-referential def must short-circuit — return the {$ref: ...} dict copy."""
    from packages.core.settings import _inline_refs

    defs = {"Recursive": {"$ref": "#/$defs/Recursive"}}
    node = {"$ref": "#/$defs/Recursive"}
    out = _inline_refs(node, defs)
    assert out == {"$ref": "#/$defs/Recursive"}


def test_inline_refs_unknown_ref_target_is_kept_as_ref() -> None:
    """defs.get(name) returning None must leave the original $ref dict in place."""
    from packages.core.settings import _inline_refs

    node = {"$ref": "#/$defs/Missing"}
    out = _inline_refs(node, {})
    assert out == {"$ref": "#/$defs/Missing"}


def test_inline_refs_non_defs_ref_kept_as_ref() -> None:
    """Refs that don't start with #/$defs/ are not expanded — left as-is."""
    from packages.core.settings import _inline_refs

    node = {"$ref": "https://json-schema.org/draft-07/schema#"}
    assert _inline_refs(node, {}) == {"$ref": "https://json-schema.org/draft-07/schema#"}


def test_inline_refs_non_string_ref_value_kept_as_dict() -> None:
    """`isinstance(node['$ref'], str)` False → recurse as a normal dict."""
    from packages.core.settings import _inline_refs

    node = {"$ref": 42, "other": "kept"}
    out = _inline_refs(node, {})
    assert out == {"$ref": 42, "other": "kept"}


def test_inline_refs_seen_set_isolated_per_branch() -> None:
    """The same def referenced twice via separate branches must expand each time."""
    from packages.core.settings import _inline_refs

    defs = {"X": {"type": "string"}}
    node = {"a": {"$ref": "#/$defs/X"}, "b": {"$ref": "#/$defs/X"}}
    assert _inline_refs(node, defs) == {"a": {"type": "string"}, "b": {"type": "string"}}


# ---------------------------------------------------------------------------
# _diff_dict — direct unit tests (recursion + key-only-in-current path)


def test_diff_dict_empty_inputs() -> None:
    from packages.core.settings import _diff_dict

    assert _diff_dict({}, {}) == {}


def test_diff_dict_keys_only_in_current_kept_wholesale() -> None:
    """Dynamic-keyed dicts (mcp.servers["n8n"]) — keys absent from defaults pass through."""
    from packages.core.settings import _diff_dict

    out = _diff_dict({"a": 1, "extra": {"nested": "value"}}, {"a": 1})
    assert out == {"extra": {"nested": "value"}}


def test_diff_dict_equal_scalars_dropped() -> None:
    from packages.core.settings import _diff_dict

    assert _diff_dict({"a": 1, "b": "x"}, {"a": 1, "b": "x"}) == {}


def test_diff_dict_unequal_scalars_kept() -> None:
    from packages.core.settings import _diff_dict

    assert _diff_dict({"a": 2}, {"a": 1}) == {"a": 2}


def test_diff_dict_nested_recurses_and_drops_empty() -> None:
    """Nested dict that ends up identical → entire subtree dropped."""
    from packages.core.settings import _diff_dict

    current = {"section": {"a": 1, "b": 2}}
    defaults = {"section": {"a": 1, "b": 2}}
    assert _diff_dict(current, defaults) == {}


def test_diff_dict_nested_keeps_only_changed_leaf() -> None:
    from packages.core.settings import _diff_dict

    current = {"section": {"a": 1, "b": 99}}
    defaults = {"section": {"a": 1, "b": 2}}
    assert _diff_dict(current, defaults) == {"section": {"b": 99}}


def test_diff_dict_list_replace_wholesale() -> None:
    """Lists are leaves — single element added means the entire list is kept."""
    from packages.core.settings import _diff_dict

    assert _diff_dict({"l": [1, 2, 3]}, {"l": [1, 2]}) == {"l": [1, 2, 3]}


def test_diff_dict_dict_in_current_scalar_in_defaults_replaces() -> None:
    """When types differ on the same key, the `else` branch (value-compare) fires."""
    from packages.core.settings import _diff_dict

    out = _diff_dict({"x": {"nested": True}}, {"x": "scalar"})
    assert out == {"x": {"nested": True}}


# ---------------------------------------------------------------------------
# _diff_paths — direct unit tests (powers classify_changes)


def test_diff_paths_identical_returns_empty() -> None:
    from packages.core.settings import _diff_paths

    assert _diff_paths({"a": 1}, {"a": 1}) == []


def test_diff_paths_scalar_change_returns_dotted_path() -> None:
    from packages.core.settings import _diff_paths

    assert _diff_paths({"a": 1}, {"a": 2}) == ["a"]


def test_diff_paths_nested_change_emits_dotted_path() -> None:
    from packages.core.settings import _diff_paths

    out = _diff_paths({"a": {"b": {"c": 1}}}, {"a": {"b": {"c": 2}}})
    assert out == ["a.b.c"]


def test_diff_paths_key_only_in_current_or_new_is_a_leaf() -> None:
    """Mid-recursion, an absent key on either side is a single leaf path — not recursed."""
    from packages.core.settings import _diff_paths

    out = sorted(_diff_paths({"a": {"b": 1}}, {"a": {}}))
    assert out == ["a.b"]
    out2 = sorted(_diff_paths({"a": {}}, {"a": {"b": 1}}))
    assert out2 == ["a.b"]


def test_diff_paths_list_is_atomic_leaf() -> None:
    """List replacement → one path entry, never per-index."""
    from packages.core.settings import _diff_paths

    assert _diff_paths({"l": [1, 2]}, {"l": [1, 2, 3]}) == ["l"]


def test_diff_paths_top_level_value_diff_returns_empty_string() -> None:
    """Calling with two non-dict roots that differ — returns [\"\"]."""
    from packages.core.settings import _diff_paths

    assert _diff_paths(1, 2) == [""]


def test_diff_paths_dict_vs_scalar_mismatch_treated_as_leaf() -> None:
    """When current is a dict but new isn't (or vice-versa), the recursion bails
    at the outer level: dict-vs-non-dict falls into the value-compare branch."""
    from packages.core.settings import _diff_paths

    out = _diff_paths({"a": {"b": 1}}, {"a": "scalar"})
    assert out == ["a"]


def test_diff_paths_multiple_changes_returned_unsorted() -> None:
    """The function builds a list — caller (classify_changes) sorts it."""
    from packages.core.settings import _diff_paths

    out = _diff_paths({"a": 1, "b": 2}, {"a": 9, "b": 8})
    assert sorted(out) == ["a", "b"]


# ---------------------------------------------------------------------------
# dereferenced_schema — top-level smoke (composition of _inline_refs + pop)


def test_dereferenced_schema_strips_defs_key() -> None:
    """`raw.pop("$defs", ...)` — top-level dict must not surface $defs."""
    from packages.core.settings import dereferenced_schema

    schema = dereferenced_schema()
    assert "$defs" not in schema


def test_dereferenced_schema_returns_dict_with_properties() -> None:
    from packages.core.settings import dereferenced_schema

    schema = dereferenced_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    # Sanity: at least one of the well-known top-level sections is present.
    assert "models" in schema["properties"]
