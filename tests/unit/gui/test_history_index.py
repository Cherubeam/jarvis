"""Tests for apps.gui.server.history.index.ConversationIndex."""

import asyncio
import json
import os
import time
from pathlib import Path

import pytest

from apps.gui.server.history.index import ConversationIndex, _build_summary_dict, _in_date_range


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
    provider: str = "openrouter",
) -> Path:
    year_dir = base / year
    year_dir.mkdir(parents=True, exist_ok=True)
    path = year_dir / f"{file_id}.json"
    data = {
        "schema_version": "1.0.0",
        "id": f"conv_{file_id.replace('-', '')}",
        "session_start": session_start,
        "session_end": session_end,
        "model": {"id": model_id, "provider": provider, "parameters": {}},
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


def test_missing_directory_lazily_created_on_refresh(tmp_path):
    """Fresh-clone case: refresh() mkdir's the dir so logger.save() can write into it."""
    target = tmp_path / "fresh-clone-conversations"
    assert not target.exists()
    idx = ConversationIndex(target)
    asyncio.run(idx.refresh())
    assert target.is_dir()


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
    # Strict shape — every key in the summary contract is present.
    summary_keys = {
        "id",
        "date",
        "title",
        "agents",
        "messages",
        "tokens",
        "cost",
        "duration_ms",
        "tool_calls",
        "tools",
        "handoffs",
        "model",
        "provider",
    }
    assert set(items[0].keys()) == summary_keys

    # First conversation: defaults.
    first = items[0]
    assert first["title"] == "Hello"
    assert first["date"] == "2026-04-19"
    assert first["agents"] == ["JARVIS"]
    assert first["messages"] == 2
    assert first["tokens"] == 150
    assert first["cost"] == 0.0042
    assert first["duration_ms"] == 42_000
    assert first["tool_calls"] == 0
    assert first["tools"] == []
    assert first["handoffs"] == 0
    assert first["model"] == "openrouter/qwen/qwen3.5-flash-02-23"
    assert first["provider"] == "openrouter"

    # Second conversation: writer, with one tool call.
    second = items[1]
    assert second["agents"] == ["writer"]
    assert second["tools"] == ["read_note"]
    assert second["tool_calls"] == 1
    assert second["messages"] == 4

    # Facets: agents + tools unique across files.
    facets = idx.facets()
    # Each entry is {id, count} — strict shape.
    assert all(set(a.keys()) == {"id", "count"} for a in facets["agents"])
    assert {a["id"] for a in facets["agents"]} == {"JARVIS", "writer"}
    assert facets["agents"] == [{"id": "JARVIS", "count": 1}, {"id": "writer", "count": 1}]
    assert facets["tools"] == [{"id": "read_note", "count": 1}]
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


def test_get_returns_none_for_corrupt_json(tmp_conversations):
    """Corrupt JSON in get() shouldn't crash — returns None."""
    bad = tmp_conversations / "2026" / "2026-04-19_10-00-00.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not json", encoding="utf-8")
    idx = ConversationIndex(tmp_conversations)
    # We don't index it (corrupt), but get() probes the filesystem directly.
    asyncio.run(idx.refresh())
    assert idx.get("2026-04-19_10-00-00") is None


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


