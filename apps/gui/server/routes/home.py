"""GET /api/home — composite endpoint for the Dashboard / Home view."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Request

from apps.gui.server.home.cost_week import cost_week_rollup
from apps.gui.server.home.task_links import link_tasks_to_conversations

# fetch_tasks is imported at module level so tests can patch this symbol.
# task_sync.py imports the macOS-only `things` module lazily inside the
# function body, so this import is safe on Linux CI.
from packages.integrations.things3.task_sync import fetch_tasks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

_QUICK_START = [
    {"label": "new chat", "cmd": None, "agent": "JARVIS"},
    {"label": "/daily-summary", "cmd": "/daily-summary", "agent": "JARVIS"},
    {"label": "/weekly-review", "cmd": "/navigator", "agent": "navigator"},
    {"label": "/research", "cmd": "/research", "agent": "researcher"},
    {"label": "/write", "cmd": "/write", "agent": "writer"},
]

_TASKS_CAP = 6
_RECENT_CAP = 4


def _greeting(now: datetime) -> str:
    h = now.hour
    if h < 12:
        return "Good morning"
    if h < 18:
        return "Good afternoon"
    return "Good evening"


def _day_label(d: date) -> str:
    # "Monday, April 20" — matches the prototype's en-long format.
    return d.strftime("%A, %B %-d") if hasattr(d, "strftime") else d.isoformat()


def _task_to_dict(task: Any, list_key: str) -> dict[str, Any]:
    """Convert a things3 Task dataclass to the wire shape. Priority from list key."""
    if list_key == "today":
        priority = "high"
    elif list_key == "inbox":
        priority = "low"
    else:
        priority = "medium"
    return {
        "title": task.title,
        "project": task.project or None,
        "when_date": task.when_date or None,
        "priority": priority,
        "list": list_key,
    }


def _flatten_tasks(by_list: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten today/upcoming/inbox lists into one ordered array, today first."""
    flat: list[dict[str, Any]] = []
    for key in ("today", "upcoming", "inbox"):
        for task in by_list.get(key, []) or []:
            flat.append(_task_to_dict(task, key))
            if len(flat) >= _TASKS_CAP:
                return flat
    return flat


@router.get("/home")
async def get_home(request: Request) -> dict[str, Any]:
    """Composite endpoint for the Dashboard / Home view."""
    app = request.app
    idx = app.state.conversation_index
    session = app.state.gui_session

    await idx.refresh()
    all_summaries, _ = idx.list(limit=500)  # sorted recent-first

    # -- tasks --------------------------------------------------------------
    tasks: list[dict[str, Any]] = []
    things3_settings = session.components.settings.things3
    if things3_settings.enabled:
        try:
            by_list = fetch_tasks(things3_settings, use_cache=True)
            tasks = _flatten_tasks(by_list)
        except Exception as e:
            logger.debug("home: things3 fetch failed, returning empty tasks: %s", e)
            tasks = []

    tasks = link_tasks_to_conversations(tasks, all_summaries[:20])

    # -- cost_week ----------------------------------------------------------
    week = cost_week_rollup(idx)

    # -- resume + recent ----------------------------------------------------
    resume = all_summaries[0] if all_summaries else None
    recent = all_summaries[1 : 1 + _RECENT_CAP] if resume else []

    # -- greeting + date ----------------------------------------------------
    now = datetime.now()
    today_dt = now.date()
    return {
        "greeting": _greeting(now),
        "today": {"date": today_dt.isoformat(), "day_label": _day_label(today_dt)},
        "tasks": tasks,
        "cost_week": week,
        "resume": resume,
        "recent": recent,
        "quick_start": _QUICK_START,
    }
