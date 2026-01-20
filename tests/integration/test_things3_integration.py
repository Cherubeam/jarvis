"""
Integration tests for Things 3 integration.
Tests full flow from configuration to context inclusion.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from context_builder import build_system_prompt
from task_sync import Task, sync_tasks_to_file


@pytest.mark.integration
class TestThings3Integration:
    """Integration tests for Things 3 context awareness."""

    def test_tasks_included_in_context(self, tmp_path):
        """Test that tasks.md is included in system prompt."""
        # Setup directories
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        # Create minimal context files
        (context_dir / "profile.md").write_text("# Test User\nSoftware engineer")
        (context_dir / "preferences.md").write_text("# Preferences\nConcise responses")
        (context_dir / "current_focus.md").write_text(
            "# Current Focus\nBuilding Jarvis"
        )

        # Create tasks.md
        (context_dir / "tasks.md").write_text(
            """# Tasks from Things 3

## Today
- Review pull request #123
- Write documentation for task sync

## Inbox
- Research MCP protocol
"""
        )

        # Build system prompt
        prompt = build_system_prompt(context_dir, "You are Jarvis.")

        # Verify all sections present
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

        # Create only essential files
        (context_dir / "profile.md").write_text("# Test User")
        (context_dir / "preferences.md").write_text("# Preferences")

        # Don't create tasks.md
        prompt = build_system_prompt(context_dir, "You are Jarvis.")

        # Should work fine without tasks
        assert "You are Jarvis" in prompt
        assert "Test User" in prompt
        assert "Their tasks" not in prompt  # Section shouldn't appear if no tasks

    @patch("task_sync.asyncio.run")
    def test_sync_creates_valid_tasks_file(self, mock_run, tmp_path):
        """Test that sync creates a valid tasks.md file."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        config = {
            "things3": {
                "enabled": True,
                "sync_on_startup": True,
                "max_tasks_per_list": 50,
            }
        }

        # Mock task data
        mock_run.return_value = {
            "inbox": [Task(title="Inbox task 1"), Task(title="Inbox task 2")],
            "today": [Task(title="Today task 1")],
            "upcoming": [Task(title="Upcoming task 1")],
        }

        # Sync tasks
        output_path = context_dir / "tasks.md"
        result = sync_tasks_to_file(output_path, config)

        assert result is True
        assert output_path.exists()

        # Verify file is valid markdown
        content = output_path.read_text()
        assert content.startswith("# Tasks from Things 3")

        # Verify can be included in context
        prompt = build_system_prompt(context_dir, "You are Jarvis.")
        assert "Inbox task 1" in prompt
        assert "Today task 1" in prompt

    def test_disabled_integration_skips_sync(self, tmp_path):
        """Test that disabled config skips sync entirely."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        config = {"things3": {"enabled": False}}

        output_path = context_dir / "tasks.md"
        result = sync_tasks_to_file(output_path, config)

        assert result is False
        assert not output_path.exists()

    @patch("task_sync.asyncio.run")
    def test_sync_failure_doesnt_break_startup(self, mock_run, tmp_path):
        """Test that sync failure doesn't prevent Jarvis from starting."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        config = {"things3": {"enabled": True, "sync_on_startup": True}}

        # Mock sync failure
        mock_run.side_effect = RuntimeError("Things 3 not running")

        output_path = context_dir / "tasks.md"
        result = sync_tasks_to_file(output_path, config)

        # Should return False but not raise
        assert result is False

        # Context should still work without tasks
        (context_dir / "profile.md").write_text("# User")
        prompt = build_system_prompt(context_dir, "You are Jarvis.")
        assert "You are Jarvis" in prompt

    @patch("task_sync.asyncio.run")
    def test_large_task_list_truncation(self, mock_run, tmp_path):
        """Test that large task lists are truncated properly."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        # Create 100 tasks
        many_tasks = [Task(title=f"Task {i}") for i in range(100)]

        config = {
            "things3": {
                "enabled": True,
                "sync_on_startup": True,
                "max_tasks_per_list": 10,  # Only show 10
            }
        }

        mock_run.return_value = {
            "inbox": many_tasks,
            "today": [],
            "upcoming": [],
        }

        output_path = context_dir / "tasks.md"
        sync_tasks_to_file(output_path, config)

        content = output_path.read_text()

        # Should see first 10 tasks
        assert "Task 0" in content
        assert "Task 9" in content

        # Should not see beyond limit
        assert "Task 50" not in content

        # Should have truncation indicator
        assert "(+90 more)" in content

    @patch("task_sync.asyncio.run")
    def test_full_cli_integration_flow(self, mock_run, tmp_path):
        """Test full integration flow as if running CLI."""
        # Setup project structure
        jarvis_dir = tmp_path / "jarvis"
        context_dir = jarvis_dir / "personal-context" / "context"
        context_dir.mkdir(parents=True)

        # Create config
        config = {
            "things3": {
                "enabled": True,
                "sync_on_startup": True,
                "max_tasks_per_list": 50,
            },
            "system_prompt_prefix": "You are Jarvis.",
        }

        # Create context files
        (context_dir / "profile.md").write_text("# Marco\nSoftware engineer")
        (context_dir / "preferences.md").write_text("# Preferences\nBe concise")
        (context_dir / "current_focus.md").write_text("# Focus\nBuilding Jarvis")

        # Mock task fetch
        mock_run.return_value = {
            "inbox": [Task(title="Review integration tests")],
            "today": [Task(title="Implement Things 3 sync")],
            "upcoming": [],
        }

        # Simulate CLI startup
        sync_tasks_to_file(context_dir / "tasks.md", config)
        prompt = build_system_prompt(context_dir, config["system_prompt_prefix"])

        # Verify complete system prompt
        assert "You are Jarvis" in prompt
        assert "Marco" in prompt
        assert "Software engineer" in prompt
        assert "Be concise" in prompt
        assert "Building Jarvis" in prompt
        assert "Review integration tests" in prompt
        assert "Implement Things 3 sync" in prompt

    def test_empty_config_section(self, tmp_path):
        """Test behavior with missing things3 config section."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()

        config = {}  # No things3 section

        output_path = context_dir / "tasks.md"
        result = sync_tasks_to_file(output_path, config)

        # Should handle gracefully
        assert result is False
