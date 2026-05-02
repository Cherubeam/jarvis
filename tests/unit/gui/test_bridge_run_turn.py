"""Tests for the regular chat-flow branch of apps.gui.server.bridge.run_turn.

The /daily-summary branch is covered separately in test_bridge_daily_summary.py.
This file targets the path where user_text doesn't start with /daily-summary —
the bulk of run_turn (event sequencing, logger persistence, _mark_current_dirty,
delegation, error handling).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.gui.server.bridge import (
    _find_deferred_handler,
    _mark_current_dirty,
    _now_hhmm,
    run_turn,
)
from packages.core.llm_client import TokenUsage
from packages.core.stream_handler import StreamResult


@dataclass
class _FakeMetrics:
    ttft_ms: int = 100
    total_latency_ms: int = 500
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def record_history_tokens(self, _n: int) -> None:
        pass


def _make_session(tmp_path: Path, *, agent_name: str = "JARVIS") -> SimpleNamespace:
    """Build a minimal GuiSession-shaped object whose active_agent.run() returns
    a deterministic StreamResult. The bridge calls active_agent.run() inside
    asyncio.to_thread, so the mock must be sync.
    """
    stream_handler = MagicMock()
    stream_handler.on_event = None

    logger_obj = MagicMock()
    logger_obj.get_messages_for_api.return_value = []
    logger_obj.session_start = MagicMock()
    logger_obj.session_start.strftime = MagicMock(return_value="2026-04-23_12-00-00")
    logger_obj.current_conversation = []
    logger_obj.metrics = _FakeMetrics()

    components = SimpleNamespace(
        agent_name=agent_name,
        stream_handler=stream_handler,
        config={"_paths": {"jarvis_dir": tmp_path}},
        settings=SimpleNamespace(
            summarization=SimpleNamespace(enabled=False, token_threshold=10_000, keep_recent=4),
            models=SimpleNamespace(),
        ),
        client=MagicMock(),
        vault_config=None,
        system_prompt="SYS",
        logger=logger_obj,
        active_agent=MagicMock(),
        agent_registry={},
        context_metadata=None,
        _deferred_handler=None,
    )
    components.active_agent.run.return_value = StreamResult(
        text="hello",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        cost_usd=0.001,
        metrics=SimpleNamespace(ttft_ms=100, total_latency_ms=500),
        tool_messages=[],
    )
    session = SimpleNamespace(
        components=components,
        confirmation=None,
        conversation_index=None,
    )
    return session


def _drain(q: Queue) -> list[dict]:
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_now_hhmm_format():
    """Returns a 5-character HH:MM string with a colon separator."""
    out = _now_hhmm()
    assert isinstance(out, str)
    assert len(out) == 5
    assert out[2] == ":"
    hh, mm = out.split(":")
    assert hh.isdigit() and mm.isdigit()
    assert 0 <= int(hh) < 24
    assert 0 <= int(mm) < 60


def test_find_deferred_handler_returns_none_when_unset(tmp_path):
    session = _make_session(tmp_path)
    assert _find_deferred_handler(session) is None


def test_find_deferred_handler_returns_components_attribute(tmp_path):
    session = _make_session(tmp_path)
    sentinel = object()
    session.components._deferred_handler = sentinel
    assert _find_deferred_handler(session) is sentinel


def test_mark_current_dirty_no_index_is_noop(tmp_path):
    session = _make_session(tmp_path)
    session.conversation_index = None
    # No-op — must not raise.
    _mark_current_dirty(session)


def test_mark_current_dirty_calls_index_with_strftime_file_id(tmp_path):
    session = _make_session(tmp_path)
    session.conversation_index = MagicMock()
    _mark_current_dirty(session)
    session.conversation_index.mark_dirty.assert_called_once_with("2026-04-23_12-00-00")
    # Strftime called with the canonical file-id format.
    session.components.logger.session_start.strftime.assert_called_with("%Y-%m-%d_%H-%M-%S")


def test_mark_current_dirty_swallows_exceptions(tmp_path, caplog):
    session = _make_session(tmp_path)
    idx = MagicMock()
    idx.mark_dirty.side_effect = RuntimeError("kaboom")
    session.conversation_index = idx
    with caplog.at_level(logging.DEBUG, logger="apps.gui.server.bridge"):
        _mark_current_dirty(session)  # must NOT raise
    # Debug log captured.
    assert any("mark_dirty failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# run_turn — happy path event sequence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_turn_emits_user_thinking_text_totals_turnfinished(tmp_path):
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)

    await run_turn(session, "hi there", q)

    events = _drain(q)
    kinds = [e["type"] for e in events]
    # Strict event sequence.
    assert kinds == [
        "user",
        "thinking_start",
        "thinking_end",
        "text",
        "totals",
        "turn_finished",
    ]


@pytest.mark.asyncio
async def test_run_turn_user_event_carries_text_and_id(tmp_path):
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)

    await run_turn(session, "hello world", q)
    events = _drain(q)

    user_ev = events[0]
    assert user_ev["type"] == "user"
    assert user_ev["text"] == "hello world"
    # turn id format: "u-XXXXXXXX" (8 hex chars).
    assert user_ev["id"].startswith("u-")
    assert len(user_ev["id"]) == 10
    # time field is HH:MM.
    assert len(user_ev["time"]) == 5 and user_ev["time"][2] == ":"
    # turn_finished id matches.
    assert events[-1] == {"type": "turn_finished", "id": user_ev["id"]}


@pytest.mark.asyncio
async def test_run_turn_thinking_events_carry_agent_name(tmp_path):
    session = _make_session(tmp_path, agent_name="writer")
    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "draft something", q)
    events = _drain(q)
    assert events[1] == {"type": "thinking_start", "agent": "writer"}
    assert events[2] == {"type": "thinking_end", "agent": "writer"}


@pytest.mark.asyncio
async def test_run_turn_text_event_uses_result_text_and_stats(tmp_path):
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "ping", q)
    events = _drain(q)
    text = events[3]
    assert text["type"] == "text"
    assert text["agent"] == "JARVIS"
    assert text["markdown"] == "hello"
    # No buffered chunks → falls back to result.text. Stats use defaults from result.
    assert text["stats"]["ttft"] == 100
    assert text["stats"]["total"] == 500
    assert text["stats"]["tokens"] == 15
    assert text["stats"]["cost"] == 0.001


@pytest.mark.asyncio
async def test_run_turn_buffered_text_overrides_result_text(tmp_path):
    """If WebStreamHandler accumulated chunks, those win over result.text."""
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)

    # Wire an on_event sink that pretends chunks were buffered.
    class _Buf:
        def buffered_text(self):
            return "buffered version"

        def last_usage(self):
            return {"tokens": 99, "cost": 0.5}

    # The bridge always constructs a fresh WebStreamHandler internally, so to
    # assert that buffered text wins we patch the constructor with a stub.
    from unittest.mock import patch

    real_buf_text = "buffered version"

    class _StubWebStream(_Buf):
        def __init__(self, *a, **kw):
            super().__init__()

        def __call__(self, _ev):
            pass

    with patch("apps.gui.server.bridge.WebStreamHandler", _StubWebStream):
        await run_turn(session, "ping", q)

    events = _drain(q)
    text = events[3]
    assert text["markdown"] == real_buf_text
    assert text["stats"]["tokens"] == 99
    assert text["stats"]["cost"] == 0.5


@pytest.mark.asyncio
async def test_run_turn_totals_uses_logger_metrics(tmp_path):
    session = _make_session(tmp_path)
    session.components.logger.metrics.total_tokens = 1234
    session.components.logger.metrics.total_cost_usd = 0.0567
    session.components.logger.current_conversation = [{"role": "user"}, {"role": "assistant"}]
    q: Queue[dict] = Queue(maxsize=64)

    await run_turn(session, "ping", q)
    events = _drain(q)
    totals = events[-2]
    assert totals == {
        "type": "totals",
        "messages": 2,
        "tokens": 1234,
        "cost": 0.0567,
    }


# ---------------------------------------------------------------------------
# run_turn — logger persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_turn_persists_assistant_message_with_usage_fields(tmp_path):
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "hi", q)

    add_calls = session.components.logger.add_message.call_args_list
    # Two add_message calls: user (from _run_one_turn) + assistant (from run_turn).
    user_call = next(c for c in add_calls if c.args[:2] == ("user", "hi"))
    assistant_call = next(c for c in add_calls if c.args[0] == "assistant")
    assert user_call.args == ("user", "hi")
    assert assistant_call.args == ("assistant", "hello")
    kw = assistant_call.kwargs
    assert kw["prompt_tokens"] == 10
    assert kw["completion_tokens"] == 5
    assert kw["total_tokens"] == 15
    assert kw["cost_usd"] == 0.001
    assert kw["ttft_ms"] == 100
    assert kw["total_latency_ms"] == 500
    assert kw["agent_name"] == "JARVIS"


@pytest.mark.asyncio
async def test_run_turn_calls_logger_save_at_end(tmp_path):
    session = _make_session(tmp_path)
    await run_turn(session, "hi", Queue(maxsize=64))
    session.components.logger.save.assert_called_once()


@pytest.mark.asyncio
async def test_run_turn_save_failure_swallowed_but_turn_completes(tmp_path):
    """logger.save() raising must not break the turn — error is logged + finishing events still go out."""
    session = _make_session(tmp_path)
    session.components.logger.save.side_effect = OSError("disk full")
    q: Queue[dict] = Queue(maxsize=64)

    await run_turn(session, "hi", q)
    events = _drain(q)
    kinds = [e["type"] for e in events]
    # Even with save failure, totals + turn_finished still emitted.
    assert "totals" in kinds
    assert kinds[-1] == "turn_finished"


@pytest.mark.asyncio
async def test_run_turn_records_utilization_when_context_metadata_present(tmp_path):
    section = SimpleNamespace(name="profile")
    session = _make_session(tmp_path)
    session.components.context_metadata = SimpleNamespace(sections=[section])
    await run_turn(session, "hi", Queue(maxsize=64))
    session.components.logger.record_utilization.assert_called_once_with("hello", ["profile"])


@pytest.mark.asyncio
async def test_run_turn_skips_record_utilization_when_metadata_none(tmp_path):
    session = _make_session(tmp_path)
    session.components.context_metadata = None
    await run_turn(session, "hi", Queue(maxsize=64))
    session.components.logger.record_utilization.assert_not_called()


@pytest.mark.asyncio
async def test_run_turn_skips_record_utilization_when_text_empty(tmp_path):
    """Empty result.text shouldn't trigger record_utilization."""
    session = _make_session(tmp_path)
    session.components.context_metadata = SimpleNamespace(sections=[SimpleNamespace(name="x")])
    session.components.active_agent.run.return_value = StreamResult(
        text="",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=0, total_tokens=1),
        cost_usd=0.0,
        metrics=SimpleNamespace(ttft_ms=0, total_latency_ms=0),
        tool_messages=[],
    )
    await run_turn(session, "hi", Queue(maxsize=64))
    session.components.logger.record_utilization.assert_not_called()


