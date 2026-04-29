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
    _parse_session_start,
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


def _write_conv(path, messages, *, conv_id="conv_replay_x", session_start="2026-04-01T10:00:00"):
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
        "metrics": {
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
        assert events[1]["agent"] == "JARVIS"
        assert events[1]["markdown"] == "world"
        assert events[1]["stats"] == {"tokens": 12, "cost": 0.0001, "ttft": 100, "total": 500}

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
        assert [e["type"] for e in events] == ["tool_call", "text"]
        assert events[0]["tool"] == "search_notes"
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

    def test_empty_user_message_is_dropped(self):
        events = _build_replay_events([{"id": "msg_001", "role": "user", "content": ""}])
        assert events == []

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
        assert len(events[0]["result"]["summary"]) == 240


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

    def test_invalid_iso_falls_back_to_stem(self):
        out = _parse_session_start("not-a-date", "2026-04-29_15-22-08")
        assert out == datetime(2026, 4, 29, 15, 22, 8)

    def test_unparseable_stem_raises(self):
        with pytest.raises(ResumeError):
            _parse_session_start(None, "garbage")


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
        assert types[-1] == "totals"
        assert emitted[-1]["messages"] == 2
        assert emitted[-1]["cost"] == pytest.approx(0.0123)
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
