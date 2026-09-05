"""
WebConfirmationHandler — bridges the two-method ConfirmationHandler ABC
across the sync/async boundary.

The ABC (packages/integrations/obsidian/writer.py:30-45) calls present_diff()
first (we buffer it), then get_confirmation() (we block on a threading.Event).
The async side flushes the buffered diff into one approval_pending WS event
and waits for the client's approval_decision, which sets the event.

resolve() is the *client decision* path and requires an exact match on the
pending approval id — a decision that names no id, names the wrong one, or
arrives before anything is pending is rejected. discard() is the *force-release*
path used by the bridge and the WS handler on disconnect / turn end; it is the
only way to unblock the worker without a matching id.
"""

from __future__ import annotations

import logging
import threading
import uuid
from queue import Queue
from typing import Any

from packages.integrations.obsidian.diff import VaultDiff
from packages.integrations.obsidian.writer import ConfirmationHandler

logger = logging.getLogger(__name__)


def _diff_lines(diff: VaultDiff) -> list[dict[str, str]]:
    """Convert VaultDiff into the wire shape the design expects.

    VaultDiff's exact structure varies; we fall back to a simple textual
    representation if the unified .lines attribute isn't available.
    """
    lines = getattr(diff, "lines", None)
    if lines is None:
        # Best-effort: parse __str__/format output.
        text = getattr(diff, "diff_text", "") or str(diff)
        out = []
        for raw in text.splitlines():
            if raw.startswith("+") and not raw.startswith("+++"):
                out.append({"kind": "add", "text": raw[1:]})
            elif raw.startswith("-") and not raw.startswith("---"):
                out.append({"kind": "del", "text": raw[1:]})
            else:
                out.append({"kind": "ctx", "text": raw})
        return out
    out = []
    for ln in lines:
        kind = getattr(ln, "kind", "ctx")
        text = getattr(ln, "text", "")
        out.append({"kind": kind, "text": text})
    return out


class WebConfirmationHandler(ConfirmationHandler):
    """Async-bridge confirmation handler.

    One handler instance per turn — the bridge instantiates it, passes it to
    the agent, and after the turn calls discard() to make sure no thread is
    left blocked.
    """

    def __init__(self, event_queue: Queue[dict[str, Any]], turn_id: str, agent: str = "JARVIS") -> None:
        self._queue = event_queue
        self._turn_id = turn_id
        self._agent = agent
        self._buffered_diff: VaultDiff | None = None
        self._event = threading.Event()
        self._approved = False
        self._pending_id: str | None = None

    def present_diff(self, diff: VaultDiff) -> None:  # called from worker thread
        self._buffered_diff = diff

    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:  # blocks worker
        diff = self._buffered_diff
        if diff is None:
            logger.warning("get_confirmation called without preceding present_diff")
            return False

        approval_id = str(uuid.uuid4())
        self._pending_id = approval_id
        path = getattr(diff, "path", "") or ""
        summary = getattr(diff, "summary", "") or prompt

        self._queue.put(
            {
                "type": "approval_pending",
                "id": approval_id,
                "tool": "vault_write",
                "agent": self._agent,
                "path": path,
                "diff": _diff_lines(diff),
                "summary": summary,
            }
        )

        self._event.wait()  # released by resolve()
        self._queue.put(
            {
                "type": "approval_resolved",
                "id": approval_id,
                "approved": self._approved,
            }
        )
        return self._approved

    def resolve(self, approved: bool, approval_id: str | None = None) -> bool:
        """Apply a client's approval_decision. Returns False if it was rejected.

        The id must match the pending approval exactly. Two holes this closes:
        a decision carrying no id used to approve whatever was pending (a stale
        tab or racing reconnect could authorize a write it never saw), and a
        decision arriving *before* any approval was pending used to pre-arm the
        event, so the next get_confirmation() returned True without ever
        emitting approval_pending — an invisible vault write.

        Use discard() to force-release; this method deliberately cannot.
        """
        if self._pending_id is None or approval_id != self._pending_id:
            return False
        self._release(approved)
        return True

    def _release(self, approved: bool) -> None:
        self._approved = approved
        self._event.set()

    def discard(self) -> None:
        """Force-resolve as not-approved so any blocked worker thread exits."""
        if not self._event.is_set():
            self._release(False)

    def pending_id(self) -> str | None:
        return self._pending_id
