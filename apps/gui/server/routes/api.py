"""REST endpoints for the GUI: agents list, session metadata."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api")


@router.get("/agents")
async def list_agents(request: Request) -> list[dict]:
    """Return the registered agents (drives palette + agents view).

    Includes JARVIS first as the orchestrator, then the data-driven agents
    sorted alphabetically by name.
    """
    session = request.app.state.gui_session
    registry = session.components.agent_registry

    out = [
        {
            "name": "JARVIS",
            "command": "",
            "description": "Orchestrator. Delegates to specialists.",
            "tools": ["web_tools", "things3_tools", "delegate"],
        }
    ]
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


@router.get("/session")
async def get_session(request: Request) -> dict:
    """Current session metadata (model, conversation path, vault, started_at)."""
    return request.app.state.gui_session.session_meta()
