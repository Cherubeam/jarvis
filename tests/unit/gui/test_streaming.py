"""Tests for apps.gui.server.streaming.WebStreamHandler."""

from queue import Queue
from typing import Any

from apps.gui.server.streaming import WebStreamHandler, _safe_parse_json, _truncate
from packages.core.events import (
    AgentFinished,
    TextChunk,
    ToolCallStarted,
    ToolResult,
    UsageReport,
)


def test_text_chunk_emits_chunk_event():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(TextChunk(text="hello"))
    h(TextChunk(text=" world"))

    first = q.get_nowait()
    second = q.get_nowait()
    assert first == {"type": "chunk", "id": "t1", "agent": "JARVIS", "delta": "hello"}
    assert second == {"type": "chunk", "id": "t1", "agent": "JARVIS", "delta": " world"}
    # Strict shape — exactly these four keys, nothing else.
    assert set(first.keys()) == {"type", "id", "agent", "delta"}
    assert h.buffered_text() == "hello world"


def test_text_chunk_uses_current_agent_not_default():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="writer")
    h(TextChunk(text="x"))
    assert q.get_nowait()["agent"] == "writer"


def test_tool_call_pair_emits_single_tool_call_event_with_elapsed():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(ToolCallStarted(tool_name="read_note", tool_call_id="c1", arguments='{"path":"x.md"}'))
    h(ToolResult(tool_name="read_note", tool_call_id="c1", result="Read 42 chars."))

    assert q.qsize() == 1
    ev = q.get_nowait()
    # Strict shape
    assert set(ev.keys()) == {"type", "id", "agent", "tool", "args", "result", "elapsed_ms", "status"}
    assert ev["type"] == "tool_call"
    assert ev["id"] == "c1"
    assert ev["agent"] == "JARVIS"
    assert ev["tool"] == "read_note"
    assert ev["args"] == {"path": "x.md"}
    assert ev["result"] == {"summary": "Read 42 chars."}
    assert ev["status"] == "ok"
    # elapsed_ms is non-negative; >0 in real wall-clock but may be 0 on fast machines.
    assert isinstance(ev["elapsed_ms"], int)
    assert ev["elapsed_ms"] >= 0


def test_unparseable_tool_args_fall_back_to_raw():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(ToolCallStarted(tool_name="noop", tool_call_id="c2", arguments="not-json"))
    h(ToolResult(tool_name="noop", tool_call_id="c2", result="done."))

    ev = q.get_nowait()
    assert ev["args"] == {"_raw": "not-json"}


def test_tool_result_without_started_has_zero_elapsed():
    """Orphaned ToolResult (no preceding Started) → elapsed_ms == 0."""
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(ToolResult(tool_name="probe", tool_call_id="lone", result="x"))
    ev = q.get_nowait()
    assert ev["elapsed_ms"] == 0
    # Falls back to event.tool_name since no pending entry exists.
    assert ev["tool"] == "probe"


def test_tool_result_uses_event_id_when_pending_id_present():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")
    h(ToolCallStarted(tool_name="x", tool_call_id="abc", arguments="{}"))
    h(ToolResult(tool_name="x", tool_call_id="abc", result="r"))
    ev = q.get_nowait()
    assert ev["id"] == "abc"


def test_tool_result_falls_back_to_turn_id_when_event_id_empty():
    """Empty tool_call_id falls back to the current turn_id (avoids broken cards)."""
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="turn-xyz", agent="JARVIS")
    h(ToolResult(tool_name="x", tool_call_id="", result="r"))
    ev = q.get_nowait()
    assert ev["id"] == "turn-xyz"


def test_tool_result_summary_truncated_to_240_chars():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")
    long = "x" * 1000
    h(ToolCallStarted(tool_name="x", tool_call_id="c", arguments="{}"))
    h(ToolResult(tool_name="x", tool_call_id="c", result=long))
    ev = q.get_nowait()
    assert len(ev["result"]["summary"]) == 240
    assert ev["result"]["summary"].endswith("…")


def test_usage_report_stored_for_bridge():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(UsageReport(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.0042))

    # ttft/total come from StreamResult.metrics (filled in by the bridge),
    # not from WebStreamHandler. Only tokens/cost are stashed here.
    assert h.last_usage() == {
        "tokens": 150,
        "cost": 0.0042,
    }
    # No event was put on the queue.
    assert q.empty()


def test_usage_report_falls_back_to_prompt_plus_completion_when_total_zero():
    """total_tokens=0 (or None) → prompt+completion sum."""
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")
    h(UsageReport(prompt_tokens=80, completion_tokens=20, total_tokens=0, cost_usd=0.001))
    assert h.last_usage() == {"tokens": 100, "cost": 0.001}


def test_last_usage_is_none_before_any_usage_report():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")
    assert h.last_usage() is None


def test_agent_finished_is_silently_ignored():
    """No queue event, no exception."""
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")
    h(AgentFinished(instance_id="i1", role="primary"))
    assert q.empty()


def test_buffered_text_empty_when_no_chunks():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")
    assert h.buffered_text() == ""


def test_queue_overflow_drops_oldest():
    q: Queue[dict[str, Any]] = Queue(maxsize=2)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(TextChunk(text="a"))
    h(TextChunk(text="b"))
    h(TextChunk(text="c"))  # overflows — oldest dropped

    remaining = []
    while not q.empty():
        remaining.append(q.get_nowait()["delta"])
    assert remaining == ["b", "c"]
    # Buffered text still contains all three — buffer is independent of the queue.
    assert h.buffered_text() == "abc"


def test_set_turn_resets_buffers_and_pending_state():
    q: Queue[dict[str, Any]] = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(TextChunk(text="first"))
    h(ToolCallStarted(tool_name="x", tool_call_id="c1", arguments="{}"))
    assert h.buffered_text() == "first"

    h.set_turn("t2", "writer")
    assert h.buffered_text() == ""
    # Pending tool-start was cleared — a stray ToolResult now reads as orphan.
    while not q.empty():
        q.get_nowait()
    h(ToolResult(tool_name="x", tool_call_id="c1", result="r"))
    orphan = q.get_nowait()
    assert orphan["elapsed_ms"] == 0  # confirms _tool_started_at was cleared
    # Subsequent chunk uses the new turn_id + agent.
    h(TextChunk(text="second"))
    chunk = q.get_nowait()
    assert chunk["type"] == "chunk"
    assert chunk["id"] == "t2"
    assert chunk["agent"] == "writer"


# ---------------------------------------------------------------------------
# Helpers — _safe_parse_json + _truncate
# ---------------------------------------------------------------------------


def test_safe_parse_json_valid_dict():
    assert _safe_parse_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_safe_parse_json_empty_string_returns_empty_dict():
    assert _safe_parse_json("") == {}


def test_safe_parse_json_invalid_returns_raw_marker():
    assert _safe_parse_json("not-json") == {"_raw": "not-json"}


def test_truncate_below_threshold_returns_unchanged():
    assert _truncate("abc", 10) == "abc"


def test_truncate_at_exact_threshold_returns_unchanged():
    """Boundary: len(s) == n is allowed, no ellipsis."""
    assert _truncate("abc", 3) == "abc"


def test_truncate_above_threshold_uses_ellipsis_and_caps_length():
    out = _truncate("hello-world", 6)
    assert len(out) == 6
    assert out.endswith("…")
    assert out == "hello…"


def test_truncate_empty_string():
    assert _truncate("", 5) == ""
