"""Tests for apps.cli.review."""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

from apps.cli.review import (
    PendingItem,
    apply_review,
    handle_review_command,
    load_pending_due,
    pending_item_to_wire,
)
from packages.core import frontmatter

TODAY = date(2026, 5, 18)
NOW = datetime(2026, 5, 18, 19, 12, 0)


def _write_outcome(
    tmp_path: Path,
    name: str,
    status: str = "pending",
    revisit_at: str = "2026-05-15",
    what: str = "Do the thing",
    why: str = "Because reasons",
    success_looks_like: str = "",
) -> Path:
    meta = {
        "created_at": "2026-04-18T14:32:00",
        "revisit_at": revisit_at,
        "status": status,
        "what": what,
        "why": why,
        "success_looks_like": success_looks_like,
        "conversation_id": "c1",
    }
    path = tmp_path / name
    path.write_text(frontmatter.dump(meta, ""), encoding="utf-8")
    return path


# --- load_pending_due ---


def test_load_pending_due_returns_empty_when_dir_missing(tmp_path: Path):
    result = load_pending_due(tmp_path / "does-not-exist", today=TODAY)
    assert result == []


def test_load_pending_due_returns_empty_when_no_files(tmp_path: Path):
    result = load_pending_due(tmp_path, today=TODAY)
    assert result == []


def test_load_pending_due_filters_reviewed_items(tmp_path: Path):
    _write_outcome(tmp_path, "reviewed.md", status="reviewed", revisit_at="2026-05-10")
    _write_outcome(tmp_path, "pending.md", status="pending", revisit_at="2026-05-10")
    result = load_pending_due(tmp_path, today=TODAY)
    assert len(result) == 1
    assert result[0].path.name == "pending.md"


def test_load_pending_due_filters_future_revisits(tmp_path: Path):
    _write_outcome(tmp_path, "future.md", revisit_at="2026-06-01")
    _write_outcome(tmp_path, "due.md", revisit_at="2026-05-10")
    result = load_pending_due(tmp_path, today=TODAY)
    assert len(result) == 1
    assert result[0].path.name == "due.md"


def test_load_pending_due_includes_exactly_today(tmp_path: Path):
    _write_outcome(tmp_path, "today.md", revisit_at="2026-05-18")
    result = load_pending_due(tmp_path, today=TODAY)
    assert len(result) == 1


def test_load_pending_due_sorts_by_revisit_date_ascending(tmp_path: Path):
    _write_outcome(tmp_path, "c.md", revisit_at="2026-05-15")
    _write_outcome(tmp_path, "a.md", revisit_at="2026-05-10")
    _write_outcome(tmp_path, "b.md", revisit_at="2026-05-12")
    result = load_pending_due(tmp_path, today=TODAY)
    assert [i.path.name for i in result] == ["a.md", "b.md", "c.md"]


def test_load_pending_due_skips_malformed_without_crashing(tmp_path: Path):
    (tmp_path / "bad.md").write_text("---\nnot: valid: yaml: here\n---\nbody", encoding="utf-8")
    _write_outcome(tmp_path, "good.md", revisit_at="2026-05-10")
    result = load_pending_due(tmp_path, today=TODAY)
    assert len(result) == 1
    assert result[0].path.name == "good.md"


def test_load_pending_due_skips_missing_revisit_at(tmp_path: Path):
    (tmp_path / "no-date.md").write_text(
        frontmatter.dump({"status": "pending", "what": "x"}, ""),
        encoding="utf-8",
    )
    _write_outcome(tmp_path, "has-date.md", revisit_at="2026-05-10")
    result = load_pending_due(tmp_path, today=TODAY)
    assert [i.path.name for i in result] == ["has-date.md"]


def test_load_pending_due_skips_invalid_revisit_at(tmp_path: Path):
    (tmp_path / "bad-date.md").write_text(
        frontmatter.dump({"status": "pending", "revisit_at": "soonish"}, ""),
        encoding="utf-8",
    )
    _write_outcome(tmp_path, "good.md", revisit_at="2026-05-10")
    result = load_pending_due(tmp_path, today=TODAY)
    assert [i.path.name for i in result] == ["good.md"]


# --- apply_review ---


def test_apply_review_updates_frontmatter_keys(tmp_path: Path):
    path = _write_outcome(tmp_path, "x.md")
    meta, body = frontmatter.parse(path.read_text())
    item = PendingItem(path=path, meta=meta, body=body)

    apply_review(item, outcome="happened", quality=4, note="went well", now=NOW)

    updated_meta, updated_body = frontmatter.parse(path.read_text())
    assert updated_meta["status"] == "reviewed"
    assert updated_meta["outcome"] == "happened"
    assert updated_meta["quality"] == 4
    assert updated_meta["reviewed_at"] == "2026-05-18T19:12:00"
    assert updated_body == "went well"


def test_apply_review_preserves_original_keys(tmp_path: Path):
    path = _write_outcome(tmp_path, "x.md", what="keep me", why="and me")
    meta, body = frontmatter.parse(path.read_text())
    item = PendingItem(path=path, meta=meta, body=body)

    apply_review(item, outcome="didnt", quality=1, note="", now=NOW)

    updated_meta, _ = frontmatter.parse(path.read_text())
    assert updated_meta["what"] == "keep me"
    assert updated_meta["why"] == "and me"
    assert updated_meta["conversation_id"] == "c1"


# --- pending_item_to_wire ---


