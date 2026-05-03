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


# ---------------------------------------------------------------------------
# run_turn — strict event-shape assertions
#
# Catch dict-key mutations (e.g. "id" → "XXidXX" / "ID") that pass type-only
# tests because `e["message"]` still works when only `e["id"]` is mutated.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_turn_event_dict_keys_are_exact(tmp_path):
    """Every emitted event has the canonical key set — no typos, no extras."""
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "hello", q)
    events = _drain(q)

    by_type = {e["type"]: e for e in events}
    assert set(by_type["user"].keys()) == {"type", "id", "text", "time"}
    assert set(by_type["thinking_start"].keys()) == {"type", "agent"}
    assert set(by_type["thinking_end"].keys()) == {"type", "agent"}
    assert set(by_type["text"].keys()) == {"type", "id", "agent", "markdown", "stats"}
    assert set(by_type["totals"].keys()) == {"type", "messages", "tokens", "cost"}
    assert set(by_type["turn_finished"].keys()) == {"type", "id"}


@pytest.mark.asyncio
async def test_run_turn_error_event_dict_keys_are_exact(tmp_path):
    """Error path emits {type, id, message} — pin the exact key set."""
    session = _make_session(tmp_path)
    session.components.active_agent.run.side_effect = RuntimeError("boom")
    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "hi", q)
    events = _drain(q)

    err = next(e for e in events if e["type"] == "error")
    assert set(err.keys()) == {"type", "id", "message"}
    assert err["message"] == "boom"


# ---------------------------------------------------------------------------
# _run_one_turn — summarization branch (~15 mutants)
#
# Existing tests exercise only summarization.enabled=False. With it True, the
# fast-model lookup and summarize_history call get exercised, killing mutations
# on the resolve_model("fast", ...) call site.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_one_turn_summarization_calls_resolve_model_with_fast_preset(tmp_path, monkeypatch):
    """When summarization.enabled, resolve_model is called with EXACTLY ("fast", models)
    and summarize_history is invoked with the resolved model_id, threshold, keep_recent."""
    from apps.gui.server import bridge

    session = _make_session(tmp_path)
    session.components.settings.summarization.enabled = True
    session.components.settings.summarization.token_threshold = 12_345
    session.components.settings.summarization.keep_recent = 7
    session.components.logger.get_messages_for_api.return_value = [{"role": "user", "content": "earlier"}]

    resolve_calls: list[tuple] = []

    def _fake_resolve(preset, models):
        resolve_calls.append((preset, models))
        return SimpleNamespace(model_id="resolved/fast/model")

    summarize_calls: list[dict] = []

    def _fake_summarize(history, client, *, model_id, token_threshold, keep_recent):
        summarize_calls.append(
            {
                "model_id": model_id,
                "token_threshold": token_threshold,
                "keep_recent": keep_recent,
                "history_len": len(history),
            }
        )
        return history  # passthrough

    monkeypatch.setattr(bridge, "resolve_model", _fake_resolve)
    monkeypatch.setattr(bridge, "summarize_history", _fake_summarize)

    await run_turn(session, "hi", Queue(maxsize=64))

    # resolve_model called exactly once with the "fast" preset literal.
    assert len(resolve_calls) == 1
    preset, models = resolve_calls[0]
    assert preset == "fast"
    assert models is session.components.settings.models
    # summarize_history called with the threshold + keep_recent verbatim.
    assert len(summarize_calls) == 1
    assert summarize_calls[0] == {
        "model_id": "resolved/fast/model",
        "token_threshold": 12_345,
        "keep_recent": 7,
        "history_len": 1,
    }


@pytest.mark.asyncio
async def test_run_one_turn_no_summarization_skips_resolve_model(tmp_path, monkeypatch):
    """summarization.enabled=False (default in fixture) — neither resolve_model
    nor summarize_history is called."""
    from apps.gui.server import bridge

    session = _make_session(tmp_path)
    # Defaults already disabled, but pin it explicitly.
    session.components.settings.summarization.enabled = False

    monkeypatch.setattr(bridge, "resolve_model", MagicMock(side_effect=AssertionError("must not run")))
    monkeypatch.setattr(bridge, "summarize_history", MagicMock(side_effect=AssertionError("must not run")))

    await run_turn(session, "hi", Queue(maxsize=64))


