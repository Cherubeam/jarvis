"""Tests for packages.integrations.obsidian.vault module."""

import pytest
from pathlib import Path

from packages.integrations.obsidian.vault import (
    VaultConfig,
    load_vault_config,
    validate_path,
    read_note,
    list_notes,
    get_daily_note_path,
)


# ==================== VaultConfig ====================


class TestVaultConfig:
    def test_default_values(self, tmp_path):
        config = VaultConfig(vault_path=tmp_path)
        assert config.vault_path == tmp_path
        assert config.allowed_dirs == []
        assert config.daily_note_path_format == "Daily Notes/%Y-%m-%d"
        assert config.enabled is True

    def test_custom_values(self, tmp_path):
        allowed = [tmp_path / "notes"]
        config = VaultConfig(
            vault_path=tmp_path,
            allowed_dirs=allowed,
            daily_note_path_format="Journal/%d-%m-%Y",
            enabled=True,
        )
        assert config.daily_note_path_format == "Journal/%d-%m-%Y"
        assert config.allowed_dirs == allowed


# ==================== load_vault_config ====================


class TestLoadVaultConfig:
    def test_disabled_returns_none(self):
        config = {"obsidian": {"enabled": False, "vault_path": "/some/path"}}
        assert load_vault_config(config) is None

    def test_missing_obsidian_key_returns_none(self):
        assert load_vault_config({}) is None

    def test_empty_vault_path_returns_none(self):
        config = {"obsidian": {"enabled": True, "vault_path": ""}}
        assert load_vault_config(config) is None

    def test_nonexistent_vault_path_returns_none(self):
        config = {"obsidian": {"enabled": True, "vault_path": "/nonexistent/path"}}
        assert load_vault_config(config) is None

    def test_valid_config(self, tmp_path):
        daily_dir = tmp_path / "Daily Notes"
        daily_dir.mkdir()
        config = {
            "obsidian": {
                "enabled": True,
                "vault_path": str(tmp_path),
                "allowed_dirs": ["Daily Notes"],
                "daily_notes": {
                    "path_format": "Daily Notes/%Y-%m-%d",
                },
            }
        }
        result = load_vault_config(config)
        assert result is not None
        assert result.vault_path == tmp_path.resolve()
        assert result.enabled is True
        assert len(result.allowed_dirs) == 1
        assert result.daily_note_path_format == "Daily Notes/%Y-%m-%d"

    def test_defaults_for_missing_daily_notes_section(self, tmp_path):
        config = {
            "obsidian": {
                "enabled": True,
                "vault_path": str(tmp_path),
                "allowed_dirs": [],
            }
        }
        result = load_vault_config(config)
        assert result is not None
        assert result.daily_note_path_format == "Daily Notes/%Y-%m-%d"


# ==================== validate_path ====================


class TestValidatePath:
    def test_path_inside_allowed_dir(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        note = allowed / "test.md"
        note.touch()
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        assert validate_path(note, config) is True

    def test_path_outside_allowed_dir(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        outside = tmp_path / "secret" / "file.md"
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        assert validate_path(outside, config) is False

    def test_traversal_attack_blocked(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        traversal = allowed / ".." / "secret" / "file.md"
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        assert validate_path(traversal, config) is False

    def test_empty_allowed_dirs(self, tmp_path):
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[])
        assert validate_path(tmp_path / "any.md", config) is False

    def test_multiple_allowed_dirs(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[dir_a, dir_b])
        assert validate_path(dir_a / "file.md", config) is True
        assert validate_path(dir_b / "file.md", config) is True
        assert validate_path(tmp_path / "c" / "file.md", config) is False


# ==================== read_note ====================


class TestReadNote:
    def test_read_valid_note(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        note = allowed / "test.md"
        note.write_text("# Hello\nContent here", encoding="utf-8")
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        assert read_note(note, config) == "# Hello\nContent here"

    def test_read_outside_allowed_raises(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        outside = tmp_path / "secret.md"
        outside.write_text("secret")
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        with pytest.raises(PermissionError):
            read_note(outside, config)

    def test_read_nonexistent_file_raises(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        with pytest.raises(FileNotFoundError):
            read_note(allowed / "missing.md", config)


# ==================== list_notes ====================


class TestListNotes:
    def test_list_notes_in_directory(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        (allowed / "a.md").write_text("a")
        (allowed / "b.md").write_text("b")
        (allowed / "c.txt").write_text("c")
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        result = list_notes(allowed, config)
        assert len(result) == 2
        assert all(p.suffix == ".md" for p in result)

    def test_list_notes_outside_allowed_raises(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        outside = tmp_path / "secret"
        outside.mkdir()
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        with pytest.raises(PermissionError):
            list_notes(outside, config)

    def test_list_notes_nonexistent_dir(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        result = list_notes(allowed / "subdir", config)
        assert result == []

    def test_list_notes_custom_pattern(self, tmp_path):
        allowed = tmp_path / "notes"
        allowed.mkdir()
        (allowed / "a.md").write_text("a")
        (allowed / "b.txt").write_text("b")
        config = VaultConfig(vault_path=tmp_path, allowed_dirs=[allowed])
        result = list_notes(allowed, config, pattern="*.txt")
        assert len(result) == 1
        assert result[0].name == "b.txt"


# ==================== get_daily_note_path ====================


class TestGetDailyNotePath:
    def test_default_today(self, tmp_path):
        from datetime import date

        config = VaultConfig(vault_path=tmp_path)
        result = get_daily_note_path(config)
        expected = tmp_path / "Daily Notes" / f"{date.today().strftime('%Y-%m-%d')}.md"
        assert result == expected

    def test_specific_date(self, tmp_path):
        config = VaultConfig(vault_path=tmp_path)
        result = get_daily_note_path(config, target_date="2026-02-09")
        assert result == tmp_path / "Daily Notes" / "2026-02-09.md"

    def test_custom_format(self, tmp_path):
        config = VaultConfig(
            vault_path=tmp_path,
            daily_note_path_format="Journal/%d-%m-%Y",
        )
        result = get_daily_note_path(config, target_date="2026-02-09")
        assert result == tmp_path / "Journal" / "09-02-2026.md"

    def test_nested_date_subdirectories(self, tmp_path):
        config = VaultConfig(
            vault_path=tmp_path,
            daily_note_path_format="Journals/%Y/%Y-%m/%Y-%m-%d",
        )
        result = get_daily_note_path(config, target_date="2026-02-09")
        assert result == tmp_path / "Journals" / "2026" / "2026-02" / "2026-02-09.md"
