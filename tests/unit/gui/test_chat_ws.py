"""Tests for the /ws/chat endpoint in apps.gui.server.routes.chat_ws.

Protocol only — the router is mounted on a bare FastAPI app with no auth
middleware, matching the house pattern. Gating of this route is covered in
test_auth_middleware.py and test_app_factory.py.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from queue import Queue
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from apps.gui.server.routes import chat_ws as chat_ws_module
from apps.gui.server.routes.chat_ws import _drain_queue
from apps.gui.server.routes.chat_ws import router as ws_router


def _make_session(*, in_flight: bool = False, confirmation: Any = None) -> SimpleNamespace:
    """A SimpleNamespace shaped like GuiSession, as the WS handler uses it."""
    logger_stub = SimpleNamespace(session_start=datetime(2026, 4, 23, 12, 0, 0))
    components = SimpleNamespace(
        agent_registry={"jarvis": object(), "writer": object()},
        logger=logger_stub,
    )
    return SimpleNamespace(
        components=components,
        started_at="12:00",
        in_flight=in_flight,
        confirmation=confirmation,
        session_meta=lambda: {"id": "conv_abc", "file_id": "2026-04-23_12-00-00"},
    )


def _build_app(session: SimpleNamespace) -> FastAPI:
    app = FastAPI()
    app.state.gui_session = session
    app.include_router(ws_router)
    return app


def _connect(session: SimpleNamespace) -> Any:
    return TestClient(_build_app(session)).websocket_connect("/ws/chat")


def _skip_handshake(ws: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    return ws.receive_json(), ws.receive_json()


# ---------------------------------------------------------------------------
# Handshake


def test_handshake_sends_session_start_then_system() -> None:
    session = _make_session()
    with _connect(session) as ws:
        start = ws.receive_json()
        system = ws.receive_json()

    assert start == {
        "type": "session_start",
        "session": {"id": "conv_abc", "file_id": "2026-04-23_12-00-00"},
    }
    assert system == {
        "type": "system",
        "text": "Session started. 2 agents registered.",
        "time": "12:00",
    }


def test_handshake_agent_count_tracks_the_registry() -> None:
    session = _make_session()
    session.components.agent_registry = {"only_one": object()}
    with _connect(session) as ws:
        ws.receive_json()
        assert ws.receive_json()["text"] == "Session started. 1 agents registered."


# ---------------------------------------------------------------------------
# submit


def test_submit_runs_a_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Any, str]] = []
    in_flight_during: list[bool] = []
    session = _make_session()

    async def fake_run_turn(sess: Any, text: str, queue: Queue[Any]) -> None:
        calls.append((sess, text))
        in_flight_during.append(sess.in_flight)

    monkeypatch.setattr(chat_ws_module, "run_turn", fake_run_turn)

    with _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "submit", "text": "hello"})
        ws.close()

    assert [text for _, text in calls] == ["hello"]
    assert in_flight_during == [True]
    assert session.in_flight is False  # reset in the finally


def test_submit_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def fake_run_turn(sess: Any, text: str, queue: Queue[Any]) -> None:
        seen.append(text)

    monkeypatch.setattr(chat_ws_module, "run_turn", fake_run_turn)

    with _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "submit", "text": "  padded  "})
        ws.close()

    assert seen == ["padded"]


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_submit_ignores_blank_text(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    async def fake_run_turn(sess: Any, body: str, queue: Queue[Any]) -> None:
        called.append(body)  # pragma: no cover — must not run

    monkeypatch.setattr(chat_ws_module, "run_turn", fake_run_turn)

    with _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "submit", "text": text})
        ws.close()

    assert called == []


def test_submit_with_a_missing_text_field_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    async def fake_run_turn(sess: Any, body: str, queue: Queue[Any]) -> None:
        called.append(body)  # pragma: no cover

    monkeypatch.setattr(chat_ws_module, "run_turn", fake_run_turn)

    with _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "submit"})
        ws.close()

    assert called == []


def test_submit_while_in_flight_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    async def fake_run_turn(sess: Any, body: str, queue: Queue[Any]) -> None:
        called.append(body)  # pragma: no cover

    monkeypatch.setattr(chat_ws_module, "run_turn", fake_run_turn)

    with _connect(_make_session(in_flight=True)) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "submit", "text": "hello"})
        assert ws.receive_json() == {
            "type": "error",
            "message": "A turn is already in flight. Cancel first.",
        }

    assert called == []


def test_in_flight_is_reset_when_run_turn_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the finally, one failed turn would wedge the session forever."""
    session = _make_session()

    async def boom(sess: Any, text: str, queue: Queue[Any]) -> None:
        raise RuntimeError("turn exploded")

    monkeypatch.setattr(chat_ws_module, "run_turn", boom)

    with pytest.raises(RuntimeError), _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "submit", "text": "hello"})
        ws.receive_json()

    assert session.in_flight is False


