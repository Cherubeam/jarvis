"""Tests for packages.integrations.obsidian.vault module."""

from pathlib import Path

import pytest

from packages.core.filesystem_access import AccessLevel, AccessRule, FilesystemGuard
from packages.core.settings import ObsidianDailyNotesSettings, ObsidianSettings
from packages.integrations.obsidian.vault import (
    VaultConfig,
    get_daily_note_path,
    list_notes,
    load_vault_config,
    read_note,
    validate_read,
    validate_write,
)


def _guard(*rules: tuple[Path, AccessLevel]) -> FilesystemGuard:
    """Helper to create a guard from (path, access) tuples."""
    return FilesystemGuard([AccessRule(path=p, access=a) for p, a in rules])


# ==================== VaultConfig ====================


class TestVaultConfig:
    def test_default_values(self, tmp_path):
        guard = FilesystemGuard([])
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert config.vault_path == tmp_path
        assert config.daily_note_path_format == "Daily Notes/%Y-%m-%d"
        assert config.enabled is True

    def test_custom_values(self, tmp_path):
        guard = _guard((tmp_path / "notes", AccessLevel.READ))
        config = VaultConfig(
            vault_path=tmp_path,
            filesystem_guard=guard,
            daily_note_path_format="Journal/%d-%m-%Y",
            enabled=True,
        )
        assert config.daily_note_path_format == "Journal/%d-%m-%Y"


# ==================== load_vault_config ====================


class TestLoadVaultConfig:
    def test_disabled_returns_none(self):
        obsidian = ObsidianSettings(enabled=False, vault_path="/some/path")
        assert load_vault_config(obsidian) is None

    def test_default_obsidian_returns_none(self):
        assert load_vault_config(ObsidianSettings()) is None

    def test_empty_vault_path_returns_none(self):
        obsidian = ObsidianSettings(enabled=True, vault_path="")
        assert load_vault_config(obsidian) is None

    def test_nonexistent_vault_path_returns_none(self):
        obsidian = ObsidianSettings(enabled=True, vault_path="/nonexistent/path")
        assert load_vault_config(obsidian) is None

    def test_valid_config(self, tmp_path):
        daily_dir = tmp_path / "Daily Notes"
        daily_dir.mkdir()
        guard = _guard((daily_dir, AccessLevel.READ_WRITE))
        obsidian = ObsidianSettings(
            enabled=True,
            vault_path=str(tmp_path),
            daily_notes=ObsidianDailyNotesSettings(path_format="Daily Notes/%Y-%m-%d"),
        )
        result = load_vault_config(obsidian, filesystem_guard=guard)
        assert result is not None
        assert result.vault_path == tmp_path.resolve()
        assert result.enabled is True
        assert result.daily_note_path_format == "Daily Notes/%Y-%m-%d"

    def test_defaults_for_missing_daily_notes_section(self, tmp_path):
        obsidian = ObsidianSettings(enabled=True, vault_path=str(tmp_path))
        result = load_vault_config(obsidian)
        assert result is not None
        assert result.daily_note_path_format == "Daily Notes/%Y-%m-%d"

    def test_none_guard_creates_empty_guard(self, tmp_path):
        obsidian = ObsidianSettings(enabled=True, vault_path=str(tmp_path))
        result = load_vault_config(obsidian, filesystem_guard=None)
        assert result is not None
        # Empty guard denies everything
        assert result.filesystem_guard.check_read(tmp_path / "file.md") is False


# ==================== validate_read / validate_write ====================


