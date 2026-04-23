"""Per-agent system-prompt snapshot store.

Snapshots live at ``<history_root>/<agent_id>/<YYYYMMDDTHHMMSS_ffffffZ>.md``
with a sibling ``index.json`` summarising ``[{id, timestamp, bytes, kind,
note?}]``. Snapshot files are the source of truth — if ``index.json`` is
missing or unreadable, we rebuild from directory contents.

Use :func:`write_snapshot` to record a point-in-time copy (Save / Restore
call sites). :func:`list_snapshots` returns newest-first for the Versions
tab. :func:`read_snapshot` reads a single snapshot back for preview or
restore.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from packages.core.frontmatter import write_atomic

logger = logging.getLogger(__name__)

SnapshotKind = Literal["save", "pre_first_save", "pre_restore"]

_SNAPSHOT_FILENAME_RE = re.compile(r"^(\d{8}T\d{6}_\d{6}Z)\.md$")


@dataclass(frozen=True)
class SnapshotMeta:
    """One row in the snapshot index."""

    id: str
    timestamp: str  # ISO-8601 UTC
    bytes: int
    kind: SnapshotKind
    note: str | None = None

    def to_json(self) -> dict[str, object]:
        d: dict[str, object] = {
            "id": self.id,
            "timestamp": self.timestamp,
            "bytes": self.bytes,
            "kind": self.kind,
        }
        if self.note is not None:
            d["note"] = self.note
        return d

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> SnapshotMeta:
        kind = raw.get("kind", "save")
        if kind not in ("save", "pre_first_save", "pre_restore"):
            kind = "save"
        return cls(
            id=str(raw["id"]),
            timestamp=str(raw["timestamp"]),
            bytes=int(raw.get("bytes", 0) or 0),
            kind=kind,
            note=str(raw["note"]) if raw.get("note") is not None else None,
        )


def _now_id() -> tuple[str, str]:
    """Return ``(snapshot_id, iso_timestamp)`` — microsecond-resolution UTC."""
    now = datetime.now(UTC)
    snapshot_id = now.strftime("%Y%m%dT%H%M%S_%fZ")
    return snapshot_id, now.isoformat()


def agent_history_dir(history_root: Path, agent_id: str) -> Path:
    """Path to an agent's snapshot directory (does not create it)."""
    return history_root / agent_id


def _index_path(history_root: Path, agent_id: str) -> Path:
    return agent_history_dir(history_root, agent_id) / "index.json"


def _snapshot_path(history_root: Path, agent_id: str, snapshot_id: str) -> Path:
    return agent_history_dir(history_root, agent_id) / f"{snapshot_id}.md"


def _rebuild_index_from_disk(history_root: Path, agent_id: str) -> list[SnapshotMeta]:
    """Recover snapshot metadata by scanning the agent's directory.

    Used when ``index.json`` is missing or unreadable. Can't recover ``kind``
    or ``note``, so every recovered row is tagged as ``save`` with no note.
    """
    snap_dir = agent_history_dir(history_root, agent_id)
    if not snap_dir.is_dir():
        return []
    rows: list[SnapshotMeta] = []
    for p in snap_dir.iterdir():
        m = _SNAPSHOT_FILENAME_RE.match(p.name)
        if not m:
            continue
        snap_id = m.group(1)
        try:
            size = p.stat().st_size
        except OSError:
            continue
        # Parse snap_id back to ISO timestamp.
        try:
            dt = datetime.strptime(snap_id, "%Y%m%dT%H%M%S_%fZ").replace(tzinfo=UTC)
            ts = dt.isoformat()
        except ValueError:
            ts = snap_id
        rows.append(SnapshotMeta(id=snap_id, timestamp=ts, bytes=size, kind="save", note=None))
    rows.sort(key=lambda r: r.id, reverse=True)
    return rows


def list_snapshots(history_root: Path, agent_id: str) -> list[SnapshotMeta]:
    """Return snapshots for ``agent_id``, newest-first.

    Reads ``index.json`` when available; falls back to a directory scan if the
    index is missing, unreadable, or malformed. Directory scan loses ``kind``
    and ``note`` data — treat it as a safety net, not a feature.
    """
    idx_path = _index_path(history_root, agent_id)
    if not idx_path.is_file():
        return _rebuild_index_from_disk(history_root, agent_id)
    try:
        raw = json.loads(idx_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("prompt-history index.json unreadable for %s; rebuilding", agent_id)
        return _rebuild_index_from_disk(history_root, agent_id)
    if not isinstance(raw, list):
        return _rebuild_index_from_disk(history_root, agent_id)
    rows: list[SnapshotMeta] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            rows.append(SnapshotMeta.from_json(item))
        except (KeyError, ValueError, TypeError):
            continue
    rows.sort(key=lambda r: r.id, reverse=True)
    return rows


def read_snapshot(history_root: Path, agent_id: str, snapshot_id: str) -> str | None:
    """Return snapshot content, or ``None`` if the file is missing."""
    if not _SNAPSHOT_FILENAME_RE.match(f"{snapshot_id}.md"):
        return None
    path = _snapshot_path(history_root, agent_id, snapshot_id)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def write_snapshot(
    history_root: Path,
    agent_id: str,
    content: str,
    *,
    kind: SnapshotKind = "save",
    note: str | None = None,
) -> SnapshotMeta:
    """Persist ``content`` as a new snapshot; update ``index.json``.

    Returns the new :class:`SnapshotMeta`. Content is written atomically via
    :func:`packages.core.frontmatter.write_atomic`. List existing snapshots
    *before* the on-disk write so the directory-glob fallback (used when
    ``index.json`` is missing/corrupt) doesn't double-count the new entry.
    """
    snapshot_id, ts = _now_id()
    meta = SnapshotMeta(
        id=snapshot_id,
        timestamp=ts,
        bytes=len(content.encode("utf-8")),
        kind=kind,
        note=note,
    )

    existing = list_snapshots(history_root, agent_id)

    path = _snapshot_path(history_root, agent_id, snapshot_id)
    write_atomic(path, content)

    rows = [meta, *existing]
    _write_index(history_root, agent_id, rows)
    return meta


def _write_index(history_root: Path, agent_id: str, rows: list[SnapshotMeta]) -> None:
    idx_path = _index_path(history_root, agent_id)
    payload = json.dumps([r.to_json() for r in rows], indent=2)
    write_atomic(idx_path, payload)


def ensure_pre_first_save_snapshot(
    history_root: Path,
    agent_id: str,
    current_content: str,
) -> SnapshotMeta | None:
    """Snapshot the pre-edit state on the very first Save for this agent.

    Idempotent: returns ``None`` if any snapshot already exists for the
    agent. Otherwise records ``current_content`` with ``kind="pre_first_save"``
    so the original prompt is always recoverable from the Versions tab.
    """
    if list_snapshots(history_root, agent_id):
        return None
    return write_snapshot(
        history_root,
        agent_id,
        current_content,
        kind="pre_first_save",
        note="original before first save",
    )
