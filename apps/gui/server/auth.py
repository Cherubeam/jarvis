"""Authentication policy for the GUI server: origin allowlist + token.

Two independent checks, because they stop two different attackers:

- **Origin allowlist** stops a *browser being used against you*. Browsers do not
  enforce same-origin on WebSockets — any page the user visits can open
  ``ws://127.0.0.1:8123/ws/chat`` with no preflight and no CORS check — so
  "it's bound to localhost" is not a boundary, it's the assumption the attack is
  built on. (DNS rebinding is the same trick against plain HTTP.)
- **Token** stops *another machine on the network*, once the server binds past
  loopback (``--host``, or Tailscale in AON-02).

Two credentials, deliberately. Cookies are scoped by host but **not by port**,
so once the browser is bootstrapped it sends the GUI cookie to every other
``127.0.0.1:<port>`` listener — a Vite server, an Electron app, a malicious
postinstall script. If the cookie carried the raw token, any of them could read
one header and walk away with a durable credential that also works over
``Authorization: Bearer``. So the cookie carries a one-way HMAC of the token:

- ``Authorization: Bearer`` accepts **only** the raw token (``data/.gui_token``).
- the cookie accepts **only** the derived value.

See ADR-035 and docs/engineering/gui.md.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from starlette.requests import HTTPConnection
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketClose

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8123

COOKIE_NAME = "jarvis_gui_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
TOKEN_ENV_VAR = "JARVIS_GUI_TOKEN"
TOKEN_FILE = ".gui_token"
COOKIE_HMAC_LABEL = b"jarvis-gui-cookie-v1"

#: Paths served before the client can possibly hold a credential. Gating these
#: would be a bootstrap deadlock: ``/auth`` issues the cookie, and ``/`` plus the
#: hashed bundle under ``/assets/`` are the page that lets a user reach it. They
#: carry no user data — every data-bearing call the page makes is gated.
EXEMPT_PATHS = frozenset({"/", "/auth", "/favicon.ico"})
EXEMPT_PREFIXES = ("/assets/",)

#: vite.config.ts pins ``strictPort: true`` on 5173, so this pair is a fixed
#: contract rather than a variable.
VITE_DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
WILDCARD_BIND_HOSTS = frozenset({"0.0.0.0", "::"})  # compared against, never bound here

_TOKEN_QUERY_RE = re.compile(r"(token=)[^&\s\"']+")


def is_exempt(path: str) -> bool:
    """True for paths served without a credential (see EXEMPT_PATHS)."""
    return path in EXEMPT_PATHS or path.startswith(EXEMPT_PREFIXES)


def default_origins(host: str, port: int) -> set[str]:
    """Origins the server always allows, derived from its own bind address.

    Computed from the live port rather than hardcoded, so ``--port 9000`` does
    not silently reject every request.
    """
    origins = {f"http://{host}:{port}"}
    if host in LOOPBACK_HOSTS or host in WILDCARD_BIND_HOSTS:
        origins |= {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    origins |= set(VITE_DEV_ORIGINS)
    return origins


def derive_cookie_value(token: str) -> str:
    """One-way value the browser cookie carries instead of the raw token."""
    return hmac.new(token.encode("utf-8"), COOKIE_HMAC_LABEL, hashlib.sha256).hexdigest()


def resolve_token(project_root: Path) -> str:
    """Resolve the GUI auth token: env var, then ``data/.gui_token``, then mint one.

    ``project_root`` is required — defaulting it to the real project root would
    mean every incidental call (a test, a bare ``create_app``) writes a token
    file into the working tree.
    """
    env_token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if env_token:
        return env_token

    path = project_root / "data" / TOKEN_FILE
    try:
        existing = path.read_text(encoding="utf-8").strip()
    except OSError:
        existing = ""
    if existing:
        return existing

    token = secrets.token_urlsafe(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # os.open with mode 0600 rather than write_text + chmod: the latter
        # leaves the secret world-readable between the two calls. fchmod covers
        # the case where the file already existed (O_CREAT ignores mode then).
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(token + "\n")
    except OSError:
        logger.warning(  # pragma: no mutate
            "could not persist the GUI auth token to %s — using an "  # pragma: no mutate
            "ephemeral one; it will change on every restart",  # pragma: no mutate
            path,
        )
    return token


def bootstrap_url(host: str, port: int, token: str) -> str:
    """One-shot sign-in URL that sets the cookie and redirects to ``/``."""
    browser_host = "127.0.0.1" if host in WILDCARD_BIND_HOSTS else host
    return f"http://{browser_host}:{port}/auth?token={token}"


def redact_token(message: str) -> str:
    """Replace ``token=<value>`` with ``token=REDACTED``."""
    return _TOKEN_QUERY_RE.sub(r"\1REDACTED", message)


class TokenRedactingFilter(logging.Filter):
    """Keep the bootstrap token out of uvicorn's access log.

    The access log records the full request line including the query string, so
    without this every ``GET /auth?token=…`` writes the credential to stdout —
    and into a file whenever the operator redirects output. That is the same
    leak this design rejects URL-param tokens for.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_token(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_token(a) if isinstance(a, str) else a for a in record.args)
        return True


