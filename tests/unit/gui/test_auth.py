"""Tests for apps.gui.server.auth — the GUI origin allowlist + token policy.

Pure logic only. The ASGI middleware is covered in test_auth_middleware.py and
the /auth bootstrap route in test_auth_route.py.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import stat
from pathlib import Path

import pytest

from apps.gui.server.auth import (
    COOKIE_NAME,
    TOKEN_ENV_VAR,
    TOKEN_FILE,
    GuiAuth,
    TokenRedactingFilter,
    bearer_from_header,
    bootstrap_url,
    default_origins,
    derive_cookie_value,
    install_access_log_redaction,
    is_exempt,
    redact_token,
    resolve_token,
)


def _auth(token: str = "test-token", origins: set[str] | None = None) -> GuiAuth:
    return GuiAuth(
        token=token,
        cookie_value=derive_cookie_value(token),
        allowed_origins=frozenset(origins or {"http://127.0.0.1:8123"}),
    )


# ---------------------------------------------------------------------------
# resolve_token — env > file > mint-and-persist


def test_resolve_token_prefers_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV_VAR, "from-the-environment")
    assert resolve_token(tmp_path) == "from-the-environment"
    # No file written — the env var is authoritative.
    assert not (tmp_path / "data" / TOKEN_FILE).exists()


def test_resolve_token_ignores_blank_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV_VAR, "   ")
    token = resolve_token(tmp_path)
    assert token != "   "
    assert (tmp_path / "data" / TOKEN_FILE).is_file()


def test_resolve_token_reads_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    path = tmp_path / "data" / TOKEN_FILE
    path.parent.mkdir(parents=True)
    path.write_text("persisted-token\n", encoding="utf-8")
    assert resolve_token(tmp_path) == "persisted-token"


def test_resolve_token_regenerates_when_file_is_blank(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    path = tmp_path / "data" / TOKEN_FILE
    path.parent.mkdir(parents=True)
    path.write_text("  \n", encoding="utf-8")
    token = resolve_token(tmp_path)
    assert token.strip() == token
    assert len(token) > 20
    assert path.read_text(encoding="utf-8").strip() == token


def test_resolve_token_mints_and_persists_at_mode_600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    token = resolve_token(tmp_path)
    path = tmp_path / "data" / TOKEN_FILE

    assert path.read_text(encoding="utf-8") == token + "\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_minted_token_has_full_entropy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """32 random bytes, url-safe encoded — exactly 43 characters.

    A length assertion of "> 20" would pass on a materially weaker token, and
    this is the credential guarding the whole GUI.
    """
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    token = resolve_token(tmp_path)
    assert len(token) == 43
    assert token == token.strip()


def test_resolve_token_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A second call must reuse the persisted token, not mint a new one —
    otherwise every restart invalidates the browser cookie."""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    assert resolve_token(tmp_path) == resolve_token(tmp_path)


def test_resolve_token_falls_back_to_ephemeral_when_unwritable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An unwritable data/ must not crash the server."""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)

    def _boom(*args: object, **kwargs: object) -> int:
        raise OSError("read-only file system")

    monkeypatch.setattr("apps.gui.server.auth.os.open", _boom)

    with caplog.at_level(logging.WARNING, logger="apps.gui.server.auth"):
        token = resolve_token(tmp_path)

    assert len(token) > 20
    assert any("ephemeral" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# derive_cookie_value


def test_derive_cookie_value_is_deterministic() -> None:
    assert derive_cookie_value("abc") == derive_cookie_value("abc")


def test_derive_cookie_value_differs_from_the_token() -> None:
    """The browser must never hold the Bearer credential: cookies are not
    port-scoped, so every other loopback listener receives this value."""
    token = "the-real-token"
    derived = derive_cookie_value(token)
    assert derived != token
    assert token not in derived


def test_derive_cookie_value_differs_per_token() -> None:
    assert derive_cookie_value("abc") != derive_cookie_value("abd")


def test_derive_cookie_value_known_answer() -> None:
    """Pins the domain-separation label, not just the shape.

    Without a fixed vector, dropping COOKIE_HMAC_LABEL (or changing it) still
    produces a stable 64-char hex digest and every structural assertion passes —
    while silently changing what the cookie means.
    """
    assert derive_cookie_value("known-token") == ("36ca7f867e3f31135b691d4762b0fbf3ca69fb6fe9bafd17cd681eb6a0830c59")


def test_derive_cookie_value_is_domain_separated() -> None:
    """The label must actually participate — a bare HMAC over an empty message
    would be a different, unlabelled construction."""
    unlabelled = hmac.new(b"known-token", None, hashlib.sha256).hexdigest()
    assert derive_cookie_value("known-token") != unlabelled


def test_derive_cookie_value_is_a_sha256_hex_digest() -> None:
    derived = derive_cookie_value("abc")
    assert len(derived) == 64
    assert all(c in "0123456789abcdef" for c in derived)


# ---------------------------------------------------------------------------
# default_origins — exact sets, so port arithmetic mutants die


def test_default_origins_loopback() -> None:
    assert default_origins("127.0.0.1", 8123) == {
        "http://127.0.0.1:8123",
        "http://localhost:8123",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }


def test_default_origins_honours_a_custom_port() -> None:
    assert default_origins("localhost", 9000) == {
        "http://localhost:9000",
        "http://127.0.0.1:9000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }


def test_default_origins_for_a_non_loopback_host_adds_only_its_own() -> None:
    """A LAN bind gets no loopback aliases — the browser will send the hostname
    it dialled, which must be added via gui.allowed_origins."""
    assert default_origins("192.168.1.20", 8123) == {
        "http://192.168.1.20:8123",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }


def test_default_origins_for_wildcard_bind_includes_loopback() -> None:
    assert default_origins("0.0.0.0", 8123) == {
        "http://0.0.0.0:8123",
        "http://127.0.0.1:8123",
        "http://localhost:8123",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }


# ---------------------------------------------------------------------------
# is_exempt


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", True),
        ("/auth", True),
        ("/favicon.ico", True),
        ("/assets/index-abc123.js", True),
        ("/assets/", True),
        ("/assets", False),  # the mount point itself is not the prefix
        ("/assetsfoo", False),  # prefix must not match a longer segment
        ("/api/session", False),
        ("/api/settings", False),
        ("/ws/chat", False),
        ("/docs", False),
        ("/redoc", False),
        ("/openapi.json", False),
        ("/authx", False),
        ("", False),
    ],
)
def test_is_exempt(path: str, expected: bool) -> None:
    assert is_exempt(path) is expected


# ---------------------------------------------------------------------------
# check_origin


def test_check_origin_allows_a_missing_header() -> None:
    """curl/tests send no Origin, and have no ambient cookie jar to be CSRF'd."""
    assert _auth().check_origin(None) is True


