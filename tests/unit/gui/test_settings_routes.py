"""Tests for /api/settings, /api/settings/schema, and PUT /api/settings."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gui.server.routes.settings import MANAGED_HEADER
from apps.gui.server.routes.settings import router as settings_router
from packages.core.settings import Settings


def _build_app(jarvis_dir: Path, settings: Settings | None = None) -> FastAPI:
    """Wire a FastAPI app with a real ``Settings`` instance on ``components.settings``.

    Unlike the outcomes tests' partial ``SimpleNamespace`` shim, settings
    routes dump the entire tree — anything less than a real ``Settings``
    instance breaks ``model_dump`` or ``diff_from_defaults``.
    """
    (jarvis_dir / "config").mkdir(parents=True, exist_ok=True)
    components = SimpleNamespace(
        settings=settings or Settings(),
        jarvis_dir=jarvis_dir,
    )
    app = FastAPI()
    app.state.gui_session = SimpleNamespace(components=components)
    app.include_router(settings_router)
    return app


def _client(jarvis_dir: Path, settings: Settings | None = None) -> TestClient:
    return TestClient(_build_app(jarvis_dir, settings))


def _write_local_yaml(jarvis_dir: Path, content: str) -> Path:
    path = jarvis_dir / "config" / "local.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# GET /api/settings


def test_get_settings_returns_current_state(tmp_path: Path) -> None:
    settings = Settings()
    settings.routing.enabled = True
    client = _client(tmp_path, settings)
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"settings", "defaults", "overrides", "local_yaml_has_managed_header", "paths"}
    assert body["settings"]["routing"]["enabled"] is True
    assert body["defaults"]["routing"]["enabled"] is False
    assert body["overrides"] == {"routing": {"enabled": True}}
    assert body["paths"] == {"default_yaml": "config/default.yaml", "local_yaml": "config/local.yaml"}


def test_get_settings_excludes_jarvis_dir(tmp_path: Path) -> None:
    """Pins ``Settings.jarvis_dir`` field's ``exclude=True`` — a regression would leak a path."""
    client = _client(tmp_path)
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert "jarvis_dir" not in body["settings"]
    assert "jarvis_dir" not in body["defaults"]


def test_get_detects_managed_header(tmp_path: Path) -> None:
    """Header detection flips with file content."""
    client = _client(tmp_path)

    # No file → False
    r = client.get("/api/settings")
    assert r.json()["local_yaml_has_managed_header"] is False

    # Hand-crafted file → False
    _write_local_yaml(tmp_path, "# custom header\nrouting:\n  enabled: true\n")
    r = client.get("/api/settings")
    assert r.json()["local_yaml_has_managed_header"] is False

    # Managed file → True
    _write_local_yaml(tmp_path, f"{MANAGED_HEADER}\nrouting:\n  enabled: true\n")
    r = client.get("/api/settings")
    assert r.json()["local_yaml_has_managed_header"] is True

    # Managed header after leading blanks → still True
    _write_local_yaml(tmp_path, f"\n\n{MANAGED_HEADER}\nrouting:\n  enabled: true\n")
    r = client.get("/api/settings")
    assert r.json()["local_yaml_has_managed_header"] is True


# ---------------------------------------------------------------------------
# GET /api/settings/schema


