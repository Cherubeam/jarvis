"""Tests for apps.gui.server.confirmation.WebConfirmationHandler."""

import threading
import time
from queue import Queue
from types import SimpleNamespace

from apps.gui.server.confirmation import WebConfirmationHandler, _diff_lines


def _fake_diff(lines=None, path="notes/x.md", summary="+1 line"):
    return SimpleNamespace(
        lines=lines
        or [
            SimpleNamespace(kind="ctx", text="existing"),
            SimpleNamespace(kind="add", text="new line"),
        ],
        path=path,
        summary=summary,
    )


def _wait_for_queue(q: Queue, deadline_s: float = 1.0) -> None:
    """Spin until the queue has at least one item, with a hard deadline."""
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        if not q.empty():
            return
        time.sleep(0.005)
    raise AssertionError("queue stayed empty past deadline")


# ---------------------------------------------------------------------------
# Happy path: present_diff → get_confirmation → resolve(True) → returns True
# ---------------------------------------------------------------------------


def test_get_confirmation_blocks_until_resolve_true_unblocks():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1", agent="JARVIS")
    diff = _fake_diff()
    h.present_diff(diff)

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()))
    worker.start()

    _wait_for_queue(q)

    pending = q.get(timeout=1)
    # Strict shape — every key matters because the WS contract depends on it.
    assert set(pending.keys()) == {"type", "id", "tool", "agent", "path", "diff", "summary"}
    assert pending["type"] == "approval_pending"
    assert pending["tool"] == "vault_write"
    assert pending["agent"] == "JARVIS"
    assert pending["path"] == "notes/x.md"
    assert pending["summary"] == "+1 line"
    # Diff lines flattened with both "kind" and "text" keys preserved.
    assert pending["diff"] == [
        {"kind": "ctx", "text": "existing"},
        {"kind": "add", "text": "new line"},
    ]
    # ID is the uuid the handler exposes via pending_id().
    assert pending["id"] == h.pending_id()
    assert isinstance(pending["id"], str)
    assert len(pending["id"]) >= 32  # uuid4 string

    h.resolve(True, approval_id=pending["id"])
    worker.join(timeout=1)

    assert result == [True]
    resolved = q.get(timeout=1)
    assert resolved == {"type": "approval_resolved", "id": pending["id"], "approved": True}


def test_resolve_false_rejects():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1", agent="JARVIS")
    h.present_diff(_fake_diff())

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()))
    worker.start()

    _wait_for_queue(q)
    pending = q.get(timeout=1)
    h.resolve(False, approval_id=pending["id"])
    worker.join(timeout=1)

    assert result == [False]
    resolved = q.get(timeout=1)
    assert resolved == {"type": "approval_resolved", "id": pending["id"], "approved": False}


def test_discard_releases_blocked_worker_as_rejected():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1", agent="JARVIS")
    h.present_diff(_fake_diff())

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()))
    worker.start()

    _wait_for_queue(q)
    _ = q.get(timeout=1)  # consume approval_pending

    h.discard()
    worker.join(timeout=1)

    assert result == [False]
    resolved = q.get(timeout=1)
    assert resolved["approved"] is False


def test_discard_is_noop_when_already_resolved():
    """discard() must not double-fire resolve once the event is already set."""
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1", agent="JARVIS")
    h.present_diff(_fake_diff())

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()))
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)

    # First resolve, then a stale discard — second call must NOT enqueue another
    # approval_resolved event.
    h.resolve(True, approval_id=pending["id"])
    worker.join(timeout=1)
    _ = q.get(timeout=1)  # the one approval_resolved we expect

    h.discard()
    assert q.empty()


def test_get_confirmation_without_present_diff_returns_false():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1", agent="JARVIS")
    # Default prompt path — exercises the bool default.
    assert h.get_confirmation() is False
    # Same with an explicit prompt — the absent-diff guard wins.
    assert h.get_confirmation("Are you sure?") is False
    # Neither call enqueues anything.
    assert q.empty()


# ---------------------------------------------------------------------------
# Custom agent name carries through to the approval_pending event
# ---------------------------------------------------------------------------


def test_custom_agent_appears_in_approval_pending_event():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1", agent="writer")
    h.present_diff(_fake_diff())

    worker = threading.Thread(target=h.get_confirmation, daemon=True)
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)
    h.discard()
    worker.join(timeout=1)

    assert pending["agent"] == "writer"