def test_pending_item_to_wire_full_fields(tmp_path: Path):
    path = _write_outcome(
        tmp_path,
        "2026-04-18-do-the-thing.md",
        what="Do the thing",
        why="Because reasons",
        revisit_at="2026-05-10",
        success_looks_like="Thing is done",
    )
    meta, body = frontmatter.parse(path.read_text())
    item = PendingItem(path=path, meta=meta, body=body)

    wire = pending_item_to_wire(item)

    assert wire["file_id"] == "2026-04-18-do-the-thing"
    assert wire["what"] == "Do the thing"
    assert wire["why"] == "Because reasons"
    assert wire["created_at"] == "2026-04-18T14:32:00"
    assert wire["revisit_at"] == "2026-05-10"
    assert wire["success_looks_like"] == "Thing is done"


def test_pending_item_to_wire_empty_success_maps_to_none(tmp_path: Path):
    path = _write_outcome(tmp_path, "x.md", success_looks_like="")
    meta, body = frontmatter.parse(path.read_text())
    item = PendingItem(path=path, meta=meta, body=body)

    wire = pending_item_to_wire(item)

    assert wire["success_looks_like"] is None


def test_pending_item_to_wire_file_id_is_stem(tmp_path: Path):
    path = _write_outcome(tmp_path, "some-file.md")
    meta, body = frontmatter.parse(path.read_text())
    item = PendingItem(path=path, meta=meta, body=body)

    wire = pending_item_to_wire(item)

    assert wire["file_id"] == "some-file"
    assert ".md" not in wire["file_id"]


# --- handle_review_command ---


def test_handle_review_empty_prints_message(tmp_path: Path):
    console = MagicMock()
    session = MagicMock()
    result = handle_review_command(tmp_path, console, session, today=TODAY, now=NOW)
    assert result == 0
    console.print.assert_called_once_with("No items due for review.")
    session.prompt.assert_not_called()


def test_handle_review_full_flow_single_item(tmp_path: Path):
    _write_outcome(tmp_path, "item1.md", what="Task A", why="Reason A", revisit_at="2026-05-10")
    console = MagicMock()
    session = MagicMock()
    session.prompt.side_effect = ["happened", "5", "All good"]

    result = handle_review_command(tmp_path, console, session, today=TODAY, now=NOW)

    assert result == 1
    meta, body = frontmatter.parse((tmp_path / "item1.md").read_text())
    assert meta["status"] == "reviewed"
    assert meta["outcome"] == "happened"
    assert meta["quality"] == 5
    assert body == "All good"


def test_handle_review_multiple_items_in_revisit_order(tmp_path: Path):
    _write_outcome(tmp_path, "second.md", revisit_at="2026-05-15")
    _write_outcome(tmp_path, "first.md", revisit_at="2026-05-10")
    console = MagicMock()
    session = MagicMock()
    session.prompt.side_effect = [
        "happened",
        "4",
        "first note",
        "partial",
        "3",
        "second note",
    ]

    result = handle_review_command(tmp_path, console, session, today=TODAY, now=NOW)

    assert result == 2
    first_meta, first_body = frontmatter.parse((tmp_path / "first.md").read_text())
    second_meta, second_body = frontmatter.parse((tmp_path / "second.md").read_text())
    assert first_meta["outcome"] == "happened"
    assert first_body == "first note"
    assert second_meta["outcome"] == "partial"
    assert second_body == "second note"


def test_handle_review_rejects_invalid_outcome_then_accepts(tmp_path: Path):
    _write_outcome(tmp_path, "x.md", revisit_at="2026-05-10")
    console = MagicMock()
    session = MagicMock()
    session.prompt.side_effect = ["maybe", "happened", "3", "note"]

    result = handle_review_command(tmp_path, console, session, today=TODAY, now=NOW)

    assert result == 1
    meta, _ = frontmatter.parse((tmp_path / "x.md").read_text())
    assert meta["outcome"] == "happened"


def test_handle_review_rejects_invalid_quality(tmp_path: Path):
    _write_outcome(tmp_path, "x.md", revisit_at="2026-05-10")
    console = MagicMock()
    session = MagicMock()
    session.prompt.side_effect = ["happened", "10", "3", "note"]

    result = handle_review_command(tmp_path, console, session, today=TODAY, now=NOW)

    assert result == 1
    meta, _ = frontmatter.parse((tmp_path / "x.md").read_text())
    assert meta["quality"] == 3


def test_handle_review_keyboard_interrupt_preserves_earlier_files(tmp_path: Path):
    _write_outcome(tmp_path, "first.md", revisit_at="2026-05-10")
    _write_outcome(tmp_path, "second.md", revisit_at="2026-05-12")

    console = MagicMock()
    session = MagicMock()
    # Complete first item, interrupt in middle of second
    session.prompt.side_effect = [
        "happened",
        "4",
        "first done",
        KeyboardInterrupt(),
    ]

    result = handle_review_command(tmp_path, console, session, today=TODAY, now=NOW)

    assert result == 1
    first_meta, _ = frontmatter.parse((tmp_path / "first.md").read_text())
    second_meta, _ = frontmatter.parse((tmp_path / "second.md").read_text())
    assert first_meta["status"] == "reviewed"
    assert second_meta["status"] == "pending"
    assert "reviewed_at" not in second_meta


def test_handle_review_case_insensitive_outcome(tmp_path: Path):
    _write_outcome(tmp_path, "x.md", revisit_at="2026-05-10")
    console = MagicMock()
    session = MagicMock()
    session.prompt.side_effect = ["HAPPENED", "3", "note"]

    handle_review_command(tmp_path, console, session, today=TODAY, now=NOW)

    meta, _ = frontmatter.parse((tmp_path / "x.md").read_text())
    assert meta["outcome"] == "happened"
