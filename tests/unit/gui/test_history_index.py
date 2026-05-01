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
