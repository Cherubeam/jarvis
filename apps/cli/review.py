"""Interactive /review command for scoring pending outcome items."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from packages.core import frontmatter

logger = logging.getLogger(__name__)

VALID_OUTCOMES = ("happened", "didnt", "partial")
VALID_QUALITY = {"1", "2", "3", "4", "5"}


class _PromptSessionLike(Protocol):
    def prompt(self, message: str) -> str: ...  # pragma: no cover


@dataclass
class _PendingItem:
    path: Path
    meta: dict
    body: str


def _load_pending_due(outcomes_dir: Path, today: date) -> list[_PendingItem]:
    """Return pending items whose revisit_at date is today or earlier.

    Files with malformed frontmatter are logged and skipped — they do not
    abort the review loop.
    """
    items: list[_PendingItem] = []
    if not outcomes_dir.exists():
        return items

    for path in sorted(outcomes_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            meta, body = frontmatter.parse(text)
        except Exception as e:
            logger.warning(f"Skipping {path.name}: failed to read ({e})")
            continue
        if meta.get("status") != "pending":
            continue
        revisit_raw = meta.get("revisit_at")
        if not revisit_raw:
            continue
        try:
            revisit = date.fromisoformat(str(revisit_raw))
        except ValueError:
            logger.warning(f"Skipping {path.name}: invalid revisit_at '{revisit_raw}'")
            continue
        if revisit <= today:
            items.append(_PendingItem(path=path, meta=meta, body=body))

    items.sort(key=lambda i: str(i.meta.get("revisit_at", "")))
    return items


def _prompt_choice(
    session: _PromptSessionLike,
    question: str,
    valid: set[str] | tuple[str, ...],
) -> str:
    """Prompt until the user types a value in the valid set."""
    valid_set = set(valid)
    while True:
        answer = session.prompt(question).strip().lower()
        if answer in valid_set:
            return answer


def _apply_review(
    item: _PendingItem,
    outcome: str,
    quality: int,
    note: str,
    now: datetime,
) -> None:
    """Update the outcome file with review results (atomic write)."""
    new_meta = dict(item.meta)
    new_meta["status"] = "reviewed"
    new_meta["reviewed_at"] = now.replace(microsecond=0).isoformat()
    new_meta["outcome"] = outcome
    new_meta["quality"] = quality
    content = frontmatter.dump(new_meta, note)
    frontmatter.write_atomic(item.path, content)


def handle_review_command(
    outcomes_dir: Path,
    console: Any,
    session: _PromptSessionLike,
    *,
    today: date | None = None,
    now: datetime | None = None,
) -> int:
    """Interactive review of pending items past their revisit date.

    Returns the number of items reviewed in this session.
    """
    today = today or date.today()
    now = now or datetime.now()

    pending = _load_pending_due(outcomes_dir, today)
    if not pending:
        console.print("No items due for review.")
        return 0

    console.print(f"{len(pending)} item(s) due for review.\n")

    reviewed_count = 0
    for i, item in enumerate(pending, start=1):
        try:
            console.print(f"[bold]({i}/{len(pending)})[/] {item.meta.get('what', '(no title)')}")
            console.print(f"  why: {item.meta.get('why', '')}")
            console.print(f"  created: {item.meta.get('created_at', '')}")
            console.print(f"  revisit: {item.meta.get('revisit_at', '')}")
            sll = item.meta.get("success_looks_like", "")
            if sll:
                console.print(f"  success: {sll}")

            outcome = _prompt_choice(
                session,
                "Did it happen? (happened/didnt/partial): ",
                VALID_OUTCOMES,
            )
            quality_str = _prompt_choice(
                session,
                "In hindsight, how good was this advice? (1=bad, 5=nailed it): ",
                VALID_QUALITY,
            )
            note = session.prompt("Retrospective note (what actually happened, why): ").strip()

            _apply_review(item, outcome, int(quality_str), note, now)
            reviewed_count += 1
            console.print("  ✓ saved\n")
        except KeyboardInterrupt:
            console.print(f"\nAborted. {reviewed_count} reviewed, {len(pending) - reviewed_count} remaining.")
            return reviewed_count

    console.print(f"Done. {reviewed_count} item(s) reviewed.")
    return reviewed_count
