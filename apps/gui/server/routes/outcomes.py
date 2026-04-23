"""Outcomes review routes.

- ``GET /api/outcomes/pending`` — items due for review (empty list when the
  feature is disabled; keeps the UI rendering a "No items due" state).
- ``POST /api/outcomes/{file_id}/review`` — apply an outcome review
  (403 when the feature is disabled).

Heavy lifting lives in ``apps.cli.review`` — these routes just translate
between HTTP and the pure helpers.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from apps.cli.review import (
    VALID_OUTCOMES,
    PendingItem,
    apply_review,
    load_pending_due,
    pending_item_to_wire,
)
from packages.core import frontmatter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class ReviewRequest(BaseModel):
    outcome: str = Field(..., description="One of: happened, didnt, partial")
    quality: int = Field(..., ge=1, le=5)
    note: str = ""


def _guard_file_id(file_id: str) -> None:
    """Reject anything that isn't a plain filename stem."""
    if not file_id or "/" in file_id or ".." in file_id or "\\" in file_id or file_id.startswith("."):
        raise HTTPException(status_code=404, detail=f"outcome '{file_id}' not found")


def _outcomes_dir(session: Any) -> Path:
    config = session.components.config
    jarvis_dir = Path(config["_paths"]["jarvis_dir"])
    subpath = str(config.get("outcomes", {}).get("dir", "data/outcomes"))
    return jarvis_dir / subpath


def _outcomes_enabled(session: Any) -> bool:
    return bool(session.components.config.get("outcomes", {}).get("enabled", True))


@router.get("/outcomes/pending")
async def list_pending(
    request: Request,
    today: str | None = Query(None, description="Optional ISO date override"),
) -> list[dict[str, Any]]:
    """Return pending outcomes whose revisit_at is today or earlier.

    Returns ``[]`` when outcomes are disabled so the UI can render a
    consistent empty state without a 503.
    """
    session = request.app.state.gui_session
    if not _outcomes_enabled(session):
        return []

    if today is not None:
        try:
            today_date = date.fromisoformat(today)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"invalid date '{today}'") from e
    else:
        today_date = date.today()

    items = load_pending_due(_outcomes_dir(session), today_date)
    return [pending_item_to_wire(i) for i in items]


@router.post("/outcomes/{file_id}/review")
async def review_outcome(
    file_id: str,
    payload: ReviewRequest,
    request: Request,
) -> dict[str, Any]:
    """Apply an outcome review to ``file_id`` and mark the file ``reviewed``."""
    _guard_file_id(file_id)

    session = request.app.state.gui_session
    if not _outcomes_enabled(session):
        raise HTTPException(
            status_code=403,
            detail="Outcome tracking is disabled. Set outcomes.enabled: true in config.",
        )

    if payload.outcome not in VALID_OUTCOMES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid outcome '{payload.outcome}'. Must be one of {list(VALID_OUTCOMES)}.",
        )

    path = _outcomes_dir(session) / f"{file_id}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"outcome '{file_id}' not found")

    try:
        text = path.read_text(encoding="utf-8")
        meta, body = frontmatter.parse(text)
    except Exception as e:
        logger.warning("failed to parse %s: %s", path, e)
        raise HTTPException(status_code=500, detail=f"failed to read outcome '{file_id}'") from e

    if meta.get("status") != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"outcome '{file_id}' is not pending (status={meta.get('status')!r})",
        )

    item = PendingItem(path=path, meta=meta, body=body)
    now = datetime.now()
    apply_review(item, outcome=payload.outcome, quality=payload.quality, note=payload.note, now=now)

    return {
        "file_id": file_id,
        "reviewed_at": now.replace(microsecond=0).isoformat(),
        "outcome": payload.outcome,
        "quality": payload.quality,
    }
