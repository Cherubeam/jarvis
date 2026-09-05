"""FastAPI app factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from apps.gui.server.auth import GuiAuth, GuiAuthMiddleware, connection_is_authenticated
from apps.gui.server.history import ConversationIndex
from apps.gui.server.routes.agent_includes import router as agent_includes_router
from apps.gui.server.routes.agents import router as agents_router
from apps.gui.server.routes.api import router as api_router
from apps.gui.server.routes.auth import router as auth_router
from apps.gui.server.routes.auth import sign_in_page
from apps.gui.server.routes.chat_ws import router as ws_router
from apps.gui.server.routes.conversations import router as conversations_router
from apps.gui.server.routes.home import router as home_router
from apps.gui.server.routes.outcomes import router as outcomes_router
from apps.gui.server.routes.settings import router as settings_router
from apps.gui.server.state import build_gui_session

logger = logging.getLogger(__name__)

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """One-time startup: build the GUI session (config, agents, tools, MCP) +
    the conversations index."""
    logger.info("Building GUI session…")
    app.state.gui_session = build_gui_session()
    logger.info("GUI session ready.")

    # Conversations index — scan data/conversations/ once up front.
    index = ConversationIndex(app.state.gui_session.components.conversations_dir)
    await index.refresh()
    app.state.conversation_index = index
    # Let the bridge reach the index to invalidate the active file_id per turn.
    app.state.gui_session.conversation_index = index
    logger.info("Conversation index built (%d entries).", len(index._cache))

    try:
        yield
    finally:
        # Shut down MCP subprocesses and persist any in-flight conversation.
        gs = app.state.gui_session
        if gs.components.mcp_manager is not None:
            try:
                gs.components.mcp_manager.shutdown()
            except Exception:
                logger.exception("mcp shutdown failed")
        try:
            gs.components.logger.save()
        except Exception:
            logger.exception("logger.save() on shutdown failed")


def create_app(auth: GuiAuth) -> FastAPI:
    """Build the GUI app.

    ``auth`` is required, not optional: a fail-open default would either ship an
    unauthenticated server or mint a token file as a side effect of constructing
    the app. Callers pass an explicit policy (see apps/gui/main.py).
    """
    app = FastAPI(title="JARVIS GUI", lifespan=lifespan)
    # Set before lifespan: the launcher needs the token to print the sign-in URL,
    # and the middleware needs the policy before the first request.
    app.state.gui_auth = auth

    # ORDER MATTERS, and it reads backwards: add_middleware inserts at index 0
    # and the stack is built reversed, so the LAST one added is the OUTERMOST.
    # CORS must end up outside auth — it answers preflight itself, and an
    # OPTIONS gated by auth (preflight carries no cookie, by spec) would break
    # every cross-origin call from the vite dev server.
    app.add_middleware(GuiAuthMiddleware, auth=auth)
    # CORS so vite dev server (:5173) can hit /api and /ws on :8123. Derived
    # from the same allowlist as the auth check so the two cannot drift.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(auth.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(api_router)
    app.include_router(agents_router)
    app.include_router(agent_includes_router)
    app.include_router(conversations_router)
    app.include_router(home_router)
    app.include_router(outcomes_router)
    app.include_router(settings_router)
    app.include_router(ws_router)

    if WEB_DIST.is_dir():
        # Vite emits <script src="/assets/index-<hash>.js"> with base="/", so the
        # bundle must be served from /assets directly. Hashed filenames cache
        # forever; only index.html is no-cache.
        assets_dir = WEB_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/")
        async def root(request: Request) -> Response:
            # "/" is exempt from the middleware so there is a page to sign in
            # from; it gates itself instead of serving the app shell to a
            # stranger. The shell holds no data either way — every call it makes
            # is gated — but a blank app whose fetches all 403 is a dead end.
            if not connection_is_authenticated(request.app.state.gui_auth, request):
                return sign_in_page()
            index_html = WEB_DIST / "index.html"
            if index_html.is_file():
                return FileResponse(
                    index_html,
                    headers={"Cache-Control": "no-cache, must-revalidate"},
                )
            return Response("GUI bundle not found. Run: cd apps/gui/web && npm run build", status_code=503)
    else:

        @app.get("/")
        async def root_no_bundle(request: Request) -> Response:
            if not connection_is_authenticated(request.app.state.gui_auth, request):
                return sign_in_page()
            return Response(
                "GUI bundle not found at apps/gui/web/dist/. Run: cd apps/gui/web && npm install && npm run build",
                status_code=503,
                media_type="text/plain",
            )

    return app
