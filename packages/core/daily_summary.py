"""Pure helpers for the /daily-summary flow — shared by CLI and GUI.

The CLI wraps these with Rich rendering + blocking streaming; the GUI bridge
wraps them with the WS event pipeline + WebConfirmationHandler. The helpers
themselves do only read-only vault I/O and string building — no stdout, no
LLM calls, no vault writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from packages.integrations.obsidian.callout import CalloutNotFound, find_jarvis_callout
from packages.integrations.obsidian.vault import get_daily_note_path, read_note


class DailySummaryError(StrEnum):
    """Discriminator for ``DailySummaryFailure``."""

    INVALID_DATE = "invalid_date"
    VAULT_NOT_CONFIGURED = "vault_not_configured"
    NOTE_NOT_FOUND = "note_not_found"
    NOTE_PERMISSION_DENIED = "note_permission_denied"
    NO_CALLOUT = "no_callout"


@dataclass
class DailySummaryRequest:
    """Everything a caller needs to stream an LLM response for the command."""

    messages: list[dict[str, Any]]
    note_path: Path
    target_date: str | None


@dataclass
class DailySummaryFailure:
    """Structured failure — carries a human-readable message both surfaces
    can display verbatim (no stdout coupling)."""

    error: DailySummaryError
    message: str


def parse_daily_summary_command(user_text: str) -> tuple[str | None, DailySummaryFailure | None]:
    """Parse '/daily-summary [YYYY-MM-DD]' into (target_date, failure).

    Empty / missing payload returns ``(None, None)`` — the caller should
    default to today. A non-ISO payload returns ``(None, Failure)``.
    """
    parts = user_text.split(None, 1)
    if len(parts) < 2:
        return (None, None)
    payload = parts[1].strip()
    if not payload:
        return (None, None)
    try:
        date.fromisoformat(payload)
    except ValueError:
        return (
            None,
            DailySummaryFailure(
                error=DailySummaryError.INVALID_DATE,
                message=f"Invalid date format: '{payload}'. Use YYYY-MM-DD.",
            ),
        )
    return (payload, None)


def build_daily_summary_request(
    vault_config: Any,
    system_prompt: str,
    history: list[dict[str, Any]],
    daily_prompt: str,
    target_date: str | None = None,
) -> DailySummaryRequest | DailySummaryFailure:
    """Build the LLM messages for a daily-summary turn.

    Reads the daily note from the vault, strips the existing JARVIS callout
    (to avoid the model repeating itself), and assembles the system +
    history + user messages. All IO is read-only.
    """
    if vault_config is None:
        return DailySummaryFailure(
            error=DailySummaryError.VAULT_NOT_CONFIGURED,
            message=(
                "Obsidian integration is not configured or disabled. "
                "Set obsidian.enabled=true and obsidian.vault_path in config/local.yaml."
            ),
        )

    note_path = get_daily_note_path(vault_config, target_date=target_date)
    try:
        note_content = read_note(note_path, vault_config)
    except FileNotFoundError:
        return DailySummaryFailure(
            error=DailySummaryError.NOTE_NOT_FOUND,
            message=(
                f"Daily note not found: {note_path.name}. "
                "Create the note with a > [!JARVIS] callout block first."
            ),
        )
    except PermissionError as e:
        return DailySummaryFailure(
            error=DailySummaryError.NOTE_PERMISSION_DENIED,
            message=str(e),
        )

    callout = find_jarvis_callout(note_content)
    if isinstance(callout, CalloutNotFound):
        return DailySummaryFailure(
            error=DailySummaryError.NO_CALLOUT,
            message=(
                f"No > [!JARVIS] callout block found in {note_path.name}. "
                "Add a '> [!JARVIS]' line to your daily note first."
            ),
        )

    note_lines = note_content.split("\n")
    note_without_callout = "\n".join(
        note_lines[: callout.start_line] + note_lines[callout.end_line + 1 :]
    ).strip()

    date_label = target_date if target_date else "today"
    user_content = (
        f"Generate my daily note summary for {date_label}.\n\n"
        f"---\n\n"
        f"**Daily note ({note_path.name}):**\n\n"
        f"{note_without_callout}"
    )
    if callout.existing_content.strip():
        user_content += (
            f"\n\n---\n\n"
            f"**Existing JARVIS callout entries (DO NOT repeat these):**\n\n"
            f"{callout.existing_content.strip()}"
        )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": f"{system_prompt}\n\n{daily_prompt}"},
        *history,
        {"role": "user", "content": user_content},
    ]

    return DailySummaryRequest(
        messages=messages,
        note_path=note_path,
        target_date=target_date,
    )