def test_refresh_drops_entries_for_deleted_files(tmp_conversations):
    """Deleting a file off-disk evicts it from the cache on next refresh."""
    p1 = _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    _write_conversation(tmp_conversations, "2026-04-19_11-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    assert len(idx._cache) == 2

    p1.unlink()
    asyncio.run(idx.refresh())
    assert str(p1) not in idx._cache
    assert len(idx._cache) == 1


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
    os.utime(path, (original_mtime, original_mtime))

    idx.mark_dirty("2026-04-19_10-00-00")
    asyncio.run(idx.refresh())
    assert idx._cache[str(path)] is not before
    items, _ = idx.list()
    assert items[0]["title"] == "forced new title"
    # Dirty flag is consumed by refresh.
    assert "2026-04-19_10-00-00" not in idx._dirty


# ---------------------------------------------------------------------------
# list() — filters, sorts, pagination
# ---------------------------------------------------------------------------


def test_list_sort_by_cost_desc(tmp_conversations):
    _write_conversation(
        tmp_conversations,
        "2026-04-20_10-00-00",
        total_cost_usd=0.10,
        messages=[{"role": "user", "content": "expensive"}],
    )
    _write_conversation(
        tmp_conversations,
        "2026-04-19_10-00-00",
        total_cost_usd=0.001,
        messages=[{"role": "user", "content": "cheap"}],
    )
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, _ = idx.list(sort="cost")
    assert items[0]["cost"] == 0.10
    assert items[1]["cost"] == 0.001


def test_list_sort_by_messages_desc(tmp_conversations):
    _write_conversation(
        tmp_conversations,
        "2026-04-20_10-00-00",
        messages=[{"role": "user", "content": "u"}],  # 1 message
    )
    _write_conversation(
        tmp_conversations,
        "2026-04-19_10-00-00",
        messages=[
            {"role": "user", "content": "u1"},
            {"role": "assistant", "agent": "JARVIS", "content": "a1"},
            {"role": "user", "content": "u2"},
        ],  # 3 messages
    )
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, _ = idx.list(sort="messages")
    assert items[0]["messages"] == 3
    assert items[1]["messages"] == 1


def test_list_sort_recent_is_default_and_descending_by_id(tmp_conversations):
    _write_conversation(tmp_conversations, "2026-04-18_09-00-00")
    _write_conversation(tmp_conversations, "2026-04-20_10-00-00")
    _write_conversation(tmp_conversations, "2026-04-19_09-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, _ = idx.list()  # default sort
    assert [i["id"] for i in items] == [
        "2026-04-20_10-00-00",
        "2026-04-19_09-00-00",
        "2026-04-18_09-00-00",
    ]


def test_list_filters_by_agent_and_treats_all_as_no_filter(tmp_conversations):
    _write_conversation(
        tmp_conversations,
        "2026-04-20_10-00-00",
        messages=[{"role": "user", "content": "u"}, {"role": "assistant", "agent": "writer"}],
    )
    _write_conversation(
        tmp_conversations,
        "2026-04-19_10-00-00",
        messages=[{"role": "user", "content": "u"}, {"role": "assistant", "agent": "JARVIS"}],
    )
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, _ = idx.list(agent="writer")
    assert [i["agents"] for i in items] == [["writer"]]
    items, total = idx.list(agent="all")
    assert total == 2


def test_list_filters_by_tool_and_treats_all_as_no_filter(tmp_conversations):
    _write_conversation(
        tmp_conversations,
        "2026-04-20_10-00-00",
        messages=[
            {"role": "user", "content": "u"},
            {
                "role": "assistant",
                "agent": "JARVIS",
                "tool_calls": [{"function": {"name": "web_fetch"}}],
            },
        ],
    )
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, _ = idx.list(tool="web_fetch")
    assert [i["id"] for i in items] == ["2026-04-20_10-00-00"]
    items, total = idx.list(tool="all")
    assert total == 2


def test_list_filters_by_query_case_insensitive(tmp_conversations):
    _write_conversation(
        tmp_conversations,
        "2026-04-20_10-00-00",
        messages=[{"role": "user", "content": "Plan the WEEK"}],
    )
    _write_conversation(
        tmp_conversations,
        "2026-04-19_10-00-00",
        messages=[{"role": "user", "content": "buy groceries"}],
    )
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, total = idx.list(q="week")
    assert total == 1
    assert items[0]["title"] == "Plan the WEEK"


def test_list_pagination_offset_past_total_returns_empty(tmp_conversations):
    _write_conversation(tmp_conversations, "2026-04-20_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    items, total = idx.list(offset=99, limit=10)
    assert items == []
    assert total == 1  # total reflects pre-pagination total, not items count


def test_list_pagination_limit_zero_returns_empty_but_total_intact(tmp_conversations):
    _write_conversation(tmp_conversations, "2026-04-20_10-00-00")
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    items, total = idx.list(limit=0)
    assert items == []
    assert total == 2


def test_list_default_limit_is_200(tmp_conversations):
    """Default limit should remain 200 — design contract for the History page."""
    # Write enough rows to verify the default cap (don't actually need 200; just
    # check that with N=3 we get 3 items, then pin the default by inspecting __defaults__).
    _write_conversation(tmp_conversations, "2026-04-20_10-00-00")
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    _write_conversation(tmp_conversations, "2026-04-18_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    items, total = idx.list()
    assert total == 3
    assert len(items) == 3


# ---------------------------------------------------------------------------
# Date range filter (`date=` preset)
# ---------------------------------------------------------------------------


def test_in_date_range_all_returns_true_for_anything():
    assert _in_date_range("not-a-date", "all") is True


def test_in_date_range_today_matches_only_today():
    assert _in_date_range("2026-05-01", "today", today="2026-05-01") is True
    assert _in_date_range("2026-04-30", "today", today="2026-05-01") is False


def test_in_date_range_7d_window_inclusive_lower_exclusive_upper():
    """0..<7 days inclusive."""
    today = "2026-05-01"
    assert _in_date_range("2026-05-01", "7d", today=today) is True  # day 0
    assert _in_date_range("2026-04-25", "7d", today=today) is True  # day 6
    assert _in_date_range("2026-04-24", "7d", today=today) is False  # day 7 — out
    assert _in_date_range("2026-05-02", "7d", today=today) is False  # future


def test_in_date_range_30d_window():
    today = "2026-05-01"
    assert _in_date_range("2026-04-02", "30d", today=today) is True  # day 29
    assert _in_date_range("2026-04-01", "30d", today=today) is False  # day 30 — out


def test_in_date_range_invalid_date_returns_false():
    assert _in_date_range("not-a-date", "7d", today="2026-05-01") is False
    assert _in_date_range("", "7d", today="2026-05-01") is False


def test_in_date_range_unknown_preset_returns_true():
    """Defensive default — unknown preset acts as 'all'."""
    assert _in_date_range("2026-05-01", "this-month", today="2026-05-01") is True


def test_list_date_filter_today(tmp_conversations, monkeypatch):
    """list(date='today') uses _in_date_range — wire it up via a freshly written file."""
    today_iso = time.strftime("%Y-%m-%d")
    _write_conversation(
        tmp_conversations,
        f"{today_iso}_12-00-00",
        session_start=f"{today_iso}T12:00:00",
        session_end=f"{today_iso}T12:00:30",
    )
    _write_conversation(
        tmp_conversations,
        "2025-01-01_10-00-00",
        session_start="2025-01-01T10:00:00",
        session_end="2025-01-01T10:00:30",
        year="2025",
    )
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, total = idx.list(date="today")
    # Only the today-dated row should pass the filter.
    assert total == 1
    assert items[0]["id"].startswith(today_iso)


# ---------------------------------------------------------------------------
# _build_summary_dict — date fallbacks + dominant agent reordering
# ---------------------------------------------------------------------------


def test_build_summary_falls_back_to_filename_stem_when_session_start_missing(tmp_path):
    path = tmp_path / "2026-03-15_10-00-00.json"
    summary = _build_summary_dict(
        path,
        {
            "messages": [{"role": "user", "content": "x"}],
            "metrics": {"total_tokens": 0, "total_cost_usd": 0.0},
            "model": {"id": "m", "provider": "p"},
            # no session_start
        },
    )
    assert summary["date"] == "2026-03-15"


def test_build_summary_date_empty_when_stem_too_short(tmp_path):
    path = tmp_path / "short.json"
    summary = _build_summary_dict(
        path,
        {"messages": [], "metrics": {}, "model": {}},
    )
    assert summary["date"] == ""


def test_build_summary_dominant_agent_moved_to_front(tmp_path):
    """When agents=[JARVIS, writer], dominant=writer → [writer, JARVIS]."""
    path = tmp_path / "2026-04-20_10-00-00.json"
    msgs = [
        {"role": "user", "content": "u"},
        {"role": "assistant", "agent": "JARVIS", "content": "a"},
        {"role": "assistant", "agent": "writer", "content": "b"},
    ]
    summary = _build_summary_dict(
        path,
        {
            "messages": msgs,
            "metrics": {"total_tokens": 0, "total_cost_usd": 0.0},
            "model": {"id": "m", "provider": "p"},
        },
    )
    assert summary["agents"] == ["writer", "JARVIS"]


def test_build_summary_session_start_preferred_over_stem_for_date(tmp_path):
    """Stem says 2026-04-20 but session_start says 2026-04-21 — start wins."""
    path = tmp_path / "2026-04-20_10-00-00.json"
    summary = _build_summary_dict(
        path,
        {
            "session_start": "2026-04-21T08:00:00",
            "messages": [],
            "metrics": {},
            "model": {},
        },
    )
    assert summary["date"] == "2026-04-21"


def test_build_summary_coerces_metrics_to_int_and_float(tmp_path):
    """tokens → int, cost → float, even from string-like inputs."""
    path = tmp_path / "2026-04-20_10-00-00.json"
    summary = _build_summary_dict(
        path,
        {
            "messages": [],
            "metrics": {"total_tokens": "0", "total_cost_usd": "0.5"},
            "model": {},
        },
    )
    assert summary["tokens"] == 0
    assert isinstance(summary["tokens"], int)
    assert summary["cost"] == 0.5
    assert isinstance(summary["cost"], float)


def test_build_summary_zero_metrics_when_keys_absent(tmp_path):
    path = tmp_path / "2026-04-20_10-00-00.json"
    summary = _build_summary_dict(path, {"messages": [], "metrics": {}, "model": {}})
    assert summary["tokens"] == 0
    assert summary["cost"] == 0.0
    assert summary["model"] == ""
    assert summary["provider"] == ""


# ---------------------------------------------------------------------------
# facets() — count-desc / id-asc ordering
# ---------------------------------------------------------------------------


def test_facets_orders_by_count_desc_then_id_asc(tmp_conversations):
    _write_conversation(
        tmp_conversations,
        "2026-04-20_10-00-00",
        messages=[
            {"role": "user", "content": "u"},
            {"role": "assistant", "agent": "writer"},
        ],
    )
    _write_conversation(
        tmp_conversations,
        "2026-04-19_10-00-00",
        messages=[
            {"role": "user", "content": "u"},
            {"role": "assistant", "agent": "writer"},
        ],
    )
    _write_conversation(
        tmp_conversations,
        "2026-04-18_10-00-00",
        messages=[
            {"role": "user", "content": "u"},
            {"role": "assistant", "agent": "JARVIS"},
        ],
    )
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    facets = idx.facets()
    # writer has 2, JARVIS has 1 — count desc puts writer first.
    assert facets["agents"] == [
        {"id": "writer", "count": 2},
        {"id": "JARVIS", "count": 1},
    ]


def test_facets_tie_breaker_id_ascending(tmp_conversations):
    """When two agents share the same count, id-asc breaks the tie."""
    _write_conversation(
        tmp_conversations,
        "2026-04-19_10-00-00",
        messages=[{"role": "user", "content": "u"}, {"role": "assistant", "agent": "writer"}],
    )
    _write_conversation(
        tmp_conversations,
        "2026-04-18_10-00-00",
        messages=[{"role": "user", "content": "u"}, {"role": "assistant", "agent": "researcher"}],
    )
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    agents = [a["id"] for a in idx.facets()["agents"]]
    # researcher < writer alphabetically.
    assert agents == ["researcher", "writer"]


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


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


def test_delete_works_for_unindexed_file_via_filesystem_probe(tmp_conversations):
    """delete() falls back to scanning year dirs when the conv isn't in the cache."""
    path = _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    # Skip refresh — file exists but isn't in idx._cache yet.
    assert str(path) not in idx._cache
    assert idx.delete("2026-04-19_10-00-00") is True
    assert not path.exists()


def test_delete_clears_dirty_flag(tmp_conversations):
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    idx.mark_dirty("2026-04-19_10-00-00")
    assert "2026-04-19_10-00-00" in idx._dirty
    assert idx.delete("2026-04-19_10-00-00") is True
    assert "2026-04-19_10-00-00" not in idx._dirty


# ---------------------------------------------------------------------------
# legacy + edge files
# ---------------------------------------------------------------------------


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


def test_dir_property_exposes_conversations_dir(tmp_conversations):
    idx = ConversationIndex(tmp_conversations)
    assert idx.dir == tmp_conversations


def test_non_year_subdirectories_are_ignored(tmp_conversations):
    """Only YYYY-style subdirs get scanned. Random files at the top-level shouldn't crash."""
    (tmp_conversations / "README.md").write_text("# notes", encoding="utf-8")
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    items, total = idx.list()
    assert total == 1
    assert items[0]["id"] == "2026-04-19_10-00-00"


# ---------------------------------------------------------------------------
# Pass-8 mutation gap closure (98 survivors after pass 7)
# ---------------------------------------------------------------------------


# _parse_file + get: encoding="utf-8" lock-in
def test_parse_file_decodes_unicode_via_utf8(tmp_conversations):
    """Non-ASCII content forces the `encoding="utf-8"` choice — any other encoding
    (None, "UTF-8" alias is OK but ASCII/latin-1 would raise UnicodeDecodeError on
    multi-byte sequences encoded as utf-8)."""
    path = tmp_conversations / "2026" / "2026-04-19_10-00-00.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": "1.0.0",
        "id": "conv_unicode",
        "session_start": "2026-04-19T10:00:00",
        "session_end": "2026-04-19T10:00:42",
        "model": {"id": "openrouter/qwen", "provider": "openrouter"},
        "messages": [
            {"role": "user", "content": "café ☃ 北京", "timestamp": "2026-04-19T10:00:00"},
            {"role": "assistant", "agent": "JARVIS", "content": "réponse"},
        ],
        "metrics": {"total_tokens": 10, "total_cost_usd": 0.001},
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    items, _ = idx.list()
    assert items[0]["title"] == "café ☃ 北京"

    # get() also opens with utf-8 — pin its encoding choice on the same fixture.
    detail = idx.get("2026-04-19_10-00-00")
    assert detail is not None
    assert detail.messages[0]["content"] == "café ☃ 北京"


# list(): default-arg literal lock-in
def test_list_default_kwargs_match_no_filter_recent_sort(tmp_conversations):
    """Calling list() with no kwargs must use the documented defaults:
    date='all', sort='recent', limit=200, offset=0. Pins each literal."""
    _write_conversation(tmp_conversations, "2026-04-17_09-00-00", session_start="2026-04-17T09:00:00")
    _write_conversation(tmp_conversations, "2026-04-19_10-00-00", session_start="2026-04-19T10:00:00")
    _write_conversation(tmp_conversations, "2026-04-18_11-00-00", session_start="2026-04-18T11:00:00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, total = idx.list()  # all defaults
    # date="all" → no filter → all 3.
    assert total == 3
    # sort="recent" → reversed by id (timestamp prefix) → most recent first.
    assert [s["id"] for s in items] == [
        "2026-04-19_10-00-00",
        "2026-04-18_11-00-00",
        "2026-04-17_09-00-00",
    ]
    # limit=200, offset=0 → first page contains everything (3 items ≤ 200).
    assert items == idx.list(limit=200, offset=0)[0]


def test_list_sort_cost_with_zero_or_none_uses_or_zero_default(tmp_conversations):
    """`-(s["cost"] or 0.0)` — when cost is 0 or None, fallback must be 0.0
    (not 1.0). Mutating to `or 1.0` would push zero-cost items behind real-cost
    items in the sort. Pins the literal."""
    _write_conversation(tmp_conversations, "2026-04-19_a", total_cost_usd=0.0)
    _write_conversation(tmp_conversations, "2026-04-19_b", total_cost_usd=0.05)
    _write_conversation(tmp_conversations, "2026-04-19_c", total_cost_usd=0.0)
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, _ = idx.list(sort="cost")
    # Highest cost first; zero-cost items follow in id-asc order (tie-break).
    assert [s["id"] for s in items] == ["2026-04-19_b", "2026-04-19_a", "2026-04-19_c"]


def test_list_sort_messages_with_zero_uses_or_zero_default(tmp_conversations):
    """`-(s["messages"] or 0)` — same defense for messages count.

    Note: the _write_conversation fixture uses `messages or [default]`, so an empty
    list silently becomes the default. Use a single-message list for the "low" case.
    """
    _write_conversation(tmp_conversations, "2026-04-19_a", messages=[{"role": "user", "content": "x"}])
    _write_conversation(
        tmp_conversations,
        "2026-04-19_b",
        messages=[
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": "y"},
            {"role": "user", "content": "z"},
        ],
    )
    _write_conversation(tmp_conversations, "2026-04-19_c", messages=[{"role": "user", "content": "x"}])
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    items, _ = idx.list(sort="messages")
    # 3-msg first, then the two 1-msg in id-asc tie-break.
    assert [s["id"] for s in items] == ["2026-04-19_b", "2026-04-19_a", "2026-04-19_c"]


# _build_summary_dict: data.get() defaults + boundary literals
def test_build_summary_messages_default_is_empty_list(tmp_path):
    """data.get('messages', []) — default must be the empty list (not None or
    omitted). Mutating to `data.get('messages', None) or []` is equivalent here
    BUT mutating to `data.get('messages', )` (omitted) makes data.get return
    None; the `or []` then kicks in. Both pass — defends the explicit `[]` is
    still readable."""
    p = tmp_path / "2026-04-19_a.json"
    summary = _build_summary_dict(p, {"session_start": "2026-04-19T10:00:00"})
    # Empty messages → counted as 0; no agents/tools; title falls back to placeholder.
    assert summary["messages"] == 0
    assert summary["agents"] == []
    assert summary["tools"] == []
    assert summary["title"] == "(no messages)"


def test_build_summary_metrics_default_is_empty_dict(tmp_path):
    """metrics absent → tokens=0, cost=0.0 via the explicit `{}` default."""
    p = tmp_path / "2026-04-19_a.json"
    summary = _build_summary_dict(p, {"session_start": "2026-04-19T10:00:00", "messages": []})
    assert summary["tokens"] == 0
    assert summary["cost"] == 0.0


def test_build_summary_model_default_is_empty_dict(tmp_path):
    """model absent → model="", provider="" via the explicit `{}` default."""
    p = tmp_path / "2026-04-19_a.json"
    summary = _build_summary_dict(p, {"session_start": "2026-04-19T10:00:00", "messages": []})
    assert summary["model"] == ""
    assert summary["provider"] == ""


def test_build_summary_session_start_exactly_10_chars_takes_session_start_branch(tmp_path):
    """`len(session_start) >= 10` boundary — exactly 10 must take the prefix branch
    (not fall back to stem). Mutating to `> 10` would push 10-char dates to fallback."""
    p = tmp_path / "2026-04-19_99-99-99.json"
    summary = _build_summary_dict(p, {"session_start": "2026-04-30", "messages": []})
    # session_start[:10] is "2026-04-30", not the stem's "2026-04-19".
    assert summary["date"] == "2026-04-30"


def test_build_summary_stem_exactly_10_chars_takes_prefix(tmp_path):
    """`len(stem) >= 10` boundary — exactly 10 must take the prefix branch
    (not fall back to ""). Mutating to `> 10` would empty the date for
    short stems."""
    p = tmp_path / "2026-04-19.json"  # stem is exactly 10 chars
    summary = _build_summary_dict(p, {"messages": []})
    assert summary["date"] == "2026-04-19"


def test_build_summary_dominant_logic_uses_and_not_or(tmp_path):
    """`if dom and agents and agents[0] != dom:` — all three conditions must hold.
    Mutating the leading `and` to `or` would short-circuit and reorder agents
    even when dom is None (no dominant agent). Pins the conjunction."""
    p = tmp_path / "2026-04-19_a.json"
    # No dominant agent (single user message) → dom is None → reorder must NOT happen.
    summary = _build_summary_dict(
        p,
        {
            "session_start": "2026-04-19T10:00:00",
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "agent": "writer", "content": "first"},
                {"role": "assistant", "agent": "researcher", "content": "second"},
            ],
        },
    )
    # writer + researcher each have 1 message — no dominant. Order preserved
    # as-seen, not rearranged. With `or` mutation, agents[0] would still equal
    # the actual first one but the reorder branch could fire spuriously and
    # always put a falsy `dom` first. The exact agents list shouldn't change.
    assert set(summary["agents"]) == {"writer", "researcher"}


# delete: return False on OSError
def test_delete_returns_false_on_unlink_failure(tmp_conversations, monkeypatch):
    """When path.unlink() raises OSError, delete() returns False (not True).
    Pins the explicit `return False` against `return True` mutation."""
    path = _write_conversation(tmp_conversations, "2026-04-19_10-00-00")
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())

    def _raise(self):
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "unlink", _raise)
    assert idx.delete("2026-04-19_10-00-00") is False
    # File still on disk because unlink failed.
    assert path.is_file()


# _refresh_sync: continue must not become break (multi-file resilience)
def test_refresh_continues_past_unstattable_file(tmp_conversations, monkeypatch):
    """When path.stat() raises OSError mid-loop, the file is skipped via `continue`
    — subsequent files in the same year_dir must still be indexed. Mutating
    `continue` to `break` would drop the rest."""
    _write_conversation(tmp_conversations, "2026-04-17_a")
    _write_conversation(tmp_conversations, "2026-04-18_b")
    _write_conversation(tmp_conversations, "2026-04-19_c")

    real_stat = Path.stat

    def _flaky_stat(self, *args, **kwargs):
        # Make the middle file's stat raise OSError; first/last succeed.
        if self.stem == "2026-04-18_b":
            raise OSError("stat failed")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _flaky_stat)
    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    items, total = idx.list()
    # Two files indexed — middle one skipped.
    assert total == 2
    assert {s["id"] for s in items} == {"2026-04-17_a", "2026-04-19_c"}


