"""Tests for GuiAuthMiddleware — the single choke point gating REST and the WS.

Driven over stub routes so this file tests the gate, not the real endpoints.
Gating of the actual app (route inventory, middleware order, /docs) lives in
test_app_factory.py.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from apps.gui.server.auth import COOKIE_NAME, GuiAuth, GuiAuthMiddleware, derive_cookie_value

TOKEN = "test-token-abc"
ORIGIN = "http://127.0.0.1:8123"

#: Records which stub handlers actually ran, so a rejection can be shown to
#: short-circuit rather than merely rewrite the status.
REACHED: list[str] = []


def _auth() -> GuiAuth:
    return GuiAuth(
        token=TOKEN,
        cookie_value=derive_cookie_value(TOKEN),
        allowed_origins=frozenset({ORIGIN}),
    )


def _build_app(auth: GuiAuth | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(GuiAuthMiddleware, auth=auth or _auth())

    @app.get("/api/ping")
    async def ping() -> dict[str, str]:
        REACHED.append("GET /api/ping")
        return {"pong": "yes"}

    @app.put("/api/ping")
    async def put_ping() -> dict[str, str]:
        REACHED.append("PUT /api/ping")
        return {"pong": "put"}

    @app.get("/")
    async def root() -> dict[str, str]:
        REACHED.append("GET /")
        return {"page": "bundle"}

    @app.get("/assets/index-abc.js")
    async def asset() -> dict[str, str]:
        REACHED.append("GET /assets/index-abc.js")
        return {"asset": "js"}

    @app.websocket("/ws/chat")
    async def chat(websocket: WebSocket) -> None:
        REACHED.append("WS /ws/chat")
        await websocket.accept()
        await websocket.send_json({"type": "session_start"})
        await websocket.close()

    return app


@pytest.fixture(autouse=True)
def _clear_reached() -> Iterator[None]:
    REACHED.clear()
    yield
    REACHED.clear()


def _client() -> TestClient:
    return TestClient(_build_app())


def _signed_in_client() -> TestClient:
    client = _client()
    client.cookies.set(COOKIE_NAME, derive_cookie_value(TOKEN))
    return client


# ---------------------------------------------------------------------------
# HTTP — rejection


def test_http_without_a_credential_is_rejected() -> None:
    r = _client().get("/api/ping")
    assert r.status_code == 403
    assert r.text == "forbidden"
    # The handler must not have run — this is a gate, not a status rewrite.
    assert REACHED == []


def test_http_with_a_wrong_cookie_is_rejected() -> None:
    client = _client()
    client.cookies.set(COOKIE_NAME, "not-the-value")
    assert client.get("/api/ping").status_code == 403
    assert REACHED == []


def test_http_with_a_wrong_bearer_is_rejected() -> None:
    r = _client().get("/api/ping", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 403
    assert REACHED == []


def test_http_uses_403_not_401() -> None:
    """401 would trigger the browser's Basic-auth prompt; there is no
    interactive challenge to offer."""
    r = _client().get("/api/ping")
    assert r.status_code == 403
    assert "www-authenticate" not in r.headers


def test_mutating_request_is_gated_too() -> None:
    assert _client().put("/api/ping", json={}).status_code == 403
    assert REACHED == []


# ---------------------------------------------------------------------------
# HTTP — acceptance


def test_http_with_the_cookie_is_allowed() -> None:
    r = _signed_in_client().get("/api/ping")
    assert r.status_code == 200
    assert r.json() == {"pong": "yes"}
    assert REACHED == ["GET /api/ping"]


def test_http_with_the_bearer_token_is_allowed() -> None:
    r = _client().get("/api/ping", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert REACHED == ["GET /api/ping"]


def test_the_raw_token_is_not_accepted_as_a_cookie() -> None:
    """The two credentials are distinct so a cookie stolen off another loopback
    port cannot be replayed as a Bearer token, and vice versa."""
    client = _client()
    client.cookies.set(COOKIE_NAME, TOKEN)
    assert client.get("/api/ping").status_code == 403


def test_the_cookie_value_is_not_accepted_as_a_bearer() -> None:
    r = _client().get("/api/ping", headers={"Authorization": f"Bearer {derive_cookie_value(TOKEN)}"})
    assert r.status_code == 403


def test_a_valid_bearer_wins_over_a_planted_cookie() -> None:
    """Credentials are checked try-all, not first-match: a junk cookie planted
    by another loopback page must not lock out a valid Bearer client."""
    client = _client()
    client.cookies.set(COOKIE_NAME, "planted-junk")
    r = client.get("/api/ping", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Exempt paths


def test_root_is_served_without_a_credential() -> None:
    """Gating "/" would be a bootstrap deadlock — there would be no page from
    which to sign in."""
    r = _client().get("/")
    assert r.status_code == 200
    assert REACHED == ["GET /"]


def test_assets_are_served_without_a_credential() -> None:
    r = _client().get("/assets/index-abc.js")
    assert r.status_code == 200


def test_an_unknown_path_is_still_gated() -> None:
    """404s must not leak the route inventory to an unauthenticated client."""
    assert _client().get("/api/does-not-exist").status_code == 403


# ---------------------------------------------------------------------------
# Origin — checked independently of the credential


def test_a_foreign_origin_is_rejected_even_with_a_valid_credential() -> None:
    """Origin AND credentials, never OR. This is the check that stops a page on
    any other site from driving the agent through the user's own browser."""
    client = _signed_in_client()
    r = client.get("/api/ping", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert REACHED == []


def test_an_allowlisted_origin_with_a_valid_credential_is_allowed() -> None:
    r = _signed_in_client().get("/api/ping", headers={"Origin": ORIGIN})
    assert r.status_code == 200


def test_an_allowlisted_origin_without_a_credential_is_still_rejected() -> None:
    r = _client().get("/api/ping", headers={"Origin": ORIGIN})
    assert r.status_code == 403


def test_an_absent_origin_with_a_valid_credential_is_allowed() -> None:
    """curl and other non-browser clients send no Origin and have no ambient
    cookie jar to be CSRF'd through."""
    r = _client().get("/api/ping", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


def test_a_foreign_origin_is_rejected_on_an_exempt_path_only_after_the_exemption() -> None:
    """Exempt paths short-circuit before the origin check — the bundle is public
    and must load regardless of who links to it."""
    r = _client().get("/", headers={"Origin": "http://evil.example"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# WebSocket — the headline requirement


def test_ws_without_a_credential_is_closed_with_1008() -> None:
    client = _client()
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect("/ws/chat"):
        pass  # pragma: no cover — the handshake never completes

    assert exc.value.code == 1008
    assert exc.value.reason == "unauthorized"
    assert REACHED == []  # the endpoint never ran


def test_ws_from_a_foreign_origin_is_closed_even_with_a_valid_cookie() -> None:
    """The attack this milestone exists to close: browsers do not enforce
    same-origin on WebSockets, so any page can open ws://127.0.0.1:8123/ws/chat.
    Only the Origin check stops it."""
    client = _signed_in_client()
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect("/ws/chat", headers={"Origin": "http://evil.example"}),
    ):
        pass  # pragma: no cover

    assert exc.value.code == 1008
    assert REACHED == []


def test_ws_with_the_cookie_is_accepted() -> None:
    """Proves the browser's own mechanism works: httpx applies the cookie jar to
    the handshake exactly as a browser would."""
    client = _signed_in_client()
    with client.websocket_connect("/ws/chat") as ws:
        assert ws.receive_json() == {"type": "session_start"}
    assert REACHED == ["WS /ws/chat"]


def test_ws_with_an_allowlisted_origin_and_cookie_is_accepted() -> None:
    client = _signed_in_client()
    with client.websocket_connect("/ws/chat", headers={"Origin": ORIGIN}) as ws:
        assert ws.receive_json() == {"type": "session_start"}


def test_ws_with_a_wrong_cookie_is_closed() -> None:
    client = _client()
    client.cookies.set(COOKIE_NAME, "not-the-value")
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect("/ws/chat"):
        pass  # pragma: no cover
    assert exc.value.code == 1008


# ---------------------------------------------------------------------------
# Non-HTTP scopes


def test_lifespan_passes_through() -> None:
    """The middleware must not swallow the lifespan scope — startup state would
    silently never be built."""
    started: list[str] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        started.append("up")
        yield
        started.append("down")

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(GuiAuthMiddleware, auth=_auth())

    @app.get("/")
    async def root() -> str:
        return "ok"

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert started == ["up"]
    assert started == ["up", "down"]


# ---------------------------------------------------------------------------
# Observability


def test_rejections_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.auth"):
        _client().get("/api/ping")
    messages = [r.getMessage() for r in caplog.records]
    assert any("bad credentials" in m for m in messages)
    assert any("/api/ping" in m for m in messages)


def test_origin_rejections_name_the_origin(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.auth"):
        _signed_in_client().get("/api/ping", headers={"Origin": "http://evil.example"})
    messages = [r.getMessage() for r in caplog.records]
    assert any("bad origin" in m for m in messages)
    assert any("evil.example" in m for m in messages)


def test_rejection_log_never_contains_the_credential(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.auth"):
        _client().get("/api/ping", headers={"Authorization": f"Bearer {TOKEN}", "Origin": "http://evil.example"})
    assert all(TOKEN not in r.getMessage() for r in caplog.records)