def test_get_schema_has_no_refs(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/settings/schema")
    assert r.status_code == 200
    body = r.json()
    assert "$defs" not in body
    _assert_no_refs(body)


def test_get_schema_preserves_mcp_transport_enum(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/settings/schema")
    schema = r.json()
    servers_values = schema["properties"]["mcp"]["properties"]["servers"]["additionalProperties"]
    assert servers_values["properties"]["transport"]["enum"] == ["stdio", "sse", "streamable_http"]


def _assert_no_refs(node: Any) -> None:
    if isinstance(node, dict):
        assert "$ref" not in node, f"unexpected $ref in {node}"
        for value in node.values():
            _assert_no_refs(value)
    elif isinstance(node, list):
        for item in node:
            _assert_no_refs(item)


# ---------------------------------------------------------------------------
# PUT /api/settings — happy path


def test_put_valid_settings_writes_local_yaml(tmp_path: Path) -> None:
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["routing"]["enabled"] = True

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 200
    body = r.json()
    assert body["overrides"] == {"routing": {"enabled": True}}
    # routing.* is captured at startup → restart required.
    assert body["restart_required"] is True
    assert body["restart_required_fields"] == ["routing.enabled"]
    assert body["hot_applied_fields"] == []
    assert body["bytes"] > 0

    written = (tmp_path / "config" / "local.yaml").read_text()
    assert written.startswith(f"{MANAGED_HEADER}\n")
    parsed = yaml.safe_load(written[len(MANAGED_HEADER) + 1 :])
    assert parsed == {"routing": {"enabled": True}}


def test_put_rebinds_components_settings_for_hot_apply(tmp_path: Path) -> None:
    """Field-level hot-apply gating: ``components.settings`` is replaced after save
    so fields re-read per turn (summarization, paths.prompt_history_dir) take
    effect immediately. jarvis_dir (runtime-injected) must be preserved.
    """
    settings = Settings()
    settings.jarvis_dir = tmp_path  # matches what build_session does
    app = _build_app(tmp_path, settings)
    before = app.state.gui_session.components.settings
    client = TestClient(app)

    payload = Settings().model_dump()
    payload["summarization"]["token_threshold"] = 50_000

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 200

    after = app.state.gui_session.components.settings
    assert after is not before
    assert after.summarization.token_threshold == 50_000
    assert after.jarvis_dir == tmp_path  # preserved across rebind


def test_put_hot_apply_only_change_does_not_require_restart(tmp_path: Path) -> None:
    """Changing only summarization.* → restart_required is False."""
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["summarization"]["enabled"] = True
    payload["summarization"]["token_threshold"] = 12_345

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 200
    body = r.json()
    assert body["restart_required"] is False
    assert body["restart_required_fields"] == []
    assert set(body["hot_applied_fields"]) == {
        "summarization.enabled",
        "summarization.token_threshold",
    }


def test_put_mixed_change_reports_both_buckets(tmp_path: Path) -> None:
    """A change that touches both hot and cold fields lists them separately."""
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["summarization"]["keep_recent"] = 25  # hot
    payload["paths"]["prompt_history_dir"] = "data/prompt-history-custom"  # hot
    payload["models"]["streaming"] = False  # cold

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 200
    body = r.json()
    assert body["restart_required"] is True
    assert body["restart_required_fields"] == ["models.streaming"]
    assert set(body["hot_applied_fields"]) == {
        "summarization.keep_recent",
        "paths.prompt_history_dir",
    }


def test_put_noop_save_reports_empty_buckets(tmp_path: Path) -> None:
    """Saving the existing settings unchanged → no fields in either bucket."""
    client = _client(tmp_path)

    r = client.put("/api/settings", json={"settings": Settings().model_dump()})
    assert r.status_code == 200
    body = r.json()
    assert body["restart_required"] is False
    assert body["restart_required_fields"] == []
    assert body["hot_applied_fields"] == []


# ---------------------------------------------------------------------------
# PUT /api/settings — credential preservation (the critical test)


def test_put_preserves_unedited_local_yaml_keys(tmp_path: Path) -> None:
    """Toggling one unrelated field must not drop credentials from ``local.yaml``.

    Simulates the real-world shape: an existing managed local.yaml has an MCP
    server with an API key. The user toggles ``rag.enabled`` only. The resulting
    file must still contain the API key byte-for-byte.
    """
    # Seed a managed local.yaml with the real shape.
    existing_overrides = {
        "mcp": {
            "enabled": True,
            "servers": {
                "n8n": {
                    "transport": "stdio",
                    "tool_group": "n8n",
                    "command": "npx",
                    "args": ["-y", "n8n-mcp"],
                    "env": {
                        "N8N_API_URL": "https://n8n.example.com",
                        "N8N_API_KEY": "eyJhbGciOiJIUzI1NiJ9.secret-jwt-token",
                    },
                }
            },
        },
        "obsidian": {"enabled": True, "vault_path": "/tmp/vault"},
    }
    _write_local_yaml(
        tmp_path,
        f"{MANAGED_HEADER}\n{yaml.safe_dump(existing_overrides, sort_keys=False)}",
    )

    # Construct the full merged Settings the frontend would have loaded via GET.
    from packages.core.settings import deep_merge

    merged = deep_merge(Settings().model_dump(), existing_overrides)
    merged["rag"]["enabled"] = False  # default is True → setting to False is a real change

    client = _client(tmp_path, Settings.model_validate(merged))
    r = client.put("/api/settings", json={"settings": merged})
    assert r.status_code == 200

    # Reparse the written file — credentials + new change must both be present.
    written = (tmp_path / "config" / "local.yaml").read_text()
    assert written.startswith(f"{MANAGED_HEADER}\n")
    parsed = yaml.safe_load(written[len(MANAGED_HEADER) + 1 :])
    assert parsed["mcp"]["servers"]["n8n"]["env"]["N8N_API_KEY"] == "eyJhbGciOiJIUzI1NiJ9.secret-jwt-token"
    assert parsed["obsidian"]["vault_path"] == "/tmp/vault"
    assert parsed["rag"]["enabled"] is False


# ---------------------------------------------------------------------------
# PUT /api/settings — managed-header guard


def test_put_refuses_overwrite_of_hand_crafted_local_yaml(tmp_path: Path) -> None:
    hand_crafted = "# custom header by user\nrouting:\n  enabled: true\n"
    path = _write_local_yaml(tmp_path, hand_crafted)
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["routing"]["enabled"] = True

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 409
    assert "accept_overwrite" in r.json()["detail"]
    # File unchanged.
    assert path.read_text() == hand_crafted


def test_put_overwrites_when_accept_overwrite_true(tmp_path: Path) -> None:
    _write_local_yaml(tmp_path, "# custom header by user\nrouting:\n  enabled: true\n")
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["routing"]["enabled"] = True

    r = client.put("/api/settings", json={"settings": payload, "accept_overwrite": True})
    assert r.status_code == 200

    written = (tmp_path / "config" / "local.yaml").read_text()
    assert written.startswith(f"{MANAGED_HEADER}\n")


def test_put_proceeds_when_managed_header_present(tmp_path: Path) -> None:
    _write_local_yaml(tmp_path, f"{MANAGED_HEADER}\nrouting:\n  enabled: true\n")
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["routing"]["enabled"] = False  # flip back to default

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 200
    body = r.json()
    assert body["overrides"] == {}


# ---------------------------------------------------------------------------
# PUT /api/settings — validation errors (loc normalization)


def test_put_invalid_field_error_returns_422_with_field_kind(tmp_path: Path) -> None:
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["summarization"]["token_threshold"] = "not an int"

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 422
    errors = r.json()["detail"]
    assert any(
        e["kind"] == "field" and e["loc"] == ["summarization", "token_threshold"] and e["card_loc"] == ["summarization"]
        for e in errors
    )


def test_put_invalid_transport_returns_422_with_model_validator_kind(tmp_path: Path) -> None:
    """MCP stdio server missing ``command`` → @model_validator raises; loc stops at the server."""
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["mcp"]["enabled"] = True
    payload["mcp"]["servers"] = {
        "n8n": {
            "transport": "stdio",
            "tool_group": "n8n",
            "timeout_seconds": 30.0,
            "command": None,
            "args": [],
            "env": None,
            "cwd": None,
            "url": None,
            "headers": None,
        }
    }

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 422
    errors = r.json()["detail"]
    assert any(
        e["kind"] == "model_validator"
        and e["loc"] == ["mcp", "servers", "n8n"]
        and e["card_loc"] == ["mcp", "servers", "n8n"]
        and "stdio transport requires 'command'" in e["msg"]
        for e in errors
    ), errors


def test_put_invalid_server_name_returns_422_with_model_validator_kind(tmp_path: Path) -> None:
    """Server name with ``__`` → @model_validator on MCPSettings; loc stops at ``mcp``."""
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["mcp"]["enabled"] = True
    payload["mcp"]["servers"] = {
        "bad__name": {
            "transport": "stdio",
            "tool_group": "x",
            "timeout_seconds": 30.0,
            "command": "echo",
            "args": [],
            "env": None,
            "cwd": None,
            "url": None,
            "headers": None,
        }
    }

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 422
    errors = r.json()["detail"]
    assert any(
        e["kind"] == "model_validator" and e["loc"] == ["mcp"] and "must not contain '__'" in e["msg"] for e in errors
    ), errors


def test_put_invalid_access_rule_returns_422_with_field_kind(tmp_path: Path) -> None:
    client = _client(tmp_path)

    payload = Settings().model_dump()
    payload["filesystem"]["access_rules"] = [{"path": "/tmp/vault", "access": "bogus"}]

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 422
    errors = r.json()["detail"]
    assert any(e["kind"] == "field" and e["loc"] == ["filesystem", "access_rules", 0, "access"] for e in errors), errors


# ---------------------------------------------------------------------------
# PUT /api/settings — atomicity + concurrency + idempotence


def test_put_atomic_on_disk_error(tmp_path: Path, monkeypatch) -> None:
    """A mid-write os.replace failure must leave ``local.yaml`` untouched."""
    existing = f"{MANAGED_HEADER}\nrouting:\n  enabled: true\n"
    path = _write_local_yaml(tmp_path, existing)
    client = _client(tmp_path)

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("packages.core.frontmatter.os.replace", _boom)

    payload = Settings().model_dump()
    payload["routing"]["enabled"] = False

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 500
    assert path.read_text() == existing


def test_put_concurrent_writes_serialized(tmp_path: Path) -> None:
    """Two concurrent PUTs both succeed and produce a valid final file."""
    client = _client(tmp_path)
    base = Settings().model_dump()

    async def call(value: bool) -> int:
        payload = dict(base)
        payload["routing"] = {**base["routing"], "enabled": value}
        return client.put("/api/settings", json={"settings": payload}).status_code

    async def driver() -> list[int]:
        return await asyncio.gather(call(True), call(False))

    statuses = asyncio.run(driver())
    assert statuses == [200, 200]

    # Final file must parse cleanly — no torn writes.
    written = (tmp_path / "config" / "local.yaml").read_text()
    assert written.startswith(f"{MANAGED_HEADER}\n")
    parsed = yaml.safe_load(written[len(MANAGED_HEADER) + 1 :]) or {}
    # One of the two values wins — either is fine, but the file must be complete.
    assert parsed in ({}, {"routing": {"enabled": True}})


def test_put_lock_lazy_init(tmp_path: Path) -> None:
    """``settings_write_lock`` is created on first PUT, not at startup."""
    app = _build_app(tmp_path)
    assert getattr(app.state, "settings_write_lock", None) is None

    client = TestClient(app)
    r = client.put("/api/settings", json={"settings": Settings().model_dump()})
    assert r.status_code == 200
    assert isinstance(app.state.settings_write_lock, asyncio.Lock)


def test_round_trip_get_put_noop_stable(tmp_path: Path) -> None:
    """GET → PUT the same body → local.yaml is the diff the GET claimed."""
    settings = Settings()
    settings.routing.enabled = True
    client = _client(tmp_path, settings)

    get_body = client.get("/api/settings").json()
    r = client.put("/api/settings", json={"settings": get_body["settings"]})
    assert r.status_code == 200

    written = (tmp_path / "config" / "local.yaml").read_text()
    parsed = yaml.safe_load(written[len(MANAGED_HEADER) + 1 :])
    assert parsed == get_body["overrides"]


# ---------------------------------------------------------------------------
# Helper: _has_managed_header (file-content sentinel)


def test_has_managed_header_missing_file_returns_false(tmp_path: Path) -> None:
    from apps.gui.server.routes.settings import _has_managed_header

    assert _has_managed_header(tmp_path / "nope.yaml") is False


def test_has_managed_header_directory_returns_false(tmp_path: Path) -> None:
    """Path that exists but isn't a file (e.g. a directory) → False, not crash."""
    from apps.gui.server.routes.settings import _has_managed_header

    d = tmp_path / "subdir"
    d.mkdir()
    assert _has_managed_header(d) is False


def test_has_managed_header_empty_file_returns_false(tmp_path: Path) -> None:
    """All-blank file: every line is skipped, function returns False at end."""
    from apps.gui.server.routes.settings import _has_managed_header

    p = tmp_path / "local.yaml"
    p.write_text("", encoding="utf-8")
    assert _has_managed_header(p) is False


def test_has_managed_header_blank_lines_only_returns_false(tmp_path: Path) -> None:
    from apps.gui.server.routes.settings import _has_managed_header

    p = tmp_path / "local.yaml"
    p.write_text("\n\n   \n\t\n", encoding="utf-8")
    assert _has_managed_header(p) is False


def test_has_managed_header_first_non_blank_matches(tmp_path: Path) -> None:
    """Leading blank lines are skipped; first non-blank must equal MANAGED_HEADER exactly."""
    from apps.gui.server.routes.settings import _has_managed_header

    p = tmp_path / "local.yaml"
    p.write_text(f"\n\n{MANAGED_HEADER}\nrouting:\n  enabled: true\n", encoding="utf-8")
    assert _has_managed_header(p) is True


def test_has_managed_header_first_non_blank_mismatches(tmp_path: Path) -> None:
    """A different first non-blank line → False, even if MANAGED_HEADER appears later."""
    from apps.gui.server.routes.settings import _has_managed_header

    p = tmp_path / "local.yaml"
    p.write_text(f"# user wrote this\n{MANAGED_HEADER}\n", encoding="utf-8")
    assert _has_managed_header(p) is False


def test_has_managed_header_strips_whitespace_before_compare(tmp_path: Path) -> None:
    """`line = raw.strip()` — surrounding whitespace on the header line is normalised."""
    from apps.gui.server.routes.settings import _has_managed_header

    p = tmp_path / "local.yaml"
    p.write_text(f"   {MANAGED_HEADER}   \n", encoding="utf-8")
    assert _has_managed_header(p) is True


def test_has_managed_header_partial_match_returns_false(tmp_path: Path) -> None:
    """Substring or prefix is not enough — must equal exactly."""
    from apps.gui.server.routes.settings import _has_managed_header

    p = tmp_path / "local.yaml"
    p.write_text(MANAGED_HEADER[:-5] + "\n", encoding="utf-8")
    assert _has_managed_header(p) is False


def test_has_managed_header_oserror_returns_false(tmp_path: Path, monkeypatch) -> None:
    """OSError during open → swallowed, returns False (not raise)."""
    from apps.gui.server.routes.settings import _has_managed_header

    p = tmp_path / "local.yaml"
    p.write_text(MANAGED_HEADER + "\n", encoding="utf-8")

    def _raise(*_a, **_k):
        raise OSError("boom")

    monkeypatch.setattr(Path, "open", _raise)
    assert _has_managed_header(p) is False


# ---------------------------------------------------------------------------
# Helper: _get_write_lock (singleton settings lock on app.state)


def test_get_write_lock_creates_lock_on_first_call() -> None:
    from apps.gui.server.routes.settings import _get_write_lock

    app = SimpleNamespace(state=SimpleNamespace())
    lock = asyncio.run(_get_write_lock(app))
    assert isinstance(lock, asyncio.Lock)
    assert app.state.settings_write_lock is lock


def test_get_write_lock_reuses_existing_lock() -> None:
    """Second call must return the exact same instance — no replacement."""
    from apps.gui.server.routes.settings import _get_write_lock

    app = SimpleNamespace(state=SimpleNamespace())

    async def _twice():
        a = await _get_write_lock(app)
        b = await _get_write_lock(app)
        return a, b

    a, b = asyncio.run(_twice())
    assert a is b


def test_get_write_lock_respects_preexisting_lock() -> None:
    """If the attribute is already set to a Lock, that exact object is returned."""
    from apps.gui.server.routes.settings import _get_write_lock

    preexisting = asyncio.Lock()
    app = SimpleNamespace(state=SimpleNamespace(settings_write_lock=preexisting))
    out = asyncio.run(_get_write_lock(app))
    assert out is preexisting


def test_get_write_lock_serialises_concurrent_holders() -> None:
    """Two coroutines holding the same lock must run serially, not interleave."""
    from apps.gui.server.routes.settings import _get_write_lock

    app = SimpleNamespace(state=SimpleNamespace())
    log: list[str] = []

    async def _hold(label: str, hold_for: float):
        lock = await _get_write_lock(app)
        async with lock:
            log.append(f"{label}-enter")
            await asyncio.sleep(hold_for)
            log.append(f"{label}-exit")

    async def _race():
        await asyncio.gather(_hold("a", 0.05), _hold("b", 0.0))

    asyncio.run(_race())
    assert log in (
        ["a-enter", "a-exit", "b-enter", "b-exit"],
        ["b-enter", "b-exit", "a-enter", "a-exit"],
    )


# ---------------------------------------------------------------------------
# Helper: _classify_error (schema-walking dispatch)


def _scalar_schema() -> dict:
    """Tiny schema fixture exercising properties / additionalProperties / items."""
    return {
        "type": "object",
        "properties": {
            "scalar": {"type": "integer"},
            "section": {
                "type": "object",
                "properties": {"flag": {"type": "boolean"}},
            },
            "rules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "access": {"type": "string"}},
                },
            },
            "servers": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {"transport": {"type": "string"}},
                },
            },
        },
    }


