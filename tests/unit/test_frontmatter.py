"""Tests for packages.core.frontmatter."""

from pathlib import Path

import pytest

from packages.core import frontmatter


def test_parse_with_frontmatter():
    text = "---\nfoo: bar\nn: 3\n---\nBody text"
    meta, body = frontmatter.parse(text)
    assert meta == {"foo": "bar", "n": 3}
    assert body == "Body text"


def test_parse_no_frontmatter_returns_empty_meta():
    text = "No frontmatter here"
    meta, body = frontmatter.parse(text)
    assert meta == {}
    assert body == "No frontmatter here"


def test_parse_empty_frontmatter_block():
    text = "---\n\n---\nBody"
    meta, body = frontmatter.parse(text)
    assert meta == {}
    assert body == "Body"


def test_parse_does_not_treat_three_dashes_in_body_as_frontmatter():
    text = "Regular text\n---\nnot frontmatter"
    meta, body = frontmatter.parse(text)
    assert meta == {}
    assert body == text


def test_dump_preserves_key_order():
    meta = {"zebra": 1, "alpha": 2, "middle": 3}
    output = frontmatter.dump(meta, "body")
    assert output == "---\nzebra: 1\nalpha: 2\nmiddle: 3\n---\nbody"


def test_dump_with_empty_metadata_returns_body_only():
    assert frontmatter.dump({}, "just body") == "just body"


def test_dump_appends_body_verbatim():
    meta = {"k": "v"}
    body = "Line 1\nLine 2\n"
    output = frontmatter.dump(meta, body)
    assert output.endswith("---\nLine 1\nLine 2\n")


def test_dump_handles_unicode():
    meta = {"what": "café — résumé"}
    output = frontmatter.dump(meta, "")
    assert "café — résumé" in output


def test_roundtrip_preserves_metadata_and_body():
    meta_in = {"status": "pending", "revisit_at": "2026-05-18", "n": 3}
    body_in = "Some retrospective note.\n\nSecond paragraph."
    text = frontmatter.dump(meta_in, body_in)
    meta_out, body_out = frontmatter.parse(text)
    assert meta_out == meta_in
    assert body_out == body_in


def test_write_atomic_creates_file(tmp_path: Path):
    target = tmp_path / "sub" / "note.md"
    frontmatter.write_atomic(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_write_atomic_overwrites_existing(tmp_path: Path):
    target = tmp_path / "note.md"
    target.write_text("old", encoding="utf-8")
    frontmatter.write_atomic(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_write_atomic_cleans_up_on_error(tmp_path: Path, monkeypatch):
    target = tmp_path / "note.md"
    original_replace = __import__("os").replace

    def failing_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", failing_replace)
    with pytest.raises(OSError):
        frontmatter.write_atomic(target, "content")

    monkeypatch.setattr("os.replace", original_replace)
    leftover_tmp = list(tmp_path.glob(".note.md.*.tmp"))
    assert leftover_tmp == []


def test_write_atomic_does_not_leave_tmp_files(tmp_path: Path):
    target = tmp_path / "note.md"
    frontmatter.write_atomic(target, "hello")
    tmp_files = [p.name for p in tmp_path.iterdir() if p.name.startswith(".note.md.")]
    assert tmp_files == []
