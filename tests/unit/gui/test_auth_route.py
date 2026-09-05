"""Tests for GET/POST /auth and GET /sign-out — the cookie bootstrap."""

from __future__ import annotations

import logging
from http.cookies import SimpleCookie

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gui.server.auth import COOKIE_MAX_AGE, COOKIE_NAME, GuiAuth, derive_cookie_value
from apps.gui.server.routes.auth import router as auth_router

TOKEN = "test-token-abc"


def _build_app() -> FastAPI:
    app = FastAPI()
    app.state.gui_auth = GuiAuth(
        token=TOKEN,
        cookie_value=derive_cookie_value(TOKEN),
        allowed_origins=frozenset({"http://testserver"}),
    )
    app.include_router(auth_router)
    return app


def _client(base_url: str = "http://testserver") -> TestClient:
    return TestClient(_build_app(), base_url=base_url)


def _set_cookie(response: object) -> SimpleCookie:
    jar = SimpleCookie()
    jar.load(response.headers["set-cookie"])  # type: ignore[attr-defined]
    return jar


# ---------------------------------------------------------------------------
# GET /auth — the happy path


def test_valid_token_redirects_to_root() -> None:
    r = _client().get(f"/auth?token={TOKEN}", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_valid_token_sets_the_derived_cookie_not_the_token() -> None:
    """A cookie is sent to every other loopback port; it must not be the
    Bearer credential."""
    r = _client().get(f"/auth?token={TOKEN}", follow_redirects=False)
    morsel = _set_cookie(r)[COOKIE_NAME]

    assert morsel.value == derive_cookie_value(TOKEN)
    assert morsel.value != TOKEN


def test_cookie_attributes_are_pinned() -> None:
    r = _client().get(f"/auth?token={TOKEN}", follow_redirects=False)
    morsel = _set_cookie(r)[COOKIE_NAME]

    assert morsel["path"] == "/"
    assert morsel["max-age"] == str(COOKIE_MAX_AGE)
    assert morsel["max-age"] == "2592000"  # 30 days
    assert morsel["httponly"] is True  # unreachable from document.cookie
    assert morsel["samesite"].lower() == "lax"


def test_cookie_is_not_secure_over_http() -> None:
    """Setting Secure over plain http makes the browser drop the cookie and the
    GUI auth-loops forever."""
    r = _client().get(f"/auth?token={TOKEN}", follow_redirects=False)
    assert _set_cookie(r)[COOKIE_NAME]["secure"] == ""


def test_cookie_is_secure_over_https() -> None:
    r = _client(base_url="https://testserver").get(f"/auth?token={TOKEN}", follow_redirects=False)
    assert _set_cookie(r)[COOKIE_NAME]["secure"] is True


def test_bootstrap_end_to_end_leaves_the_cookie_in_the_jar() -> None:
    app = _build_app()

    @app.get("/")
    async def root() -> str:
        return "bundle"

    client = TestClient(app)
    r = client.get(f"/auth?token={TOKEN}")  # follows the redirect
    assert r.status_code == 200
    assert client.cookies[COOKIE_NAME] == derive_cookie_value(TOKEN)


# ---------------------------------------------------------------------------
# GET /auth — rejection


def test_wrong_token_is_rejected_without_setting_a_cookie() -> None:
    """The negative that matters: a mutant setting the cookie before validating
    still returns 403, so the status alone proves nothing."""
    r = _client().get("/auth?token=wrong", follow_redirects=False)
    assert r.status_code == 403
    assert "set-cookie" not in r.headers


def test_wrong_token_renders_the_form_again_with_an_error() -> None:
    r = _client().get("/auth?token=wrong", follow_redirects=False)
    assert "not accepted" in r.text
    assert '<form method="post" action="/auth">' in r.text


def test_missing_token_param_shows_the_form_not_a_422() -> None:
    """FastAPI's default for a required query param is 422; a human landing on
    /auth should get the sign-in form instead."""
    r = _client().get("/auth", follow_redirects=False)
    assert r.status_code == 200
    assert "set-cookie" not in r.headers
    assert '<form method="post" action="/auth">' in r.text
    assert "not accepted" not in r.text


def test_empty_token_param_shows_the_form() -> None:
    r = _client().get("/auth?token=", follow_redirects=False)
    assert r.status_code == 200
    assert "set-cookie" not in r.headers


def test_rejection_is_logged_with_the_client_host(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.routes.auth"):
        _client().get("/auth?token=wrong", follow_redirects=False)
    assert any("rejected sign-in from" in r.getMessage() for r in caplog.records)


def test_no_open_redirect_via_a_next_parameter() -> None:
    """The redirect target is a constant. An open redirect on the route that
    issues the session cookie would be a token-exfiltration primitive."""
    r = _client().get(f"/auth?token={TOKEN}&next=http://evil.example", follow_redirects=False)
    assert r.headers["location"] == "/"


# ---------------------------------------------------------------------------
# POST /auth — the URL-free path used by the sign-in page


def test_form_post_with_a_valid_token_signs_in() -> None:
    r = _client().post("/auth", data={"token": TOKEN}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert _set_cookie(r)[COOKIE_NAME].value == derive_cookie_value(TOKEN)


def test_form_post_with_a_wrong_token_is_rejected() -> None:
    r = _client().post("/auth", data={"token": "wrong"}, follow_redirects=False)
    assert r.status_code == 403
    assert "set-cookie" not in r.headers


def test_form_post_with_a_blank_token_is_rejected() -> None:
    r = _client().post("/auth", data={"token": "   "}, follow_redirects=False)
    assert r.status_code == 403
    assert "set-cookie" not in r.headers


def test_form_post_without_a_token_field_is_rejected() -> None:
    r = _client().post("/auth", data={}, follow_redirects=False)
    assert r.status_code == 403
    assert "set-cookie" not in r.headers


def test_form_post_strips_surrounding_whitespace() -> None:
    """Pasting from a terminal often carries a trailing newline."""
    r = _client().post("/auth", data={"token": f"  {TOKEN}\n"}, follow_redirects=False)
    assert r.status_code == 303


# ---------------------------------------------------------------------------
# The sign-in page itself


def test_sign_in_page_is_not_cached() -> None:
    r = _client().get("/auth", follow_redirects=False)
    assert r.headers["cache-control"] == "no-store"


def test_sign_in_page_names_where_to_find_the_token() -> None:
    r = _client().get("/auth", follow_redirects=False)
    assert "data/.gui_token" in r.text
    assert "jarvis-gui" in r.text


def test_sign_in_page_never_contains_the_token() -> None:
    for response in (
        _client().get("/auth", follow_redirects=False),
        _client().get("/auth?token=wrong", follow_redirects=False),
    ):
        assert TOKEN not in response.text
        assert derive_cookie_value(TOKEN) not in response.text


def test_sign_in_field_is_a_password_input() -> None:
    """Keeps the token out of shoulder-surfing range and out of form autofill."""
    r = _client().get("/auth", follow_redirects=False)
    assert 'type="password"' in r.text
    assert 'autocomplete="off"' in r.text


# ---------------------------------------------------------------------------
# GET /sign-out


def test_sign_out_clears_the_cookie() -> None:
    r = _client().get("/sign-out", follow_redirects=False)
    assert r.status_code == 200
    assert r.text == "signed out"

    morsel = _set_cookie(r)[COOKIE_NAME]
    assert morsel.value == ""
    assert morsel["path"] == "/"