def test_check_origin_allows_an_allowlisted_origin() -> None:
    assert _auth().check_origin("http://127.0.0.1:8123") is True


def test_check_origin_rejects_a_foreign_origin() -> None:
    assert _auth().check_origin("http://evil.example") is False


def test_check_origin_rejects_an_empty_string() -> None:
    """An empty Origin is a present-but-opaque header, not an absent one."""
    assert _auth().check_origin("") is False


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:8123/",  # trailing slash is not a serialized origin
        "http://127.0.0.1:8124",  # neighbouring port
        "https://127.0.0.1:8123",  # different scheme
        "HTTP://127.0.0.1:8123",  # case-sensitive exact match
        "http://127.0.0.1",  # no port
    ],
)
def test_check_origin_matches_exactly(origin: str) -> None:
    assert _auth().check_origin(origin) is False


# ---------------------------------------------------------------------------
# check_credentials — try-all, never first-match


def test_check_credentials_accepts_the_cookie() -> None:
    auth = _auth()
    assert auth.check_credentials(cookie=auth.cookie_value, bearer=None) is True


def test_check_credentials_accepts_the_bearer_token() -> None:
    auth = _auth()
    assert auth.check_credentials(cookie=None, bearer=auth.token) is True


def test_check_credentials_rejects_the_token_in_the_cookie() -> None:
    """The two credentials are distinct: the raw token is not a valid cookie."""
    auth = _auth()
    assert auth.check_credentials(cookie=auth.token, bearer=None) is False


def test_check_credentials_rejects_the_cookie_value_as_a_bearer() -> None:
    """A stolen cookie must not become a Bearer credential."""
    auth = _auth()
    assert auth.check_credentials(cookie=None, bearer=auth.cookie_value) is False


def test_check_credentials_accepts_a_valid_bearer_despite_a_junk_cookie() -> None:
    """Try-all, not first-match. Any page on any other loopback port can plant a
    same-name cookie at a different path; first-match would let that lock out a
    legitimate client."""
    auth = _auth()
    assert auth.check_credentials(cookie="planted-junk", bearer=auth.token) is True


def test_check_credentials_accepts_a_valid_cookie_despite_a_junk_bearer() -> None:
    auth = _auth()
    assert auth.check_credentials(cookie=auth.cookie_value, bearer="junk") is True


def test_check_credentials_rejects_when_neither_is_presented() -> None:
    assert _auth().check_credentials(cookie=None, bearer=None) is False


def test_check_credentials_rejects_empty_strings() -> None:
    assert _auth().check_credentials(cookie="", bearer="") is False


def test_check_credentials_rejects_both_wrong() -> None:
    assert _auth().check_credentials(cookie="nope", bearer="nope") is False


def test_check_credentials_handles_non_ascii_without_raising() -> None:
    """secrets.compare_digest raises TypeError on non-ASCII str operands; the
    presented value is attacker-controlled, so it is compared as bytes."""
    assert _auth().check_credentials(cookie="tökén", bearer="tökén") is False


