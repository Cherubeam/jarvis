"""Tests for ``apps.gui.server.agents.prompt_history`` snapshot store."""

from __future__ import annotations

import json
from pathlib import Path

from apps.gui.server.agents.prompt_history import (
    SnapshotMeta,
    ensure_pre_first_save_snapshot,
    list_snapshots,
    read_snapshot,
    write_snapshot,
)


def test_write_snapshot_creates_file_and_index_row(tmp_path: Path) -> None:
    meta = write_snapshot(tmp_path, "writer", "prompt v1", kind="save", note="first edit")
    snap_file = tmp_path / "writer" / f"{meta.id}.md"
    assert snap_file.read_text(encoding="utf-8") == "prompt v1"
    assert meta.bytes == len(b"prompt v1")
    assert meta.kind == "save"
    assert meta.note == "first edit"


def test_index_json_is_written_newest_first(tmp_path: Path) -> None:
    first = write_snapshot(tmp_path, "writer", "v1")
    second = write_snapshot(tmp_path, "writer", "v2")
    third = write_snapshot(tmp_path, "writer", "v3")
    index_raw = json.loads((tmp_path / "writer" / "index.json").read_text(encoding="utf-8"))
    ids = [row["id"] for row in index_raw]
    assert ids == [third.id, second.id, first.id]


def test_list_snapshots_returns_newest_first(tmp_path: Path) -> None:
    a = write_snapshot(tmp_path, "writer", "a")
    b = write_snapshot(tmp_path, "writer", "b")
    rows = list_snapshots(tmp_path, "writer")
    assert [r.id for r in rows] == [b.id, a.id]


def test_list_snapshots_returns_empty_for_unknown_agent(tmp_path: Path) -> None:
    assert list_snapshots(tmp_path, "never-existed") == []


def test_read_snapshot_roundtrips_content(tmp_path: Path) -> None:
    meta = write_snapshot(tmp_path, "writer", "the full prompt body")
    assert read_snapshot(tmp_path, "writer", meta.id) == "the full prompt body"


def test_read_snapshot_returns_none_for_missing_file(tmp_path: Path) -> None:
    write_snapshot(tmp_path, "writer", "x")
    assert read_snapshot(tmp_path, "writer", "20990101T000000_000000Z") is None


def test_read_snapshot_rejects_invalid_id_format(tmp_path: Path) -> None:
    # Path-traversal and non-matching patterns should return None, not raise.
    assert read_snapshot(tmp_path, "writer", "../../etc/passwd") is None
    assert read_snapshot(tmp_path, "writer", "not-a-timestamp") is None


def test_ensure_pre_first_save_is_idempotent(tmp_path: Path) -> None:
    first = ensure_pre_first_save_snapshot(tmp_path, "writer", "original")
    assert first is not None
    assert first.kind == "pre_first_save"
    # Second call must be a no-op.
    second = ensure_pre_first_save_snapshot(tmp_path, "writer", "newer")
    assert second is None
    rows = list_snapshots(tmp_path, "writer")
    assert len(rows) == 1
    assert rows[0].id == first.id


def test_ensure_pre_first_save_skips_when_any_snapshot_exists(tmp_path: Path) -> None:
    write_snapshot(tmp_path, "writer", "v1", kind="save")
    assert ensure_pre_first_save_snapshot(tmp_path, "writer", "original") is None


def test_index_rebuilds_from_disk_when_index_missing(tmp_path: Path) -> None:
    meta_a = write_snapshot(tmp_path, "writer", "a")
    meta_b = write_snapshot(tmp_path, "writer", "b")
    # Delete index.json — list_snapshots must reconstruct from .md files.
    (tmp_path / "writer" / "index.json").unlink()
    rows = list_snapshots(tmp_path, "writer")
    ids = {r.id for r in rows}
    assert ids == {meta_a.id, meta_b.id}
    # Rebuild loses kind/note — everything defaults to "save".
    assert all(r.kind == "save" and r.note is None for r in rows)


def test_index_rebuilds_from_disk_when_index_corrupt(tmp_path: Path) -> None:
    meta = write_snapshot(tmp_path, "writer", "a")
    (tmp_path / "writer" / "index.json").write_text("{not json", encoding="utf-8")
    rows = list_snapshots(tmp_path, "writer")
    assert [r.id for r in rows] == [meta.id]


def test_snapshot_id_format_is_microsecond_resolution(tmp_path: Path) -> None:
    meta = write_snapshot(tmp_path, "writer", "x")
    # Example: 20260423T091530_123456Z — 23 chars: 8 date, T, 6 time, _, 6 µs, Z.
    assert len(meta.id) == 23
    assert meta.id[8] == "T"
    assert meta.id[15] == "_"
    assert meta.id.endswith("Z")


def test_bytes_reflects_utf8_length_not_char_count(tmp_path: Path) -> None:
    # "ü" is 2 bytes in UTF-8, 1 char.
    meta = write_snapshot(tmp_path, "writer", "ü")
    assert meta.bytes == 2


def test_snapshot_meta_json_roundtrip_preserves_kind_and_note() -> None:
    meta = SnapshotMeta(
        id="20260423T091530_000000Z",
        timestamp="2026-04-23T09:15:30+00:00",
        bytes=7,
        kind="pre_restore",
        note="before restoring x",
    )
    round_tripped = SnapshotMeta.from_json(meta.to_json())
    assert round_tripped == meta
