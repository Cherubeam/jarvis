"""Tests for apps.gui.server.history.index.ConversationIndex."""

import asyncio
import json
from pathlib import Path

import pytest

from apps.gui.server.history.index import ConversationIndex


def _write_conversation(
    base: Path,
    file_id: str,
    *,
    year: str = "2026",
    messages: list[dict] | None = None,
    model_id: str = "openrouter/qwen/qwen3.5-flash-02-23",
    total_tokens: int = 150,
    total_cost_usd: float = 0.0042,
    session_start: str = "2026-04-19T10:00:00",
    session_end: str = "2026-04-19T10:00:42",
) -> Path:
    year_dir = base / year
    year_dir.mkdir(parents=True, exist_ok=True)
    path = year_dir / f"{file_id}.json"
    data = {
        "schema_version": "1.0.0",
        "id": f"conv_{file_id.replace('-', '')}",
        "session_start": session_start,
        "session_end": session_end,
        "model": {"id": model_id, "provider": "openrouter", "parameters": {}},
        "agent": {"name": "JARVIS"},
        "context": {"files_loaded": [], "metadata": {}},
        "environment": {"client": "cli"},
        "metrics": {
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost_usd,
            "total_prompt_tokens": 100,
            "total_completion_tokens": 50,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "total_ttft_ms": 0,
            "total_latency_ms": 0,
            "request_count": 1,
        },
        "messages": messages
        or [
            {"role": "user", "content": "Hello", "timestamp": session_start},
            {"role": "assistant", "agent": "JARVIS", "content": "hi", "timestamp": session_end},
        ],
        "feedback": [],
        "metadata": {},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def tmp_conversations(tmp_path):
    d = tmp_path / "conversations"
    d.mkdir()
    return d


def test_missing_directory_returns_empty(tmp_path):
    idx = ConversationIndex(tmp_path / "does" / "not" / "exist")
    asyncio.run(idx.refresh())
    items, total = idx.list()
    assert items == []
    assert total == 0
    facets = idx.facets()
    assert facets == {"agents": [], "tools": [], "total": 0}


def test_basic_list_facets_and_get(tmp_conversations):
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    _write_conversation(
        tmp_conversations,
        "2026-04-18_09-00-00",
        messages=[
            {"role": "user", "content": "draft an opening"},
            {
                "role": "assistant",
                "agent": "writer",
                "tool_calls": [{"function": {"name": "read_note"}}],
            },
            {"role": "tool", "content": "Read 42 chars."},
            {"role": "assistant", "agent": "writer", "content": "draft…"},
        ],
    )
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, total = idx.list()
    assert total == 2
    # Sorted recent-first (by filename stem desc).
    assert [i["id"] for i in items] == ["2026-04-19_10-00-00", "2026-04-18_09-00-00"]
    assert items[0]["title"] == "Hello"
    assert items[1]["agents"] == ["writer"]
    assert items[1]["tools"] == ["read_note"]

    # Facets: agents + tools unique across files.
    facets = idx.facets()
    assert {a["id"] for a in facets["agents"]} == {"JARVIS", "writer"}
    assert [t["id"] for t in facets["tools"]] == ["read_note"]
    assert facets["total"] == 2

    # Detail — includes preview and full messages.
    detail = idx.get("2026-04-18_09-00-00")
    assert detail is not None
    detail_dict = detail.to_dict()
    assert detail_dict["id"] == "2026-04-18_09-00-00"
    assert len(detail_dict["messages"]) == 4
    assert detail_dict["preview"][0] == {"role": "user", "text": "draft an opening"}


def test_get_returns_none_for_missing_id(tmp_conversations):
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    assert idx.get("no-such-id") is None


def test_corrupt_json_is_skipped_silently(tmp_conversations):
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    bad = tmp_conversations / "2026" / "2026-04-19_11-00-00.json"
    bad.write_text("{not valid json", encoding="utf-8")

    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    items, total = idx.list()
    assert total == 1
    assert items[0]["id"] == "2026-04-19_10-00-00"


def test_incremental_refresh_reparses_only_changed(tmp_conversations):
    path = _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    before = idx._cache[str(path)]

    # Unchanged — second refresh keeps the same (mtime, summary) tuple identity.
    asyncio.run(idx.refresh())
    assert idx._cache[str(path)] is before

    # Now touch the file with a new mtime + new content.
    import os
    import time

    time.sleep(0.01)
    _write_conversation(
        tmp_conversations,
        "2026-04-19_10-00-00",
        messages=[{"role": "user", "content": "updated title"}],
    )
    os.utime(path, None)
    asyncio.run(idx.refresh())
    assert idx._cache[str(path)] is not before
    items, _ = idx.list()
    assert items[0]["title"] == "updated title"


def test_mark_dirty_forces_reparse(tmp_conversations):
    path = _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    before = idx._cache[str(path)]

    # Overwrite WITHOUT bumping mtime — simulates a quick-save race.
    original_mtime = path.stat().st_mtime
    _write_conversation(
        tmp_conversations,
        "2026-04-19_10-00-00",
        messages=[{"role": "user", "content": "forced new title"}],
    )
    # Pin mtime so the normal changed-check wouldn't trigger a reparse.
    import os

    os.utime(path, (original_mtime, original_mtime))

    idx.mark_dirty("2026-04-19_10-00-00")
    asyncio.run(idx.refresh())
    assert idx._cache[str(path)] is not before
    items, _ = idx.list()
    assert items[0]["title"] == "forced new title"


def test_list_filters_sort_and_paginate(tmp_conversations):
    _write_conversation(
        tmp_conversations,
        "2026-04-20_10-00-00",
        total_tokens=1000,
        total_cost_usd=0.10,
        messages=[
            {"role": "user", "content": "expensive session"},
            {"role": "assistant", "agent": "writer"},
        ],
    )
    _write_conversation(
        tmp_conversations,
        "2026-04-19_10-00-00",
        total_tokens=100,
        total_cost_usd=0.001,
        messages=[
            {"role": "user", "content": "cheap session"},
            {"role": "assistant", "agent": "JARVIS"},
        ],
    )
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    # Sort by cost desc: expensive first.
    items, _ = idx.list(sort="cost")
    assert items[0]["cost"] > items[1]["cost"]

    # Agent filter.
    items, _ = idx.list(agent="writer")
    assert [i["agents"] for i in items] == [["writer"]]

    # Pagination.
    items, total = idx.list(limit=1, offset=1)
    assert total == 2 and len(items) == 1


def test_legacy_file_without_agent_field_is_tolerated(tmp_conversations):
    path = tmp_conversations / "2026" / "2025-09-22_08-47-51.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy = {
        "schema_version": "1.0.0",
        "id": "conv_old",
        "session_start": "2025-09-22T08:47:51",
        "session_end": "2025-09-22T08:48:10",
        "model": {"id": "openai/gpt-4", "provider": "openai"},
        "messages": [
            {"role": "user", "content": "legacy q"},
            {"role": "assistant", "content": "legacy a"},  # NOTE: no `agent` field
        ],
        "metrics": {"total_tokens": 50, "total_cost_usd": 0.002},
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")

    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    items, _ = idx.list()
    assert items[0]["agents"] == []
    assert items[0]["title"] == "legacy q"


def test_delete_unlinks_file_and_evicts_cache(tmp_conversations):
    path = _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    _write_conversation(tmp_conversations, "2026-04-19_11-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    assert idx.facets()["total"] == 2

    deleted = idx.delete("2026-04-19_10-00-00")
    assert deleted is True
    assert not path.exists()
    assert str(path) not in idx._cache
    items, total = idx.list()
    assert total == 1
    assert items[0]["id"] == "2026-04-19_11-00-00"


def test_delete_returns_false_for_missing_id(tmp_conversations):
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    assert idx.delete("does-not-exist") is False
    # Existing entry untouched.
    assert idx.facets()["total"] == 1


def test_delete_clears_dirty_flag(tmp_conversations):
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    idx.mark_dirty("2026-04-19_10-00-00")
    assert "2026-04-19_10-00-00" in idx._dirty
    assert idx.delete("2026-04-19_10-00-00") is True
    assert "2026-04-19_10-00-00" not in idx._dirty