@pytest.mark.asyncio
async def test_run_one_turn_records_history_tokens_with_floor_div_4(tmp_path):
    """The history-byte budget is recorded as `bytes // 4` (rough token estimate).
    Pins the literal `// 4` against `// 5`, `/ 4`, `None` mutations."""
    session = _make_session(tmp_path)
    # Two messages with known byte-length content — predictable history_bytes.
    session.components.logger.get_messages_for_api.return_value = [
        {"role": "user", "content": "x" * 40},  # 40 bytes utf-8
        {"role": "assistant", "content": "y" * 40},  # 40 bytes utf-8
    ]
    # Replace _FakeMetrics.record_history_tokens with a recording mock.
    record_calls: list = []
    session.components.logger.metrics.record_history_tokens = lambda n: record_calls.append(n)

    await run_turn(session, "hi", Queue(maxsize=64))

    # 80 bytes // 4 = 20 tokens. Mutation to // 5 → 16, / 4 → 20.0 (float), None crashes.
    assert record_calls == [20]
    # And the value must be int (not float — defends `// 4` → `/ 4` mutation).
    assert isinstance(record_calls[0], int) and not isinstance(record_calls[0], bool)


# ---------------------------------------------------------------------------
# _run_delegation — covers 193 untested mutants
#
# The delegation flow is reached when active_agent.run() returns a StreamResult
# whose .delegate_to matches a registered agent id. Bridge then calls
# build_delegate_agent (mocked here) and runs the result through asyncio.to_thread.
# ---------------------------------------------------------------------------


def _make_session_with_delegation(
    tmp_path: Path,
    *,
    agent_name: str = "JARVIS",
    delegate_id: str = "writer",
    delegate_task: str = "draft a section",
    delegate_context: str | None = None,
    delegate_text: str = "drafted output",
    delegate_tool_messages: list | None = None,
) -> tuple[SimpleNamespace, MagicMock]:
    """Build a session whose active_agent.run() returns a delegating StreamResult,
    plus the delegate agent mock (whose .run will be called inside _run_delegation).
    Returns (session, delegate_agent_mock) so tests can assert against the delegate."""
    session = _make_session(tmp_path, agent_name=agent_name)
    session.components.agent_registry = {delegate_id: MagicMock(name=f"AgentMeta:{delegate_id}")}
    # Make the orchestrator's StreamResult delegate.
    session.components.active_agent.run.return_value = StreamResult(
        text="orchestrator decision",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        cost_usd=0.001,
        metrics=SimpleNamespace(ttft_ms=100, total_latency_ms=500),
        tool_messages=[],
        delegate_to=delegate_id,
        delegate_task=delegate_task,
        delegate_context=delegate_context,
    )

    delegate_agent = MagicMock(name=f"DelegateAgent:{delegate_id}")
    delegate_agent.run.return_value = StreamResult(
        text=delegate_text,
        usage=TokenUsage(prompt_tokens=20, completion_tokens=15, total_tokens=35),
        cost_usd=0.005,
        metrics=SimpleNamespace(ttft_ms=200, total_latency_ms=900),
        tool_messages=delegate_tool_messages or [],
    )
    return session, delegate_agent


@pytest.mark.asyncio
async def test_run_delegation_emits_delegation_then_thinking_then_text(tmp_path, monkeypatch):
    """Full happy-path event sequence: original turn finishes, then delegation
    overlays {delegation, thinking_start, thinking_end, text} for the delegate."""
    from apps.gui.server import bridge

    session, delegate_agent = _make_session_with_delegation(tmp_path)
    monkeypatch.setattr(bridge, "build_delegate_agent", MagicMock(return_value=delegate_agent))

    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "go write something", q)
    events = _drain(q)
    kinds = [e["type"] for e in events]

    # Original turn's events come first, then the delegate's, then totals/finished.
    assert kinds == [
        "user",
        "thinking_start",
        "thinking_end",
        "text",  # orchestrator's text
        "delegation",
        "thinking_start",  # delegate's
        "thinking_end",
        "text",  # delegate's text
        "totals",
        "turn_finished",
    ]


