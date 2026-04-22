"""Rolls up per-day cost over the last 7 days from a ConversationIndex.

Walks `index._cache.values()` the same way `ConversationIndex.facets()` does
(`index.py:178`) — a deliberate mirror of that internal-access pattern, not
a one-off reach into private state.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def cost_week_rollup(index: Any, today: date | None = None) -> dict[str, Any]:
    """Return 7-day cost breakdown ending today.

    Returns:
        {
          "days": [
            {"date": "YYYY-MM-DD", "cost": float, "conversations": int},
            ...  # exactly 7, oldest first, today last
          ],
          "total": float,
          "conversation_count": int,  # sum of conversations across the 7 days
        }
    """
    today = today or date.today()
    window: list[dict[str, Any]] = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        window.append({"date": d.isoformat(), "cost": 0.0, "conversations": 0})
    by_date = {entry["date"]: entry for entry in window}

    for _, summary in index._cache.values():
        sd = summary.get("date")
        if sd in by_date:
            by_date[sd]["cost"] += float(summary.get("cost") or 0.0)
            by_date[sd]["conversations"] += 1

    total = sum(d["cost"] for d in window)
    convs = sum(d["conversations"] for d in window)
    return {"days": window, "total": total, "conversation_count": convs}
