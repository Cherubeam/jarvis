"""Agent list + detail routes.

- GET /api/agents           → grid cards (name, command, description, tools)
- GET /api/agents/{id}      → detail view (meta.yaml re-parse, recent sessions,
                              14-day cost rollup)

JARVIS (the orchestrator) is excluded from registry discovery but still
appears here as the first list item and supports detail lookups by id.
"""

from __future__ import annotations

import logging
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request

from apps.gui.server.agents import cost_14d_rollup, recent_sessions_for_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


_JARVIS_LIST_ENTRY: dict[str, Any] = {
    "name": "JARVIS",
    "command": "",
    "description": "Orchestrator. Delegates to specialists.",
    "tools": ["web_tools", "things3_tools", "delegate"],
}


@router.get("/agents")
async def list_agents(request: Request) -> list[dict[str, Any]]:
    """Return all registered agents. JARVIS first, then data-driven agents alphabetical."""
    session = request.app.state.gui_session
    registry = session.components.agent_registry

    out: list[dict[str, Any]] = [dict(_JARVIS_LIST_ENTRY)]
    for name in sorted(registry):
        meta = registry[name]
        out.append({
            "name": name,
            "command": meta.command or "",
            "description": meta.description or "",
            "tools": list(meta.tool_groups or []),
        })
    return out


@router.get("/agents/{agent_id}")
async def get_agent_detail(agent_id: str, request: Request) -> dict[str, Any]:
    """Detail payload for one agent.

    404 for unknown ids. Defensively 404s on ``/`` or ``..`` in the id — no
    known agent has those, but the id is reflected into a relative ``prompt_path``.
    """
    if "/" in agent_id or ".." in agent_id:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

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
            # JARVIS builds its prompt dynamically from ~/.jarvis/context/ via
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
        try:
            meta_dict = yaml.safe_load(meta.meta_path.read_text(encoding="utf-8")) or {}
        except Exception:
            logger.debug("failed to re-parse meta.yaml for %s", agent_id, exc_info=True)

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