# ---------------------------------------------------------------------------
# bearer_from_header


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Bearer abc123", "abc123"),
        ("bearer abc123", "abc123"),  # scheme is case-insensitive
        ("BEARER abc123", "abc123"),
        ("Bearer  abc123 ", "abc123"),
        ("Basic abc123", None),  # wrong scheme
        ("Bearer", None),  # no value
        ("Bearer   ", None),  # blank value
        ("abc123", None),  # no scheme
        ("", None),
        (None, None),
    ],
)
def test_bearer_from_header(header: str | None, expected: str | None) -> None:
    assert bearer_from_header(header) == expected


# ---------------------------------------------------------------------------
# GuiAuth.create


def test_create_derives_the_cookie_and_unions_extra_origins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV_VAR, "env-token")
    auth = GuiAuth.create(
        "127.0.0.1",
        8123,
        project_root=tmp_path,
        extra_origins=["https://jarvis.example.ts.net"],
    )

    assert auth.token == "env-token"
    assert auth.cookie_value == derive_cookie_value("env-token")
    assert auth.allowed_origins == frozenset(default_origins("127.0.0.1", 8123) | {"https://jarvis.example.ts.net"})


def test_create_without_extra_origins_uses_the_computed_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV_VAR, "env-token")
    auth = GuiAuth.create("127.0.0.1", 8123, project_root=tmp_path)
    assert auth.allowed_origins == frozenset(default_origins("127.0.0.1", 8123))


def test_create_warns_on_a_wildcard_bind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Browsers reach a 0.0.0.0 bind under some other hostname, which the
    allowlist rejects — the warning names the fix instead of leaving a 403."""
    monkeypatch.setenv(TOKEN_ENV_VAR, "env-token")
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.auth"):
        GuiAuth.create("0.0.0.0", 8123, project_root=tmp_path)
    assert any("gui.allowed_origins" in r.getMessage() for r in caplog.records)


def test_create_does_not_warn_on_loopback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(TOKEN_ENV_VAR, "env-token")
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.auth"):
        GuiAuth.create("127.0.0.1", 8123, project_root=tmp_path)
    assert caplog.records == []


# ---------------------------------------------------------------------------
# bootstrap_url


def test_bootstrap_url() -> None:
    assert bootstrap_url("127.0.0.1", 8123, "tok") == "http://127.0.0.1:8123/auth?token=tok"


def test_bootstrap_url_rewrites_a_wildcard_bind_to_loopback() -> None:
    """http://0.0.0.0:8123 is not dialable — send the operator to loopback."""
    assert bootstrap_url("0.0.0.0", 9000, "tok") == "http://127.0.0.1:9000/auth?token=tok"


# ---------------------------------------------------------------------------
# Access-log redaction


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('GET /auth?token=s3cret HTTP/1.1" 303', 'GET /auth?token=REDACTED HTTP/1.1" 303'),
        ("/auth?token=s3cret&next=/", "/auth?token=REDACTED&next=/"),
        ("/auth?token=s3cret", "/auth?token=REDACTED"),
        ("/api/session", "/api/session"),  # untouched
        ("/auth?token=", "/auth?token="),  # nothing to redact
    ],
)
def test_redact_token(raw: str, expected: str) -> None:
    assert redact_token(raw) == expected


def test_redacting_filter_scrubs_the_access_log_record() -> None:
    """uvicorn logs the request line via record.args, not the message."""
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:1234", "GET", "/auth?token=s3cret", "1.1", 303),
        exc_info=None,
    )
    assert TokenRedactingFilter().filter(record) is True
    assert record.args is not None
    assert "s3cret" not in record.getMessage()
    assert "/auth?token=REDACTED" in record.getMessage()


def test_redacting_filter_scrubs_a_plain_message() -> None:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="visit /auth?token=s3cret",
        args=None,
        exc_info=None,
    )
    assert TokenRedactingFilter().filter(record) is True
    assert record.getMessage() == "visit /auth?token=REDACTED"


def test_install_access_log_redaction_attaches_to_uvicorn_access() -> None:
    """The filter is useless unless it is actually installed on the logger
    uvicorn writes access lines to."""
    access_logger = logging.getLogger("uvicorn.access")
    before = list(access_logger.filters)
    try:
        installed = install_access_log_redaction()
        assert isinstance(installed, TokenRedactingFilter)
        assert installed in access_logger.filters

        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="%s %s",
            args=("GET", "/auth?token=s3cret"),
            exc_info=None,
        )
        for f in access_logger.filters:
            f.filter(record)  # type: ignore[union-attr]
        assert "s3cret" not in record.getMessage()
    finally:
        access_logger.filters = before


def test_redacting_filter_leaves_unrelated_records_alone() -> None:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="%s %s",
        args=("GET", "/api/session"),
        exc_info=None,
    )
    assert TokenRedactingFilter().filter(record) is True
    assert record.getMessage() == "GET /api/session"


# ---------------------------------------------------------------------------
# Constants that the frontend / docs depend on


def test_cookie_name_is_stable() -> None:
    """Renaming this logs every existing browser out."""
    assert COOKIE_NAME == "jarvis_gui_token"
