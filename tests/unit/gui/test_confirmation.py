"""Tests for apps.gui.server.confirmation.WebConfirmationHandler."""

import threading
import time
from queue import Queue
from types import SimpleNamespace

from apps.gui.server.confirmation import WebConfirmationHandler


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


def test_get_confirmation_blocks_until_resolve_true_unblocks():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1", agent="JARVIS")
    diff = _fake_diff()
    h.present_diff(diff)

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()))
    worker.start()

    # Wait for the approval_pending event to arrive on the queue.
    for _ in range(50):
        if not q.empty():
            break
        time.sleep(0.01)

    pending = q.get(timeout=1)
    assert pending["type"] == "approval_pending"
    assert pending["path"] == "notes/x.md"
    assert pending["tool"] == "vault_write"
    # diff lines flattened into wire shape
    kinds = [d["kind"] for d in pending["diff"]]
    assert kinds == ["ctx", "add"]

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

    for _ in range(50):
        if not q.empty():
            break
        time.sleep(0.01)

    pending = q.get(timeout=1)
    h.resolve(False, approval_id=pending["id"])
    worker.join(timeout=1)

    assert result == [False]


def test_discard_releases_blocked_worker_as_rejected():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1", agent="JARVIS")
    h.present_diff(_fake_diff())

    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(h.get_confirmation()))
    worker.start()

    for _ in range(50):
        if not q.empty():
            break
        time.sleep(0.01)
    _ = q.get(timeout=1)  # consume approval_pending

    h.discard()
    worker.join(timeout=1)

    assert result == [False]


def test_get_confirmation_without_present_diff_returns_false():
    q: Queue = Queue(maxsize=10)
    h = WebConfirmationHandler(q, turn_id="t1", agent="JARVIS")
    assert h.get_confirmation() is False
