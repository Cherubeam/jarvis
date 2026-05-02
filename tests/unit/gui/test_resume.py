"""Tests for apps.gui.server.resume — chat-view conversation resume."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from typing import Any

import pytest

from apps.gui.server.resume import (
    ResumeError,
    _build_replay_events,
    _metrics_from_dict,
    _msg_text,
    _parse_session_start,
    _path_for_file_id,
    _safe_parse_json,
    load_and_replay,
)
from packages.core.memory import ConversationLogger


@dataclass
class _StubComponents:
    conversations_dir: Any
    logger: ConversationLogger


@dataclass
class _StubSession:
    components: _StubComponents
    conversation_index: Any = None

    def session_meta(self) -> dict[str, Any]:
        c = self.components
        file_id = c.logger.session_start.strftime("%Y-%m-%d_%H-%M-%S")
        return {
            "id": c.logger.conversation_id,
            "file_id": file_id,
            "model": "test/model",
            "model_short": "model",
            "provider": "test",
            "conversation_path": str(c.conversations_dir / str(c.logger.session_start.year) / f"{file_id}.json"),
            "vault": None,
            "started_at": "00:00",
            "agents_count": 0,
        }


def _write_conv(path, messages, *, conv_id="conv_replay_x", session_start="2026-04-01T10:00:00", metrics=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": "1.0.0",
        "id": conv_id,
        "session_start": session_start,
        "session_end": session_start,
        "model": {"id": "test/model", "provider": "test", "parameters": {}},
        "agent": {"name": "JARVIS"},
        "context": {"files_loaded": [], "metadata": {}},
        "environment": {"client": "test"},
        "metrics": metrics
        or {
            "total_tokens": 250,
            "total_cost_usd": 0.0123,
            "total_prompt_tokens": 200,
            "total_completion_tokens": 50,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "total_ttft_ms": 0,
            "total_latency_ms": 0,
            "request_count": 1,
        },
        "messages": messages,
        "feedback": [],
        "metadata": {},
    }
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# _build_replay_events
# ---------------------------------------------------------------------------


class TestBuildReplayEvents:
    def test_user_assistant_pair_emits_two_events(self):
        events = _build_replay_events(
            [
                {"id": "msg_001", "role": "user", "content": "hello"},
                {
                    "id": "msg_002",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "world"}],
                    "agent": "JARVIS",
                    "usage": {"total_tokens": 12, "cost_usd": 0.0001},
                    "latency": {"ttft_ms": 100, "total_ms": 500},
                },
            ]
        )
        assert [e["type"] for e in events] == ["user", "text"]
        assert events[0] == {"type": "user", "id": "msg_001", "text": "hello", "time": ""}
        assert set(events[0].keys()) == {"type", "id", "text", "time"}
        assert events[1]["type"] == "text"
        assert events[1]["agent"] == "JARVIS"
        assert events[1]["markdown"] == "world"
        assert events[1]["id"] == "msg_002"
        assert events[1]["stats"] == {"tokens": 12, "cost": 0.0001, "ttft": 100, "total": 500}
        assert set(events[1].keys()) == {"type", "id", "agent", "markdown", "stats"}

    def test_assistant_default_agent_is_jarvis(self):
        """Missing `agent` field on assistant message → "JARVIS" default."""
        events = _build_replay_events([{"id": "m1", "role": "assistant", "content": "hello"}])
        assert len(events) == 1
        assert events[0]["agent"] == "JARVIS"

    def test_text_event_omits_stats_keys_when_usage_absent(self):
        """No usage / latency on the message → stats={} on the text event."""
        events = _build_replay_events([{"id": "m1", "role": "assistant", "agent": "writer", "content": "hi"}])
        assert events[0]["stats"] == {}

    def test_tool_call_paired_with_following_tool_result(self):
        events = _build_replay_events(
            [
                {
                    "id": "msg_003",
                    "role": "assistant",
                    "agent": "writer",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_42",
                            "type": "function",
                            "function": {"name": "read_note", "arguments": '{"path": "/x.md"}'},
                        }
                    ],
                },
                {
                    "id": "msg_004",
                    "role": "tool",
                    "tool_call_id": "call_42",
                    "content": [{"type": "text", "text": "Read 17 chars."}],
                },
            ]
        )
        assert len(events) == 1
        ev = events[0]
        # Strict shape — wire contract for the chat-view tool card.
        assert set(ev.keys()) == {"type", "id", "agent", "tool", "args", "result", "elapsed_ms", "status"}
        assert ev["type"] == "tool_call"
        assert ev["id"] == "call_42"
        assert ev["agent"] == "writer"
        assert ev["tool"] == "read_note"
        assert ev["args"] == {"path": "/x.md"}
        assert ev["result"] == {"summary": "Read 17 chars."}
        assert ev["elapsed_ms"] == 0
        assert ev["status"] == "ok"

    def test_assistant_with_both_tool_call_and_text_emits_both(self):
        events = _build_replay_events(
            [
                {
                    "id": "msg_010",
                    "role": "assistant",
                    "agent": "JARVIS",
                    "content": [{"type": "text", "text": "thinking out loud"}],
                    "tool_calls": [
                        {
                            "id": "call_99",
                            "function": {"name": "search_notes", "arguments": "{}"},
                        }
                    ],
                },
                {
                    "id": "msg_011",
                    "role": "tool",
                    "tool_call_id": "call_99",
                    "content": "no results",
                },
            ]
        )
        # tool_call is emitted before the text — matches the loop order.
        assert [e["type"] for e in events] == ["tool_call", "text"]
        assert events[0]["tool"] == "search_notes"
        assert events[0]["result"] == {"summary": "no results"}
        assert events[1]["markdown"] == "thinking out loud"

    def test_tool_call_without_paired_result_emits_empty_summary(self):
        events = _build_replay_events(
            [
                {
                    "id": "msg_020",
                    "role": "assistant",
                    "agent": "JARVIS",
                    "content": "",
                    "tool_calls": [{"id": "orphan", "function": {"name": "noop", "arguments": "{}"}}],
                }
            ]
        )
        assert len(events) == 1
        assert events[0]["result"] == {"summary": ""}

    def test_tool_call_id_falls_back_to_msg_id_when_absent(self):
        """call without `id` → uses the assistant message's id as the tool-call id."""
        events = _build_replay_events(
            [
                {
                    "id": "msg_alt",
                    "role": "assistant",
                    "agent": "JARVIS",
                    "content": "",
                    "tool_calls": [{"function": {"name": "x", "arguments": "{}"}}],
                }
            ]
        )
        assert events[0]["id"] == "msg_alt"

    def test_unparseable_arguments_become_empty_dict(self):
        events = _build_replay_events(
            [
                {
                    "id": "msg_030",
                    "role": "assistant",
                    "agent": "JARVIS",
                    "content": "",
                    "tool_calls": [{"id": "c", "function": {"name": "x", "arguments": "not-json{{"}}],
                }
            ]
        )
        assert events[0]["args"] == {}

    def test_arguments_already_dict_passes_through(self):
        """JSON-arguments already parsed (some imports do this)."""
        events = _build_replay_events(
            [
                {
                    "id": "m1",
                    "role": "assistant",
                    "agent": "JARVIS",
                    "content": "",
                    "tool_calls": [{"id": "c", "function": {"name": "x", "arguments": {"k": "v"}}}],
                }
            ]
        )
        assert events[0]["args"] == {"k": "v"}

    def test_empty_user_message_is_dropped(self):
        events = _build_replay_events([{"id": "msg_001", "role": "user", "content": ""}])
        assert events == []

    def test_user_message_without_id_uses_empty_string_id(self):
        events = _build_replay_events([{"role": "user", "content": "hi"}])
        assert events == [{"type": "user", "id": "", "text": "hi", "time": ""}]

    def test_tool_result_text_truncated_to_240_chars(self):
        long_text = "a" * 1000
        events = _build_replay_events(
            [
                {
                    "id": "msg_010",
                    "role": "assistant",
                    "agent": "JARVIS",
                    "content": "",
                    "tool_calls": [{"id": "c1", "function": {"name": "x", "arguments": "{}"}}],
                },
                {
                    "id": "msg_011",
                    "role": "tool",
                    "tool_call_id": "c1",
                    "content": [{"type": "text", "text": long_text}],
                },
            ]
        )
        # Truncated to exactly 240 — no ellipsis (the implementation uses [:240]).
        assert len(events[0]["result"]["summary"]) == 240

    def test_tool_messages_alone_emit_no_visible_event(self):
        """Tool messages without a preceding assistant tool_call are dropped."""
        events = _build_replay_events([{"id": "m1", "role": "tool", "tool_call_id": "x", "content": "orphan"}])
        assert events == []

    def test_unknown_role_dropped_silently(self):
        events = _build_replay_events([{"id": "m1", "role": "system", "content": "noise"}])
        assert events == []


