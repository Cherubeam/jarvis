"""Tests for packages.core.filesystem_access module."""

import pytest
from pathlib import Path

from packages.core.filesystem_access import (
    AccessLevel,
    AccessRule,
    FilesystemGuard,
    load_filesystem_guard,
)


# ==================== AccessLevel ====================


class TestAccessLevel:
    def test_all_values(self):
        assert AccessLevel("deny") == AccessLevel.DENY
        assert AccessLevel("read") == AccessLevel.READ
        assert AccessLevel("write") == AccessLevel.WRITE
        assert AccessLevel("read-write") == AccessLevel.READ_WRITE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            AccessLevel("invalid")


# ==================== FilesystemGuard - deny by default ====================


class TestDenyByDefault:
    def test_empty_rules_denies_read(self, tmp_path):
        guard = FilesystemGuard([])
        assert guard.check_read(tmp_path / "any.md") is False

    def test_empty_rules_denies_write(self, tmp_path):
        guard = FilesystemGuard([])
        assert guard.check_write(tmp_path / "any.md") is False

    def test_unmatched_path_denied(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        guard = FilesystemGuard([AccessRule(path=allowed, access=AccessLevel.READ)])
        assert guard.check_read(tmp_path / "other" / "file.md") is False


# ==================== FilesystemGuard - access levels ====================


class TestAccessLevels:
    def test_read_allows_read(self, tmp_path):
        guard = FilesystemGuard([AccessRule(path=tmp_path, access=AccessLevel.READ)])
        assert guard.check_read(tmp_path / "file.md") is True

    def test_read_denies_write(self, tmp_path):
        guard = FilesystemGuard([AccessRule(path=tmp_path, access=AccessLevel.READ)])
        assert guard.check_write(tmp_path / "file.md") is False

    def test_write_allows_write(self, tmp_path):
        guard = FilesystemGuard([AccessRule(path=tmp_path, access=AccessLevel.WRITE)])
        assert guard.check_write(tmp_path / "file.md") is True

    def test_write_denies_read(self, tmp_path):
        guard = FilesystemGuard([AccessRule(path=tmp_path, access=AccessLevel.WRITE)])
        assert guard.check_read(tmp_path / "file.md") is False

    def test_read_write_allows_both(self, tmp_path):
        guard = FilesystemGuard([AccessRule(path=tmp_path, access=AccessLevel.READ_WRITE)])
        assert guard.check_read(tmp_path / "file.md") is True
        assert guard.check_write(tmp_path / "file.md") is True

    def test_deny_blocks_both(self, tmp_path):
        guard = FilesystemGuard([AccessRule(path=tmp_path, access=AccessLevel.DENY)])
        assert guard.check_read(tmp_path / "file.md") is False
        assert guard.check_write(tmp_path / "file.md") is False


# ==================== Most-specific-path wins ====================


class TestMostSpecificWins:
    def test_child_overrides_parent(self, tmp_path):
        parent = tmp_path / "vault"
        parent.mkdir()
        child = parent / "private"
        child.mkdir()
        guard = FilesystemGuard([
            AccessRule(path=parent, access=AccessLevel.READ),
            AccessRule(path=child, access=AccessLevel.DENY),
        ])
        assert guard.check_read(parent / "public.md") is True
        assert guard.check_read(child / "secret.md") is False

    def test_deeper_child_wins_over_intermediate(self, tmp_path):
        root = tmp_path / "vault"
        root.mkdir()
        areas = root / "areas"
        areas.mkdir()
        blog = areas / "blog"
        blog.mkdir()

        guard = FilesystemGuard([
            AccessRule(path=root, access=AccessLevel.READ),
            AccessRule(path=areas, access=AccessLevel.DENY),
            AccessRule(path=blog, access=AccessLevel.READ_WRITE),
        ])
        assert guard.check_read(root / "readme.md") is True
        assert guard.check_read(areas / "private.md") is False
        assert guard.check_read(blog / "post.md") is True
        assert guard.check_write(blog / "post.md") is True

    def test_order_of_rules_does_not_matter(self, tmp_path):
        parent = tmp_path / "vault"
        parent.mkdir()
        child = parent / "writable"
        child.mkdir()
        # Rules given in reverse depth order
        guard = FilesystemGuard([
            AccessRule(path=child, access=AccessLevel.READ_WRITE),
            AccessRule(path=parent, access=AccessLevel.READ),
        ])
        assert guard.check_write(child / "file.md") is True
        assert guard.check_write(parent / "other.md") is False


# ==================== Path security ====================


class TestPathSecurity:
    def test_traversal_attack_blocked(self, tmp_path):
        allowed = tmp_path / "vault"
        allowed.mkdir()
        guard = FilesystemGuard([AccessRule(path=allowed, access=AccessLevel.READ)])
        traversal = allowed / ".." / "secret" / "file.md"
        assert guard.check_read(traversal) is False

    def test_symlink_resolved(self, tmp_path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "file.md").write_text("content")
        link = tmp_path / "link"
        link.symlink_to(real_dir)

        # Rule allows real_dir
        guard = FilesystemGuard([AccessRule(path=real_dir, access=AccessLevel.READ)])
        # Access via symlink resolves to real_dir → allowed
        assert guard.check_read(link / "file.md") is True

    def test_tilde_expansion_in_rule(self, tmp_path):
        # AccessRule paths should be pre-resolved; this tests that resolve works
        guard = FilesystemGuard([AccessRule(path=tmp_path.resolve(), access=AccessLevel.READ)])
        assert guard.check_read(tmp_path / "file.md") is True


# ==================== load_filesystem_guard ====================


class TestLoadFilesystemGuard:
    def test_empty_config(self):
        guard = load_filesystem_guard({})
        assert guard.rules == []

    def test_empty_access_rules(self):
        guard = load_filesystem_guard({"filesystem": {"access_rules": []}})
        assert guard.rules == []

    def test_loads_rules(self, tmp_path):
        config = {
            "filesystem": {
                "access_rules": [
                    {"path": str(tmp_path), "access": "read"},
                    {"path": str(tmp_path / "sub"), "access": "read-write"},
                ]
            }
        }
        guard = load_filesystem_guard(config)
        assert len(guard.rules) == 2
        assert guard.check_read(tmp_path / "file.md") is True
        assert guard.check_write(tmp_path / "file.md") is False
        assert guard.check_write(tmp_path / "sub" / "file.md") is True

    def test_tilde_expansion(self):
        config = {
            "filesystem": {
                "access_rules": [
                    {"path": "~/some/path", "access": "read"},
                ]
            }
        }
        guard = load_filesystem_guard(config)
        assert len(guard.rules) == 1
        # Path should be expanded (no ~ in resolved path)
        assert "~" not in str(guard.rules[0].path)

    def test_invalid_access_level_defaults_to_deny(self, tmp_path):
        config = {
            "filesystem": {
                "access_rules": [
                    {"path": str(tmp_path), "access": "banana"},
                ]
            }
        }
        guard = load_filesystem_guard(config)
        assert guard.check_read(tmp_path / "file.md") is False
        assert guard.check_write(tmp_path / "file.md") is False

    def test_missing_filesystem_key(self):
        guard = load_filesystem_guard({"other": "stuff"})
        assert guard.rules == []


# ==================== rules property ====================


class TestRulesProperty:
    def test_returns_copy(self, tmp_path):
        rule = AccessRule(path=tmp_path, access=AccessLevel.READ)
        guard = FilesystemGuard([rule])
        rules = guard.rules
        rules.clear()
        assert len(guard.rules) == 1  # Original unchanged
