"""Tests for packages.integrations.obsidian.writer module."""

import pytest
from pathlib import Path
from unittest.mock import Mock

from packages.core.filesystem_access import AccessLevel, AccessRule, FilesystemGuard
from packages.integrations.obsidian.vault import VaultConfig
from packages.integrations.obsidian.diff import VaultDiff
from packages.integrations.obsidian.writer import (
    ConfirmationHandler,
    CLIConfirmationHandler,
    WriteResult,
    append_to_daily_note,
    append_to_note,
)


# ==================== Test Helpers ====================


class MockConfirmationHandler(ConfirmationHandler):
    """Test implementation that auto-confirms or auto-rejects."""

    def __init__(self, confirm: bool = True):
        self.confirm = confirm
        self.presented_diff: VaultDiff | None = None

    def present_diff(self, diff: VaultDiff) -> None:
        self.presented_diff = diff

    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:
        return self.confirm


def _guard(*rules: tuple[Path, AccessLevel]) -> FilesystemGuard:
    return FilesystemGuard([AccessRule(path=p, access=a) for p, a in rules])


@pytest.fixture
def vault_with_daily_note(tmp_path):
    """Create a vault with a daily note containing a JARVIS callout."""
    daily_dir = tmp_path / "Daily Notes"
    daily_dir.mkdir()
    note = daily_dir / "2026-02-09.md"
    note.write_text(
        "# 2026-02-09\n\nSome notes here.\n\n> [!JARVIS]\n> Previous entry\n\n## Tasks\n- Buy milk",
        encoding="utf-8",
    )
    guard = _guard((daily_dir, AccessLevel.READ_WRITE))
    config = VaultConfig(
        vault_path=tmp_path,
        filesystem_guard=guard,
    )
    return config, note


@pytest.fixture
def vault_no_callout(tmp_path):
    """Create a vault with a daily note without JARVIS callout."""
    daily_dir = tmp_path / "Daily Notes"
    daily_dir.mkdir()
    note = daily_dir / "2026-02-09.md"
    note.write_text("# 2026-02-09\n\nJust notes.", encoding="utf-8")
    guard = _guard((daily_dir, AccessLevel.READ_WRITE))
    config = VaultConfig(
        vault_path=tmp_path,
        filesystem_guard=guard,
    )
    return config, note


# ==================== append_to_note ====================


class TestAppendToNote:
    def test_successful_append(self, vault_with_daily_note):
        config, note = vault_with_daily_note
        handler = MockConfirmationHandler(confirm=True)
        result = append_to_note(note, "New summary line", config, handler)
        assert result.success is True
        assert result.action == "appended"
        assert handler.presented_diff is not None
        # Verify file was actually written
        content = note.read_text(encoding="utf-8")
        assert "> New summary line" in content
        assert "> Previous entry" in content

    def test_rejected_write(self, vault_with_daily_note):
        config, note = vault_with_daily_note
        handler = MockConfirmationHandler(confirm=False)
        result = append_to_note(note, "Rejected content", config, handler)
        assert result.success is False
        assert result.action == "rejected"
        # File should be unchanged
        content = note.read_text(encoding="utf-8")
        assert "Rejected content" not in content

    def test_no_callout_block(self, vault_no_callout):
        config, note = vault_no_callout
        handler = MockConfirmationHandler()
        result = append_to_note(note, "Content", config, handler)
        assert result.success is False
        assert result.action == "no_callout"

    def test_file_not_found(self, tmp_path):
        daily_dir = tmp_path / "Daily Notes"
        daily_dir.mkdir()
        guard = _guard((daily_dir, AccessLevel.READ_WRITE))
        config = VaultConfig(
            vault_path=tmp_path,
            filesystem_guard=guard,
        )
        handler = MockConfirmationHandler()
        result = append_to_note(
            daily_dir / "missing.md", "Content", config, handler
        )
        assert result.success is False
        assert result.action == "error"

    def test_path_outside_allowed_dirs(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        secret = tmp_path / "secret"
        secret.mkdir()
        note = secret / "note.md"
        note.write_text("> [!JARVIS]\n> content")
        guard = _guard((allowed, AccessLevel.READ_WRITE))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        handler = MockConfirmationHandler()
        result = append_to_note(note, "Hack", config, handler)
        assert result.success is False
        assert result.action == "error"
        assert "denied" in result.message.lower()

    def test_read_only_path_denies_append(self, tmp_path):
        daily_dir = tmp_path / "Daily Notes"
        daily_dir.mkdir()
        note = daily_dir / "2026-02-09.md"
        note.write_text("> [!JARVIS]\n> entry")
        guard = _guard((daily_dir, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        handler = MockConfirmationHandler()
        result = append_to_note(note, "Content", config, handler)
        assert result.success is False
        assert "denied" in result.message.lower()

    def test_diff_attached_to_result(self, vault_with_daily_note):
        config, note = vault_with_daily_note
        handler = MockConfirmationHandler(confirm=True)
        result = append_to_note(note, "Entry", config, handler)
        assert result.diff is not None
        assert result.diff.file_path

    def test_multi_line_content(self, vault_with_daily_note):
        config, note = vault_with_daily_note
        handler = MockConfirmationHandler(confirm=True)
        result = append_to_note(
            note, "- Item one\n- Item two\n- Item three", config, handler
        )
        assert result.success is True
        content = note.read_text(encoding="utf-8")
        assert "> - Item one" in content
        assert "> - Item two" in content
        assert "> - Item three" in content


# ==================== append_to_daily_note ====================


class TestAppendToDailyNote:
    def test_append_to_specific_date(self, vault_with_daily_note):
        config, note = vault_with_daily_note
        handler = MockConfirmationHandler(confirm=True)
        result = append_to_daily_note(
            "Daily summary", config, handler, date="2026-02-09"
        )
        assert result.success is True
        assert result.action == "appended"

    def test_missing_daily_note(self, tmp_path):
        daily_dir = tmp_path / "Daily Notes"
        daily_dir.mkdir()
        guard = _guard((daily_dir, AccessLevel.READ_WRITE))
        config = VaultConfig(
            vault_path=tmp_path,
            filesystem_guard=guard,
        )
        handler = MockConfirmationHandler()
        result = append_to_daily_note(
            "Content", config, handler, date="2099-01-01"
        )
        assert result.success is False


# ==================== CLIConfirmationHandler ====================


class TestCLIConfirmationHandler:
    def test_present_diff_prints(self, capsys):
        handler = CLIConfirmationHandler()
        diff = VaultDiff(
            file_path="test.md",
            original_content="old",
            proposed_content="new",
        )
        handler.present_diff(diff)
        captured = capsys.readouterr()
        assert "test.md" in captured.out

    def test_get_confirmation_yes(self, monkeypatch):
        handler = CLIConfirmationHandler()
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert handler.get_confirmation() is True

    def test_get_confirmation_no(self, monkeypatch):
        handler = CLIConfirmationHandler()
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert handler.get_confirmation() is False

    def test_get_confirmation_empty(self, monkeypatch):
        handler = CLIConfirmationHandler()
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert handler.get_confirmation() is False

    def test_get_confirmation_eof(self, monkeypatch):
        handler = CLIConfirmationHandler()

        def raise_eof(_):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        assert handler.get_confirmation() is False
