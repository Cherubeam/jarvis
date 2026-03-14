"""
Unit tests for AutoConfirmationHandler.
"""

import logging
from pathlib import Path

import pytest

from packages.agents.developer.confirmation import AutoConfirmationHandler
from packages.integrations.obsidian.diff import VaultDiff


def _make_diff(file_path: str) -> VaultDiff:
    return VaultDiff(
        file_path=file_path,
        original_content="old",
        proposed_content="new",
    )


@pytest.mark.unit
class TestAutoConfirmationHandler:
    """Tests for auto-approval within scope."""

    def _handler(self) -> AutoConfirmationHandler:
        return AutoConfirmationHandler(
            allowed_dirs=["packages/agents/", "data/context/", "config/"],
            project_root=Path("/fake/project"),
        )

    def test_approves_within_scope(self):
        h = self._handler()
        h.present_diff(_make_diff("packages/agents/test/meta.yaml"))
        assert h.get_confirmation() is True

    def test_approves_nested_path_in_scope(self):
        h = self._handler()
        h.present_diff(_make_diff("packages/agents/deep/nested/file.md"))
        assert h.get_confirmation() is True

    def test_rejects_outside_scope(self):
        h = self._handler()
        h.present_diff(_make_diff("apps/cli/main.py"))
        assert h.get_confirmation() is False

    def test_rejects_partial_prefix_match(self):
        """'packages/agentsXYZ/' should not match 'packages/agents/'."""
        h = self._handler()
        h.present_diff(_make_diff("packages/agentsXYZ/file.md"))
        assert h.get_confirmation() is False

    def test_approves_exact_prefix(self):
        h = self._handler()
        h.present_diff(_make_diff("config/default.yaml"))
        assert h.get_confirmation() is True

    def test_rejects_root_level_file(self):
        h = self._handler()
        h.present_diff(_make_diff("pyproject.toml"))
        assert h.get_confirmation() is False

    def test_present_diff_logs(self, caplog):
        h = self._handler()
        with caplog.at_level(logging.INFO, logger="packages.agents.developer.confirmation"):
            h.present_diff(_make_diff("packages/agents/test.md"))
        assert "auto-approving" in caplog.text

    def test_present_diff_logs_rejection(self, caplog):
        h = self._handler()
        with caplog.at_level(logging.INFO, logger="packages.agents.developer.confirmation"):
            h.present_diff(_make_diff("apps/cli/main.py"))
        assert "rejecting" in caplog.text

    def test_sequential_calls_track_last_diff(self):
        """get_confirmation should reflect the most recent present_diff."""
        h = self._handler()
        h.present_diff(_make_diff("packages/agents/ok.md"))
        assert h.get_confirmation() is True
        h.present_diff(_make_diff("apps/cli/bad.py"))
        assert h.get_confirmation() is False

    def test_default_state_rejects(self):
        """Before any present_diff call, should default to rejection."""
        h = self._handler()
        assert h.get_confirmation() is False
