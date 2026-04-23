"""Agent list + detail routes.

- GET    /api/agents                                 → grid cards
- GET    /api/agents/{id}                            → detail view
- GET    /api/agents/{id}/prompt                     → current system.md content
- PUT    /api/agents/{id}/prompt                     → write + snapshot
- GET    /api/agents/{id}/prompt/snapshots           → history listing
- GET    /api/agents/{id}/prompt/snapshots/{snap_id} → one snapshot
- POST   /api/agents/{id}/prompt/restore             → restore a snapshot
- GET    /api/agents/{id}/prompt/stats               → Stats tab payload
- GET    /api/agents/{id}/prompt/resolved            → placeholder-expanded prompt

JARVIS (the orchestrator) is excluded from registry discovery but still
appears here as the first list item and supports detail lookups by id.
JARVIS's system prompt is assembled dynamically from ``data/context/`` —
write endpoints return 403 for that agent, read endpoints return the
already-assembled prompt from the running session.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.gui.server.agents import cost_14d_rollup, recent_sessions_for_agent
from apps.gui.server.agents.prompt_history import (
    ensure_pre_first_save_snapshot,
    list_snapshots,
    read_snapshot,
    write_snapshot,
)
from apps.gui.server.agents.prompt_stats import compute_stats
from packages.agents.base import resolve_system_prompt
from packages.core.frontmatter import write_atomic

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

_MAX_PROMPT_BYTES = 1_000_000  # 1 MB guardrail — real prompts are 0.5-8 KB.


_JARVIS_LIST_ENTRY: dict[str, Any] = {
    "name": "JARVIS",
    "command": "",
    "description": "Orchestrator. Delegates to specialists.",
    "tools": ["web_tools", "things3_tools", "delegate"],
}


def _guard_agent_id(agent_id: str) -> None:
    """Defensively reject path-traversal attempts on the id segment."""
    if "/" in agent_id or ".." in agent_id:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")


def _history_root(session: Any) -> Path:
    """Resolve the prompt-history root from session config."""
    config = session.components.config
    jarvis_dir = Path(config["_paths"]["jarvis_dir"])
    subpath = str(config.get("paths", {}).get("prompt_history_dir", "data/prompt-history"))
    return jarvis_dir / subpath


def _meta_path(agent_id: str, session: Any) -> Path | None:
    meta = session.components.agent_registry.get(agent_id)
    return meta.meta_path if meta is not None else None


def _agent_dir(agent_id: str, session: Any) -> Path | None:
    """Agent directory derived from the registry's ``meta_path``.

    Returns ``None`` if the agent isn't registered — callers 404 on that.
    """
    mp = _meta_path(agent_id, session)
    return mp.parent if mp is not None else None


def _system_prompt_path(agent_id: str, session: Any) -> Path | None:
    d = _agent_dir(agent_id, session)
    return (d / "prompts" / "system.md") if d is not None else None


def _load_meta_dict(meta_path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except Exception:
        logger.debug("failed to re-parse meta.yaml at %s", meta_path, exc_info=True)
        return {}


async def _get_write_lock(app: Any, agent_id: str) -> asyncio.Lock:
    """Return the per-agent write lock, creating it on first use.

    Serialises read-snapshot-write sequences so concurrent PUTs can't
    interleave and lose a user's edit.
    """
    locks: dict[str, asyncio.Lock] = getattr(app.state, "prompt_write_locks", None) or {}
    if not locks:
        app.state.prompt_write_locks = locks
    lock = locks.get(agent_id)
    if lock is None:
        lock = asyncio.Lock()
        locks[agent_id] = lock
    return lock


# ---------------------------------------------------------------------------
# Request/response models


class PromptSaveRequest(BaseModel):
    content: str
    note: str | None = None


class PromptRestoreRequest(BaseModel):
    snapshot_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# List + detail


@router.get("/agents")
async def list_agents(request: Request) -> list[dict[str, Any]]:
    """Return all registered agents. JARVIS first, then data-driven agents alphabetical."""
    session = request.app.state.gui_session
    registry = session.components.agent_registry

    out: list[dict[str, Any]] = [dict(_JARVIS_LIST_ENTRY)]
    for name in sorted(registry):
        meta = registry[name]
        out.append(
            {
                "name": name,
                "command": meta.command or "",
                "description": meta.description or "",
                "tools": list(meta.tool_groups or []),
            }
        )
    return out


@router.get("/agents/{agent_id}")
async def get_agent_detail(agent_id: str, request: Request) -> dict[str, Any]:
    """Detail payload for one agent."""
    _guard_agent_id(agent_id)

    app = request.app
    idx = app.state.conversation_index
    session = app.state.gui_session
    registry = session.components.agent_registry

    # Keep cache fresh — matches home.py:82 pattern and survives mark_dirty calls.
    await idx.refresh()

    recent = recent_sessions_for_agent(idx, agent_id, limit=6)
    cost = cost_14d_rollup(idx, agent_id)
    last_used = recent[0]["date"] if recent else None

    if agent_id == "JARVIS":
        return {
            **_JARVIS_LIST_ENTRY,
            "temperature": None,
            "max_tokens": None,
            "max_iterations": None,
            "skills": [],
            # JARVIS builds its prompt dynamically from data/context/ via
            # packages/core/context_builder.py — no single canonical file.
            "prompt_path": None,
            "prompt_includes_count": 0,
            "model": None,
            "last_used": last_used,
            "recent_sessions": recent,
            "cost_14d": cost["days"],
            "cost_14d_total": cost["total"],
        }

    if agent_id not in registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    meta = registry[agent_id]
    meta_dict: dict[str, Any] = {}
    if meta.meta_path is not None:
        meta_dict = _load_meta_dict(meta.meta_path)

    return {
        "name": meta.name,
        "command": meta.command or "",
        "description": meta.description or "",
        "tools": list(meta.tool_groups or []),
        "temperature": meta_dict.get("temperature"),
        "max_tokens": meta_dict.get("max_tokens"),
        "max_iterations": meta_dict.get("max_iterations"),
        "skills": list(meta.skills or []),
        "prompt_path": f"packages/agents/{agent_id}/prompts/system.md",
        "prompt_includes_count": len(meta_dict.get("prompt_includes") or {}),
        "model": None,
        "last_used": last_used,
        "recent_sessions": recent,
        "cost_14d": cost["days"],
        "cost_14d_total": cost["total"],
    }


# ---------------------------------------------------------------------------
# Prompt editor — read / write


@router.get("/agents/{agent_id}/prompt")
async def get_prompt(agent_id: str, request: Request) -> dict[str, Any]:
    """Return the current system prompt content for ``agent_id``.

    JARVIS: returns ``editable: false`` and the live assembled prompt from
    the running session — no single file backs it.
    """
    _guard_agent_id(agent_id)
    session = request.app.state.gui_session

    if agent_id == "JARVIS":
        active = session.components.active_agent
        content = active.config.system_prompt if active is not None else ""
        return {
            "content": content,
            "path": None,
            "bytes": len(content.encode("utf-8")),
            "last_modified_iso": None,
            "editable": False,
            "explanation": "JARVIS's prompt is assembled at session start from data/context/. "
            "Edit source files there, not here.",
        }

    registry = session.components.agent_registry
    if agent_id not in registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    path = _system_prompt_path(agent_id, session)
    if path is None or not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"prompts/system.md not found for agent '{agent_id}'",
        )
    content = path.read_text(encoding="utf-8")
    stat = path.stat()

    return {
        "content": content,
        "path": f"packages/agents/{agent_id}/prompts/system.md",
        "bytes": stat.st_size,
        "last_modified_iso": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
        "editable": True,
        "explanation": None,
    }


@router.put("/agents/{agent_id}/prompt")
async def save_prompt(agent_id: str, payload: PromptSaveRequest, request: Request) -> dict[str, Any]:
    """Overwrite ``prompts/system.md`` with ``payload.content``; snapshot first."""
    _guard_agent_id(agent_id)
    if agent_id == "JARVIS":
        raise HTTPException(
            status_code=403,
            detail="JARVIS prompt is not editable. Edit source files in data/context/.",
        )

    content = payload.content
    if len(content.encode("utf-8")) > _MAX_PROMPT_BYTES:
        raise HTTPException(status_code=413, detail=f"prompt exceeds {_MAX_PROMPT_BYTES}-byte cap")

    session = request.app.state.gui_session
    registry = session.components.agent_registry
    if agent_id not in registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    path = _system_prompt_path(agent_id, session)
    if path is None or not path.parent.is_dir():
        raise HTTPException(status_code=500, detail=f"agent dir missing for '{agent_id}'")

    history_root = _history_root(session)
    lock = await _get_write_lock(request.app, agent_id)
    async with lock:
        prior = path.read_text(encoding="utf-8") if path.is_file() else ""
        ensure_pre_first_save_snapshot(history_root, agent_id, prior)
        snapshot_meta = write_snapshot(history_root, agent_id, prior, kind="save", note=payload.note)
        write_atomic(path, content)

    stat = path.stat()
    return {
        "bytes": stat.st_size,
        "last_modified_iso": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
        "snapshot_id": snapshot_meta.id,
    }


# ---------------------------------------------------------------------------
# Prompt editor — snapshots


@router.get("/agents/{agent_id}/prompt/snapshots")
async def get_snapshots(agent_id: str, request: Request) -> list[dict[str, Any]]:
    """List historical snapshots for ``agent_id``, newest-first.

    Empty list for JARVIS (no editable backing file).
    """
    _guard_agent_id(agent_id)
    if agent_id == "JARVIS":
        return []
    session = request.app.state.gui_session
    if agent_id not in session.components.agent_registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    history_root = _history_root(session)
    return [m.to_json() for m in list_snapshots(history_root, agent_id)]


@router.get("/agents/{agent_id}/prompt/snapshots/{snapshot_id}")
async def get_snapshot(agent_id: str, snapshot_id: str, request: Request) -> dict[str, Any]:
    """Return the full content of one snapshot."""
    _guard_agent_id(agent_id)
    if agent_id == "JARVIS":
        raise HTTPException(status_code=404, detail="no snapshots for JARVIS")
    session = request.app.state.gui_session
    if agent_id not in session.components.agent_registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    history_root = _history_root(session)
    content = read_snapshot(history_root, agent_id, snapshot_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f"snapshot '{snapshot_id}' not found")

    rows = list_snapshots(history_root, agent_id)
    match = next((r for r in rows if r.id == snapshot_id), None)
    return {
        "id": snapshot_id,
        "timestamp": match.timestamp if match else None,
        "bytes": match.bytes if match else len(content.encode("utf-8")),
        "kind": match.kind if match else "save",
        "note": match.note if match else None,
        "content": content,
    }


@router.post("/agents/{agent_id}/prompt/restore")
async def restore_snapshot(
    agent_id: str,
    payload: PromptRestoreRequest,
    request: Request,
) -> dict[str, Any]:
    """Copy ``payload.snapshot_id`` back over ``system.md``; snapshot the
    pre-restore state first so the action is reversible."""
    _guard_agent_id(agent_id)
    if agent_id == "JARVIS":
        raise HTTPException(status_code=403, detail="JARVIS prompt is not editable")

    session = request.app.state.gui_session
    if agent_id not in session.components.agent_registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    history_root = _history_root(session)
    path = _system_prompt_path(agent_id, session)
    if path is None:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")
    lock = await _get_write_lock(request.app, agent_id)

    async with lock:
        snapshot_content = read_snapshot(history_root, agent_id, payload.snapshot_id)
        if snapshot_content is None:
            raise HTTPException(status_code=404, detail=f"snapshot '{payload.snapshot_id}' not found")
        prior = path.read_text(encoding="utf-8") if path.is_file() else ""
        pre_restore = write_snapshot(
            history_root,
            agent_id,
            prior,
            kind="pre_restore",
            note=f"before restoring {payload.snapshot_id}",
        )
        write_atomic(path, snapshot_content)

    stat = path.stat()
    return {
        "bytes": stat.st_size,
        "last_modified_iso": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
        "snapshot_id": pre_restore.id,
    }


# ---------------------------------------------------------------------------
# Prompt editor — stats + resolved


@router.get("/agents/{agent_id}/prompt/stats")
async def get_prompt_stats(agent_id: str, request: Request) -> dict[str, Any]:
    """Stats-tab payload: char/line counts, token estimate, include statuses."""
    _guard_agent_id(agent_id)
    session = request.app.state.gui_session

    if agent_id == "JARVIS":
        active = session.components.active_agent
        text = active.config.system_prompt if active is not None else ""
        return {
            "char_count": len(text),
            "line_count": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
            "token_estimate": len(text.encode("utf-8")) // 4,
            "token_estimate_method": "len_utf8_over_4",
            "last_modified_iso": None,
            "snapshot_count": 0,
            "prompt_includes": [],
        }

    registry = session.components.agent_registry
    if agent_id not in registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    meta_path = _meta_path(agent_id, session)
    meta_dict = _load_meta_dict(meta_path) if meta_path is not None else {}
    history_root = _history_root(session)
    snapshot_count = len(list_snapshots(history_root, agent_id))

    system_path = _system_prompt_path(agent_id, session)
    agent_dir = _agent_dir(agent_id, session)
    assert system_path is not None and agent_dir is not None  # registry hit ⇒ both set

    stats = compute_stats(
        system_prompt_path=system_path,
        agent_dir=agent_dir,
        prompt_includes=meta_dict.get("prompt_includes") or {},
        snapshot_count=snapshot_count,
    )
    return stats.to_json()


@router.get("/agents/{agent_id}/prompt/resolved")
async def get_prompt_resolved(agent_id: str, request: Request) -> dict[str, Any]:
    """Return the placeholder-expanded prompt as the LLM will see it.

    JARVIS: returns the assembled prompt from the running session (no
    re-read — the session already has it materialised).
    """
    _guard_agent_id(agent_id)
    session = request.app.state.gui_session

    if agent_id == "JARVIS":
        active = session.components.active_agent
        text = active.config.system_prompt if active is not None else ""
        return {"resolved_content": text}

    registry = session.components.agent_registry
    if agent_id not in registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    meta_path = _meta_path(agent_id, session)
    meta_dict = _load_meta_dict(meta_path) if meta_path is not None else {}
    agent_dir = _agent_dir(agent_id, session)
    assert agent_dir is not None  # registry hit ⇒ set
    try:
        resolved = resolve_system_prompt(
            agent_dir,
            prompt_includes=meta_dict.get("prompt_includes") or {},
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"prompts/system.md not found for agent '{agent_id}'",
        ) from None
    return {"resolved_content": resolved}
