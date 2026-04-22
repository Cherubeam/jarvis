"""REST endpoints for the GUI: session metadata.

Agent list + detail endpoints moved to ``routes/agents.py`` in Phase 5.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api")


@router.get("/session")
async def get_session(request: Request) -> dict[str, Any]:
    """Current session metadata (model, conversation path, vault, started_at)."""
    meta: dict[str, Any] = request.app.state.gui_session.session_meta()
    return meta
