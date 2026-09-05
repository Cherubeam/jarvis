"""Tests for apps.gui.server.app — the real create_app() wiring and lifespan.

The other GUI route tests mount one router on a bare FastAPI app, so none of
them exercise the middleware stack. This file is the only place the assembled
application is checked, which makes it the guard against "router registered but
never gated".

TestClient(app) used WITHOUT `with` does not run the lifespan, so app.state can
be faked; the lifespan half explicitly stubs build_gui_session, which would
otherwise load config and spawn MCP subprocesses.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starlette.routing import Route
from starlette.websockets import WebSocketDisconnect

from apps.gui.server import app as app_module
from apps.gui.server.app import create_app
from apps.gui.server.auth import COOKIE_NAME, GuiAuth, GuiAuthMiddleware, derive_cookie_value
from apps.gui.server.state import GuiSession

TOKEN = "test-token-abc"


def _auth() -> GuiAuth:
    return GuiAuth(
        token=TOKEN,
        cookie_value=derive_cookie_value(TOKEN),
        allowed_origins=frozenset({"http://testserver", "http://127.0.0.1:8123"}),
    )


def _fake_gui_session() -> GuiSession:
    """A real GuiSession over faked components — session_meta() is exercised for
    real, only build_session()'s expensive wiring is skipped."""
    components = SimpleNamespace(
        conversation_id="conv_abc",
        model_id="anthropic/claude-sonnet-4.5",
        provider="anthropic",
        conversations_dir=Path("/tmp/conversations"),
        vault_config=None,
        agent_registry={"jarvis": object()},
        logger=SimpleNamespace(session_start=datetime(2026, 4, 23, 12, 0, 0)),
    )
    return GuiSession(components=components, started_at="12:00")


def _app_without_lifespan() -> FastAPI:
    app = create_app(_auth())
    app.state.gui_session = _fake_gui_session()  # what lifespan would have set
    return app


def _client() -> TestClient:
    return TestClient(_app_without_lifespan())


def _signed_in_client() -> TestClient:
    client = _client()
    client.cookies.set(COOKIE_NAME, derive_cookie_value(TOKEN))
    return client


# ---------------------------------------------------------------------------
# Wiring


def test_all_routers_are_registered() -> None:
    """Drop an include_router and this fails."""
    paths = {getattr(route, "path", None) for route in _app_without_lifespan().routes}
    assert {
        "/auth",
        "/sign-out",
        "/api/session",
        "/api/agents",
        "/api/conversations",
        "/api/home",
        "/api/outcomes/pending",
        "/api/settings",
        "/ws/chat",
        "/",
    } <= paths


def test_middleware_order_puts_cors_outside_auth() -> None:
    """The single most breakable line in the factory, because it reads
    backwards: add_middleware inserts at index 0, so index 0 is OUTERMOST.

    CORS must be outside — it answers preflight itself, and an OPTIONS gated by
    auth (preflight carries no cookie, by spec) would break every cross-origin
    call from the vite dev server.
    """
    assert [m.cls for m in _app_without_lifespan().user_middleware] == [
        CORSMiddleware,
        GuiAuthMiddleware,
    ]


def test_cors_origins_are_derived_from_the_auth_allowlist() -> None:
    """Two independently maintained origin lists would inevitably drift."""
    auth = _auth()
    app = create_app(auth)
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert cors.kwargs["allow_origins"] == sorted(auth.allowed_origins)
    assert cors.kwargs["allow_credentials"] is True


def test_the_auth_policy_is_reachable_on_app_state() -> None:
    auth = _auth()
    assert create_app(auth).state.gui_auth is auth


def test_create_app_requires_an_auth_policy() -> None:
    """No fail-open default: a bare create_app() must not produce an
    unauthenticated server."""
    with pytest.raises(TypeError):
        create_app()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Gating, through the real factory


def test_api_is_gated() -> None:
    assert _client().get("/api/session").status_code == 403


def test_api_is_reachable_once_signed_in() -> None:
    r = _signed_in_client().get("/api/session")
    assert r.status_code == 200
    assert r.json()["id"] == "conv_abc"


