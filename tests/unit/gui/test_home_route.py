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


# ---------------------------------------------------------------------------
# Helper: _greeting (datetime -> str by hour bucket)


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (0, "Good morning"),
        (5, "Good morning"),
        (11, "Good morning"),
        (12, "Good afternoon"),
        (15, "Good afternoon"),
        (17, "Good afternoon"),
        (18, "Good evening"),
        (21, "Good evening"),
        (23, "Good evening"),
    ],
)
def test_greeting_hour_buckets(hour: int, expected: str) -> None:
    """Pin the exact boundary at h<12, h<18, else."""
    from datetime import datetime as dt

    from apps.gui.server.routes.home import _greeting

    assert _greeting(dt(2026, 4, 19, hour, 30, 0)) == expected


# ---------------------------------------------------------------------------
# Helper: _day_label (date -> "Monday, April 20")


def test_day_label_strftime_format() -> None:
    """Format must be %A, %B %-d — not isoformat."""
    from datetime import date as d

    from apps.gui.server.routes.home import _day_label

    # 2026-04-20 was a Monday.
    assert _day_label(d(2026, 4, 20)) == "Monday, April 20"


def test_day_label_falls_back_to_isoformat_when_no_strftime() -> None:
    """Fallback branch — exercise the `hasattr(d, 'strftime')` False arm."""

    from apps.gui.server.routes.home import _day_label

    class FakeDate:
        def isoformat(self) -> str:
            return "fake-iso"

    assert _day_label(FakeDate()) == "fake-iso"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Helper: _task_to_dict (Task, list_key) -> wire dict


@pytest.mark.parametrize(
    ("list_key", "expected_priority"),
    [
        ("today", "high"),
        ("upcoming", "medium"),
        ("inbox", "low"),
        ("anything_else", "medium"),  # else-branch falls through to medium
    ],
)
def test_task_to_dict_priority_mapping(list_key: str, expected_priority: str) -> None:
    from apps.gui.server.routes.home import _task_to_dict

    task = Task(title="Write tests", project="Mutmut", when_date="2026-04-19")
    out = _task_to_dict(task, list_key)
    assert out == {
        "title": "Write tests",
        "project": "Mutmut",
        "when_date": "2026-04-19",
        "priority": expected_priority,
        "list": list_key,
    }


def test_task_to_dict_null_coalesces_empty_project_and_date() -> None:
    """Empty/falsy project & when_date must become None (not ''), per `or None`."""
    from apps.gui.server.routes.home import _task_to_dict

    task = Task(title="bare", project="", when_date="")
    out = _task_to_dict(task, "today")
    assert out["project"] is None
    assert out["when_date"] is None
    assert out["title"] == "bare"
    assert out["priority"] == "high"


# ---------------------------------------------------------------------------
# Helper: _flatten_tasks (by_list dict -> ordered list, capped at 6)


def test_flatten_tasks_orders_today_upcoming_inbox() -> None:
    from apps.gui.server.routes.home import _flatten_tasks

    by_list = {
        "inbox": [Task(title="i1", project=None, when_date=None)],
        "upcoming": [Task(title="u1", project=None, when_date=None)],
        "today": [Task(title="t1", project=None, when_date=None)],
    }
    flat = _flatten_tasks(by_list)
    assert [t["title"] for t in flat] == ["t1", "u1", "i1"]
    assert [t["list"] for t in flat] == ["today", "upcoming", "inbox"]


def test_flatten_tasks_caps_at_six() -> None:
    """_TASKS_CAP = 6 — early-return must fire on the seventh task."""
    from apps.gui.server.routes.home import _flatten_tasks

    by_list = {
        "today": [Task(title=f"t{i}", project=None, when_date=None) for i in range(10)],
        "upcoming": [Task(title="u-extra", project=None, when_date=None)],
        "inbox": [],
    }
    flat = _flatten_tasks(by_list)
    assert len(flat) == 6
    assert [t["title"] for t in flat] == ["t0", "t1", "t2", "t3", "t4", "t5"]


def test_flatten_tasks_handles_missing_keys_and_none_values() -> None:
    """`.get(key, []) or []` must tolerate both missing keys and explicit None."""
    from apps.gui.server.routes.home import _flatten_tasks

    assert _flatten_tasks({}) == []
    assert _flatten_tasks({"today": None, "upcoming": None, "inbox": None}) == []


def test_flatten_tasks_cap_split_across_buckets() -> None:
    """Cap must trigger mid-bucket — 4 today + 3 upcoming = stop after 6."""
    from apps.gui.server.routes.home import _flatten_tasks

    by_list = {
        "today": [Task(title=f"t{i}", project=None, when_date=None) for i in range(4)],
        "upcoming": [Task(title=f"u{i}", project=None, when_date=None) for i in range(3)],
        "inbox": [Task(title="i-never", project=None, when_date=None)],
    }
    flat = _flatten_tasks(by_list)
    assert [t["title"] for t in flat] == ["t0", "t1", "t2", "t3", "u0", "u1"]
    assert all(t["title"] != "i-never" for t in flat)
