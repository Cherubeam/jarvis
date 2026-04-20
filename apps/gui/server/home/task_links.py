"""Heuristic linking between Things 3 tasks and recent conversations.

Match the longest ≥ 4-char word from a task title against the lowercased
titles of recent conversations. Dumb but useful: "Week-12 Substack draft"
links to the "week-12 substack · draft opening" conversation. Iterate when
the user flags false matches.
"""

from __future__ import annotations

import re
from typing import Any

_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_MIN_WORD_LEN = 4
_MAX_LINKS_PER_TASK = 2


def _salient_words(title: str) -> list[str]:
    """Words ≥ 4 chars in length, lowercased, longest first."""
    words = [w.lower() for w in _WORD_RE.findall(title) if len(w) >= _MIN_WORD_LEN]
    words.sort(key=len, reverse=True)
    return words


def link_tasks_to_conversations(
    tasks: list[dict[str, Any]],
    recent_summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Annotate each task with `linked_conversation_ids`.

    Returns a new list; inputs are not mutated.
    """
    out: list[dict[str, Any]] = []
    for task in tasks:
        words = _salient_words(task.get("title", ""))
        linked: list[str] = []
        seen: set[str] = set()
        for w in words:
            for summary in recent_summaries:
                sid = summary["id"]
                if sid in seen:
                    continue
                if w in summary["title"].lower():
                    linked.append(sid)
                    seen.add(sid)
                    if len(linked) >= _MAX_LINKS_PER_TASK:
                        break
            if len(linked) >= _MAX_LINKS_PER_TASK:
                break
        out.append({**task, "linked_conversation_ids": linked})
    return out
