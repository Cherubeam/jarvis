"""WebSocket endpoint for the chat stream."""

from __future__ import annotations

import asyncio
import json
import logging
from queue import Empty, Queue
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from apps.gui.server.bridge import run_turn

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    session = websocket.app.state.gui_session

    # Tell the client about the session so it can render the header.
    await websocket.send_json({"type": "session_start", "session": session.session_meta()})
    await websocket.send_json(
        {
            "type": "system",
            "text": (f"Session started. {len(session.components.agent_registry)} agents registered."),
            "time": session.started_at,
        }
    )

    queue: Queue[dict[str, Any]] = Queue(maxsize=1024)
    drain_task = asyncio.create_task(_drain_queue(queue, websocket))

    try:
        while True:
            try:
                msg_text = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            try:
                msg = json.loads(msg_text)
            except json.JSONDecodeError:
                logger.warning("dropped non-JSON ws message")
                continue

            kind = msg.get("type")
            if kind == "submit":
                if session.in_flight:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "A turn is already in flight. Cancel first.",
                        }
                    )
                    continue
                user_text = msg.get("text", "").strip()
                if not user_text:
                    continue
                session.in_flight = True
                try:
                    await run_turn(session, user_text, queue)
                finally:
                    session.in_flight = False
            elif kind == "approval_decision":
                if session.confirmation is not None:
                    session.confirmation.resolve(
                        bool(msg.get("approved", False)),
                        approval_id=msg.get("id"),
                    )
            elif kind == "cancel":
                # Best-effort: stops event dispatch by replacing the on_event sink.
                # The in-flight LLM call will continue in the worker thread (see
                # the plan's "cancel/interrupt" caveat).
                if session.confirmation is not None:
                    session.confirmation.discard()
            else:
                logger.warning("unknown ws message kind: %r", kind)
    finally:
        drain_task.cancel()
        # Clean up any pending approval so the worker thread can exit.
        if session.confirmation is not None:
            session.confirmation.discard()


async def _drain_queue(queue: Queue[dict[str, Any]], websocket: WebSocket) -> None:
    """Continuously drain the worker-thread queue and forward to the WS."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            payload = await loop.run_in_executor(None, queue.get, True, 0.25)
        except Empty:
            continue
        except Exception:
            logger.exception("drain loop crashed")
            break
        try:
            await websocket.send_json(payload)
        except WebSocketDisconnect:
            return
        except Exception:
            logger.exception("ws send failed")
            return
