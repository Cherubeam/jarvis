"""Tests for GET /api/home. Scaffold mirrors tests/unit/gui/test_conversations_route.py."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gui.server.history.index import ConversationIndex
from apps.gui.server.routes.home import router as home_router
from packages.core.settings import Things3Settings
from packages.integrations.things3.task_sync import Task


def _write(path, messages=None, cost=0.01, tokens=100):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": "1.0.0",
        "id": "conv_x",
        "session_start": "2026-04-19T10:00:00",
        "session_end": "2026-04-19T10:00:10",
        "model": {"id": "openrouter/qwen", "provider": "openrouter"},
        "messages": messages
        or [
            {"role": "user", "content": "week-12 substack draft"},
            {"role": "assistant", "agent": "JARVIS"},
        ],
        "metrics": {"total_tokens": tokens, "total_cost_usd": cost},
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def _fake_session(things3_enabled=True):
    """Stand-in for GuiSession — the route reads session.components.settings.things3."""
    settings = SimpleNamespace(
        things3=Things3Settings(
            enabled=things3_enabled,
            cache_ttl_seconds=300,
            lists_to_include=["Today", "Upcoming"],
        )
    )
    components = SimpleNamespace(config={}, settings=settings)
    return SimpleNamespace(components=components)


@pytest.fixture
def client_with_tasks(tmp_path):
    convs = tmp_path / "conversations"
    _write(convs / "2026" / "2026-04-19_09-00-00.json", cost=0.005, tokens=400)

    index = ConversationIndex(convs)
    asyncio.run(index.refresh())

    app = FastAPI()
    app.state.conversation_index = index
    app.state.gui_session = _fake_session(things3_enabled=True)
    app.include_router(home_router)

    def _fake_fetch_tasks(cfg, use_cache=True):
        return {
            "today": [Task(title="Week-12 Substack draft", project="Blog")],
            "upcoming": [Task(title="Weekly review with Navigator", project="Operations")],
            "inbox": [],
        }

    with patch("apps.gui.server.routes.home.fetch_tasks", _fake_fetch_tasks):
        yield TestClient(app)


def test_shape_and_status(client_with_tasks):
    r = client_with_tasks.get("/api/home")
    assert r.status_code == 200
    j = r.json()
    assert set(j.keys()) == {
        "greeting",
        "today",
        "tasks",
        "cost_week",
        "resume",
        "recent",
        "quick_start",
    }
    assert j["greeting"] in ("Good morning", "Good afternoon", "Good evening")
    assert len(j["today"]["date"]) == 10  # YYYY-MM-DD
    assert len(j["cost_week"]["days"]) == 7
    assert len(j["quick_start"]) == 5


def test_task_priority_from_list_key(client_with_tasks):
    j = client_with_tasks.get("/api/home").json()
    tasks = j["tasks"]
    assert len(tasks) == 2
    # First task came from "today" → high.
    assert tasks[0]["priority"] == "high"
    assert tasks[0]["list"] == "today"
    # Second came from "upcoming" → medium.
    assert tasks[1]["priority"] == "medium"
    assert tasks[1]["list"] == "upcoming"


def test_task_linking_uses_recent_summaries(client_with_tasks):
    j = client_with_tasks.get("/api/home").json()
    tasks = j["tasks"]
    # "Week-12 Substack draft" should substring-match "week-12 substack draft"
    # in the single conversation we wrote.
    linked = tasks[0]["linked_conversation_ids"]
    assert linked == ["2026-04-19_09-00-00"]


def test_resume_is_most_recent_summary(client_with_tasks):
    j = client_with_tasks.get("/api/home").json()
    assert j["resume"] is not None
    assert j["resume"]["id"] == "2026-04-19_09-00-00"
    assert j["recent"] == []  # only one conversation


def test_things3_disabled_returns_empty_tasks(tmp_path):
    convs = tmp_path / "conversations"
    index = ConversationIndex(convs)
    asyncio.run(index.refresh())

    app = FastAPI()
    app.state.conversation_index = index
    app.state.gui_session = _fake_session(things3_enabled=False)
    app.include_router(home_router)

    r = TestClient(app).get("/api/home")
    assert r.status_code == 200
    j = r.json()
    assert j["tasks"] == []


def test_empty_index_returns_null_resume_and_seven_zero_days(tmp_path):
    convs = tmp_path / "conversations"
    index = ConversationIndex(convs)
    asyncio.run(index.refresh())

    app = FastAPI()
    app.state.conversation_index = index
    app.state.gui_session = _fake_session(things3_enabled=False)
    app.include_router(home_router)

    r = TestClient(app).get("/api/home")
    assert r.status_code == 200
    j = r.json()
    assert j["resume"] is None
    assert j["recent"] == []
    assert j["cost_week"]["total"] == 0.0
    assert all(d["cost"] == 0.0 for d in j["cost_week"]["days"])
