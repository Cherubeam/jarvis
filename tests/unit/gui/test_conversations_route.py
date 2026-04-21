"""Tests for /api/conversations* REST routes."""

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gui.server.history.index import ConversationIndex
from apps.gui.server.routes.conversations import router as conversations_router


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
            {"role": "user", "content": "hello"},
            {"role": "assistant", "agent": "JARVIS"},
        ],
        "metrics": {"total_tokens": tokens, "total_cost_usd": cost},
    }
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def client(tmp_path):
    convs = tmp_path / "conversations"
    _write(convs / "2026" / "2026-04-20_10-00-00.json", cost=0.10, tokens=1000)
    _write(
        convs / "2026" / "2026-04-19_09-00-00.json",
        cost=0.001,
        tokens=50,
        messages=[
            {"role": "user", "content": "draft"},
            {
                "role": "assistant",
                "agent": "writer",
                "tool_calls": [{"function": {"name": "read_note"}}],
            },
            {"role": "tool", "content": "Read 42 chars."},
        ],
    )

    index = ConversationIndex(convs)
    asyncio.run(index.refresh())

    app = FastAPI()
    app.state.conversation_index = index
    app.include_router(conversations_router)
    return TestClient(app)


def test_list_returns_items_and_total(client):
    r = client.get("/api/conversations")
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 2
    assert len(j["items"]) == 2
    # Default sort is recent: newer file first.
    assert j["items"][0]["id"] == "2026-04-20_10-00-00"


def test_list_validates_sort_and_date(client):
    r = client.get("/api/conversations?sort=bogus")
    assert r.status_code == 400
    r = client.get("/api/conversations?date=yesterday")
    assert r.status_code == 400


def test_list_filters_by_agent_tool_date(client):
    r = client.get("/api/conversations?agent=writer")
    assert r.status_code == 200
    assert [i["id"] for i in r.json()["items"]] == ["2026-04-19_09-00-00"]

    r = client.get("/api/conversations?tool=read_note")
    assert r.status_code == 200
    assert [i["id"] for i in r.json()["items"]] == ["2026-04-19_09-00-00"]

    r = client.get("/api/conversations?date=30d")
    assert r.status_code == 200  # just validates the preset is allowed


def test_list_sort_by_cost_desc(client):
    r = client.get("/api/conversations?sort=cost")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["cost"] > items[1]["cost"]


def test_facets_shape(client):
    r = client.get("/api/conversations/facets")
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 2
    assert {a["id"] for a in j["agents"]} == {"JARVIS", "writer"}
    assert [t["id"] for t in j["tools"]] == ["read_note"]


def test_detail_200_and_404(client):
    r = client.get("/api/conversations/2026-04-19_09-00-00")
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == "2026-04-19_09-00-00"
    assert j["title"] == "draft"
    assert len(j["messages"]) == 3
    assert j["preview"][0] == {"role": "user", "text": "draft"}

    r = client.get("/api/conversations/does-not-exist")
    assert r.status_code == 404


def test_empty_index_is_healthy(tmp_path):
    empty = tmp_path / "nope"
    index = ConversationIndex(empty)
    asyncio.run(index.refresh())
    app = FastAPI()
    app.state.conversation_index = index
    app.include_router(conversations_router)
    c = TestClient(app)

    r = c.get("/api/conversations")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "limit": 200, "offset": 0}

    r = c.get("/api/conversations/facets")
    assert r.status_code == 200
    assert r.json() == {"agents": [], "tools": [], "total": 0}
