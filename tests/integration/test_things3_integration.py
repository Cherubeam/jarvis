"""
Integration tests for Things 3 integration.
Tests full flow from configuration to context inclusion.
"""

from unittest.mock import patch

import pytest

from packages.core.context_builder import build_system_prompt
from packages.core.settings import Things3Settings
from packages.integrations.things3.task_sync import Task, sync_tasks_to_file


@pytest.mark.integration
class TestThings3Integration:
    """Integration tests for Things 3 context awareness."""

    def test_tasks_included_in_context(self, tmp_path):
        """Test that tasks.md is included in system prompt."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        (context_dir / "personal_context.md").write_text("# Test User\nSoftware engineer")
        (context_dir / "preferences.md").write_text("# Preferences\nConcise responses")
        (context_dir / "current_focus.md").write_text("# Current Focus\nBuilding Jarvis")

        (context_dir / "tasks.md").write_text(
            """# Tasks from Things 3

## Today
- Review pull request #123
- Write documentation for task sync

## Inbox
- Research MCP protocol
"""
        )

        prompt = build_system_prompt(context_dir)

        assert "Test User" in prompt
        assert "Preferences" in prompt
        assert "Current Focus" in prompt
        assert "Their tasks" in prompt
        assert "Review pull request #123" in prompt
        assert "Write documentation for task sync" in prompt

    def test_context_works_without_tasks(self, tmp_path):
        """Test that context builder works when tasks.md doesn't exist."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        (context_dir / "personal_context.md").write_text("# Test User")
        (context_dir / "preferences.md").write_text("# Preferences")

        prompt = build_system_prompt(context_dir)

        assert "Test User" in prompt
        assert "Their tasks" not in prompt

    @patch("packages.integrations.things3.task_sync.fetch_tasks")
    def test_sync_creates_valid_tasks_file(self, mock_fetch, tmp_path):
        """Test that sync creates a valid tasks.md file."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        things3 = Things3Settings(enabled=True, sync_on_startup=True, max_tasks_per_list=50)

        mock_fetch.return_value = {
            "inbox": [Task(title="Inbox task 1"), Task(title="Inbox task 2")],
            "today": [Task(title="Today task 1")],
            "upcoming": [Task(title="Upcoming task 1")],
        }

        output_path = context_dir / "tasks.md"
        result = sync_tasks_to_file(output_path, things3)

        assert result is True
        assert output_path.exists()

        content = output_path.read_text()
        assert content.startswith("# Tasks from Things 3")

        prompt = build_system_prompt(context_dir)
        assert "Inbox task 1" in prompt
        assert "Today task 1" in prompt

    def test_disabled_integration_skips_sync(self, tmp_path):
        """Test that disabled config skips sync entirely."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        things3 = Things3Settings(enabled=False)

        output_path = context_dir / "tasks.md"
        result = sync_tasks_to_file(output_path, things3)

        assert result is False
        assert not output_path.exists()

    @patch("packages.integrations.things3.task_sync.fetch_tasks")
    def test_sync_failure_doesnt_break_startup(self, mock_fetch, tmp_path):
        """Test that sync failure doesn't prevent Jarvis from starting."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        things3 = Things3Settings(enabled=True, sync_on_startup=True)

        mock_fetch.side_effect = RuntimeError("Things 3 not running")

        output_path = context_dir / "tasks.md"
        result = sync_tasks_to_file(output_path, things3)

        assert result is False

        (context_dir / "personal_context.md").write_text("# User")
        prompt = build_system_prompt(context_dir)
        assert "# User" in prompt

    @patch("packages.integrations.things3.task_sync.fetch_tasks")
    def test_large_task_list_truncation(self, mock_fetch, tmp_path):
        """Test that large task lists are truncated properly."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        many_tasks = [Task(title=f"Task {i}") for i in range(100)]

        things3 = Things3Settings(enabled=True, sync_on_startup=True, max_tasks_per_list=10)

        mock_fetch.return_value = {
            "inbox": many_tasks,
            "today": [],
            "upcoming": [],
        }

        output_path = context_dir / "tasks.md"
        sync_tasks_to_file(output_path, things3)

        content = output_path.read_text()

        assert "Task 0" in content
        assert "Task 9" in content
        assert "Task 50" not in content
        assert "(+90 more)" in content

    @patch("packages.integrations.things3.task_sync.fetch_tasks")
    def test_full_cli_integration_flow(self, mock_fetch, tmp_path):
        """Test full integration flow as if running CLI."""
        jarvis_dir = tmp_path / "jarvis"
        context_dir = jarvis_dir / "personal-context" / "context"
        context_dir.mkdir(parents=True)

        things3 = Things3Settings(enabled=True, sync_on_startup=True, max_tasks_per_list=50)

        (context_dir / "soul.md").write_text("You are Jarvis.")
        (context_dir / "personal_context.md").write_text("# Marco\nSoftware engineer")
        (context_dir / "preferences.md").write_text("# Preferences\nBe concise")
        (context_dir / "current_focus.md").write_text("# Focus\nBuilding Jarvis")

        mock_fetch.return_value = {
            "inbox": [Task(title="Review integration tests")],
            "today": [Task(title="Implement Things 3 sync")],
            "upcoming": [],
        }

        sync_tasks_to_file(context_dir / "tasks.md", things3)
        prompt = build_system_prompt(context_dir)

        assert "You are Jarvis" in prompt
        assert "Marco" in prompt
        assert "Software engineer" in prompt
        assert "Be concise" in prompt
        assert "Building Jarvis" in prompt
        assert "Review integration tests" in prompt
        assert "Implement Things 3 sync" in prompt

    def test_default_settings_skip_when_disabled(self, tmp_path):
        """Defaults have enabled=True, sync_on_startup=True; skip when disabled."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        things3 = Things3Settings(enabled=False)

        output_path = context_dir / "tasks.md"
        result = sync_tasks_to_file(output_path, things3)

        assert result is False