def test_classify_error_scalar_leaf_is_field_kind() -> None:
    """loc lands on a scalar → 'field' + card_loc strips the leaf segment."""
    from apps.gui.server.routes.settings import _classify_error

    kind, card_loc = _classify_error(("scalar",), _scalar_schema())
    assert kind == "field"
    assert card_loc == []


def test_classify_error_nested_field_strips_leaf() -> None:
    """Nested scalar: card_loc = parent path."""
    from apps.gui.server.routes.settings import _classify_error

    kind, card_loc = _classify_error(("section", "flag"), _scalar_schema())
    assert kind == "field"
    assert card_loc == ["section"]


def test_classify_error_object_node_is_model_validator() -> None:
    """loc stops at an object boundary → 'model_validator' + full loc retained."""
    from apps.gui.server.routes.settings import _classify_error

    kind, card_loc = _classify_error(("section",), _scalar_schema())
    assert kind == "model_validator"
    assert card_loc == ["section"]


def test_classify_error_int_segment_descends_via_items() -> None:
    """An int segment in loc must follow the array's `items` schema."""
    from apps.gui.server.routes.settings import _classify_error

    kind, card_loc = _classify_error(("rules", 0, "access"), _scalar_schema())
    assert kind == "field"
    assert card_loc == ["rules", 0]