# ---------------------------------------------------------------------------
# _parse_session_start
# ---------------------------------------------------------------------------


class TestParseSessionStart:
    def test_isoformat_wins(self):
        out = _parse_session_start("2026-04-01T12:34:56", "2026-04-29_00-00-00")
        assert out == datetime(2026, 4, 1, 12, 34, 56)

    def test_falls_back_to_file_id_stem(self):
        out = _parse_session_start(None, "2026-04-29_15-22-08")
        assert out == datetime(2026, 4, 29, 15, 22, 8)

    def test_empty_string_falls_back_to_stem(self):
        out = _parse_session_start("", "2026-04-29_15-22-08")
        assert out == datetime(2026, 4, 29, 15, 22, 8)

    def test_invalid_iso_falls_back_to_stem(self):
        out = _parse_session_start("not-a-date", "2026-04-29_15-22-08")
        assert out == datetime(2026, 4, 29, 15, 22, 8)

    def test_unparseable_stem_raises(self):
        with pytest.raises(ResumeError, match="could not derive session_start"):
            _parse_session_start(None, "garbage")


# ---------------------------------------------------------------------------
# _path_for_file_id — security guard + resolution
# ---------------------------------------------------------------------------


class TestPathForFileId:
    def test_resolves_under_year_subdir(self, tmp_path):
        f = tmp_path / "2026" / "2026-04-01_10-00-00.json"
        f.parent.mkdir(parents=True)
        f.write_text("{}")
        assert _path_for_file_id(tmp_path, "2026-04-01_10-00-00") == f

    def test_rejects_traversal(self, tmp_path):
        with pytest.raises(ResumeError, match="invalid file_id"):
            _path_for_file_id(tmp_path, "../etc/passwd")

    def test_rejects_slash(self, tmp_path):
        with pytest.raises(ResumeError, match="invalid file_id"):
            _path_for_file_id(tmp_path, "2026/04/01")

    def test_rejects_empty(self, tmp_path):
        with pytest.raises(ResumeError, match="invalid file_id"):
            _path_for_file_id(tmp_path, "")

    def test_rejects_non_year_prefix(self, tmp_path):
        with pytest.raises(ResumeError, match="invalid file_id"):
            _path_for_file_id(tmp_path, "abcd-04-01_10-00-00")

    def test_raises_when_file_missing(self, tmp_path):
        with pytest.raises(ResumeError, match="conversation not found"):
            _path_for_file_id(tmp_path, "2026-04-01_10-00-00")


