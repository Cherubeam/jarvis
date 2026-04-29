"""REST endpoints for the Conversations browser.

- GET    /api/conversations         — filtered + sorted + paginated summaries
- GET    /api/conversations/facets  — unique agents + tools for filter chips
- GET    /api/conversations/{id}    — full detail for one conversation
- DELETE /api/conversations/{id}    — hard-delete the JSON file + RAG record
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations")

_ALLOWED_SORT = {"recent", "cost", "messages"}
_ALLOWED_DATE = {"all", "today", "7d", "30d"}


async def _refresh(request: Request) -> Any:
    idx = request.app.state.conversation_index
    await idx.refresh()
    return idx


@router.get("")
async def list_conversations(
    request: Request,
    q: str | None = None,
    agent: str | None = None,
    tool: str | None = None,
    date: str = "all",
    sort: str = "recent",
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if sort not in _ALLOWED_SORT:
        raise HTTPException(400, f"sort must be one of {sorted(_ALLOWED_SORT)}")
    if date not in _ALLOWED_DATE:
        raise HTTPException(400, f"date must be one of {sorted(_ALLOWED_DATE)}")

    idx = await _refresh(request)
    items, total = idx.list(
        q=q,
        agent=agent,
        tool=tool,
        date=date,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/facets")
async def list_facets(request: Request) -> dict[str, Any]:
    idx = await _refresh(request)
    facets: dict[str, Any] = idx.facets()
    return facets


@router.get("/{conv_id}")
async def get_conversation(request: Request, conv_id: str) -> dict[str, Any]:
    idx = request.app.state.conversation_index
    detail = idx.get(conv_id)
    if detail is None:
        raise HTTPException(404, f"conversation not found: {conv_id}")
    result: dict[str, Any] = detail.to_dict()
    return result


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(request: Request, conv_id: str) -> Response:
    idx = request.app.state.conversation_index

    # Refuse to delete the conversation that the running session is actively
    # writing to — the logger would silently re-create the file on the next
    # save and the index would diverge.
    gs = getattr(request.app.state, "gui_session", None)
    if gs is not None:
        try:
            active_file_id = gs.session_meta()["file_id"]
        except Exception:  # session not yet initialised in tests
            active_file_id = None
        if active_file_id and conv_id == active_file_id:
            raise HTTPException(409, "cannot delete the currently active conversation")

    if not idx.delete(conv_id):
        raise HTTPException(404, f"conversation not found: {conv_id}")

    # Best-effort RAG cleanup — only when RAG is enabled and the DB is on disk.
    # Constructing the indexer here is cheap (chromadb opens the persistent
    # client) and avoids holding an indexer instance for the lifetime of the
    # GUI process.
    if gs is not None:
        try:
            settings = gs.components.settings
            if settings.rag.enabled:
                from packages.core.rag.indexer import ConversationIndexer

                db_path = gs.components.jarvis_dir / settings.rag.db_path
                if db_path.exists():
                    indexer = ConversationIndexer(
                        db_path,
                        settings.rag.embedding_model,
                        api_key=None,
                    )
                    indexer.delete_conversation(conv_id)
        except Exception:
            logger.exception("RAG cleanup failed for %s", conv_id)

    return Response(status_code=204)
