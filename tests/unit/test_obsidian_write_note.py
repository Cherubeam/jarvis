"""Tests for write_note() in packages.integrations.obsidian.writer."""

from pathlib import Path

import pytest

from packages.core.filesystem_access import AccessLevel, AccessRule, FilesystemGuard
from packages.integrations.obsidian.diff import VaultDiff
from packages.integrations.obsidian.vault import VaultConfig
from packages.integrations.obsidian.writer import (
    ConfirmationHandler,
    write_note,
)


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
def vault(tmp_path):
    blog_dir = tmp_path / "Blog"
    blog_dir.mkdir()
    guard = _guard((blog_dir, AccessLevel.READ_WRITE))
    config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
    return config, blog_dir


@pytest.mark.unit
class TestWriteNoteNewFile:
    def test_creates_new_file(self, vault):
        config, blog_dir = vault
        handler = MockConfirmationHandler(confirm=True)
        target = blog_dir / "new-post.md"

        result = write_note(target, "# Hello\n\nContent", config, handler)

        assert result.success is True
        assert result.action == "created"
        assert target.read_text(encoding="utf-8") == "# Hello\n\nContent"

    def test_new_file_diff_is_all_additions(self, vault):
        config, blog_dir = vault
        handler = MockConfirmationHandler(confirm=True)
        target = blog_dir / "new-post.md"

        write_note(target, "line one\nline two\n", config, handler)

        assert handler.presented_diff is not None
        assert handler.presented_diff.original_content == ""

    def test_creates_parent_directories(self, vault):
        config, blog_dir = vault
        handler = MockConfirmationHandler(confirm=True)
        target = blog_dir / "drafts" / "deep" / "post.md"

        result = write_note(target, "content", config, handler)

        assert result.success is True
        assert target.exists()


@pytest.mark.unit
class TestWriteNoteExistingFile:
    def test_overwrites_existing_file(self, vault):
        config, blog_dir = vault
        handler = MockConfirmationHandler(confirm=True)
        target = blog_dir / "post.md"
        target.write_text("old content", encoding="utf-8")

        result = write_note(target, "new content", config, handler)

        assert result.success is True
        assert result.action == "written"
        assert target.read_text(encoding="utf-8") == "new content"

    def test_diff_shows_changes(self, vault):
        config, blog_dir = vault
        handler = MockConfirmationHandler(confirm=True)
        target = blog_dir / "post.md"
        target.write_text("old content\n", encoding="utf-8")

        write_note(target, "new content\n", config, handler)

        diff = handler.presented_diff
        assert diff is not None
        assert diff.original_content == "old content\n"
        assert diff.proposed_content == "new content\n"


@pytest.mark.unit
class TestWriteNoteRejection:
    def test_rejected_write_does_not_modify_file(self, vault):
        config, blog_dir = vault
        handler = MockConfirmationHandler(confirm=False)
        target = blog_dir / "post.md"
        target.write_text("original", encoding="utf-8")

        result = write_note(target, "modified", config, handler)

        assert result.success is False
        assert result.action == "rejected"
        assert target.read_text(encoding="utf-8") == "original"

    def test_rejected_new_file_is_not_created(self, vault):
        config, blog_dir = vault
        handler = MockConfirmationHandler(confirm=False)
        target = blog_dir / "rejected.md"

        result = write_note(target, "content", config, handler)

        assert result.success is False
        assert not target.exists()


@pytest.mark.unit
class TestWriteNotePathValidation:
    def test_rejects_path_outside_allowed_dirs(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        secret = tmp_path / "secret"
        secret.mkdir()
        guard = _guard((allowed, AccessLevel.READ_WRITE))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        handler = MockConfirmationHandler(confirm=True)

        result = write_note(secret / "hack.md", "bad", config, handler)

        assert result.success is False
        assert result.action == "error"
        assert "denied" in result.message.lower()

    def test_rejects_read_only_path(self, tmp_path):
        read_dir = tmp_path / "readonly"
        read_dir.mkdir()
        guard = _guard((read_dir, AccessLevel.READ))
        config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
        handler = MockConfirmationHandler(confirm=True)

        result = write_note(read_dir / "file.md", "content", config, handler)

        assert result.success is False
        assert result.action == "error"
        assert "denied" in result.message.lower()


@pytest.mark.unit
class TestWriteNoteReasoning:
    def test_reasoning_printed_before_diff(self, vault, capsys):
        config, blog_dir = vault
        handler = MockConfirmationHandler(confirm=True)
        target = blog_dir / "post.md"
        target.write_text("old", encoding="utf-8")

        write_note(target, "new", config, handler, reasoning="Tightened the intro")

        captured = capsys.readouterr()
        assert "Tightened the intro" in captured.out
