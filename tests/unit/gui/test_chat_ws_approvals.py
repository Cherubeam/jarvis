"""Vault-write approvals and cancels that arrive while a turn is running.

The other /ws/chat tests send approval_decision with no turn in flight. Here a
turn runs in a worker thread, like ``bridge.run_turn``, and blocks in the real
``WebConfirmationHandler`` until the client decides. A watchdog stands in for
the user closing the tab: it force-releases the handler after
``WATCHDOG_S``, so a decision the server never reads fails the test instead of
hanging it.
"""

from __future__ import annotations

import asyncio
import threading
import time
from queue import Queue
from types import SimpleNamespace
from typing import Any

import pytest

from apps.gui.server.confirmation import WebConfirmationHandler
from apps.gui.server.routes import chat_ws as chat_ws_module
from tests.unit.gui.test_chat_ws import _connect, _make_session, _skip_handshake

WATCHDOG_S = 3.0


def _diff(path: str) -> SimpleNamespace:
    """Just enough of a VaultDiff for WebConfirmationHandler to emit a card."""
    return SimpleNamespace(file_path=path, summary=f"write {path}", diff_lines=[], link_warnings=[])


def _install_turn(monkeypatch: pytest.MonkeyPatch, paths: list[str], results: list[bool]) -> None:
    """Replace run_turn with one that asks for one approval per path, like bridge.run_turn."""

    async def fake_run_turn(session: Any, text: str, queue: Queue[Any]) -> None:
        handler = WebConfirmationHandler(queue, "u-test")
        session.confirmation = handler
        watchdog = threading.Timer(WATCHDOG_S, handler.discard)
        watchdog.start()

        def worker() -> None:
            for path in paths:
                handler.present_diff(_diff(path))  # type: ignore[arg-type]
                results.append(handler.get_confirmation())

        try:
            await asyncio.to_thread(worker)
        finally:
            watchdog.cancel()
            queue.put({"type": "turn_finished", "id": "u-test"})

    monkeypatch.setattr(chat_ws_module, "run_turn", fake_run_turn)


def _receive_until(ws: Any, kind: str) -> dict[str, Any]:
    while True:
        event = ws.receive_json()
        if event["type"] == kind:
            return event


def test_an_approval_sent_mid_turn_reaches_the_waiting_write(monkeypatch: pytest.MonkeyPatch) -> None:
    results: list[bool] = []
    _install_turn(monkeypatch, ["Inbox/a.md"], results)
    session = _make_session()

    with _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "submit", "text": "write a note"})
        pending = _receive_until(ws, "approval_pending")
        started = time.monotonic()
        ws.send_json({"type": "approval_decision", "id": pending["id"], "approved": True})
        resolved = _receive_until(ws, "approval_resolved")
        elapsed = time.monotonic() - started
        _receive_until(ws, "turn_finished")

    assert resolved == {"type": "approval_resolved", "id": pending["id"], "approved": True}
    assert results == [True]
    assert elapsed < WATCHDOG_S / 2


def test_a_second_write_in_the_same_turn_asks_again(monkeypatch: pytest.MonkeyPatch) -> None:
    results: list[bool] = []
    _install_turn(monkeypatch, ["Inbox/a.md", "Inbox/b.md"], results)
    session = _make_session()

    with _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "submit", "text": "write two notes"})
        first = _receive_until(ws, "approval_pending")
        ws.send_json({"type": "approval_decision", "id": first["id"], "approved": True})
        _receive_until(ws, "approval_resolved")
        second = _receive_until(ws, "approval_pending")
        ws.send_json({"type": "approval_decision", "id": second["id"], "approved": False})
        resolved = _receive_until(ws, "approval_resolved")
        _receive_until(ws, "turn_finished")

    assert second["path"] == "Inbox/b.md"
    assert second["id"] != first["id"]
    assert resolved == {"type": "approval_resolved", "id": second["id"], "approved": False}
    assert results == [True, False]


def test_cancel_mid_turn_releases_the_waiting_write(monkeypatch: pytest.MonkeyPatch) -> None:
    results: list[bool] = []
    _install_turn(monkeypatch, ["Inbox/a.md"], results)
    session = _make_session()

    with _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "submit", "text": "write a note"})
        _receive_until(ws, "approval_pending")
        started = time.monotonic()
        ws.send_json({"type": "cancel"})
        resolved = _receive_until(ws, "approval_resolved")
        elapsed = time.monotonic() - started
        _receive_until(ws, "turn_finished")

    assert resolved["approved"] is False
    assert results == [False]
    assert elapsed < WATCHDOG_S / 2