class TestValidateRead:
    def test_read_allowed(self, tmp_path):
        guard = _guard((tmp_path, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert validate_read(tmp_path / "file.md", config) is True

    def test_read_denied(self, tmp_path):
        guard = FilesystemGuard([])
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert validate_read(tmp_path / "file.md", config) is False

    def test_write_only_denies_read(self, tmp_path):
        guard = _guard((tmp_path, AccessLevel.WRITE))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert validate_read(tmp_path / "file.md", config) is False

    def test_read_write_allows_read(self, tmp_path):
        guard = _guard((tmp_path, AccessLevel.READ_WRITE))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert validate_read(tmp_path / "file.md", config) is True


class TestValidateWrite:
    def test_write_allowed(self, tmp_path):
        guard = _guard((tmp_path, AccessLevel.WRITE))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert validate_write(tmp_path / "file.md", config) is True

    def test_write_denied(self, tmp_path):
        guard = FilesystemGuard([])
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert validate_write(tmp_path / "file.md", config) is False

    def test_read_only_denies_write(self, tmp_path):
        guard = _guard((tmp_path, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert validate_write(tmp_path / "file.md", config) is False

    def test_read_write_allows_write(self, tmp_path):
        guard = _guard((tmp_path, AccessLevel.READ_WRITE))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert validate_write(tmp_path / "file.md", config) is True

    def test_traversal_blocked(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        guard = _guard((allowed, AccessLevel.READ_WRITE))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        traversal = allowed / ".." / "secret" / "file.md"
        assert validate_write(traversal, config) is False


# ==================== read_note ====================


class TestReadNote:
    def test_read_valid_note(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        note = notes / "test.md"
        note.write_text("# Hello\nContent here", encoding="utf-8")
        guard = _guard((notes, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        assert read_note(note, config) == "# Hello\nContent here"

    def test_read_outside_allowed_raises(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        outside = tmp_path / "secret.md"
        outside.write_text("secret")
        guard = _guard((notes, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        with pytest.raises(PermissionError):
            read_note(outside, config)

    def test_read_nonexistent_file_raises(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        guard = _guard((notes, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        with pytest.raises(FileNotFoundError):
            read_note(notes / "missing.md", config)


# ==================== list_notes ====================


class TestListNotes:
    def test_list_notes_in_directory(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        (notes / "a.md").write_text("a")
        (notes / "b.md").write_text("b")
        (notes / "c.txt").write_text("c")
        guard = _guard((notes, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        result = list_notes(notes, config)
        assert len(result) == 2
        assert all(p.suffix == ".md" for p in result)

    def test_list_notes_outside_allowed_raises(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        outside = tmp_path / "secret"
        outside.mkdir()
        guard = _guard((notes, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        with pytest.raises(PermissionError):
            list_notes(outside, config)

    def test_list_notes_nonexistent_dir(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        guard = _guard((notes, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        result = list_notes(notes / "subdir", config)
        assert result == []

    def test_list_notes_custom_pattern(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        (notes / "a.md").write_text("a")
        (notes / "b.txt").write_text("b")
        guard = _guard((notes, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        result = list_notes(notes, config, pattern="*.txt")
        assert len(result) == 1
        assert result[0].name == "b.txt"


# ==================== get_daily_note_path ====================


class TestGetDailyNotePath:
    def test_default_today(self, tmp_path):
        from datetime import date

        guard = FilesystemGuard([])
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        result = get_daily_note_path(config)
        expected = tmp_path / "Daily Notes" / f"{date.today().strftime('%Y-%m-%d')}.md"
        assert result == expected

    def test_specific_date(self, tmp_path):
        guard = FilesystemGuard([])
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        result = get_daily_note_path(config, target_date="2026-02-09")
        assert result == tmp_path / "Daily Notes" / "2026-02-09.md"

    def test_custom_format(self, tmp_path):
        guard = FilesystemGuard([])
        config = VaultConfig(
            vault_path=tmp_path,
            filesystem_guard=guard,
            daily_note_path_format="Journal/%d-%m-%Y",
        )
        result = get_daily_note_path(config, target_date="2026-02-09")
        assert result == tmp_path / "Journal" / "09-02-2026.md"

    def test_nested_date_subdirectories(self, tmp_path):
        guard = FilesystemGuard([])
        config = VaultConfig(
            vault_path=tmp_path,
            filesystem_guard=guard,
            daily_note_path_format="Journals/%Y/%Y-%m/%Y-%m-%d",
        )
        result = get_daily_note_path(config, target_date="2026-02-09")
        assert result == tmp_path / "Journals" / "2026" / "2026-02" / "2026-02-09.md"
