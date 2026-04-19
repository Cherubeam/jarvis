"""Tests for apps.gui.server.streaming.WebStreamHandler."""

from queue import Queue

from apps.gui.server.streaming import WebStreamHandler
from packages.core.events import TextChunk, ToolCallStarted, ToolResult, UsageReport


def test_text_chunk_emits_chunk_event():
    q = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(TextChunk(text="hello"))
    h(TextChunk(text=" world"))

    first = q.get_nowait()
    second = q.get_nowait()
    assert first == {"type": "chunk", "id": "t1", "agent": "JARVIS", "delta": "hello"}
    assert second == {"type": "chunk", "id": "t1", "agent": "JARVIS", "delta": " world"}
    assert h.buffered_text() == "hello world"


def test_tool_call_pair_emits_single_tool_call_event_with_elapsed():
    q = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(ToolCallStarted(tool_name="read_note", tool_call_id="c1", arguments='{"path":"x.md"}'))
    h(ToolResult(tool_name="read_note", tool_call_id="c1", result="Read 42 chars."))

    assert q.qsize() == 1
    ev = q.get_nowait()
    assert ev["type"] == "tool_call"
    assert ev["id"] == "c1"
    assert ev["agent"] == "JARVIS"
    assert ev["tool"] == "read_note"
    assert ev["args"] == {"path": "x.md"}
    assert ev["result"] == {"summary": "Read 42 chars."}
    assert ev["status"] == "ok"
    assert isinstance(ev["elapsed_ms"], int)


def test_unparseable_tool_args_fall_back_to_raw():
    q = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(ToolCallStarted(tool_name="noop", tool_call_id="c2", arguments="not-json"))
    h(ToolResult(tool_name="noop", tool_call_id="c2", result="done."))

    ev = q.get_nowait()
    assert ev["args"] == {"_raw": "not-json"}


def test_usage_report_stored_for_bridge():
    q = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(UsageReport(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.0042))

    # ttft/total come from StreamResult.metrics (filled in by the bridge),
    # not from WebStreamHandler. Only tokens/cost are stashed here.
    assert h.last_usage() == {
        "tokens": 150,
        "cost": 0.0042,
    }


def test_queue_overflow_drops_oldest():
    q = Queue(maxsize=2)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(TextChunk(text="a"))
    h(TextChunk(text="b"))
    h(TextChunk(text="c"))  # overflows — oldest dropped

    remaining = []
    while not q.empty():
        remaining.append(q.get_nowait()["delta"])
    assert remaining == ["b", "c"]
    assert h.buffered_text() == "abc"


def test_set_turn_resets_buffers():
    q = Queue(maxsize=10)
    h = WebStreamHandler(q, turn_id="t1", agent="JARVIS")

    h(TextChunk(text="first"))
    assert h.buffered_text() == "first"

    h.set_turn("t2", "writer")
    assert h.buffered_text() == ""
    h(TextChunk(text="second"))
    while not q.empty():
        q.get_nowait()