def install_access_log_redaction() -> TokenRedactingFilter:
    """Attach the redacting filter to uvicorn's access logger."""
    log_filter = TokenRedactingFilter()
    logging.getLogger("uvicorn.access").addFilter(log_filter)
    return log_filter


def bearer_from_header(value: str | None) -> str | None:
    """Extract the credential from an ``Authorization: Bearer <token>`` header."""
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def _credential_matches(presented: str | None, expected: str) -> bool:
    if not presented:
        return False
    # Compare bytes, not str: secrets.compare_digest rejects non-ASCII str
    # operands with TypeError, and the presented value is attacker-controlled.
    return secrets.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


@dataclass(frozen=True)
class GuiAuth:
    """Immutable auth policy for one server process."""

    token: str
    cookie_value: str
    allowed_origins: frozenset[str]

    @classmethod
    def create(
        cls,
        host: str,
        port: int,
        *,
        project_root: Path,
        extra_origins: Iterable[str] = (),
    ) -> GuiAuth:
        token = resolve_token(project_root)
        if host in WILDCARD_BIND_HOSTS:
            logger.warning(  # pragma: no mutate
                "binding to %s: browsers reach this server under some other hostname, "  # pragma: no mutate
                "which the origin allowlist will reject. Add that origin to "  # pragma: no mutate
                "gui.allowed_origins in config/local.yaml.",  # pragma: no mutate
                host,
            )
        return cls(
            token=token,
            cookie_value=derive_cookie_value(token),
            allowed_origins=frozenset(default_origins(host, port) | set(extra_origins)),
        )

    def check_origin(self, origin: str | None) -> bool:
        """Exact match against the allowlist; a missing Origin header is allowed.

        Browsers always send Origin on WebSocket handshakes and on cross-origin
        requests, so only non-browser clients (curl, tests) omit it — and they
        have no ambient cookie jar to be CSRF'd through. The token is still
        required either way, so this is a CSRF-check skip, not an auth bypass.

        This is safe only while no GET route changes state; a side-effecting GET
        would become live CSRF, since a cross-site top-level navigation sends no
        Origin but does carry a SameSite=Lax cookie. A test in
        test_auth_middleware.py pins that invariant.
        """
        if origin is None:
            return True
        return origin in self.allowed_origins

    def check_credentials(self, *, cookie: str | None, bearer: str | None) -> bool:
        """True if *either* presented credential validates.

        Try-all rather than first-match: any page on any other loopback port can
        set a same-name cookie at a different path (browsers only block
        overwriting HttpOnly at the *same* path), so both would be sent and one
        would silently win. First-match would turn that into a trivial lockout.
        """
        matched = _credential_matches(cookie, self.cookie_value)
        # Deliberately not `or` — evaluate both, no short-circuit.
        matched |= _credential_matches(bearer, self.token)
        return matched


def connection_is_authenticated(auth: GuiAuth, conn: HTTPConnection) -> bool:
    """True if this connection presents a valid cookie or Bearer token.

    Shared by the middleware and the exempt ``/`` route, so the bundle and the
    gated API can never disagree about who is signed in.
    """
    return auth.check_credentials(
        cookie=conn.cookies.get(COOKIE_NAME),
        bearer=bearer_from_header(conn.headers.get("authorization")),
    )


class GuiAuthMiddleware:
    """Gate every HTTP request and WebSocket handshake on origin + credentials.

    Raw ASGI rather than BaseHTTPMiddleware (which hard-passes non-HTTP scopes
    and so structurally cannot see a WebSocket) and rather than a per-route
    dependency (which must be repeated on every route, would never cover /docs,
    and is the auth-deferral shape this milestone exists to remove).

    Must be added *before* CORSMiddleware so CORS ends up outermost —
    add_middleware inserts at index 0 and the stack is built reversed, so the
    last one added is the outer one. CORS answers preflight itself and never
    reaches this middleware, which is why there is no OPTIONS bypass here.
    """

    def __init__(self, app: ASGIApp, *, auth: GuiAuth) -> None:
        self.app = app
        self.auth = auth

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Exemptions apply to HTTP only — a WebSocket is never a bootstrap path.
        if scope["type"] == "http" and is_exempt(scope["path"]):
            await self.app(scope, receive, send)
            return

        conn = HTTPConnection(scope)
        origin = conn.headers.get("origin")
        if not self.auth.check_origin(origin):
            await self._reject(scope, receive, send, "origin", origin)
            return

        if not connection_is_authenticated(self.auth, conn):
            await self._reject(scope, receive, send, "credentials", origin)
            return

        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send, reason: str, origin: str | None) -> None:
        logger.warning(  # pragma: no mutate
            "rejected %s %s: bad %s (origin=%r)",  # pragma: no mutate
            scope["type"],
            scope.get("path", ""),  # pragma: no mutate
            reason,
            origin,
        )
        if scope["type"] == "websocket":
            # Closing before accept makes uvicorn answer the handshake with an
            # HTTP 403; the upgrade never completes.
            await WebSocketClose(code=1008, reason="unauthorized")(scope, receive, send)
            return
        # 403, not 401: a 401 invites the browser's Basic-auth prompt, and there
        # is no interactive challenge to offer.
        await PlainTextResponse("forbidden", status_code=403)(scope, receive, send)