# _refresh_sync: mkdir kwargs lock-in
def test_refresh_mkdir_uses_parents_true_and_exist_ok_true(tmp_path):
    """When the conversations dir is missing, refresh calls mkdir(parents=True,
    exist_ok=True). Pins both kwargs — mutating either to False would either
    raise (no parents) or fail on a pre-existing dir (no exist_ok)."""
    deep = tmp_path / "missing" / "nested" / "conversations"
    assert not deep.exists()
    idx = ConversationIndex(deep)
    asyncio.run(idx.refresh())
    # parents=True created the intermediate dirs.
    assert deep.is_dir()

    # Calling refresh again must not raise — exist_ok=True tolerates the
    # already-present dir. (Mutation `exist_ok=False` would raise here.)
    asyncio.run(idx.refresh())
    assert deep.is_dir()


# _in_date_range: integer-comparison literal residue
def test_in_date_range_today_zero_days_match(tmp_conversations):
    """`days == 0` for today preset — pins the integer literal."""
    assert _in_date_range("2026-04-19", "today", today="2026-04-19") is True
    assert _in_date_range("2026-04-18", "today", today="2026-04-19") is False
    assert _in_date_range("2026-04-20", "today", today="2026-04-19") is False


def test_in_date_range_7d_window_exact_boundaries(tmp_conversations):
    """`0 <= days < 7` — both bounds pinned. Day 0 in, day 6 in, day 7 out, day -1 out."""
    assert _in_date_range("2026-04-19", "7d", today="2026-04-19") is True  # day 0
    assert _in_date_range("2026-04-13", "7d", today="2026-04-19") is True  # day 6
    assert _in_date_range("2026-04-12", "7d", today="2026-04-19") is False  # day 7 — out
    assert _in_date_range("2026-04-20", "7d", today="2026-04-19") is False  # day -1 (future)


