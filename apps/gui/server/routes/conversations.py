"""REST endpoints for the Conversations browser.

- GET /api/conversations         — filtered + sorted + paginated summaries
- GET /api/conversations/facets  — unique agents + tools for filter chips
- GET /api/conversations/{id}    — full detail for one conversation
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/conversations")

_ALLOWED_SORT = {"recent", "cost", "messages"}
_ALLOWED_DATE = {"all", "today", "7d", "30d"}


async def _refresh(request: Request):
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
) -> dict:
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
async def list_facets(request: Request) -> dict:
    idx = await _refresh(request)
    return idx.facets()


@router.get("/{conv_id}")
async def get_conversation(request: Request, conv_id: str) -> dict:
    idx = request.app.state.conversation_index
    detail = idx.get(conv_id)
    if detail is None:
        raise HTTPException(404, f"conversation not found: {conv_id}")
    return detail.to_dict()