def test_classify_error_int_segment_landing_on_object_is_model_validator() -> None:
    """loc=('rules', 0) — current ends on the items-object → model_validator."""
    from apps.gui.server.routes.settings import _classify_error

    kind, card_loc = _classify_error(("rules", 0), _scalar_schema())
    assert kind == "model_validator"
    assert card_loc == ["rules", 0]


def test_classify_error_descends_via_additional_properties() -> None:
    """Dynamic-keyed dict: a string segment not in `properties` falls into `additionalProperties`."""
    from apps.gui.server.routes.settings import _classify_error

    kind, card_loc = _classify_error(("servers", "n8n", "transport"), _scalar_schema())
    assert kind == "field"
    assert card_loc == ["servers", "n8n"]


def test_classify_error_unknown_segment_breaks_walk() -> None:
    """Segment not in properties/additionalProperties → current = None → field with loc[:-1]."""
    from apps.gui.server.routes.settings import _classify_error

    kind, card_loc = _classify_error(("section", "missing"), _scalar_schema())
    assert kind == "field"
    assert card_loc == ["section"]


def test_classify_error_walk_into_non_dict_short_circuits() -> None:
    """Once `current` becomes a non-dict, the loop bails out and treats as field."""
    from apps.gui.server.routes.settings import _classify_error

    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    kind, card_loc = _classify_error(("a", "deeper"), schema)
    assert kind == "field"
    assert card_loc == ["a"]


