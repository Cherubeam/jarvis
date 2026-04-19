"""
WebStreamHandler — bridges packages.core.stream_handler.StreamHandler events
into a thread-safe queue that the FastAPI side drains and pushes over WS.

We subscribe to the typed `on_event` bus (TextChunk/ToolCallStarted/ToolResult/
UsageReport/AgentFinished). The CLI's spinner-control hooks (on_before_tool_exec,
on_after_tool_exec) and the legacy on_tool_call/on_chunk callbacks are not
wired — leaving on_tool_call=None silences the `print(f"[Tool: ...]")` fallback
in stream_handler.py:264, :523 from leaking into server stdout.

The queue is bounded (maxsize=1024). On overflow, we drop oldest events with a
warning so a slow WS client cannot OOM the server.
"""

from __future__ import annotations

import json
import logging
import time
from queue import Full, Queue
from typing import Any

from packages.core.events import (
    AgentFinished,
    Event,
    TextChunk,
    ToolCallStarted,
    ToolResult,
    UsageReport,
)

logger = logging.getLogger(__name__)


def _now_hhmm() -> str:
    return time.strftime("%H:%M")


class WebStreamHandler:
    """Subscribes to StreamHandler.on_event and queues protocol events.

    Each `Event` is mapped to a server-protocol dict and put on the queue.
    The bridge maintains the agent-name + active turn-id context outside this
    class — we just stamp what we know and let the bridge enrich.
    """

    def __init__(self, queue: Queue[dict[str, Any]], turn_id: str, agent: str) -> None:
        self._queue = queue
        self._turn_id = turn_id
        self._agent = agent
        # Pending tool calls keyed by tool_call_id so we can pair Started with Result.
        self._pending: dict[str, dict[str, Any]] = {}
        self._tool_started_at: dict[str, float] = {}
        self._chunk_buffer: list[str] = []

    # -- public API used by the bridge ---------------------------------------

    def set_turn(self, turn_id: str, agent: str) -> None:
        """Refresh per-turn context (called by bridge between turns)."""
        self._turn_id = turn_id
        self._agent = agent
        self._chunk_buffer = []
        self._pending.clear()
        self._tool_started_at.clear()

    def buffered_text(self) -> str:
        """Concatenate all chunks emitted during the current turn (used to build
        the final 'text' event with stats)."""
        return "".join(self._chunk_buffer)

    # -- on_event sink -------------------------------------------------------

    def __call__(self, event: Event) -> None:
        """Route a typed event to a wire-protocol dict on the queue."""
        try:
            if isinstance(event, TextChunk):
                self._chunk_buffer.append(event.text)
                self._put({
                    "type": "chunk",
                    "id": self._turn_id,
                    "agent": self._agent,
                    "delta": event.text,
                })
            elif isinstance(event, ToolCallStarted):
                started = time.monotonic()
                self._tool_started_at[event.tool_call_id] = started
                self._pending[event.tool_call_id] = {
                    "tool": event.tool_name,
                    "args_raw": event.arguments,
                }
            elif isinstance(event, ToolResult):
                started = self._tool_started_at.pop(event.tool_call_id, None)
                elapsed_ms = int((time.monotonic() - started) * 1000) if started else 0
                pending = self._pending.pop(event.tool_call_id, {})
                self._put({
                    "type": "tool_call",
                    "id": event.tool_call_id or self._turn_id,
                    "agent": self._agent,
                    "tool": pending.get("tool", event.tool_name),
                    "args": _safe_parse_json(pending.get("args_raw", "")),
                    "result": {"summary": _truncate(event.result, 240)},
                    "elapsed_ms": elapsed_ms,
                    "status": "ok",
                })
            elif isinstance(event, UsageReport):
                # Stash for the bridge to attach to the final TextEvent.
                self._last_usage = {
                    "tokens": event.total_tokens or (event.prompt_tokens + event.completion_tokens),
                    "cost": event.cost_usd,
                    "ttft": 0,  # Filled in by bridge from StreamResult.metrics
                    "total": 0,
                }
            elif isinstance(event, AgentFinished):
                # Agent-finished is informational; no wire event in Phase 1.
                pass
        except Exception:  # never let a bad event break the worker
            logger.exception("WebStreamHandler failed to route event")

    def last_usage(self) -> dict[str, Any] | None:
        return getattr(self, "_last_usage", None)

    # -- internal ------------------------------------------------------------

    def _put(self, payload: dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(payload)
        except Full:
            logger.warning("WS event queue full; dropping oldest")
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(payload)
            except Exception:
                logger.exception("Failed to recover from full queue")


def _safe_parse_json(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"
