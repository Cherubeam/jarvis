"""Outcome tracking tools — capture recommendations JARVIS makes for later review.

The `track_recommendation` tool writes a pending outcome file that the user
later scores via the /review CLI command. Reviewed outcomes feed back into
RAG so future conversations benefit from past learning.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from packages.core import frontmatter
from packages.core.date_utils import SUPPORTED_FORMS, parse_relative_date
from packages.core.filesystem_access import FilesystemGuard
from packages.core.tools.base import ToolDefinition

logger = logging.getLogger(__name__)

_NON_ALNUM = re.compile(r"[^a-z0-9-]+")
_MULTI_DASH = re.compile(r"-+")


def _slugify(text: str, max_words: int = 6) -> str:
    """Turn free text into a filename-safe slug from its first N words."""
    words = re.split(r"\s+", text.strip())[:max_words]
    joined = "-".join(words).lower()
    joined = _NON_ALNUM.sub("-", joined)
    joined = _MULTI_DASH.sub("-", joined).strip("-")
    return joined or "untitled"


def _next_available_path(outcomes_dir: Path, date_str: str, slug: str) -> Path:
    """Return an unused outcome file path, appending -2, -3, ... on collision."""
    candidate = outcomes_dir / f"{date_str}-{slug}.md"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = outcomes_dir / f"{date_str}-{slug}-{n}.md"
        if not candidate.exists():
            return candidate
        n += 1


def make_outcome_tools(
    outcomes_dir: Path,
    fs_guard: FilesystemGuard,
    conversation_id: str,
) -> list[ToolDefinition]:
    """Create the outcome-tracking tool set.

    Args:
        outcomes_dir: Directory where outcome markdown files are written.
        fs_guard: Filesystem guard used to validate write access.
        conversation_id: ID of the current CLI session's conversation —
            captured into every tracked item's frontmatter so the user
            can jump back to the originating conversation later.

    Returns:
        A list with a single `track_recommendation` ToolDefinition.
    """

    def _track_recommendation(
        what: str,
        why: str,
        revisit_in: str,
        success_looks_like: str = "",
    ) -> str:
        now = datetime.now()
        try:
            revisit_at = parse_relative_date(revisit_in, now=now)
        except ValueError as e:
            return f"Error: {e}"

        if not fs_guard.check_write(outcomes_dir):
            return (
                f"Error: filesystem guard denies write access to {outcomes_dir}. "
                f"Add a read-write rule for this path in config."
            )

        date_str = now.date().isoformat()
        slug = _slugify(what)
        target = _next_available_path(outcomes_dir, date_str, slug)

        meta = {
            "created_at": now.replace(microsecond=0).isoformat(),
            "revisit_at": revisit_at.isoformat(),
            "status": "pending",
            "what": what,
            "why": why,
            "success_looks_like": success_looks_like,
            "conversation_id": conversation_id,
        }
        content = frontmatter.dump(meta, "")
        frontmatter.write_atomic(target, content)

        truncated = what if len(what) <= 80 else what[:77] + "..."
        return f"Tracked: '{truncated}' — revisit {revisit_at.isoformat()}"

    tools: list[ToolDefinition] = []
    tools.append(
        ToolDefinition(
            name="track_recommendation",
            description=(  # pragma: no mutate
                "Record an actionable recommendation you just gave the user so they "
                "can review its outcome later. Use this ONLY when you give a concrete, "
                "actionable suggestion with an implied or stated timeframe — not for "
                "opinions, explanations, hypotheticals, or information lookups. "
                f"Supported revisit_in forms: {SUPPORTED_FORMS}."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "what": {
                        "type": "string",
                        "description": "The recommendation itself, in one sentence.",  # pragma: no mutate
                    },
                    "why": {
                        "type": "string",
                        "description": "The reason or context behind the recommendation.",  # pragma: no mutate
                    },
                    "revisit_in": {
                        "type": "string",
                        "description": (  # pragma: no mutate
                            "When to revisit: 'N day(s)', 'N week(s)', 'N month(s)', "
                            "'N year(s)', 'tomorrow', 'next week', 'next month', "
                            "or ISO date 'YYYY-MM-DD'."
                        ),
                    },
                    "success_looks_like": {
                        "type": "string",
                        "description": "Optional: what a good outcome looks like.",  # pragma: no mutate
                    },
                },
                "required": ["what", "why", "revisit_in"],
            },
            execute=_track_recommendation,
        )
    )
    return tools