@pytest.mark.asyncio
async def test_run_delegation_event_carries_from_to_reason(tmp_path, monkeypatch):
    """delegation event has exact key set + values pulled from the StreamResult."""
    from apps.gui.server import bridge

    session, delegate_agent = _make_session_with_delegation(
        tmp_path,
        agent_name="JARVIS",
        delegate_id="writer",
        delegate_task="draft a Substack note",
    )
    monkeypatch.setattr(bridge, "build_delegate_agent", MagicMock(return_value=delegate_agent))

    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "delegate plz", q)
    events = _drain(q)
    deleg = next(e for e in events if e["type"] == "delegation")

    assert set(deleg.keys()) == {"type", "id", "from", "to", "reason"}
    assert deleg["from"] == "JARVIS"
    assert deleg["to"] == "writer"
    assert deleg["reason"] == "draft a Substack note"
    # delegation id format: "d-XXXXXXXX" (8 hex chars).
    assert deleg["id"].startswith("d-")
    assert len(deleg["id"]) == 10


@pytest.mark.asyncio
async def test_run_delegation_text_event_uses_delegate_id_as_agent(tmp_path, monkeypatch):
    """The post-delegation text event reports the DELEGATE's id as `agent`,
    not the orchestrator's. Pins the agent attribution."""
    from apps.gui.server import bridge

    session, delegate_agent = _make_session_with_delegation(
        tmp_path, agent_name="JARVIS", delegate_id="writer", delegate_text="draft body"
    )
    monkeypatch.setattr(bridge, "build_delegate_agent", MagicMock(return_value=delegate_agent))

    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "go", q)
    events = _drain(q)

    # Two text events: orchestrator's first ("orchestrator decision"), delegate's second.
    text_events = [e for e in events if e["type"] == "text"]
    assert len(text_events) == 2
    assert text_events[0]["agent"] == "JARVIS"
    assert text_events[0]["markdown"] == "orchestrator decision"
    assert text_events[1]["agent"] == "writer"
    assert text_events[1]["markdown"] == "draft body"
    # Delegate's text event id format: "r-XXXXXXXX" (8 hex chars).
    assert text_events[1]["id"].startswith("r-")
    assert len(text_events[1]["id"]) == 10


@pytest.mark.asyncio
async def test_run_delegation_appends_context_to_initial_prompt(tmp_path, monkeypatch):
    """When result.delegate_context is set, the delegate's run() is called with
    initial = f"{task}\\n\\nContext:\\n{context}"."""
    from apps.gui.server import bridge

    session, delegate_agent = _make_session_with_delegation(
        tmp_path,
        delegate_task="continue the draft",
        delegate_context="prior turn produced X",
    )
    monkeypatch.setattr(bridge, "build_delegate_agent", MagicMock(return_value=delegate_agent))

    await run_turn(session, "go", Queue(maxsize=64))

    # First positional arg to delegate_agent.run is the assembled prompt.
    args, kwargs = delegate_agent.run.call_args
    assert args[0] == "continue the draft\n\nContext:\nprior turn produced X"
    assert kwargs["stream_handler"] is session.components.stream_handler


@pytest.mark.asyncio
async def test_run_delegation_no_context_uses_bare_task(tmp_path, monkeypatch):
    """delegate_context=None → initial = the task verbatim, no Context: suffix."""
    from apps.gui.server import bridge

    session, delegate_agent = _make_session_with_delegation(
        tmp_path,
        delegate_task="just do it",
        delegate_context=None,
    )
    monkeypatch.setattr(bridge, "build_delegate_agent", MagicMock(return_value=delegate_agent))

    await run_turn(session, "go", Queue(maxsize=64))

    args, _ = delegate_agent.run.call_args
    assert args[0] == "just do it"
    assert "Context:" not in args[0]


@pytest.mark.asyncio
async def test_run_delegation_persists_assistant_message_with_delegate_agent_name(tmp_path, monkeypatch):
    """Logger.add_message for the delegate's response uses agent_name=delegate_id,
    not the orchestrator's name. Pins the per-agent attribution in History."""
    from apps.gui.server import bridge

    session, delegate_agent = _make_session_with_delegation(
        tmp_path, agent_name="JARVIS", delegate_id="writer", delegate_text="written"
    )
    monkeypatch.setattr(bridge, "build_delegate_agent", MagicMock(return_value=delegate_agent))

    await run_turn(session, "go", Queue(maxsize=64))

    add_msg_calls = session.components.logger.add_message.call_args_list
    # Two "assistant" messages: orchestrator's then delegate's.
    assistant_calls = [c for c in add_msg_calls if c.args and c.args[0] == "assistant"]
    assert len(assistant_calls) == 2
    # Last assistant call is the delegate's.
    delegate_call = assistant_calls[-1]
    assert delegate_call.args[1] == "written"
    assert delegate_call.kwargs["agent_name"] == "writer"
    assert delegate_call.kwargs["total_tokens"] == 35
    assert delegate_call.kwargs["cost_usd"] == 0.005