def test_classify_error_empty_loc_returns_root_model_validator() -> None:
    """No segments — current stays as the root schema → model_validator with empty loc."""
    from apps.gui.server.routes.settings import _classify_error

    kind, card_loc = _classify_error((), _scalar_schema())
    assert kind == "model_validator"
    assert card_loc == []


def test_classify_error_object_with_only_additional_properties_is_model_validator() -> None:
    """A node missing `type: object` but with `additionalProperties` → still model_validator."""
    from apps.gui.server.routes.settings import _classify_error

    schema = {"properties": {"servers": {"additionalProperties": {"type": "string"}}}}
    kind, card_loc = _classify_error(("servers",), schema)
    assert kind == "model_validator"
    assert card_loc == ["servers"]


def test_classify_error_object_with_only_properties_is_model_validator() -> None:
    """A node with `properties` but no explicit `type: object` → still model_validator."""
    from apps.gui.server.routes.settings import _classify_error

    schema = {"properties": {"section": {"properties": {"flag": {"type": "boolean"}}}}}
    kind, card_loc = _classify_error(("section",), schema)
    assert kind == "model_validator"


def test_classify_error_type_object_alone_is_model_validator() -> None:
    """A node with ONLY `{"type": "object"}` (no properties, no additionalProperties)
    must classify as model_validator. Pins `current.get("type") == "object"` against
    mutations to either string literal — defends mutants on `"type"` key and `"object"`
    value where the secondary `properties in current` clauses can't pick up the slack."""
    from apps.gui.server.routes.settings import _classify_error

    schema = {"properties": {"empty_obj": {"type": "object"}}}
    kind, card_loc = _classify_error(("empty_obj",), schema)
    assert kind == "model_validator"
    assert card_loc == ["empty_obj"]