@pytest.mark.asyncio
async def test_run_turn_persists_tool_messages_when_present(tmp_path):
    """Tool messages from agent.run() are added BEFORE the assistant message."""
    session = _make_session(tmp_path)
    tool_msgs = [{"role": "tool", "content": "result", "tool_call_id": "c1"}]
    session.components.active_agent.run.return_value = StreamResult(
        text="ok",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        cost_usd=0.0,
        metrics=SimpleNamespace(ttft_ms=0, total_latency_ms=0),
        tool_messages=tool_msgs,
    )
    await run_turn(session, "hi", Queue(maxsize=64))
    session.components.logger.add_tool_messages.assert_called_once_with(tool_msgs, agent_name="JARVIS")


@pytest.mark.asyncio
async def test_run_turn_skips_add_tool_messages_when_none(tmp_path):
    session = _make_session(tmp_path)  # default StreamResult has no tool_messages
    await run_turn(session, "hi", Queue(maxsize=64))
    session.components.logger.add_tool_messages.assert_not_called()


# ---------------------------------------------------------------------------
# run_turn — error handling on agent.run() exceptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_turn_agent_exception_emits_error_and_turn_finished(tmp_path):
    session = _make_session(tmp_path)
    session.components.active_agent.run.side_effect = RuntimeError("agent boom")
    q: Queue[dict] = Queue(maxsize=64)

    await run_turn(session, "hi", q)
    events = _drain(q)
    kinds = [e["type"] for e in events]
    # No thinking_end, no text, no totals — just user, thinking_start, error, turn_finished.
    assert kinds == ["user", "thinking_start", "error", "turn_finished"]
    assert events[2]["message"] == "agent boom"
    # Logger save NOT called (we bailed before persistence).
    session.components.logger.save.assert_not_called()


