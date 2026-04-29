"""ConversationIndex — scans data/conversations/YYYY/*.json, builds summaries.

Not ChromaDB — just an in-memory mtime-keyed cache. Refreshes are incremental
and run off the event loop via asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from apps.gui.server.history.derive import (
    agents_seen,
    dominant_agent,
    duration_ms,
    handoff_count,
    preview_messages,
    title_from_messages,
    tool_call_count,
    tools_used,
)
from apps.gui.server.history.summary import ConversationDetail, ConversationSummary
from packages.core.memory import migrate_conversation

logger = logging.getLogger(__name__)


class ConversationIndex:
    """In-memory index over conversation JSON files.

    Keyed by file path; each entry stores (mtime_ns, summary). list() is a
    pure in-memory filter over the cache. refresh() is incremental — only
    changed or new files are re-parsed.
    """

    def __init__(self, conversations_dir: Path) -> None:
        self._dir = conversations_dir
        # path -> (mtime_ns, summary_dict)
        self._cache: dict[str, tuple[int, dict[str, Any]]] = {}
        # file_ids explicitly marked dirty by external signals (WS turn_finished).
        self._dirty: set[str] = set()

    @property
    def dir(self) -> Path:
        return self._dir

    def mark_dirty(self, file_id: str) -> None:
        """Invalidate one file so the next refresh re-parses it even if mtime is unchanged."""
        self._dirty.add(file_id)

    async def refresh(self) -> None:
        """Walk the conversations dir, re-parse changed/new/dirty files, drop missing."""
        await asyncio.to_thread(self._refresh_sync)

    def _refresh_sync(self) -> None:
        if not self._dir.is_dir():
            # Fresh clone — nothing to index. Lazily create so logger.save() works.
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                logger.debug("couldn't mkdir %s", self._dir, exc_info=True)
            self._cache.clear()
            self._dirty.clear()
            return

        seen_paths: set[str] = set()
        for year_dir in sorted(self._dir.iterdir()):
            if not year_dir.is_dir():
                continue
            for path in year_dir.glob("*.json"):
                key = str(path)
                seen_paths.add(key)
                try:
                    mtime = path.stat().st_mtime_ns
                except OSError:
                    continue

                file_id = path.stem
                cached = self._cache.get(key)
                if cached is not None and cached[0] == mtime and file_id not in self._dirty:
                    continue  # Unchanged — skip.

                summary = self._parse_file(path)
                if summary is not None:
                    self._cache[key] = (mtime, summary)

        # Drop entries for files that no longer exist.
        for stale in set(self._cache) - seen_paths:
            self._cache.pop(stale, None)
        self._dirty.clear()

    def _parse_file(self, path: Path) -> dict[str, Any] | None:
        """Read + migrate + extract a summary. Returns None on corrupt/unreadable file."""
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as e:
            # Non-atomic writes race — skip this pass, next refresh picks it up.
            logger.debug("skipping unreadable %s: %s", path, e)
            return None

        try:
            data = migrate_conversation(data)
        except Exception as e:  # never let one bad file kill the whole refresh
            logger.debug("skipping unmigrateable %s: %s", path, e)
            return None

        try:
            return _build_summary_dict(path, data)
        except Exception as e:
            logger.debug("skipping unparseable %s: %s", path, e)
            return None

    def list(
        self,
        *,
        q: str | None = None,
        agent: str | None = None,
        tool: str | None = None,
        date: str = "all",  # "all" | "today" | "7d" | "30d"
        sort: str = "recent",  # "recent" | "cost" | "messages"
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Filtered + sorted + paginated summaries. Returns (items, total_unpaginated)."""
        items = [s for _, s in self._cache.values()]

        if q:
            ql = q.lower()
            items = [s for s in items if ql in s["title"].lower()]
        if agent and agent != "all":
            items = [s for s in items if agent in s["agents"]]
        if tool and tool != "all":
            items = [s for s in items if tool in s["tools"]]
        if date != "all":
            items = [s for s in items if _in_date_range(s["date"], date)]

        if sort == "cost":
            items.sort(key=lambda s: (-(s["cost"] or 0.0), s["id"]))
        elif sort == "messages":
            items.sort(key=lambda s: (-(s["messages"] or 0), s["id"]))
        else:  # recent
            items.sort(key=lambda s: s["id"], reverse=True)

        total = len(items)
        return items[offset : offset + limit], total

    def delete(self, conv_id: str) -> bool:
        """Hard-delete a conversation: unlink the JSON file and evict from cache.

        Returns True if a file was found and unlinked, False if not found.
        ChromaDB cleanup is the caller's responsibility (RAG is opt-in and
        not always wired into the GUI process).
        """
        path = self._path_for(conv_id)
        if path is None or not path.is_file():
            return False
        try:
            path.unlink()
        except OSError as e:
            logger.warning("delete(%s) unlink failed: %s", conv_id, e)
            return False
        self._cache.pop(str(path), None)
        self._dirty.discard(conv_id)
        return True

    def get(self, conv_id: str) -> ConversationDetail | None:
        """Load full detail for one conversation. None if not found."""
        path = self._path_for(conv_id)
        if path is None or not path.is_file():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data = migrate_conversation(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("get(%s) read failed: %s", conv_id, e)
            return None

        summary_dict = _build_summary_dict(path, data)
        messages = data.get("messages", []) or []
        summary = ConversationSummary(**summary_dict)
        return ConversationDetail(
            summary=summary,
            messages=messages,
            preview=preview_messages(messages),
        )

    def facets(self) -> dict[str, Any]:
        """Aggregate filter-chip data: unique agents + tools + totals."""
        agent_counts: dict[str, int] = {}
        tool_counts: dict[str, int] = {}
        for _, s in self._cache.values():
            for a in s["agents"]:
                agent_counts[a] = agent_counts.get(a, 0) + 1
            for t in s["tools"]:
                tool_counts[t] = tool_counts.get(t, 0) + 1

        return {
            "agents": [{"id": a, "count": c} for a, c in sorted(agent_counts.items(), key=lambda kv: (-kv[1], kv[0]))],
            "tools": [{"id": t, "count": c} for t, c in sorted(tool_counts.items(), key=lambda kv: (-kv[1], kv[0]))],
            "total": len(self._cache),
        }

    def _path_for(self, conv_id: str) -> Path | None:
        """Look up the on-disk path for a given summary id (filename stem)."""
        # Scan cache first — O(N) but N is small and avoids recomputing year dirs.
        for path_str in self._cache:
            if Path(path_str).stem == conv_id:
                return Path(path_str)
        # Fall back to a filesystem probe (handles a new file not yet indexed).
        if not self._dir.is_dir():
            return None
        for year_dir in self._dir.iterdir():
            if year_dir.is_dir():
                candidate = year_dir / f"{conv_id}.json"
                if candidate.is_file():
                    return candidate
        return None


def _in_date_range(date_str: str, preset: str, *, today: str | None = None) -> bool:
    """Date preset filter, matching the prototype's inDateRange()."""
    from datetime import date, datetime

    if preset == "all":
        return True
    try:
        target = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return False
    today_d = date.fromisoformat(today) if today else datetime.now().date()
    days = (today_d - target).days
    if preset == "today":
        return days == 0
    if preset == "7d":
        return 0 <= days < 7
    if preset == "30d":
        return 0 <= days < 30
    return True


def _build_summary_dict(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Extract the summary dict from a migrated conversation JSON."""
    messages = data.get("messages", []) or []
    metrics = data.get("metrics", {}) or {}
    model_cfg = data.get("model", {}) or {}

    session_start = data.get("session_start")
    # Prefer session_start's date; fall back to the filename stem's date prefix.
    if isinstance(session_start, str) and len(session_start) >= 10:
        date_str = session_start[:10]
    else:
        stem = path.stem
        date_str = stem[:10] if len(stem) >= 10 else ""

    agents = agents_seen(messages)
    # Dominant agent first so the sidebar/list left-border pick is stable.
    dom = dominant_agent(agents)
    if dom and agents and agents[0] != dom:
        agents = [dom] + [a for a in agents if a != dom]

    return {
        "id": path.stem,
        "date": date_str,
        "title": title_from_messages(messages),
        "agents": agents,
        "messages": len(messages),
        "tokens": int(metrics.get("total_tokens") or 0),
        "cost": float(metrics.get("total_cost_usd") or 0.0),
        "duration_ms": duration_ms(session_start, data.get("session_end")),
        "tool_calls": tool_call_count(messages),
        "tools": tools_used(messages),
        "handoffs": handoff_count(messages),
        "model": str(model_cfg.get("id") or ""),
        "provider": str(model_cfg.get("provider") or ""),
    }