def test_classify_error_int_segment_returns_none_when_array_lacks_items() -> None:
    """When an array node has no `items` key, `current.get("items")` returns None,
    which on the NEXT iteration triggers the inner `not isinstance(current, dict)`
    arm. This pins `current = None; break` against `current = None; return`
    mutations (which would crash callers expecting a tuple)."""
    from apps.gui.server.routes.settings import _classify_error

    # Array node without `items` — first iter descends via properties to {"type": "array"};
    # second iter (int) does .get("items") → None; third iter sees not-dict → break.
    schema = {"properties": {"arr": {"type": "array"}}}
    kind, card_loc = _classify_error(("arr", 0, "x"), schema)
    assert kind == "field"
    assert card_loc == ["arr", 0]


# ---------------------------------------------------------------------------
# Helper: _normalize_validation_errors (wraps _classify_error per pydantic err)


def test_normalize_validation_errors_attaches_card_loc_and_kind() -> None:
    """Each pydantic error grows `card_loc` + `kind`; original `loc`/`msg`/`type` preserved."""
    from pydantic import ValidationError

    from apps.gui.server.routes.settings import _normalize_validation_errors

    payload = Settings().model_dump()
    payload["summarization"]["token_threshold"] = "not an int"
    try:
        Settings.model_validate(payload)
    except ValidationError as exc:
        out = _normalize_validation_errors(exc)
    else:
        raise AssertionError("expected ValidationError")

    assert len(out) >= 1
    err = next(e for e in out if e["loc"] == ["summarization", "token_threshold"])
    assert err["kind"] == "field"
    assert err["card_loc"] == ["summarization"]
    assert err["msg"]
    assert err["type"]