def test_the_websocket_is_gated_by_the_factory_not_by_the_endpoint() -> None:
    """chat_ws.py deliberately holds no auth code, so this is the regression
    guard for a router registered without the middleware."""
    with pytest.raises(WebSocketDisconnect) as exc, _client().websocket_connect("/ws/chat"):
        pass  # pragma: no cover

    assert exc.value.code == 1008


def test_the_websocket_is_reachable_once_signed_in() -> None:
    with _signed_in_client().websocket_connect("/ws/chat") as ws:
        assert ws.receive_json()["type"] == "session_start"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_the_auto_generated_api_docs_are_gated(path: str) -> None:
    """FastAPI registers these by default; they publish the whole route
    inventory, PUT /api/settings included."""
    assert _client().get(path).status_code == 403


def test_settings_write_is_gated() -> None:
    """The highest-value target: PUT /api/settings rewrites config/local.yaml."""
    assert _client().put("/api/settings", json={"settings": {}}).status_code == 403


# ---------------------------------------------------------------------------
# The invariant that keeps the absent-Origin allowance safe


#: Every GET/HEAD route, snapshotted. check_origin(None) returns True so curl
#: and the tests work — and a cross-site top-level navigation also sends no
#: Origin while still carrying the SameSite=Lax cookie. That is safe only while
#: GETs are side-effect free, and nothing in the code enforces it. Adding a GET
#: fails this test on purpose: confirm it is read-only, then add it here.
#:
#: The one deliberate exception is /sign-out, which clears the caller's own
#: cookie. A cross-site page can therefore force a logout — an annoyance, not a
#: privilege escalation, since it grants the attacker nothing and the user
#: simply signs in again.
EXPECTED_GET_ROUTES = {
    "/",
    "/api/agents",
    "/api/agents/{agent_id}",
    "/api/agents/{agent_id}/includes",
    "/api/agents/{agent_id}/includes/{placeholder}",
    "/api/agents/{agent_id}/includes/{placeholder}/snapshots",
    "/api/agents/{agent_id}/prompt",
    "/api/agents/{agent_id}/prompt/resolved",
    "/api/agents/{agent_id}/prompt/snapshots",
    "/api/agents/{agent_id}/prompt/snapshots/{snapshot_id}",
    "/api/agents/{agent_id}/prompt/stats",
    "/api/conversations",
    "/api/conversations/facets",
    "/api/conversations/{conv_id}",
    "/api/home",
    "/api/outcomes/pending",
    "/api/session",
    "/api/settings",
    "/api/settings/schema",
    "/auth",
    "/docs",
    "/docs/oauth2-redirect",
    "/openapi.json",
    "/redoc",
    "/sign-out",
}


def test_get_routes_are_an_audited_set() -> None:
    """See EXPECTED_GET_ROUTES — this is the guard on the absent-Origin allowance."""
    actual = {
        route.path
        for route in _app_without_lifespan().routes
        if isinstance(route, Route) and route.methods is not None and route.methods <= {"GET", "HEAD"}
    }
    assert actual == EXPECTED_GET_ROUTES


# ---------------------------------------------------------------------------
# "/" gates itself


def test_root_serves_the_sign_in_page_when_unauthenticated() -> None:
    r = _client().get("/")
    assert r.status_code == 200
    assert '<form method="post" action="/auth">' in r.text


def test_root_serves_the_bundle_once_signed_in() -> None:
    r = _signed_in_client().get("/")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache, must-revalidate"


# ---------------------------------------------------------------------------
# WEB_DIST branches — three arms, only one of which the repo ever takes


def test_missing_dist_dir_returns_a_build_hint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app_module, "WEB_DIST", tmp_path / "nope")
    client = TestClient(create_app(_auth()))
    client.cookies.set(COOKIE_NAME, derive_cookie_value(TOKEN))

    r = client.get("/")
    assert r.status_code == 503
    assert r.text == (
        "GUI bundle not found at apps/gui/web/dist/. Run: cd apps/gui/web && npm install && npm run build"
    )


