"""
Auto-confirmation handler for unattended/CI runs of the developer agent.

Extends the ConfirmationHandler ABC to auto-approve file writes within
scoped directories, rejecting writes outside the allowed scope.
"""

import logging
from pathlib import Path

from packages.integrations.obsidian.diff import VaultDiff
from packages.integrations.obsidian.writer import ConfirmationHandler

logger = logging.getLogger(__name__)


class AutoConfirmationHandler(ConfirmationHandler):
    """Auto-approves writes within developer.scope for unattended/CI runs.

    Safety: only auto-approves if the target path is within one of the
    allowed scope directories from config.
    """

    def __init__(self, allowed_dirs: list[str], project_root: Path):
        self._allowed_dirs = allowed_dirs
        self._project_root = project_root
        self._last_path_in_scope = False

    def _is_in_scope(self, file_path: str) -> bool:
        """Check if a file path falls within an allowed directory."""
        for allowed in self._allowed_dirs:
            if file_path.startswith(allowed):
                return True
        return False

    def present_diff(self, diff: VaultDiff) -> None:
        """Log the diff summary but don't block on display."""
        in_scope = self._is_in_scope(diff.file_path)
        self._last_path_in_scope = in_scope
        action = "auto-approving" if in_scope else "rejecting (out of scope)"
        logger.info(
            "AutoConfirmationHandler: %s write to %s",
            action, diff.file_path,
        )

    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:
        """Auto-approve if the last presented diff was within scope."""
        return self._last_path_in_scope
