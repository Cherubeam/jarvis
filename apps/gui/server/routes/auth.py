"""Sign-in: the one place a client exchanges the token for a session cookie.

``GET /auth?token=…`` is the convenience path the launcher auto-opens; it 303s
to ``/`` so the token leaves the address bar immediately, and uvicorn's access
log is scrubbed by ``TokenRedactingFilter``. ``POST /auth`` is the same exchange
with the token in a form body, used by the sign-in page so the credential never
touches a URL at all.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from apps.gui.server.auth import COOKIE_MAX_AGE, COOKIE_NAME, GuiAuth

logger = logging.getLogger(__name__)
router = APIRouter()

#: Where a successful sign-in lands. A constant, never a caller-supplied `next`
#: parameter — an open redirect on the route that issues the session cookie
#: would be a token-exfiltration primitive.
SIGN_IN_REDIRECT = "/"

_SIGN_IN_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JARVIS — sign in</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    font: 15px/1.5 ui-sans-serif, -apple-system, "Segoe UI", sans-serif;
    background: #fafaf9; color: #1c1917;
  }}
  main {{ width: min(28rem, 90vw); }}
  h1 {{ font-size: 1.15rem; margin: 0 0 .35rem; }}
  p {{ margin: 0 0 1.25rem; color: #57534e; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9em; }}
  form {{ display: flex; gap: .5rem; }}
  input {{
    flex: 1; padding: .55rem .7rem; border: 1px solid #d6d3d1; border-radius: .4rem;
    background: #fff; color: inherit; font: inherit;
  }}
  button {{
    padding: .55rem 1rem; border: 0; border-radius: .4rem; cursor: pointer;
    background: #1c1917; color: #fafaf9; font: inherit;
  }}
  .error {{ margin: 0 0 1rem; padding: .5rem .7rem; border-radius: .4rem;
            background: #fee2e2; color: #991b1b; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1c1917; color: #fafaf9; }}
    p {{ color: #a8a29e; }}
    input {{ background: #292524; border-color: #44403c; }}
    button {{ background: #fafaf9; color: #1c1917; }}
    .error {{ background: #450a0a; color: #fecaca; }}
  }}
</style>
</head>
<body>
<main>
  <h1>JARVIS</h1>
  <p>Paste the token printed by <code>jarvis-gui</code>, or find it in
     <code>data/.gui_token</code>.</p>
  {error}
  <form method="post" action="/auth">
    <input type="password" name="token" placeholder="Access token" autofocus
           autocomplete="off" spellcheck="false" aria-label="Access token">
    <button type="submit">Sign in</button>
  </form>
</main>
</body>
</html>
"""

_ERROR_BLOCK = '<p class="error">That token was not accepted.</p>'


def sign_in_page(*, failed: bool = False, status_code: int = 200) -> HTMLResponse:
    """The unauthenticated landing page.

    Server-rendered rather than part of the React bundle: an unauthenticated
    visitor would otherwise get a blank shell whose every fetch 403s, with no
    way to sign in short of finding the terminal.
    """
    return HTMLResponse(
        _SIGN_IN_PAGE.format(error=_ERROR_BLOCK if failed else ""),
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _grant(request: Request, presented: str) -> Response:
    """Validate the token and hand back a cookie-setting redirect, or reject."""
    auth: GuiAuth = request.app.state.gui_auth
    if not auth.check_credentials(cookie=None, bearer=presented):
        client = request.client.host if request.client else "?"  # pragma: no mutate
        logger.warning("rejected sign-in from %s", client)  # pragma: no mutate
        return sign_in_page(failed=True, status_code=403)

    # 303 rather than 302/307: it forces a GET on the target and discards any
    # method or body, so the token cannot be replayed onto the redirect.
    response = RedirectResponse(url=SIGN_IN_REDIRECT, status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=auth.cookie_value,  # never the raw token — see auth.py
        max_age=COOKIE_MAX_AGE,
        path="/",
        httponly=True,
        samesite="lax",
        # Unconditional Secure over plain http makes browsers drop the cookie
        # and the GUI auth-loops forever. Behind a TLS-terminating proxy this
        # reads the real transport scheme unless uvicorn is run with
        # --proxy-headers (AON-02).
        secure=request.url.scheme == "https",
    )
    return response


@router.get("/auth")
async def sign_in_via_query(request: Request, token: str = Query(default="")) -> Response:
    """Bootstrap from the URL the launcher prints and auto-opens.

    ``token`` defaults to empty rather than being required so a missing
    parameter yields the same rejection as a wrong one, instead of a 422 that
    distinguishes the two.
    """
    if not token:
        return sign_in_page()
    return _grant(request, token)


@router.post("/auth")
async def sign_in_via_form(request: Request) -> Response:
    """Bootstrap from the sign-in page — keeps the token out of the URL entirely."""
    form = await request.form()
    value = form.get("token")
    if not isinstance(value, str) or not value.strip():
        return sign_in_page(failed=True, status_code=403)
    return _grant(request, value.strip())


@router.get("/sign-out")
async def sign_out() -> Response:
    """Clear the session cookie on this browser.

    Does not rotate the token — to revoke every client, delete
    ``data/.gui_token`` and restart.
    """
    response = PlainTextResponse("signed out", status_code=200)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return response
