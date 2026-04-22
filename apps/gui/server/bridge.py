"""
Per-turn orchestration: takes user input → runs agent.run() in a worker thread
→ pumps StreamHandler typed events through WebStreamHandler → emits the
finalized text + stats event → persists to ConversationLogger → handles
single-shot delegation.

Mirrors the CLI's chat-loop body in apps/cli/main.py:1172-1270 but adapted
for the async/event-pumped GUI environment.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from queue import Queue
from typing import Any

from apps.gui.server.confirmation import WebConfirmationHandler
from apps.gui.server.session_factory_helpers import build_delegate_agent
from apps.gui.server.state import GuiSession
from apps.gui.server.streaming import WebStreamHandler
from packages.core.history import summarize_history, trim_tool_results
from packages.core.model_resolver import resolve_model

logger = logging.getLogger(__name__)


def _now_hhmm() -> str:
    return time.strftime("%H:%M")


async def run_turn(session: GuiSession, user_text: str, queue: Queue[dict[str, Any]]) -> None:
    """Run one user turn end-to-end.

    Emits events into the queue:
      thinking_start → chunk... → text (with stats) → tool_call... →
      [optional: delegation → another text] → totals → turn_finished
    """
    components = session.components
    agent_name = components.agent_name
    turn_id = f"u-{uuid.uuid4().hex[:8]}"

    # Emit user echo
    queue.put({"type": "user", "id": turn_id, "text": user_text, "time": _now_hhmm()})

    # Bind WebConfirmationHandler so the deferred handler routes to it.
    confirmation = WebConfirmationHandler(queue, turn_id, agent=agent_name)
    session.confirmation = confirmation
    deferred = _find_deferred_handler(session)
    if deferred is not None:
        deferred.bind(confirmation)

    web_stream = WebStreamHandler(queue, turn_id, agent=agent_name)
    components.stream_handler.on_event = web_stream

    queue.put({"type": "thinking_start", "agent": agent_name})
    try:
        result = await asyncio.to_thread(_run_one_turn, session, user_text)
    except Exception as e:
        logger.exception("Turn failed")
        queue.put({"type": "error", "id": turn_id, "message": str(e)})
        queue.put({"type": "turn_finished", "id": turn_id})
        confirmation.discard()
        if deferred is not None:
            deferred.unbind()
        return

    queue.put({"type": "thinking_end", "agent": agent_name})

    # Final text event with stats from the buffered chunks + last UsageReport.
    final_text = web_stream.buffered_text() or result.text
    stats = web_stream.last_usage() or {}
    stats.setdefault("ttft", int(getattr(result.metrics, "ttft_ms", 0) or 0))
    stats.setdefault("total", int(getattr(result.metrics, "total_latency_ms", 0) or 0))
    if "tokens" not in stats and getattr(result, "usage", None) is not None:
        stats["tokens"] = result.usage.total_tokens or (result.usage.prompt_tokens + result.usage.completion_tokens)
    if "cost" not in stats:
        stats["cost"] = float(result.cost_usd or 0.0)

    queue.put(
        {
            "type": "text",
            "id": turn_id,
            "agent": agent_name,
            "markdown": final_text,
            "stats": stats,
        }
    )

    # Persist to logger (mirroring apps/cli/main.py:1222-1237)
    if result.tool_messages:
        components.logger.add_tool_messages(result.tool_messages, agent_name=agent_name)
    components.logger.add_message(
        "assistant",
        result.text,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
        cache_read_tokens=result.usage.cache_read_tokens,
        cache_write_tokens=result.usage.cache_write_tokens,
        cost_usd=result.cost_usd,
        ttft_ms=getattr(result.metrics, "ttft_ms", 0),
        total_latency_ms=getattr(result.metrics, "total_latency_ms", 0),
        agent_name=agent_name,
    )
    if components.context_metadata and result.text:
        section_names = [s.name for s in components.context_metadata.sections]
        components.logger.record_utilization(result.text, section_names)

    # Single-shot delegation (Phase 1: no interactive sub-loop).
    if result.delegate_to and result.delegate_to in components.agent_registry:
        await _run_delegation(session, queue, turn_id, result)

    # Save the conversation file every turn (long-lived server, no process-exit
    # finally to rely on).
    try:
        components.logger.save()
    except Exception:
        logger.exception("logger.save() failed")

    # Invalidate the current session's summary in the History index so the
    # sidebar + /api/conversations reflect this turn on the next fetch.
    _mark_current_dirty(session)

    # Totals — current_conversation is list[dict]; metrics lives on logger.metrics.
    queue.put(
        {
            "type": "totals",
            "messages": len(components.logger.current_conversation),
            "tokens": int(components.logger.metrics.total_tokens or 0),
            "cost": float(components.logger.metrics.total_cost_usd or 0.0),
        }
    )
    queue.put({"type": "turn_finished", "id": turn_id})

    # Cleanup per-turn state.
    confirmation.discard()
    if deferred is not None:
        deferred.unbind()
    session.confirmation = None


def _run_one_turn(session: GuiSession, user_text: str):
    """Synchronous body — runs in asyncio.to_thread."""
    c = session.components
    history = c.logger.get_messages_for_api()

    history_bytes = sum(len(str(m.get("content", "")).encode("utf-8")) for m in history)
    c.logger.metrics.record_history_tokens(history_bytes // 4)

    summ_config = c.config.get("summarization", {})
    if summ_config.get("enabled", False):
        fast_model = resolve_model("fast", c.config).model_id
        history = summarize_history(
            history,
            c.client,
            model_id=fast_model,
            token_threshold=summ_config.get("token_threshold", 40000),
            keep_recent=summ_config.get("keep_recent", 10),
        )

    c.logger.add_message("user", user_text)

    return c.active_agent.run(
        user_text,
        messages_override=trim_tool_results(history),
        stream_handler=c.stream_handler,
    )


async def _run_delegation(session: GuiSession, queue: Queue[dict[str, Any]], turn_id: str, result) -> None:
    """Single-shot delegation: emit notice, run delegate, emit its text, return."""
    c = session.components
    delegate_id = result.delegate_to
    delegate_meta = c.agent_registry[delegate_id]

    queue.put(
        {
            "type": "delegation",
            "id": f"d-{uuid.uuid4().hex[:8]}",
            "from": c.agent_name,
            "to": delegate_id,
            "reason": result.delegate_task or "",
        }
    )

    delegate_agent = build_delegate_agent(c, delegate_meta, session.confirmation)

    web_stream = WebStreamHandler(queue, turn_id, agent=delegate_id)
    c.stream_handler.on_event = web_stream
    queue.put({"type": "thinking_start", "agent": delegate_id})

    initial = result.delegate_task or ""
    if result.delegate_context:
        initial = f"{initial}\n\nContext:\n{result.delegate_context}"

    try:
        delegate_result = await asyncio.to_thread(
            delegate_agent.run,
            initial,
            stream_handler=c.stream_handler,
        )
    except Exception as e:
        logger.exception("Delegate run failed")
        queue.put({"type": "error", "id": turn_id, "message": f"Delegate {delegate_id} failed: {e}"})
        return

    queue.put({"type": "thinking_end", "agent": delegate_id})

    final_text = web_stream.buffered_text() or delegate_result.text
    stats = web_stream.last_usage() or {}
    stats.setdefault("ttft", int(getattr(delegate_result.metrics, "ttft_ms", 0) or 0))
    stats.setdefault("total", int(getattr(delegate_result.metrics, "total_latency_ms", 0) or 0))
    if "tokens" not in stats:
        stats["tokens"] = delegate_result.usage.total_tokens or (
            delegate_result.usage.prompt_tokens + delegate_result.usage.completion_tokens
        )
    if "cost" not in stats:
        stats["cost"] = float(delegate_result.cost_usd or 0.0)

    queue.put(
        {
            "type": "text",
            "id": f"r-{uuid.uuid4().hex[:8]}",
            "agent": delegate_id,
            "markdown": final_text,
            "stats": stats,
        }
    )

    if delegate_result.tool_messages:
        c.logger.add_tool_messages(delegate_result.tool_messages, agent_name=delegate_id)
    c.logger.add_message(
        "assistant",
        delegate_result.text,
        prompt_tokens=delegate_result.usage.prompt_tokens,
        completion_tokens=delegate_result.usage.completion_tokens,
        total_tokens=delegate_result.usage.total_tokens,
        cache_read_tokens=delegate_result.usage.cache_read_tokens,
        cache_write_tokens=delegate_result.usage.cache_write_tokens,
        cost_usd=delegate_result.cost_usd,
        ttft_ms=getattr(delegate_result.metrics, "ttft_ms", 0),
        total_latency_ms=getattr(delegate_result.metrics, "total_latency_ms", 0),
        agent_name=delegate_id,
    )


def _mark_current_dirty(session: GuiSession) -> None:
    """Flag the active conversation's summary as stale in the index so the
    next /api/conversations request re-parses it."""
    index = session.conversation_index
    if index is None:
        return
    try:
        file_id = session.components.logger.session_start.strftime("%Y-%m-%d_%H-%M-%S")
        index.mark_dirty(file_id)
    except Exception:
        logger.debug("mark_dirty failed", exc_info=True)


def _find_deferred_handler(session: GuiSession):
    """Look up the _DeferredConfirmationHandler that was passed to build_session.

    We stored a reference on the components so the bridge can rebind per turn.
    Falls back to None if no deferred handler is wired (older sessions).
    """
    return getattr(session.components, "_deferred_handler", None)