# ---------------------------------------------------------------------------
# _metrics_from_dict — coerces floats/ints, defaults to zero
# ---------------------------------------------------------------------------


class TestMetricsFromDict:
    def test_all_keys_coerced(self):
        m = _metrics_from_dict(
            {
                "total_prompt_tokens": "10",
                "total_completion_tokens": "5",
                "total_tokens": 15,
                "total_cost_usd": "0.5",
                "total_cache_read_tokens": "2",
                "total_cache_write_tokens": "1",
                "total_thinking_tokens": "3",
                "request_count": "4",
                "total_ttft_ms": "100",
                "total_latency_ms": "200",
            }
        )
        assert m.total_prompt_tokens == 10
        assert m.total_completion_tokens == 5
        assert m.total_tokens == 15
        assert m.total_cost_usd == 0.5
        assert m.total_cache_read_tokens == 2
        assert m.total_cache_write_tokens == 1
        assert m.total_thinking_tokens == 3
        assert m.request_count == 4
        assert m.total_ttft_ms == 100.0
        assert m.total_latency_ms == 200.0

    def test_empty_dict_yields_zero_metrics(self):
        m = _metrics_from_dict({})
        assert m.total_tokens == 0
        assert m.total_cost_usd == 0.0
        assert m.request_count == 0

    def test_none_values_treated_as_zero(self):
        m = _metrics_from_dict({"total_tokens": None, "total_cost_usd": None})
        assert m.total_tokens == 0
        assert m.total_cost_usd == 0.0