def test_normalize_validation_errors_empty_when_no_errors() -> None:
    """A ValidationError with zero entries → empty list."""
    from unittest.mock import MagicMock

    from apps.gui.server.routes.settings import _normalize_validation_errors

    fake = MagicMock()
    fake.errors.return_value = []
    assert _normalize_validation_errors(fake) == []


def test_normalize_validation_errors_preserves_loc_as_list() -> None:
    """loc tuples from pydantic must be serialised as lists (JSON-friendly)."""
    from unittest.mock import MagicMock

    from apps.gui.server.routes.settings import _normalize_validation_errors

    fake = MagicMock()
    fake.errors.return_value = [{"loc": ("routing", "enabled"), "msg": "bad", "type": "type_error.bool"}]
    out = _normalize_validation_errors(fake)
    assert out[0]["loc"] == ["routing", "enabled"]
    assert isinstance(out[0]["loc"], list)


def test_normalize_validation_errors_handles_missing_loc_msg_type() -> None:
    """Defensive `.get()` calls — missing keys default to () / "" / "" without raising."""
    from unittest.mock import MagicMock

    from apps.gui.server.routes.settings import _normalize_validation_errors

    fake = MagicMock()
    fake.errors.return_value = [{}]
    out = _normalize_validation_errors(fake)
    assert out == [{"loc": [], "card_loc": [], "msg": "", "type": "", "kind": "model_validator"}]