@pytest.mark.asyncio
async def test_run_delegation_persists_tool_messages_with_delegate_agent_name(tmp_path, monkeypatch):
    """When the delegate emits tool_messages, logger.add_tool_messages is called
    with agent_name=delegate_id (not the orchestrator's)."""
    from apps.gui.server import bridge

    tool_messages = [{"role": "tool", "content": "result"}]
    session, delegate_agent = _make_session_with_delegation(
        tmp_path,
        delegate_id="researcher",
        delegate_tool_messages=tool_messages,
    )
    monkeypatch.setattr(bridge, "build_delegate_agent", MagicMock(return_value=delegate_agent))

    await run_turn(session, "go", Queue(maxsize=64))

    # add_tool_messages called twice — once for orchestrator (empty list, NOT called),
    # once for the delegate.
    add_tool_calls = session.components.logger.add_tool_messages.call_args_list
    delegate_call = next((c for c in add_tool_calls if c.kwargs.get("agent_name") == "researcher"), None)
    assert delegate_call is not None
    assert delegate_call.args[0] == tool_messages


@pytest.mark.asyncio
async def test_run_delegation_skips_when_delegate_to_not_in_registry(tmp_path, monkeypatch):
    """If delegate_to is set but the id isn't registered, the bridge silently
    skips delegation — no delegation event, no build_delegate_agent call."""
    from apps.gui.server import bridge

    session = _make_session(tmp_path)
    session.components.active_agent.run.return_value = StreamResult(
        text="x",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        cost_usd=0.0,
        metrics=SimpleNamespace(ttft_ms=10, total_latency_ms=20),
        tool_messages=[],
        delegate_to="ghost_agent",  # not in (empty) registry
    )
    build_mock = MagicMock()
    monkeypatch.setattr(bridge, "build_delegate_agent", build_mock)

    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "go", q)
    events = _drain(q)

    assert all(e["type"] != "delegation" for e in events)
    build_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_delegation_failure_emits_error_event_and_continues(tmp_path, monkeypatch):
    """If the delegate's run() raises, the bridge emits an error event with the
    delegate id in the message and continues to totals/turn_finished."""
    from apps.gui.server import bridge

    session, delegate_agent = _make_session_with_delegation(tmp_path, delegate_id="writer")
    delegate_agent.run.side_effect = RuntimeError("delegate boom")
    monkeypatch.setattr(bridge, "build_delegate_agent", MagicMock(return_value=delegate_agent))

    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "go", q)
    events = _drain(q)
    kinds = [e["type"] for e in events]

    # delegation event still emitted, then thinking_start, then error (not thinking_end/text).
    assert "delegation" in kinds
    err = next(e for e in events if e["type"] == "error")
    assert err["message"] == "Delegate writer failed: delegate boom"
    # Original turn's totals + turn_finished still happen because _run_delegation
    # returns early but run_turn's outer flow continues.
    assert kinds[-2:] == ["totals", "turn_finished"]


@pytest.mark.asyncio
async def test_run_delegation_text_event_dict_keys_are_exact(tmp_path, monkeypatch):
    """Delegate's text event has the canonical key set — pins {type,id,agent,markdown,stats}."""
    from apps.gui.server import bridge

    session, delegate_agent = _make_session_with_delegation(tmp_path, delegate_id="writer")
    monkeypatch.setattr(bridge, "build_delegate_agent", MagicMock(return_value=delegate_agent))

    await run_turn(session, "go", Queue(maxsize=64))

    # Re-drain via the queue would lose ordering; rebuild events list manually.
    q: Queue[dict] = Queue(maxsize=64)
    await run_turn(session, "go", q)
    events = _drain(q)
    delegate_text = [e for e in events if e["type"] == "text" and e.get("agent") == "writer"]
    assert len(delegate_text) == 1
    assert set(delegate_text[0].keys()) == {"type", "id", "agent", "markdown", "stats"}
    # Stats has the canonical sub-keys (defaulted from delegate_result.metrics).
    assert set(delegate_text[0]["stats"].keys()) == {"ttft", "total", "tokens", "cost"}