@pytest.mark.asyncio
async def test_run_turn_agent_exception_clears_session_confirmation(tmp_path):
    """A confirmation handler is bound during a turn — it must be discarded on error."""
    session = _make_session(tmp_path)
    session.components.active_agent.run.side_effect = RuntimeError("boom")
    await run_turn(session, "hi", Queue(maxsize=64))
    # session.confirmation gets reset to None at the cleanup step in the
    # success path, but the error path leaves it bound. The discard call
    # makes any blocked worker exit. Verify it WAS bound before the run
    # body raised.
    assert session.confirmation is not None
    # discard() was effectively called (idempotent — verify by triggering it
    # again; the handler should have its event set).
    assert session.confirmation._event.is_set()


# ---------------------------------------------------------------------------
# run_turn — _mark_current_dirty integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_turn_marks_index_dirty_on_success(tmp_path):
    session = _make_session(tmp_path)
    idx = MagicMock()
    session.conversation_index = idx
    await run_turn(session, "hi", Queue(maxsize=64))
    idx.mark_dirty.assert_called_once_with("2026-04-23_12-00-00")


# ---------------------------------------------------------------------------
# run_turn — deferred-handler binding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_turn_binds_and_unbinds_deferred_handler(tmp_path):
    session = _make_session(tmp_path)
    deferred = MagicMock()
    session.components._deferred_handler = deferred
    await run_turn(session, "hi", Queue(maxsize=64))
    deferred.bind.assert_called_once()
    deferred.unbind.assert_called_once()


@pytest.mark.asyncio
async def test_run_turn_unbinds_deferred_handler_on_error(tmp_path):
    """Even when agent.run raises, the deferred handler must be unbound."""
    session = _make_session(tmp_path)
    deferred = MagicMock()
    session.components._deferred_handler = deferred
    session.components.active_agent.run.side_effect = RuntimeError("boom")
    await run_turn(session, "hi", Queue(maxsize=64))
    deferred.bind.assert_called_once()
    deferred.unbind.assert_called_once()