def test_dist_without_index_html_returns_the_other_hint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A distinct message from the missing-dist case — a mutant swapping the two
    survives a status-only assertion."""
    (tmp_path / "dist").mkdir()
    monkeypatch.setattr(app_module, "WEB_DIST", tmp_path / "dist")
    client = TestClient(create_app(_auth()))
    client.cookies.set(COOKIE_NAME, derive_cookie_value(TOKEN))

    r = client.get("/")
    assert r.status_code == 503
    assert r.text == "GUI bundle not found. Run: cd apps/gui/web && npm run build"


def test_dist_with_index_html_is_served(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>jarvis</html>", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEB_DIST", dist)
    client = TestClient(create_app(_auth()))
    client.cookies.set(COOKIE_NAME, derive_cookie_value(TOKEN))

    r = client.get("/")
    assert r.status_code == 200
    assert r.text == "<html>jarvis</html>"
    assert r.headers["cache-control"] == "no-cache, must-revalidate"


def test_missing_assets_dir_is_not_mounted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    monkeypatch.setattr(app_module, "WEB_DIST", dist)
    mounts = [r for r in create_app(_auth()).routes if getattr(r, "name", None) == "assets"]
    assert mounts == []


def test_assets_dir_is_mounted_when_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    monkeypatch.setattr(app_module, "WEB_DIST", dist)
    mounts = [r for r in create_app(_auth()).routes if getattr(r, "name", None) == "assets"]
    assert len(mounts) == 1


def test_the_sign_in_page_is_served_even_without_a_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Both "/" arms gate themselves, so the no-bundle branch cannot become an
    accidental information leak."""
    monkeypatch.setattr(app_module, "WEB_DIST", tmp_path / "nope")
    r = TestClient(create_app(_auth())).get("/")
    assert r.status_code == 200
    assert '<form method="post" action="/auth">' in r.text


# ---------------------------------------------------------------------------
# Lifespan


def _stub_build_gui_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> GuiSession:
    session = _fake_gui_session()
    session.components.conversations_dir = tmp_path
    session.components.mcp_manager = MagicMock()
    session.components.logger = MagicMock()
    session.conversation_index = None
    monkeypatch.setattr(app_module, "build_gui_session", lambda: session)
    return session


def test_lifespan_builds_the_session_and_index(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session = _stub_build_gui_session(monkeypatch, tmp_path)
    app = create_app(_auth())

    with TestClient(app):
        assert app.state.gui_session is session
        assert app.state.conversation_index is not None
        # The bridge reaches the index through the session to invalidate the
        # active file_id per turn — this cross-link has never been tested.
        assert app.state.gui_session.conversation_index is app.state.conversation_index


def test_lifespan_shuts_down_mcp_and_saves_the_conversation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session = _stub_build_gui_session(monkeypatch, tmp_path)

    with TestClient(create_app(_auth())):
        pass

    session.components.mcp_manager.shutdown.assert_called_once_with()
    session.components.logger.save.assert_called_once_with()


def test_lifespan_tolerates_no_mcp_manager(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session = _stub_build_gui_session(monkeypatch, tmp_path)
    session.components.mcp_manager = None

    with TestClient(create_app(_auth())):
        pass

    session.components.logger.save.assert_called_once_with()


def test_a_failing_mcp_shutdown_still_saves_the_conversation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The two teardown steps are independent — a mutant merging them would lose
    the in-flight conversation whenever MCP shutdown fails."""
    session = _stub_build_gui_session(monkeypatch, tmp_path)
    session.components.mcp_manager.shutdown.side_effect = RuntimeError("mcp died")

    with caplog.at_level(logging.ERROR, logger="apps.gui.server.app"), TestClient(create_app(_auth())):
        pass

    assert any("mcp shutdown failed" in r.getMessage() for r in caplog.records)
    session.components.logger.save.assert_called_once_with()


def test_a_failing_save_is_logged_and_swallowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    session = _stub_build_gui_session(monkeypatch, tmp_path)
    session.components.logger.save.side_effect = RuntimeError("disk full")

    with caplog.at_level(logging.ERROR, logger="apps.gui.server.app"), TestClient(create_app(_auth())):
        pass  # exiting must not raise

    assert any("logger.save() on shutdown failed" in r.getMessage() for r in caplog.records)


def test_requests_work_inside_the_lifespan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_build_gui_session(monkeypatch, tmp_path)

    with TestClient(create_app(_auth())) as client:
        client.cookies.set(COOKIE_NAME, derive_cookie_value(TOKEN))
        assert client.get("/api/session").status_code == 200
