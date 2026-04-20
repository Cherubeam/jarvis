"""
GUI session state — owns the SessionComponents for the running app.

For Phase 1 there is one session at a time (single-user localhost). The state
is built once at FastAPI lifespan startup and reused across WS connections.
A second WS connection takes over from the first.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from argparse import Namespace
from dataclasses import dataclass, field
from queue import Queue
from typing import Any

from apps.cli.main import load_config
from apps.cli.session_factory import SessionComponents, build_session
from apps.gui.server.confirmation import WebConfirmationHandler

logger = logging.getLogger(__name__)


@dataclass
class GuiSession:
    """Holds the SessionComponents + per-connection state."""

    components: SessionComponents
    started_at: str
    # The per-turn event queue; a fresh one is bound on each `submit`.
    queue: Queue[dict[str, Any]] | None = None
    confirmation: WebConfirmationHandler | None = None
    cancel_event: threading.Event | None = None
    last_agent_session: list[dict] | None = None
    in_flight: bool = False
    in_flight_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Set by app.py lifespan after the index is built. Used by the bridge to
    # invalidate the current session's summary on turn_finished so the sidebar
    # refreshes without staleness.
    conversation_index: Any = None

    def session_meta(self) -> dict[str, Any]:
        """Current-session metadata for the client.

        `file_id` is the filename stem the logger writes — matches
        ConversationSummary.id in the /api/conversations response so the
        Sidebar can highlight the active row. `conversation_id` (the
        internal `conv_*_hex` string) is kept for traceability.
        `conversation_path` is derived from logger.session_start, NOT from
        conversation_id — Phase 1 had this wrong.
        """
        c = self.components
        model_short = c.model_id.split("/")[-1] if c.model_id else c.model_id

        session_start = c.logger.session_start  # datetime set by ConversationLogger
        file_id = session_start.strftime("%Y-%m-%d_%H-%M-%S")
        conv_path = str(c.conversations_dir / str(session_start.year) / f"{file_id}.json")

        vault = None
        if c.vault_config is not None:
            vault = str(getattr(c.vault_config, "vault_path", "")) or None
        return {
            "id": c.conversation_id,        # internal id (kept for traceability)
            "file_id": file_id,              # filename stem — matches /api/conversations items
            "model": c.model_id,
            "model_short": model_short,
            "provider": c.provider,
            "conversation_path": conv_path,
            "vault": vault,
            "started_at": self.started_at,
            "agents_count": len(c.agent_registry),
        }


def build_gui_session() -> GuiSession:
    """One-time GUI startup: load config + assemble components.

    Confirmation handler is per-turn (created fresh each `submit` so the
    threading.Event isn't reused). The factory needs *some* handler for the
    initial wiring of blog/suggest/dev/vault tools — we wire a placeholder
    that defers to whatever turn-specific handler is bound on `session.confirmation`.
    """
    config = load_config()

    # Create a deferred handler — the queue comes later (per turn).
    deferred = _DeferredConfirmationHandler()

    args = Namespace(model=None, agent=None, auto_confirm=False)
    components = build_session(
        args, config, deferred,
        on_tool_call=None,
        client_label="gui",
        auto_confirm=False,
    )
    # Attach the deferred handler so the bridge can rebind it per turn.
    components._deferred_handler = deferred
    started = time.strftime("%H:%M")
    return GuiSession(components=components, started_at=started)


class _DeferredConfirmationHandler:
    """Routes present_diff/get_confirmation calls to the *current* turn's
    WebConfirmationHandler. The GUI session swaps this on every submit.

    If no handler is bound when the agent calls present_diff, the write is
    automatically rejected (no client to ask).
    """

    def __init__(self) -> None:
        self._target: WebConfirmationHandler | None = None

    def bind(self, handler: WebConfirmationHandler) -> None:
        self._target = handler

    def unbind(self) -> None:
        self._target = None

    def present_diff(self, diff) -> None:
        if self._target is None:
            logger.warning("present_diff with no bound GUI handler; write will be rejected")
            return
        self._target.present_diff(diff)

    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:
        if self._target is None:
            return False
        return self._target.get_confirmation(prompt)