# ---------------------------------------------------------------------------
# resume


def test_resume_replays_the_requested_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_load_and_replay(sess: Any, file_id: str, queue: Queue[Any]) -> None:
        seen.append(file_id)

    monkeypatch.setattr(chat_ws_module, "load_and_replay", fake_load_and_replay)

    with _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "resume", "file_id": "2026-04-01_10-00-00"})
        ws.close()

    assert seen == ["2026-04-01_10-00-00"]


def test_resume_defaults_to_an_empty_file_id(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        chat_ws_module,
        "load_and_replay",
        lambda sess, file_id, queue: seen.append(file_id),
    )

    with _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "resume"})
        ws.close()

    assert seen == [""]


def test_resume_while_in_flight_is_refused() -> None:
    with _connect(_make_session(in_flight=True)) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "resume", "file_id": "x"})
        assert ws.receive_json() == {
            "type": "error",
            "message": "A turn is in flight — wait for it to finish before resuming.",
        }


def test_resume_error_is_forwarded_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_resume_error(sess: Any, file_id: str, queue: Queue[Any]) -> None:
        raise chat_ws_module.ResumeError("no such conversation: x")

    monkeypatch.setattr(chat_ws_module, "load_and_replay", raise_resume_error)

    with _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "resume", "file_id": "x"})
        assert ws.receive_json() == {
            "type": "error",
            "message": "no such conversation: x",
        }