# ---------------------------------------------------------------------------
# _msg_text + _safe_parse_json
# ---------------------------------------------------------------------------


def test_msg_text_string_content():
    assert _msg_text({"content": "hello"}) == "hello"


def test_msg_text_block_list_content():
    """Block-list content delegates to memory._extract_text_from_content."""
    out = _msg_text({"content": [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]})
    assert out == "hello world"


def test_msg_text_missing_content_returns_empty():
    assert _msg_text({}) == ""


def test_msg_text_none_content_returns_empty():
    assert _msg_text({"content": None}) == ""


def test_safe_parse_json_passes_dict_through():
    assert _safe_parse_json({"k": "v"}) == {"k": "v"}


def test_safe_parse_json_returns_empty_for_non_string():
    assert _safe_parse_json(42) == {}
    assert _safe_parse_json(None) == {}
    assert _safe_parse_json(["list"]) == {}


def test_safe_parse_json_returns_empty_for_invalid_json():
    assert _safe_parse_json("not-json") == {}


def test_safe_parse_json_returns_empty_when_parsed_isnt_dict():
    """JSON arrays parse fine but aren't dicts — must return {}."""
    assert _safe_parse_json("[1, 2, 3]") == {}


def test_safe_parse_json_valid_json_dict():
    assert _safe_parse_json('{"a": 1}') == {"a": 1}


# ---------------------------------------------------------------------------
# load_and_replay (integration of file load + logger mutate + queue events)
# ---------------------------------------------------------------------------