def test_normalize_validation_errors_classifies_model_validator_at_server_dict() -> None:
    """End-to-end: missing `command` on stdio MCP server → model_validator on the server node."""
    from pydantic import ValidationError

    from apps.gui.server.routes.settings import _normalize_validation_errors

    payload = Settings().model_dump()
    payload["mcp"]["enabled"] = True
    payload["mcp"]["servers"] = {
        "n8n": {
            "transport": "stdio",
            "tool_group": "n8n",
            "timeout_seconds": 30.0,
            "command": None,
            "args": [],
            "env": None,
            "cwd": None,
            "url": None,
            "headers": None,
        }
    }
    try:
        Settings.model_validate(payload)
    except ValidationError as exc:
        out = _normalize_validation_errors(exc)
    else:
        raise AssertionError("expected ValidationError")

    err = next(e for e in out if e["loc"] == ["mcp", "servers", "n8n"])
    assert err["kind"] == "model_validator"
    assert err["card_loc"] == ["mcp", "servers", "n8n"]


def test_normalize_validation_errors_multiple_errors_each_classified() -> None:
    """Two failing fields → two normalised entries, each with its own kind+card_loc."""
    from pydantic import ValidationError

    from apps.gui.server.routes.settings import _normalize_validation_errors

    payload = Settings().model_dump()
    payload["summarization"]["token_threshold"] = "not an int"
    payload["routing"]["enabled"] = "not a bool"
    try:
        Settings.model_validate(payload)
    except ValidationError as exc:
        out = _normalize_validation_errors(exc)
    else:
        raise AssertionError("expected ValidationError")

    locs = {tuple(e["loc"]) for e in out}
    assert ("summarization", "token_threshold") in locs
    assert ("routing", "enabled") in locs
    for e in out:
        assert "kind" in e
        assert "card_loc" in e
        assert isinstance(e["card_loc"], list)


# ---------------------------------------------------------------------------
# Helper: _local_yaml_path (anchors the literal path)


def test_local_yaml_path_joins_jarvis_dir_with_config_local_yaml(tmp_path: Path) -> None:
    """Pin the literal "config/local.yaml" segments so a refactor is caught."""
    from apps.gui.server.routes.settings import _local_yaml_path

    session = SimpleNamespace(components=SimpleNamespace(jarvis_dir=tmp_path))
    assert _local_yaml_path(session) == tmp_path / "config" / "local.yaml"