# ---------------------------------------------------------------------------
# Empty path / summary attributes — fall back to "" and prompt respectively
# ---------------------------------------------------------------------------


def test_missing_path_attribute_emits_empty_path():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")
    diff = _fake_diff(path=None)
    h.present_diff(diff)

    worker = threading.Thread(target=h.get_confirmation, daemon=True)
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)
    h.discard()
    worker.join(timeout=1)

    assert pending["path"] == ""


def test_missing_summary_falls_back_to_prompt():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")
    diff = _fake_diff(summary=None)
    h.present_diff(diff)

    worker = threading.Thread(
        target=lambda: h.get_confirmation(prompt="custom-prompt"),
        daemon=True,
    )
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)
    h.discard()
    worker.join(timeout=1)

    assert pending["summary"] == "custom-prompt"


def test_default_agent_is_jarvis():
    """Constructor default must remain "JARVIS" — design contract."""
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")  # no agent= kwarg
    h.present_diff(_fake_diff())

    worker = threading.Thread(target=h.get_confirmation, daemon=True)
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)
    h.discard()
    worker.join(timeout=1)

    assert pending["agent"] == "JARVIS"


# ---------------------------------------------------------------------------
# resolve() approval_id mismatch — must NOT release the worker
# ---------------------------------------------------------------------------


def test_resolve_with_wrong_approval_id_does_not_unblock():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")
    h.present_diff(_fake_diff())

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()))
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)

    # Stale approval — worker should still be blocked.
    accepted = h.resolve(True, approval_id="wrong-id")
    assert accepted is False
    worker.join(timeout=0.05)
    assert worker.is_alive()
    assert result == []

    # Now resolve with the right id — worker exits.
    h.resolve(True, approval_id=pending["id"])
    worker.join(timeout=1)
    assert result == [True]


def test_resolve_without_approval_id_is_rejected():
    """A decision naming no id must NOT resolve the pending approval.

    discard() is the sanctioned force-release path (bridge / WS handler call it
    on disconnect and turn end); resolve() is the client-decision path and
    requires an exact id match.
    """
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")
    h.present_diff(_fake_diff())

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()))
    worker.start()
    _wait_for_queue(q)
    _ = q.get(timeout=1)

    accepted = h.resolve(False)  # no approval_id kwarg
    assert accepted is False
    worker.join(timeout=0.05)
    assert worker.is_alive()
    assert result == []

    # discard() is what actually releases it.
    h.discard()
    worker.join(timeout=1)
    assert result == [False]


def test_resolve_without_approval_id_cannot_approve_pending_write():
    """Regression: the approval-hijack path.

    A client that sends {"approved": true} with no id used to approve whatever
    vault write happened to be pending — a stale tab or racing reconnect could
    authorize a write it never saw.
    """
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")
    h.present_diff(_fake_diff())

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()), daemon=True)
    worker.start()
    _wait_for_queue(q)
    _ = q.get(timeout=1)

    assert h.resolve(True) is False
    worker.join(timeout=0.05)
    assert worker.is_alive()
    assert result == []
    assert q.empty()  # no approval_resolved event escaped

    h.discard()
    worker.join(timeout=1)
    assert result == [False]


def test_resolve_before_anything_pending_is_rejected():
    """Regression: the pre-arm hijack.

    A decision arriving before any approval is pending used to set the event,
    so the NEXT get_confirmation() returned True at once without ever emitting
    approval_pending — an unprompted, invisible vault write.
    """
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")

    assert h.pending_id() is None
    assert h.resolve(True, approval_id="anything") is False
    assert h.resolve(True) is False

    # The event must NOT be pre-armed: a subsequent approval still blocks.
    h.present_diff(_fake_diff())
    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()), daemon=True)
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)
    assert pending["type"] == "approval_pending"

    worker.join(timeout=0.05)
    assert worker.is_alive()
    assert result == []

    h.resolve(True, approval_id=pending["id"])
    worker.join(timeout=1)
    assert result == [True]


def test_resolve_after_discard_returns_false():
    """Once discarded, a late decision must not flip the outcome."""
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")
    h.present_diff(_fake_diff())

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()), daemon=True)
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)

    h.discard()
    worker.join(timeout=1)
    assert result == [False]

    # The id still matches, so resolve() returns True, but the worker is gone
    # and the recorded outcome stays False for the caller that already read it.
    assert h.resolve(True, approval_id=pending["id"]) is True
    assert result == [False]


