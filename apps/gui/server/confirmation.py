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

Every approval starts from fresh state, so a second vault write in the same
turn asks again instead of replaying the first decision. An approval nobody
answers within APPROVAL_TIMEOUT_S is rejected, and once discarded the handler
rejects every further write without asking: no person is there to see it.
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

APPROVAL_TIMEOUT_S = 600.0  # an unanswered approval is rejected after 10 minutes


_KIND = {"added": "add", "removed": "del", "unchanged": "ctx"}


def _diff_lines(diff: VaultDiff) -> list[dict[str, str]]:
    """Convert VaultDiff.diff_lines into the wire shape the approval card renders."""
    return [{"kind": _KIND.get(dl.type, "ctx"), "text": dl.content} for dl in diff.diff_lines]


class WebConfirmationHandler(ConfirmationHandler):
    """Async-bridge confirmation handler.

    One handler instance per turn — the bridge instantiates it, passes it to
    the agent, and after the turn calls discard() to make sure no thread is
    left blocked.
    """

    def __init__(
        self,
        event_queue: Queue[dict[str, Any]],
        turn_id: str,
        agent: str = "JARVIS",
        timeout_s: float = APPROVAL_TIMEOUT_S,
    ) -> None:
        self._queue = event_queue
        self._turn_id = turn_id
        self._agent = agent
        self._timeout_s = timeout_s
        self._buffered_diff: VaultDiff | None = None
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._approved = False
        self._pending_id: str | None = None
        self._closed = False

    def present_diff(self, diff: VaultDiff) -> None:  # called from worker thread
        self._buffered_diff = diff

    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:  # blocks worker
        diff = self._buffered_diff
        if diff is None:
            logger.warning("get_confirmation called without preceding present_diff")
            return False

        approval_id = str(uuid.uuid4())
        with self._lock:
            if self._closed:
                return False
            # Fresh state per approval: a decision never carries over to the next write.
            self._event.clear()
            self._approved = False
            self._pending_id = approval_id
        path = diff.file_path
        summary = diff.summary or prompt

        self._queue.put(
            {
                "type": "approval_pending",
                "id": approval_id,
                "tool": "vault_write",
                "agent": self._agent,
                "path": path,
                "diff": _diff_lines(diff),
                "summary": summary,
                "link_warnings": diff.link_warnings,
            }
        )

        decided = self._event.wait(timeout=self._timeout_s)  # released by resolve() or discard()
        with self._lock:
            approved = self._approved if decided else False
            self._pending_id = None
        if not decided:
            logger.warning(  # pragma: no mutate
                "approval %s for %s timed out after %.0f s; rejected", approval_id, path, self._timeout_s
            )
        self._queue.put(
            {
                "type": "approval_resolved",
                "id": approval_id,
                "approved": approved,
            }
        )
        return approved

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
        with self._lock:
            if self._pending_id is None or approval_id != self._pending_id or self._event.is_set():
                return False
            self._approved = approved
            self._event.set()
            return True

    def discard(self) -> None:
        """Reject any pending approval and every later one: nobody is there to decide."""
        with self._lock:
            self._closed = True
            if self._pending_id is not None and not self._event.is_set():
                self._approved = False
                self._event.set()

    def pending_id(self) -> str | None:
        return self._pending_id
