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
    assert body["restart_required"] is True
    assert body["bytes"] > 0

    written = (tmp_path / "config" / "local.yaml").read_text()
    assert written.startswith(f"{MANAGED_HEADER}\n")
    parsed = yaml.safe_load(written[len(MANAGED_HEADER) + 1 :])
    assert parsed == {"routing": {"enabled": True}}


def test_put_does_not_rebind_components_settings(tmp_path: Path) -> None:
    """PR-8b deliberately does NOT rebind ``components.settings`` after save.

    Downstream tools / LLM clients / MCP subprocesses capture settings at startup,
    so a bare rebind would give a false impression of hot-apply. The banner says
    'restart required' because that's the honest story.
    """
    app = _build_app(tmp_path)
    before = app.state.gui_session.components.settings
    client = TestClient(app)

    payload = Settings().model_dump()
    payload["routing"]["enabled"] = True

    r = client.put("/api/settings", json={"settings": payload})
    assert r.status_code == 200

    after = app.state.gui_session.components.settings
    assert after is before


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