def test_unexpected_resume_failure_is_hidden_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An unexpected exception must not leak its text to the client."""

    def boom(sess: Any, file_id: str, queue: Queue[Any]) -> None:
        raise ValueError("internal detail that should not reach the browser")

    monkeypatch.setattr(chat_ws_module, "load_and_replay", boom)

    with caplog.at_level(logging.ERROR, logger="apps.gui.server.routes.chat_ws"), _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "resume", "file_id": "x"})
        assert ws.receive_json() == {
            "type": "error",
            "message": "resume failed — see server logs",
        }

    assert any("resume failed for" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# approval_decision


def test_approval_decision_forwards_the_id_and_verdict() -> None:
    confirmation = MagicMock()
    confirmation.resolve.return_value = True
    session = _make_session(confirmation=confirmation)

    with _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "approval_decision", "id": "abc", "approved": True})
        ws.close()

    confirmation.resolve.assert_called_once_with(True, approval_id="abc")


def test_approval_decision_defaults_to_not_approved() -> None:
    confirmation = MagicMock()
    confirmation.resolve.return_value = True
    session = _make_session(confirmation=confirmation)

    with _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "approval_decision", "id": "abc"})
        ws.close()

    confirmation.resolve.assert_called_once_with(False, approval_id="abc")


def test_a_rejected_approval_decision_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """A stale tab or a client omitting the id must be visible, not silent."""
    confirmation = MagicMock()
    confirmation.resolve.return_value = False
    session = _make_session(confirmation=confirmation)

    with caplog.at_level(logging.WARNING, logger="apps.gui.server.routes.chat_ws"), _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "approval_decision", "approved": True})
        ws.close()

    assert any("stale id" in r.getMessage() for r in caplog.records)


def test_an_accepted_approval_decision_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    confirmation = MagicMock()
    confirmation.resolve.return_value = True
    session = _make_session(confirmation=confirmation)

    with caplog.at_level(logging.WARNING, logger="apps.gui.server.routes.chat_ws"), _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "approval_decision", "id": "abc", "approved": True})
        ws.close()

    assert not any("stale id" in r.getMessage() for r in caplog.records)


def test_approval_decision_without_a_confirmation_handler_is_a_noop() -> None:
    with _connect(_make_session(confirmation=None)) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "approval_decision", "id": "abc", "approved": True})
        ws.send_json({"type": "ping-to-prove-we-survived"})
        ws.close()


# ---------------------------------------------------------------------------
# cancel


def test_cancel_discards_the_pending_approval() -> None:
    confirmation = MagicMock()
    session = _make_session(confirmation=confirmation)

    with _connect(session) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "cancel"})
        ws.close()

    assert confirmation.discard.call_count >= 1


# ---------------------------------------------------------------------------
# Malformed and unknown messages


def test_non_json_is_dropped_and_the_socket_survives(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.routes.chat_ws"), _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_text("not json at all")
        ws.send_json({"type": "resume", "file_id": ""})  # proves the loop continues
        ws.receive_json()

    assert any("dropped non-JSON ws message" in r.getMessage() for r in caplog.records)


def test_an_unknown_message_kind_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.routes.chat_ws"), _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_json({"type": "teleport"})
        ws.close()

    assert any("unknown ws message kind: 'teleport'" in r.getMessage() for r in caplog.records)


def test_a_message_without_a_type_is_treated_as_unknown(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.routes.chat_ws"), _connect(_make_session()) as ws:
        _skip_handshake(ws)
        ws.send_json({"no": "type"})
        ws.close()

    assert any("unknown ws message kind: None" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# Disconnect cleanup


def test_disconnect_discards_any_pending_approval() -> None:
    """Otherwise a worker thread stays blocked on the approval event forever."""
    confirmation = MagicMock()
    session = _make_session(confirmation=confirmation)

    with _connect(session) as ws:
        _skip_handshake(ws)

    confirmation.discard.assert_called_once_with()


def test_disconnect_without_a_confirmation_handler_is_clean() -> None:
    with _connect(_make_session(confirmation=None)) as ws:
        _skip_handshake(ws)


# ---------------------------------------------------------------------------
# _drain_queue


async def test_drain_queue_forwards_payloads() -> None:
    queue: Queue[dict[str, Any]] = Queue()
    queue.put({"type": "chunk", "text": "hi"})
    websocket = MagicMock()
    sent: list[dict[str, Any]] = []

    async def send_json(payload: dict[str, Any]) -> None:
        sent.append(payload)
        raise WebSocketDisconnect(1000)  # stop the loop after one payload

    websocket.send_json = send_json
    await _drain_queue(queue, websocket)

    assert sent == [{"type": "chunk", "text": "hi"}]


async def test_drain_queue_returns_quietly_on_disconnect() -> None:
    queue: Queue[dict[str, Any]] = Queue()
    queue.put({"type": "chunk"})
    websocket = MagicMock()

    async def send_json(payload: dict[str, Any]) -> None:
        raise WebSocketDisconnect(1006)

    websocket.send_json = send_json
    await _drain_queue(queue, websocket)  # must not raise


async def test_drain_queue_logs_and_stops_on_a_send_failure(caplog: pytest.LogCaptureFixture) -> None:
    queue: Queue[dict[str, Any]] = Queue()
    queue.put({"type": "chunk"})
    websocket = MagicMock()

    async def send_json(payload: dict[str, Any]) -> None:
        raise RuntimeError("socket exploded")

    websocket.send_json = send_json

    with caplog.at_level(logging.ERROR, logger="apps.gui.server.routes.chat_ws"):
        await _drain_queue(queue, websocket)

    assert any("ws send failed" in r.getMessage() for r in caplog.records)


async def test_drain_queue_logs_and_breaks_when_the_queue_raises(caplog: pytest.LogCaptureFixture) -> None:
    queue = MagicMock()
    queue.get.side_effect = RuntimeError("queue exploded")

    with caplog.at_level(logging.ERROR, logger="apps.gui.server.routes.chat_ws"):
        await _drain_queue(queue, MagicMock())

    assert any("drain loop crashed" in r.getMessage() for r in caplog.records)


async def test_drain_queue_keeps_polling_an_empty_queue() -> None:
    """Empty is the normal idle case — it must continue, not exit."""
    queue: Queue[dict[str, Any]] = Queue()
    websocket = MagicMock()
    sent: list[dict[str, Any]] = []

    async def send_json(payload: dict[str, Any]) -> None:
        sent.append(payload)
        raise WebSocketDisconnect(1000)

    websocket.send_json = send_json
    task = asyncio.create_task(_drain_queue(queue, websocket))

    # Idle across at least one 0.25s poll timeout, then deliver.
    await asyncio.sleep(0.35)
    assert not task.done()
    queue.put({"type": "chunk", "text": "late"})
    await asyncio.wait_for(task, timeout=2)

    assert sent == [{"type": "chunk", "text": "late"}]
