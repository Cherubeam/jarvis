"""
Write coordinator for Obsidian vault operations.

Orchestrates: diff computation -> confirmation -> write.
GUI-ready via the ConfirmationHandler ABC — CLI and future GUI
each provide their own implementation.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from packages.integrations.obsidian.callout import (
    CalloutBlock,
    CalloutNotFound,
    build_updated_content,
    find_jarvis_callout,
)
from packages.integrations.obsidian.diff import (
    VaultDiff,
    compute_diff,
    format_diff_for_cli,
)
from packages.integrations.obsidian.vault import VaultConfig, validate_write

logger = logging.getLogger(__name__)


class ConfirmationHandler(ABC):
    """Abstract interface for diff presentation and write confirmation.

    CLI and future GUI each implement this. A WebConfirmationHandler
    would live in apps/web/, not in this integration package.
    """

    @abstractmethod
    def present_diff(self, diff: VaultDiff) -> None:
        """Display the proposed diff to the user."""
        ...

    @abstractmethod
    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:
        """Ask the user for write confirmation. Returns True to proceed."""
        ...


class CLIConfirmationHandler(ConfirmationHandler):
    """CLI implementation: prints colored diff, asks y/n."""

    def present_diff(self, diff: VaultDiff) -> None:
        print("\n" + format_diff_for_cli(diff) + "\n")

    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:
        try:
            answer = input(f"\n{prompt} (y/yes to confirm): ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False


@dataclass
class WriteResult:
    """Result of a vault write operation."""

    success: bool
    file_path: str
    action: str  # "appended", "rejected", "no_callout", "error"
    message: str
    diff: VaultDiff | None = None


def write_note(
    note_path: Path,
    proposed_content: str,
    vault_config: VaultConfig,
    confirmation_handler: ConfirmationHandler,
    reasoning: str = "",
) -> WriteResult:
    """Write full content to a note with diff-based confirmation.

    For existing files: shows diff against current content.
    For new files: shows diff against empty string (all additions).

    Args:
        note_path: Absolute path to the note file.
        proposed_content: Full file content to write.
        vault_config: Vault configuration.
        confirmation_handler: Handler for diff display and confirmation.
        reasoning: Optional explanation shown before the diff.

    Returns:
        WriteResult describing the outcome.
    """
    rel_path = str(note_path.relative_to(vault_config.vault_path))

    # Validate write access
    if not validate_write(note_path, vault_config):
        return WriteResult(
            success=False,
            file_path=rel_path,
            action="error",
            message=f"Access denied: {rel_path} is not writable",
        )

    # Read current content (empty string for new files)
    is_new = not note_path.exists()
    if is_new:
        original = ""
    else:
        try:
            original = note_path.read_text(encoding="utf-8")
        except OSError as e:
            return WriteResult(
                success=False,
                file_path=rel_path,
                action="error",
                message=str(e),
            )

    # Compute diff
    diff = compute_diff(rel_path, original, proposed_content)

    # Print reasoning before diff if provided
    if reasoning:
        print(f"\n{reasoning}")

    # Present diff and get confirmation
    confirmation_handler.present_diff(diff)
    if not confirmation_handler.get_confirmation():
        return WriteResult(
            success=False,
            file_path=rel_path,
            action="rejected",
            message="Write cancelled by user",
            diff=diff,
        )

    # Create parent directories if needed
    note_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the file
    try:
        note_path.write_text(proposed_content, encoding="utf-8")
        action = "created" if is_new else "written"
        logger.info(f"{'Created' if is_new else 'Wrote'} {rel_path}")
        return WriteResult(
            success=True,
            file_path=rel_path,
            action=action,
            message=f"Successfully {'created' if is_new else 'wrote'} {rel_path}",
            diff=diff,
        )
    except OSError as e:
        return WriteResult(
            success=False,
            file_path=rel_path,
            action="error",
            message=f"Write failed: {e}",
            diff=diff,
        )


def append_to_daily_note(
    content: str,
    vault_config: VaultConfig,
    confirmation_handler: ConfirmationHandler,
    date: str | None = None,
) -> WriteResult:
    """Append content to today's (or specified date's) daily note JARVIS callout.

    Args:
        content: Text to append (without > prefix — will be formatted).
        vault_config: Vault configuration.
        confirmation_handler: Handler for diff display and confirmation.
        date: Optional date string (YYYY-MM-DD). Defaults to today.

    Returns:
        WriteResult describing the outcome.
    """
    from packages.integrations.obsidian.vault import get_daily_note_path

    note_path = get_daily_note_path(vault_config, date)
    return append_to_note(note_path, content, vault_config, confirmation_handler)


def append_to_note(
    note_path: Path,
    content: str,
    vault_config: VaultConfig,
    confirmation_handler: ConfirmationHandler,
) -> WriteResult:
    """Append content to a note's JARVIS callout block.

    Args:
        note_path: Absolute path to the note file.
        content: Text to append (without > prefix).
        vault_config: Vault configuration.
        confirmation_handler: Handler for diff display and confirmation.

    Returns:
        WriteResult describing the outcome.
    """
    rel_path = str(note_path.relative_to(vault_config.vault_path))

    # Validate write access
    if not validate_write(note_path, vault_config):
        return WriteResult(
            success=False,
            file_path=rel_path,
            action="error",
            message=f"Access denied: {rel_path} is not writable",
        )

    # Read current content
    try:
        original = note_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return WriteResult(
            success=False,
            file_path=rel_path,
            action="error",
            message=f"Note not found: {rel_path}",
        )
    except PermissionError as e:
        return WriteResult(
            success=False,
            file_path=rel_path,
            action="error",
            message=str(e),
        )

    # Find callout block
    callout = find_jarvis_callout(original)
    if isinstance(callout, CalloutNotFound):
        return WriteResult(
            success=False,
            file_path=rel_path,
            action="no_callout",
            message=f"No > [!JARVIS] callout block found in {rel_path}",
        )

    # Build proposed content
    proposed = build_updated_content(original, callout, content)

    # Compute diff
    diff = compute_diff(rel_path, original, proposed)

    # Present diff and get confirmation
    confirmation_handler.present_diff(diff)
    if not confirmation_handler.get_confirmation():
        return WriteResult(
            success=False,
            file_path=rel_path,
            action="rejected",
            message="Write cancelled by user",
            diff=diff,
        )

    # Write the file
    try:
        note_path.write_text(proposed, encoding="utf-8")
        logger.info(f"Appended to {rel_path}")
        return WriteResult(
            success=True,
            file_path=rel_path,
            action="appended",
            message=f"Successfully appended to JARVIS callout in {rel_path}",
            diff=diff,
        )
    except OSError as e:
        return WriteResult(
            success=False,
            file_path=rel_path,
            action="error",
            message=f"Write failed: {e}",
            diff=diff,
        )