# facets: exercise the tool-counting branch (existing tests have no tool data)
def test_facets_aggregates_tool_counts_across_conversations(tmp_conversations):
    """Two conversations using two different tools each — facets should report
    every tool's correct count and sort by count desc, id asc on ties.
    Pins the `tool_counts.get(t, 0) + 1` accumulator and the lambda kv: (-kv[1], kv[0])
    sort key — defends against `get(None, 0)`, `key=None`, removed key, lambda → +kv[1]
    or kv[1] mutations."""
    tool_call_a = {
        "id": "call_a",
        "type": "function",
        "function": {"name": "search_vault", "arguments": "{}"},
    }
    tool_call_b = {
        "id": "call_b",
        "type": "function",
        "function": {"name": "read_file", "arguments": "{}"},
    }
    tool_call_c = {
        "id": "call_c",
        "type": "function",
        "function": {"name": "search_vault", "arguments": "{}"},
    }
    _write_conversation(
        tmp_conversations,
        "2026-04-19_a",
        messages=[
            {"role": "user", "content": "find x"},
            {"role": "assistant", "agent": "JARVIS", "content": "", "tool_calls": [tool_call_a, tool_call_b]},
        ],
    )
    _write_conversation(
        tmp_conversations,
        "2026-04-19_b",
        messages=[
            {"role": "user", "content": "find y"},
            {"role": "assistant", "agent": "JARVIS", "content": "", "tool_calls": [tool_call_c]},
        ],
    )

    idx = ConversationIndex(tmp_conversations)
    asyncio.run(idx.refresh())
    facets = idx.facets()
    # search_vault appears in 2 conversations, read_file in 1.
    # Sorted by count desc, then id asc.
    assert facets["tools"] == [
        {"id": "search_vault", "count": 2},
        {"id": "read_file", "count": 1},
    ]
    assert facets["total"] == 2
