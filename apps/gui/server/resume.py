"""Resume an existing conversation in the live chat session.

`load_and_replay` mutates the GUI session's logger so it points back at a
historic conversation file (subsequent saves append rather than starting a
new file), then synthesises the StreamEvents the chat view needs to render
the prior turns.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any

from apps.gui.server.state import GuiSession
from packages.core.memory import ConversationLogger, SessionMetrics, _extract_text_from_content

logger = logging.getLogger(__name__)

# Mirrors apps.gui.server.streaming._truncate's tool-result cap so replayed
# tool cards match the runtime ones.
_TOOL_SUMMARY_CHARS = 240


class ResumeError(Exception):
    """Raised when a resume request can't be satisfied."""


def _path_for_file_id(conversations_dir: Path, file_id: str) -> Path:
    """Resolve a file_id (filename stem) to its on-disk path under YYYY/."""
    if not file_id or "/" in file_id or ".." in file_id:
        raise ResumeError(f"invalid file_id: {file_id!r}")
    year = file_id[:4]
    if not year.isdigit():
        raise ResumeError(f"invalid file_id: {file_id!r}")
    candidate = conversations_dir / year / f"{file_id}.json"
    if not candidate.is_file():
        raise ResumeError(f"conversation not found: {file_id}")
    return candidate


def _parse_session_start(value: str | None, fallback_file_id: str) -> datetime:
    """Best-effort: prefer the JSON's session_start, fall back to the file_id stem."""
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    # file_id stem like "2026-04-29_16-30-00" — parse strictly.
    try:
        return datetime.strptime(fallback_file_id, "%Y-%m-%d_%H-%M-%S")
    except ValueError as e:
        raise ResumeError(f"could not derive session_start from {fallback_file_id!r}") from e


def _metrics_from_dict(d: dict[str, Any]) -> SessionMetrics:
    """Reconstruct a SessionMetrics from its serialised form."""
    m = SessionMetrics()
    m.total_prompt_tokens = int(d.get("total_prompt_tokens") or 0)
    m.total_completion_tokens = int(d.get("total_completion_tokens") or 0)
    m.total_tokens = int(d.get("total_tokens") or 0)
    m.total_cost_usd = float(d.get("total_cost_usd") or 0.0)
    m.total_cache_read_tokens = int(d.get("total_cache_read_tokens") or 0)
    m.total_cache_write_tokens = int(d.get("total_cache_write_tokens") or 0)
    m.total_thinking_tokens = int(d.get("total_thinking_tokens") or 0)
    m.request_count = int(d.get("request_count") or 0)
    m.total_ttft_ms = float(d.get("total_ttft_ms") or 0.0)
    m.total_latency_ms = float(d.get("total_latency_ms") or 0.0)
    return m


def _msg_text(msg: dict[str, Any]) -> str:
    """Extract a plain-text rendering of a message's content, list-or-string."""
    content = msg.get("content")
    if isinstance(content, list):
        return _extract_text_from_content(content)
    return str(content or "")


def _safe_parse_json(raw: Any) -> dict[str, Any]:
    import json as _json

    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        parsed = _json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_replay_events(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate a historic messages list into the StreamEvents the chat view renders.

    Pairs each assistant `tool_calls` entry with the immediately following
    `tool_call_id` message. Non-paired tool messages (orphaned results) are
    skipped silently — they're already represented in the assistant card.
    """
    # Index tool results by tool_call_id for O(1) pairing.
    tool_results: dict[str, dict[str, Any]] = {}
    for m in messages:
        tcid = m.get("tool_call_id")
        if isinstance(tcid, str):
            tool_results[tcid] = m

    events: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        msg_id = str(msg.get("id") or "")

        if role == "user":
            text = _msg_text(msg)
            if text:
                events.append({"type": "user", "id": msg_id, "text": text, "time": ""})
            continue

        if role == "assistant":
            agent = str(msg.get("agent") or "JARVIS")
            tool_calls = msg.get("tool_calls") or []

            for call in tool_calls:
                tc_id = str(call.get("id") or msg_id)
                fn = call.get("function") or {}
                tool_name = str(fn.get("name") or "")
                args = _safe_parse_json(fn.get("arguments"))
                result_msg = tool_results.get(tc_id)
                summary = _msg_text(result_msg) if result_msg else ""
                events.append(
                    {
                        "type": "tool_call",
                        "id": tc_id,
                        "agent": agent,
                        "tool": tool_name,
                        "args": args,
                        "result": {"summary": summary[:_TOOL_SUMMARY_CHARS]},
                        "elapsed_ms": 0,
                        "status": "ok",
                    }
                )

            text = _msg_text(msg)
            if text:
                usage = msg.get("usage") or {}
                latency = msg.get("latency") or {}
                stats: dict[str, Any] = {}
                if usage.get("total_tokens"):
                    stats["tokens"] = int(usage["total_tokens"])
                if usage.get("cost_usd") is not None:
                    stats["cost"] = float(usage["cost_usd"])
                if latency.get("ttft_ms"):
                    stats["ttft"] = int(latency["ttft_ms"])
                if latency.get("total_ms"):
                    stats["total"] = int(latency["total_ms"])
                events.append(
                    {
                        "type": "text",
                        "id": msg_id,
                        "agent": agent,
                        "markdown": text,
                        "stats": stats,
                    }
                )
            continue

        # Tool messages and any other roles are handled via the pairing above
        # or intentionally dropped from the visible replay.

    return events


def load_and_replay(session: GuiSession, file_id: str, queue: Queue[dict[str, Any]]) -> None:
    """Mutate ``session.components.logger`` to point at *file_id*, then push
    a synthetic event stream into *queue* so the client can render the prior
    turns and continue chatting in-place.

    Caller is responsible for the in-flight guard (the running turn would
    overwrite the rebound logger's messages on save).
    """
    components = session.components
    path = _path_for_file_id(Path(components.conversations_dir), file_id)

    raw = ConversationLogger.load(path)  # already runs migrate_conversation
    messages: list[dict[str, Any]] = raw.get("messages", []) or []
    session_start = _parse_session_start(raw.get("session_start"), file_id)
    conversation_id = str(raw.get("id") or components.logger.conversation_id)
    metrics = _metrics_from_dict(raw.get("metrics") or {})

    components.logger.rehydrate(
        messages=messages,
        session_start=session_start,
        conversation_id=conversation_id,
        metrics=metrics,
    )

    # Tell the client to swap context: new file_id → ChatView clears its
    # event buffer and re-binds the session header.
    queue.put({"type": "session_start", "session": session.session_meta()})
    queue.put(
        {
            "type": "system",
            "text": f"Resumed conversation · {file_id} ({len(messages)} prior message(s))",
        }
    )

    for ev in _build_replay_events(messages):
        queue.put(ev)

    # Refresh the session totals strip.
    queue.put(
        {
            "type": "totals",
            "messages": len(messages),
            "tokens": int(metrics.total_tokens),
            "cost": float(metrics.total_cost_usd),
        }
    )

    # Invalidate the History index entry so the sidebar/list pick up any
    # session_end change on next refresh.
    idx = getattr(session, "conversation_index", None)
    if idx is not None:
        try:
            idx.mark_dirty(file_id)
        except Exception:
            logger.debug("mark_dirty failed for %s", file_id, exc_info=True)
