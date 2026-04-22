"""Per-agent rollups over the ConversationIndex cache.

Walks `index._cache.values()` the same way `home/cost_week.py` does (see
`index.py:178` for the internal-access precedent — a deliberate mirror of
that pattern, not a one-off reach into private state).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

_DEFAULT_WINDOW_DAYS = 14


def cost_14d_rollup(
    index: Any,
    agent_id: str,
    today: date | None = None,
    *,
    days: int = _DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    """Return a per-day cost breakdown for the last ``days`` days for ``agent_id``.

    Only summaries where ``agent_id in summary['agents']`` contribute.

    Returns:
        {
          "days": [{"date": "YYYY-MM-DD", "cost": float}, ...],  # len == days, oldest first
          "total": float,
        }
    """
    today = today or date.today()
    window: list[dict[str, Any]] = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        window.append({"date": d.isoformat(), "cost": 0.0})
    by_date = {entry["date"]: entry for entry in window}

    for _, summary in index._cache.values():
        if agent_id not in (summary.get("agents") or []):
            continue
        sd = summary.get("date")
        if sd in by_date:
            by_date[sd]["cost"] += float(summary.get("cost") or 0.0)

    total = sum(d["cost"] for d in window)
    return {"days": window, "total": total}


def recent_sessions_for_agent(
    index: Any,
    agent_id: str,
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Return summaries where ``agent_id`` participated, sorted recent-first.

    Uses ``summary["id"]`` (timestamp-prefixed filename stem) for ordering — same
    sort key the index's ``list(sort="recent")`` uses.
    """
    items = [s for _, s in index._cache.values() if agent_id in (s.get("agents") or [])]
    items.sort(key=lambda s: s["id"], reverse=True)
    return items[:limit]
