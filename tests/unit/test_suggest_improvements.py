"""Tests for packages.core.tools.suggest_improvements."""

import pytest
from pathlib import Path

from packages.integrations.obsidian.vault import VaultConfig
from packages.integrations.obsidian.diff import VaultDiff
from packages.integrations.obsidian.writer import ConfirmationHandler
from packages.core.tools.suggest_improvements import make_suggest_improvements_tool


class MockConfirmationHandler(ConfirmationHandler):
    def __init__(self):
        self.presented_diff: VaultDiff | None = None
        self.confirmation_requested = False

    def present_diff(self, diff: VaultDiff) -> None:
        self.presented_diff = diff

    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:
        self.confirmation_requested = True
        return False


@pytest.fixture
def vault(tmp_path):
    """Create a vault with an allowed directory and a sample file."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    sample = content_dir / "post.md"
    sample.write_text("# Hello\n\nThis is the original content.\n", encoding="utf-8")

    config = VaultConfig(
        vault_path=tmp_path,
        allowed_dirs=[content_dir.resolve()],
    )
    return config, content_dir, sample


@pytest.fixture
def tool_and_handler(vault):
    config, content_dir, sample = vault
    handler = MockConfirmationHandler()
    tool = make_suggest_improvements_tool(config, handler)
    return tool, handler, sample


# ==================== Tool Definition ====================


@pytest.mark.unit
class TestToolDefinition:
    def test_tool_name(self, tool_and_handler):
        tool, _, _ = tool_and_handler
        assert tool.name == "suggest_improvements"

    def test_required_params(self, tool_and_handler):
        tool, _, _ = tool_and_handler
        assert tool.parameters["required"] == ["path", "improved_content"]

    def test_has_reasoning_param(self, tool_and_handler):
        tool, _, _ = tool_and_handler
        assert "reasoning" in tool.parameters["properties"]


# ==================== Suggest Improvements ====================


@pytest.mark.unit
class TestSuggestImprovements:
    def test_happy_path_shows_diff(self, tool_and_handler):
        tool, handler, _ = tool_and_handler
        result = tool.execute(
            path="content/post.md",
            improved_content="# Hello\n\nThis is the improved content.\n",
        )
        assert handler.presented_diff is not None
        assert "displayed to user" in result
        assert "NOT been applied" in result

    def test_diff_summary_in_result(self, tool_and_handler):
        tool, handler, _ = tool_and_handler
        result = tool.execute(
            path="content/post.md",
            improved_content="# Hello\n\nThis is the improved content.\n",
        )
        # Summary should mention added/removed lines
        assert "+" in result or "-" in result

    def test_no_changes(self, tool_and_handler):
        tool, handler, _ = tool_and_handler
        result = tool.execute(
            path="content/post.md",
            improved_content="# Hello\n\nThis is the original content.\n",
        )
        assert "No changes" in result
        assert handler.presented_diff is None

    def test_file_not_found(self, tool_and_handler):
        tool, handler, _ = tool_and_handler
        result = tool.execute(
            path="content/nonexistent.md",
            improved_content="anything",
        )
        assert "Error: File not found" in result
        assert handler.presented_diff is None

    def test_permission_error(self, vault):
        config, _, _ = vault
        # Create a file outside allowed dirs
        outside = config.vault_path / "secret" / "file.md"
        outside.parent.mkdir()
        outside.write_text("secret", encoding="utf-8")

        handler = MockConfirmationHandler()
        tool = make_suggest_improvements_tool(config, handler)
        result = tool.execute(
            path="secret/file.md",
            improved_content="new content",
        )
        assert "Error" in result
        assert handler.presented_diff is None

    def test_reasoning_displayed(self, tool_and_handler, capsys):
        tool, handler, _ = tool_and_handler
        tool.execute(
            path="content/post.md",
            improved_content="# Hello\n\nBetter content.\n",
            reasoning="Tightened the opening paragraph.",
        )
        captured = capsys.readouterr()
        assert "Tightened the opening paragraph." in captured.out

    def test_no_reasoning_no_output(self, tool_and_handler, capsys):
        tool, handler, _ = tool_and_handler
        tool.execute(
            path="content/post.md",
            improved_content="# Hello\n\nBetter content.\n",
        )
        captured = capsys.readouterr()
        # present_diff output may appear, but no reasoning line
        assert "Tightened" not in captured.out

    def test_get_confirmation_never_called(self, tool_and_handler):
        tool, handler, _ = tool_and_handler
        tool.execute(
            path="content/post.md",
            improved_content="# Hello\n\nImproved.\n",
        )
        assert handler.confirmation_requested is False

    def test_file_not_modified(self, tool_and_handler):
        tool, _, sample = tool_and_handler
        original = sample.read_text(encoding="utf-8")
        tool.execute(
            path="content/post.md",
            improved_content="# Hello\n\nCompletely different content.\n",
        )
        assert sample.read_text(encoding="utf-8") == original
