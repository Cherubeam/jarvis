"""
Apply old_text -> new_text replacements to a file's content.

Edit tools take a list of these instead of the full new file, so the model outputs
only the text that changes. A full-file rewrite costs output tokens for every
unchanged line and silently alters whatever the model doesn't copy exactly
(no-break spaces, zero-width characters, URLs).
"""

from dataclasses import dataclass
from typing import Any

# Characters models don't reproduce reliably when copying text. They're folded for
# *matching* only; the file keeps its own characters outside the replaced span.
_FOLD = {
    "\u00a0": " ",  # no-break space
    "\u202f": " ",  # narrow no-break space
    "\u2007": " ",  # figure space
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
}
_DROP = {"\u200b", "\u200c", "\u2060", "\ufeff", "\u00ad"}  # zero-width chars, soft hyphen


@dataclass
class EditError(Exception):
    """An edit that can't be applied; the message is written for the model to act on."""

    message: str

    def __str__(self) -> str:
        return self.message


def _fold(text: str) -> tuple[str, list[int]]:
    """Return the folded text and, for each folded char, its index in *text*."""
    chars: list[str] = []
    index: list[int] = []
    for i, c in enumerate(text):
        if c in _DROP:
            continue
        chars.append(_FOLD.get(c, c))
        index.append(i)
    return "".join(chars), index


def _find_unique(content: str, old_text: str) -> tuple[int, int] | int:
    """Span of the single occurrence of *old_text*, or the number of occurrences (0 or >1).

    Tries an exact match first, then a match that ignores the characters in _FOLD/_DROP.
    """
    count = content.count(old_text)
    if count == 1:
        start = content.index(old_text)
        return start, start + len(old_text)
    if count > 1:
        return count

    folded, index = _fold(content)
    needle, _ = _fold(old_text)
    if not needle:
        return 0
    starts = []
    pos = folded.find(needle)
    while pos != -1:
        starts.append(pos)
        pos = folded.find(needle, pos + 1)
    if len(starts) != 1:
        return len(starts)
    start = starts[0]
    return index[start], index[start + len(needle) - 1] + 1


def apply_edits(content: str, edits: list[dict[str, Any]]) -> str:
    """Apply *edits* in order and return the new content.

    Each edit is ``{"old_text": ..., "new_text": ...}``; ``old_text`` must occur exactly
    once in the content as it stands after the previous edits. All-or-nothing: raises
    EditError on the first edit that can't be applied.
    """
    if not edits:
        raise EditError("Error: no edits given.")
    for n, edit in enumerate(edits, 1):
        old_text, new_text = edit.get("old_text", ""), edit.get("new_text", "")
        if not old_text:
            raise EditError(f"Error in edit {n}: old_text is empty. Nothing was written.")
        span = _find_unique(content, old_text)
        if span == 0:
            raise EditError(
                f"Error in edit {n}: old_text not found. Copy it exactly from the current file. Nothing was written."
            )
        if isinstance(span, int):
            raise EditError(
                f"Error in edit {n}: old_text occurs {span} times. "
                "Include more surrounding text so it matches once. Nothing was written."
            )
        start, end = span
        content = content[:start] + new_text + content[end:]
    return content