def test_second_confirmation_in_same_turn_replays_first_decision():
    """Known limitation, pinned so a fix is a deliberate change.

    Neither _event nor _pending_id is reset after a decision, and bridge.py
    creates one handler per TURN, not per tool call. So a second vault write in
    the same turn returns the first decision without prompting. Tracked as a
    separate AON-01 roadmap item.
    """
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")
    h.present_diff(_fake_diff())

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()), daemon=True)
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)
    h.resolve(True, approval_id=pending["id"])
    worker.join(timeout=1)
    assert result == [True]
    _ = q.get(timeout=1)  # approval_resolved

    # Second write in the same turn: returns immediately, reusing the decision.
    h.present_diff(_fake_diff(path="second.md"))
    assert h.get_confirmation() is True


# ---------------------------------------------------------------------------
# pending_id() lifecycle
# ---------------------------------------------------------------------------


def test_pending_id_starts_none_and_populates_on_get_confirmation():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")
    assert h.pending_id() is None

    h.present_diff(_fake_diff())
    worker = threading.Thread(target=h.get_confirmation, daemon=True)
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)

    assert h.pending_id() == pending["id"]
    h.discard()
    worker.join(timeout=1)


def test_present_diff_overwrites_buffered_diff():
    """Two consecutive present_diff calls — only the latest is sent."""
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1")
    first = _fake_diff(path="first.md")
    second = _fake_diff(path="second.md")
    h.present_diff(first)
    h.present_diff(second)

    worker = threading.Thread(target=h.get_confirmation, daemon=True)
    worker.start()
    _wait_for_queue(q)
    pending = q.get(timeout=1)
    h.discard()
    worker.join(timeout=1)

    assert pending["path"] == "second.md"


# ---------------------------------------------------------------------------
# _diff_lines fallback path (no .lines attribute → parse diff_text)
# ---------------------------------------------------------------------------


def test_diff_lines_fallback_parses_unified_diff_text():
    """Diffs without a structured `.lines` attr fall back to text parsing."""
    diff = SimpleNamespace(
        diff_text=("--- a/notes/x.md\n+++ b/notes/x.md\n@@ -1,2 +1,3 @@\n context line\n-old line\n+new line\n"),
        path="notes/x.md",
    )
    out = _diff_lines(diff)

    # Full event sequence — order preserved, header lines kept verbatim as ctx,
    # real add/del lines stripped of their leading +/- char.
    assert out == [
        {"kind": "ctx", "text": "--- a/notes/x.md"},
        {"kind": "ctx", "text": "+++ b/notes/x.md"},
        {"kind": "ctx", "text": "@@ -1,2 +1,3 @@"},
        {"kind": "ctx", "text": " context line"},
        {"kind": "del", "text": "old line"},
        {"kind": "add", "text": "new line"},
    ]


def test_diff_lines_fallback_uses_str_when_no_diff_text():
    """Last-ditch fallback: parse __str__ output."""

    class _StrOnly:
        def __str__(self) -> str:
            return "+added\n-removed"

    out = _diff_lines(_StrOnly())  # type: ignore[arg-type]
    assert out == [
        {"kind": "add", "text": "added"},
        {"kind": "del", "text": "removed"},
    ]


def test_diff_lines_structured_uses_kind_and_text_attrs():
    """Structured `.lines` carries (kind, text) attributes through unchanged."""
    diff = _fake_diff(
        lines=[
            SimpleNamespace(kind="ctx", text="A"),
            SimpleNamespace(kind="add", text="B"),
            SimpleNamespace(kind="del", text="C"),
        ],
    )
    out = _diff_lines(diff)
    assert out == [
        {"kind": "ctx", "text": "A"},
        {"kind": "add", "text": "B"},
        {"kind": "del", "text": "C"},
    ]


def test_diff_lines_structured_defaults_when_attrs_missing():
    """Lines that lack `kind`/`text` attrs get sensible defaults."""

    class _Bare:
        pass

    diff = SimpleNamespace(lines=[_Bare()])
    out = _diff_lines(diff)
    assert out == [{"kind": "ctx", "text": ""}]
