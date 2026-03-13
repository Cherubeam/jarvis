"""
Integration tests for the Obsidian vault integration.

Tests the full flow: config → read → parse → diff → confirm → write.
Uses temporary vaults with real filesystem operations.
"""

import pytest
from pathlib import Path

from packages.core.filesystem_access import AccessLevel, AccessRule, FilesystemGuard
from packages.integrations.obsidian.vault import (
    VaultConfig,
    load_vault_config,
    read_note,
    get_daily_note_path,
    list_notes,
)
from packages.integrations.obsidian.callout import (
    CalloutBlock,
    CalloutNotFound,
    find_jarvis_callout,
    build_updated_content,
)
from packages.integrations.obsidian.diff import compute_diff, format_diff_for_cli, format_diff_for_api
from packages.integrations.obsidian.writer import (
    ConfirmationHandler,
    WriteResult,
    append_to_note,
    append_to_daily_note,
)
from packages.integrations.obsidian.diff import VaultDiff


class AutoConfirmHandler(ConfirmationHandler):
    """Auto-confirms for integration tests."""

    def __init__(self):
        self.presented_diff: VaultDiff | None = None

    def present_diff(self, diff: VaultDiff) -> None:
        self.presented_diff = diff

    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:
        return True


class TestEndToEndDailyNoteFlow:
    """Full flow: read daily note → find callout → append → verify."""

    def test_full_append_flow(self, sample_vault_config, daily_note_with_callout):
        """The complete happy path from reading to writing."""
        config = sample_vault_config
        note_path = daily_note_with_callout

        # 1. Read the note
        content = read_note(note_path, config)
        assert "> [!JARVIS]" in content

        # 2. Find callout
        callout = find_jarvis_callout(content)
        assert isinstance(callout, CalloutBlock)
        assert "reviewed code architecture" in callout.existing_content

        # 3. Build updated content
        new_entry = "- Explored Obsidian integration\n- Connected to [[JARVIS roadmap]]"
        proposed = build_updated_content(content, callout, new_entry)

        # 4. Compute diff
        rel_path = str(note_path.relative_to(config.vault_path))
        diff = compute_diff(rel_path, content, proposed)
        assert "+2 lines" in diff.summary or "+3 lines" in diff.summary

        # 5. Verify diff formats work
        cli_output = format_diff_for_cli(diff)
        assert "Obsidian integration" in cli_output

        api_output = format_diff_for_api(diff)
        assert api_output["has_changes"] is True

        # 6. Write via append_to_note
        handler = AutoConfirmHandler()
        result = append_to_note(note_path, new_entry, config, handler)
        assert result.success is True
        assert result.action == "appended"

        # 7. Verify the written content
        final = note_path.read_text(encoding="utf-8")
        assert "> - Explored Obsidian integration" in final
        assert "> - Connected to [[JARVIS roadmap]]" in final
        # Original content preserved
        assert "> Morning: reviewed code architecture" in final
        assert "## Tasks" in final
        assert "- Finish integration" in final

    def test_append_via_daily_note_helper(self, sample_vault_config, daily_note_with_callout):
        """Test append_to_daily_note with specific date."""
        handler = AutoConfirmHandler()
        result = append_to_daily_note(
            "Evening wrap-up entry",
            sample_vault_config,
            handler,
            date="2026-02-09",
        )
        assert result.success is True
        content = daily_note_with_callout.read_text(encoding="utf-8")
        assert "> Evening wrap-up entry" in content


class TestConfigToVaultFlow:
    """Test loading config and using it to access the vault."""

    def test_load_config_and_read(self, temp_vault):
        daily_dir = temp_vault / "Daily Notes"
        note = daily_dir / "2026-01-15.md"
        note.write_text("# Test\n\n> [!JARVIS]\n> entry\n")

        guard = FilesystemGuard([
            AccessRule(path=daily_dir.resolve(), access=AccessLevel.READ_WRITE),
        ])
        config_dict = {
            "obsidian": {
                "enabled": True,
                "vault_path": str(temp_vault),
                "daily_notes": {
                    "path_format": "Daily Notes/%Y-%m-%d",
                },
            }
        }
        vault_config = load_vault_config(config_dict, filesystem_guard=guard)
        assert vault_config is not None

        content = read_note(note, vault_config)
        callout = find_jarvis_callout(content)
        assert isinstance(callout, CalloutBlock)


class TestSecurityBoundaries:
    """Verify that path traversal and unauthorized access are blocked."""

    def test_read_outside_allowed_dirs_blocked(self, temp_vault, sample_vault_config):
        # Create a file outside allowed dirs
        secret_dir = temp_vault / "Private"
        secret_dir.mkdir()
        secret = secret_dir / "secret.md"
        secret.write_text("TOP SECRET")

        with pytest.raises(PermissionError):
            read_note(secret, sample_vault_config)

    def test_write_outside_allowed_dirs_blocked(self, temp_vault, sample_vault_config):
        secret_dir = temp_vault / "Private"
        secret_dir.mkdir()
        note = secret_dir / "note.md"
        note.write_text("> [!JARVIS]\n> content")

        handler = AutoConfirmHandler()
        result = append_to_note(note, "injected", sample_vault_config, handler)
        assert result.success is False
        assert result.action == "error"

    def test_symlink_traversal_blocked(self, temp_vault, sample_vault_config):
        # Create a directory outside the vault
        outside = temp_vault.parent / "outside_vault"
        outside.mkdir(exist_ok=True)
        secret = outside / "secret.md"
        secret.write_text("secret content")

        # Create symlink inside allowed dir pointing outside
        daily_dir = temp_vault / "Daily Notes"
        symlink = daily_dir / "sneaky.md"
        try:
            symlink.symlink_to(secret)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        with pytest.raises(PermissionError):
            read_note(symlink, sample_vault_config)

    def test_list_notes_only_in_allowed_dirs(self, temp_vault, sample_vault_config):
        private = temp_vault / "Private"
        private.mkdir()
        (private / "note.md").write_text("private")

        with pytest.raises(PermissionError):
            list_notes(private, sample_vault_config)


class TestMultipleAppends:
    """Test appending multiple times to the same callout."""

    def test_two_successive_appends(self, sample_vault_config, daily_note_with_callout):
        handler = AutoConfirmHandler()
        note = daily_note_with_callout

        # First append
        result1 = append_to_note(note, "First new entry", sample_vault_config, handler)
        assert result1.success is True

        # Second append
        result2 = append_to_note(note, "Second new entry", sample_vault_config, handler)
        assert result2.success is True

        # Both should be present
        content = note.read_text(encoding="utf-8")
        assert "> First new entry" in content
        assert "> Second new entry" in content
        assert "> Morning: reviewed code architecture" in content