class TestLoadAndReplay:
    def _make_session(self, tmp_path) -> _StubSession:
        convs = tmp_path / "conversations"
        logger = ConversationLogger(convs, conversation_id="conv_fresh")
        components = _StubComponents(conversations_dir=convs, logger=logger)
        return _StubSession(components=components)

    def test_happy_path_swaps_logger_and_emits_events(self, tmp_path):
        session = self._make_session(tmp_path)
        convs = session.components.conversations_dir
        _write_conv(
            convs / "2026" / "2026-04-01_10-00-00.json",
            [
                {"id": "msg_001", "role": "user", "content": "first"},
                {
                    "id": "msg_002",
                    "role": "assistant",
                    "agent": "JARVIS",
                    "content": [{"type": "text", "text": "answered"}],
                },
            ],
            conv_id="conv_replay_target",
            session_start="2026-04-01T10:00:00",
        )

        queue: Queue[dict[str, Any]] = Queue()
        load_and_replay(session, "2026-04-01_10-00-00", queue)

        # Logger now points at the historic file.
        c = session.components
        assert c.logger.conversation_id == "conv_replay_target"
        assert c.logger.session_start == datetime(2026, 4, 1, 10, 0, 0)
        assert len(c.logger.current_conversation) == 2
        # Subsequent save() writes back to the same file path.
        c.logger.add_message("user", "follow-up")
        c.logger.save()
        target = convs / "2026" / "2026-04-01_10-00-00.json"
        assert target.is_file()
        data = json.loads(target.read_text())
        assert [m["role"] for m in data["messages"]] == ["user", "assistant", "user"]

        # Queue carries: session_start (new), system notice, replay events, totals.
        emitted = []
        while not queue.empty():
            emitted.append(queue.get_nowait())
        types = [e["type"] for e in emitted]
        assert types[0] == "session_start"
        assert types[1] == "system"
        assert "Resumed conversation" in emitted[1]["text"]
        # System message includes the file_id and the message count.
        assert "2026-04-01_10-00-00" in emitted[1]["text"]
        assert "2 prior message(s)" in emitted[1]["text"]
        assert types[-1] == "totals"
        assert emitted[-1]["messages"] == 2
        assert emitted[-1]["cost"] == pytest.approx(0.0123)
        assert emitted[-1]["tokens"] == 250
        # Replay events sit between system and totals.
        replay_types = types[2:-1]
        assert replay_types == ["user", "text"]

    def test_missing_file_raises_resume_error(self, tmp_path):
        session = self._make_session(tmp_path)
        # Year dir doesn't exist.
        with pytest.raises(ResumeError, match="conversation not found"):
            load_and_replay(session, "2026-04-01_10-00-00", Queue())

    def test_invalid_file_id_rejected(self, tmp_path):
        session = self._make_session(tmp_path)
        with pytest.raises(ResumeError, match="invalid file_id"):
            load_and_replay(session, "../etc/passwd", Queue())
        with pytest.raises(ResumeError, match="invalid file_id"):
            load_and_replay(session, "", Queue())

    def test_marks_index_dirty_when_present(self, tmp_path):
        session = self._make_session(tmp_path)
        convs = session.components.conversations_dir
        _write_conv(
            convs / "2026" / "2026-04-01_10-00-00.json",
            [{"id": "msg_001", "role": "user", "content": "hi"}],
            session_start="2026-04-01T10:00:00",
        )

        marked: list[str] = []

        class _Idx:
            def mark_dirty(self, file_id: str) -> None:
                marked.append(file_id)

        session.conversation_index = _Idx()
        load_and_replay(session, "2026-04-01_10-00-00", Queue())
        assert marked == ["2026-04-01_10-00-00"]

    def test_index_mark_dirty_failure_is_swallowed(self, tmp_path):
        """An exception from mark_dirty must NOT bubble out of resume."""
        session = self._make_session(tmp_path)
        convs = session.components.conversations_dir
        _write_conv(
            convs / "2026" / "2026-04-01_10-00-00.json",
            [{"id": "m", "role": "user", "content": "hi"}],
            session_start="2026-04-01T10:00:00",
        )

        class _BadIdx:
            def mark_dirty(self, file_id: str) -> None:
                raise RuntimeError("boom")

        session.conversation_index = _BadIdx()
        # Should not raise.
        load_and_replay(session, "2026-04-01_10-00-00", Queue())

    def test_no_index_attribute_is_tolerated(self, tmp_path):
        """conversation_index defaults to None — code path that skips mark_dirty."""
        session = self._make_session(tmp_path)
        session.conversation_index = None
        convs = session.components.conversations_dir
        _write_conv(
            convs / "2026" / "2026-04-01_10-00-00.json",
            [{"id": "m", "role": "user", "content": "hi"}],
            session_start="2026-04-01T10:00:00",
        )
        # Should not raise.
        load_and_replay(session, "2026-04-01_10-00-00", Queue())

    def test_session_start_event_carries_session_meta_payload(self, tmp_path):
        """First event is session_start with the full session_meta dict."""
        session = self._make_session(tmp_path)
        convs = session.components.conversations_dir
        _write_conv(
            convs / "2026" / "2026-04-01_10-00-00.json",
            [{"id": "m", "role": "user", "content": "hi"}],
            session_start="2026-04-01T10:00:00",
        )
        q: Queue[dict[str, Any]] = Queue()
        load_and_replay(session, "2026-04-01_10-00-00", q)
        first = q.get_nowait()
        assert first["type"] == "session_start"
        assert "session" in first
        assert first["session"]["model"] == "test/model"

    def test_empty_messages_emits_only_meta_and_totals(self, tmp_path):
        """An empty conversation file → session_start + system + totals (no replay)."""
        session = self._make_session(tmp_path)
        convs = session.components.conversations_dir
        _write_conv(
            convs / "2026" / "2026-04-01_10-00-00.json",
            [],
            session_start="2026-04-01T10:00:00",
        )
        q: Queue[dict[str, Any]] = Queue()
        load_and_replay(session, "2026-04-01_10-00-00", q)
        types = []
        while not q.empty():
            types.append(q.get_nowait()["type"])
        assert types == ["session_start", "system", "totals"]
