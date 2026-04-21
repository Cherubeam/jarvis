"""
Unit tests for task_sync module.
Tests task synchronization from Things 3 via things.py (SQLite).
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from packages.integrations.things3.task_sync import (
    Task,
    TaskSyncCache,
    _to_task,
    fetch_tasks,
    format_tasks_as_markdown,
    sync_tasks_to_file,
)


@pytest.mark.unit
class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation(self):
        """Test creating a Task object."""
        task = Task(
            title="Test Task",
            uuid="ABC123",
            notes="Test notes",
            due_date="2026-01-25",
            when_date="2026-01-20",
            tags="work, important",
            project="My Project",
            area="Work",
        )
        assert task.title == "Test Task"
        assert task.uuid == "ABC123"
        assert task.notes == "Test notes"
        assert task.due_date == "2026-01-25"
        assert task.when_date == "2026-01-20"
        assert task.tags == "work, important"
        assert task.project == "My Project"
        assert task.area == "Work"

    def test_task_defaults(self):
        """Test Task with default values."""
        task = Task(title="Simple Task")
        assert task.title == "Simple Task"
        assert task.uuid == ""
        assert task.notes == ""
        assert task.due_date == ""
        assert task.when_date == ""
        assert task.tags == ""
        assert task.project == ""
        assert task.area == ""


@pytest.mark.unit
class TestTaskSyncCache:
    """Tests for TaskSyncCache."""

    def test_cache_miss(self, tmp_path):
        """Test cache returns None when no cache exists."""
        cache = TaskSyncCache()
        cache.cache_file = tmp_path / "cache.json"
        assert cache.get() is None

    def test_cache_hit(self, tmp_path):
        """Test cache returns data when valid cache exists."""
        cache = TaskSyncCache(cache_ttl_seconds=300)
        cache.cache_file = tmp_path / "cache.json"

        test_data = {"inbox": [{"title": "Task 1"}], "today": [], "upcoming": []}
        cache.set(test_data)

        result = cache.get()
        assert result == test_data

    def test_cache_expiration(self, tmp_path):
        """Test cache returns None when expired."""
        cache = TaskSyncCache(cache_ttl_seconds=1)
        cache.cache_file = tmp_path / "cache.json"

        test_data = {"inbox": [{"title": "Task 1"}]}
        cache.set(test_data)

        # Manually modify timestamp to be old
        data = json.loads(cache.cache_file.read_text())
        old_time = datetime.now() - timedelta(seconds=10)
        data["timestamp"] = old_time.isoformat()
        cache.cache_file.write_text(json.dumps(data))

        assert cache.get() is None

    def test_cache_expired_at_exact_ttl(self, tmp_path):
        """Test cache returns None when exactly at TTL boundary."""
        cache = TaskSyncCache(cache_ttl_seconds=60)
        cache.cache_file = tmp_path / "cache.json"

        test_data = {"inbox": [{"title": "Task 1"}]}
        cache.set(test_data)

        # Set timestamp to exactly TTL seconds ago
        data = json.loads(cache.cache_file.read_text())
        boundary_time = datetime.now() - timedelta(seconds=60)
        data["timestamp"] = boundary_time.isoformat()
        cache.cache_file.write_text(json.dumps(data))

        # At exactly TTL, timedelta is NOT < TTL, so cache should be expired
        assert cache.get() is None

    def test_cache_valid_just_before_ttl(self, tmp_path):
        """Test cache returns data when just under TTL."""
        cache = TaskSyncCache(cache_ttl_seconds=60)
        cache.cache_file = tmp_path / "cache.json"

        test_data = {"inbox": [{"title": "Task 1"}]}
        cache.set(test_data)

        # Set timestamp to 1 second before TTL
        data = json.loads(cache.cache_file.read_text())
        just_before = datetime.now() - timedelta(seconds=59)
        data["timestamp"] = just_before.isoformat()
        cache.cache_file.write_text(json.dumps(data))

        assert cache.get() is not None

    def test_cache_invalid_json(self, tmp_path):
        """Test cache handles invalid JSON gracefully."""
        cache = TaskSyncCache()
        cache.cache_file = tmp_path / "cache.json"

        cache.cache_file.write_text("not valid json{")

        assert cache.get() is None

    def test_invalidate_deletes_cache_file(self, tmp_path):
        """Test invalidate removes cache file."""
        cache = TaskSyncCache()
        cache.cache_file = tmp_path / "cache.json"
        cache.set({"inbox": []})

        assert cache.cache_file.exists()
        cache.invalidate()
        assert not cache.cache_file.exists()

    def test_invalidate_no_file(self, tmp_path):
        """Test invalidate is safe when no cache file exists."""
        cache = TaskSyncCache()
        cache.cache_file = tmp_path / "nonexistent.json"

        cache.invalidate()  # Should not raise
        assert not cache.cache_file.exists()


@pytest.mark.unit
class TestToTask:
    """Tests for _to_task converter."""

    def test_full_task(self):
        """Test converting a full things.py dict."""
        t = {
            "uuid": "6Hf2qWBjWhq7B1xszwdo34",
            "title": "Review PR",
            "notes": "Check auth changes",
            "deadline": "2026-03-15",
            "start_date": "2026-03-12",
            "tags": ["urgent", "code-review"],
            "project_title": "Jarvis Dev",
            "area_title": "Work",
        }
        task = _to_task(t)
        assert task.uuid == "6Hf2qWBjWhq7B1xszwdo34"
        assert task.title == "Review PR"
        assert task.notes == "Check auth changes"
        # deadline maps to due_date, start_date maps to when_date
        assert task.due_date == "2026-03-15"
        assert task.when_date == "2026-03-12"
        # Verify exact separator: comma-space
        assert task.tags == "urgent, code-review"
        assert ", " in task.tags
        assert task.project == "Jarvis Dev"
        assert task.area == "Work"

    def test_deadline_maps_to_due_date_not_start_date(self):
        """Verify deadline maps to due_date by providing conflicting values."""
        t = {
            "title": "Task",
            "deadline": "2026-06-01",
            "start_date": "2026-05-01",
        }
        task = _to_task(t)
        assert task.due_date == "2026-06-01"
        assert task.when_date == "2026-05-01"
        assert task.due_date != task.when_date

    def test_uuid_extracted(self):
        """Test uuid is extracted from things.py dict."""
        task = _to_task({"title": "Task", "uuid": "XYZ789"})
        assert task.uuid == "XYZ789"

    def test_missing_uuid_defaults_to_empty(self):
        """Test missing uuid defaults to empty string."""
        task = _to_task({"title": "Task"})
        assert task.uuid == ""

    def test_minimal_task(self):
        """Test converting a task with only a title."""
        task = _to_task({"title": "Quick thought"})
        assert task.title == "Quick thought"
        assert task.uuid == ""
        assert task.notes == ""
        assert task.due_date == ""
        assert task.tags == ""
        assert task.project == ""
        assert task.area == ""

    def test_none_values_become_empty_strings(self):
        """Test that None values from things.py are converted to empty strings via `or ''` fallback."""
        t = {
            "title": "Task",
            "notes": None,
            "deadline": None,
            "start_date": None,
            "tags": None,
            "project_title": None,
            "area_title": None,
        }
        task = _to_task(t)
        # Each field should be exactly "" (not None, not "None")
        assert task.notes is not None
        assert task.notes == ""
        assert task.due_date is not None
        assert task.due_date == ""
        assert task.when_date is not None
        assert task.when_date == ""
        assert task.tags is not None
        assert task.tags == ""
        assert task.project is not None
        assert task.project == ""
        assert task.area is not None
        assert task.area == ""

    def test_empty_tags_list(self):
        """Test that empty tags list produces empty string."""
        task = _to_task({"title": "Task", "tags": []})
        assert task.tags == ""

    def test_tag_separator_is_comma_space(self):
        """Verify the exact separator is ', ' (comma followed by space)."""
        task = _to_task({"title": "Task", "tags": ["a", "b", "c"]})
        assert task.tags == "a, b, c"
        parts = task.tags.split(", ")
        assert parts == ["a", "b", "c"]


@pytest.mark.unit
class TestFetchTasks:
    """Tests for fetch_tasks function."""

    def test_fetch_uses_cache(self):
        """Test that fetch uses cache when available."""
        config = {
            "cache_ttl_seconds": 300,
            "lists_to_include": ["Inbox"],
        }

        cache_data = {
            "inbox": [
                {
                    "title": "Cached Task",
                    "notes": "",
                    "due_date": "",
                    "when_date": "",
                    "tags": "",
                    "project": "",
                    "area": "",
                }
            ],
            "today": [],
            "upcoming": [],
        }

        with patch("packages.integrations.things3.task_sync.TaskSyncCache") as mock_cache_class:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = cache_data
            mock_cache_class.return_value = mock_cache_instance

            result = fetch_tasks(config, use_cache=True)

            assert len(result["inbox"]) == 1
            assert result["inbox"][0].title == "Cached Task"
            mock_cache_instance.get.assert_called_once()

    def test_fetch_from_things_py(self):
        """Test fetch reads from things.py when cache misses."""
        config = {
            "cache_ttl_seconds": 300,
            "lists_to_include": ["Inbox", "Today"],
        }

        mock_things = MagicMock()
        mock_things.inbox.return_value = [
            {
                "title": "Inbox item",
                "notes": "",
                "deadline": None,
                "start_date": None,
                "tags": [],
                "project_title": None,
                "area_title": None,
            }
        ]
        mock_things.today.return_value = [
            {
                "title": "Today item",
                "notes": "note",
                "deadline": "2026-03-15",
                "start_date": "2026-03-12",
                "tags": ["work"],
                "project_title": "Proj",
                "area_title": "Work",
            }
        ]

        with patch("packages.integrations.things3.task_sync.TaskSyncCache") as mock_cache_class:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            mock_cache_class.return_value = mock_cache_instance

            with patch.dict("sys.modules", {"things": mock_things}):
                result = fetch_tasks(config, use_cache=False)

            assert len(result["inbox"]) == 1
            assert result["inbox"][0].title == "Inbox item"
            assert len(result["today"]) == 1
            assert result["today"][0].title == "Today item"
            assert result["today"][0].project == "Proj"
            mock_cache_instance.set.assert_called_once()

    def test_fetch_skips_unlisted(self):
        """Test that lists not in lists_to_include are skipped."""
        config = {
            "cache_ttl_seconds": 300,
            "lists_to_include": ["Today"],
        }

        mock_things = MagicMock()
        mock_things.today.return_value = []

        with patch("packages.integrations.things3.task_sync.TaskSyncCache") as mock_cache_class:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            mock_cache_class.return_value = mock_cache_instance

            with patch.dict("sys.modules", {"things": mock_things}):
                result = fetch_tasks(config, use_cache=False)

            assert result["inbox"] == []
            assert result["upcoming"] == []
            mock_things.inbox.assert_not_called()
            mock_things.upcoming.assert_not_called()


@pytest.mark.unit
class TestFormatTasksAsMarkdown:
    """Tests for format_tasks_as_markdown function."""

    def test_format_empty_tasks(self):
        """Test formatting with no tasks."""
        markdown = format_tasks_as_markdown([], [], [], max_tasks=50)
        assert "# Tasks from Things 3" in markdown
        assert "*No tasks found.*" in markdown

    def test_format_single_section(self):
        """Test formatting with only today's tasks."""
        today = [Task(title="Task 1"), Task(title="Task 2")]
        markdown = format_tasks_as_markdown([], today, [], max_tasks=50)

        assert "## Today" in markdown
        assert "- Task 1" in markdown
        assert "- Task 2" in markdown
        assert "## Inbox" not in markdown

    def test_format_all_sections(self):
        """Test formatting with tasks in all sections."""
        inbox = [Task(title="Inbox 1")]
        today = [Task(title="Today 1")]
        upcoming = [Task(title="Upcoming 1")]

        markdown = format_tasks_as_markdown(inbox, today, upcoming, max_tasks=50)

        assert "## Today" in markdown
        assert "## Upcoming" in markdown
        assert "## Inbox" in markdown
        assert "- Today 1" in markdown
        assert "- Upcoming 1" in markdown
        assert "- Inbox 1" in markdown

    def test_format_with_max_tasks_limit(self):
        """Test that max_tasks limit is respected."""
        many_tasks = [Task(title=f"Task {i}") for i in range(60)]
        markdown = format_tasks_as_markdown(many_tasks, [], [], max_tasks=50)

        assert "(+10 more)" in markdown
        assert "- Task 49" in markdown
        assert "- Task 55" not in markdown

    def test_format_includes_timestamp(self):
        """Test that timestamp is included."""
        markdown = format_tasks_as_markdown([], [], [], max_tasks=50)
        assert "*Last synced:" in markdown

    def test_format_grouped_by_area_and_project(self):
        """Test tasks are grouped by area then project."""
        today = [
            Task(title="PR Review", project="Jarvis Dev", area="Work"),
            Task(title="Deploy fix", project="Jarvis Dev", area="Work"),
            Task(title="Buy groceries", area="Personal"),
            Task(title="Random idea"),
        ]
        markdown = format_tasks_as_markdown([], today, [], max_tasks=50)

        assert "### Work" in markdown
        assert "#### Jarvis Dev" in markdown
        assert "- PR Review" in markdown
        assert "- Deploy fix" in markdown
        assert "### Personal" in markdown
        assert "- Buy groceries" in markdown
        assert "### Uncategorized" in markdown
        assert "- Random idea" in markdown

    def test_format_task_with_metadata(self):
        """Test task line includes due date, tags, and UUID (UUID last)."""
        today = [
            Task(
                title="Review PR",
                uuid="6Hf2qWBjWhq7B1xszwdo34",
                due_date="2026-03-15",
                tags="urgent, code-review",
            )
        ]
        markdown = format_tasks_as_markdown([], today, [], max_tasks=50)

        assert (
            "[Due: 2026-03-15 | Tags: urgent, code-review | ID: 6Hf2qWBjWhq7B1xszwdo34]" in markdown
        )

    def test_format_task_uuid_last_in_metadata(self):
        """Test UUID appears after due date and tags in metadata."""
        today = [Task(title="Task", uuid="ABC123", due_date="2026-01-01", tags="work")]
        markdown = format_tasks_as_markdown([], today, [], max_tasks=50)

        # UUID should be last
        assert "Due: 2026-01-01 | Tags: work | ID: ABC123" in markdown

    def test_format_task_uuid_only(self):
        """Test task with only UUID shows just the ID."""
        today = [Task(title="Task", uuid="ABC123")]
        markdown = format_tasks_as_markdown([], today, [], max_tasks=50)

        assert "[ID: ABC123]" in markdown

    def test_format_task_with_notes(self):
        """Test task notes appear indented below task."""
        today = [Task(title="Review PR", notes="Check the auth middleware changes")]
        markdown = format_tasks_as_markdown([], today, [], max_tasks=50)

        assert "- Review PR" in markdown
        assert "  Check the auth middleware changes" in markdown

    def test_format_long_notes_truncated(self):
        """Test that long notes are truncated."""
        long_notes = "A" * 200
        today = [Task(title="Task", notes=long_notes)]
        markdown = format_tasks_as_markdown([], today, [], max_tasks=50)

        assert "..." in markdown
        # Should contain first 150 chars
        assert "A" * 150 in markdown

    def test_uncategorized_sorted_last(self):
        """Test that uncategorized tasks appear after named areas."""
        today = [
            Task(title="No area task"),
            Task(title="Work task", area="Work"),
        ]
        markdown = format_tasks_as_markdown([], today, [], max_tasks=50)

        work_pos = markdown.index("### Work")
        uncat_pos = markdown.index("### Uncategorized")
        assert work_pos < uncat_pos


@pytest.mark.unit
class TestSyncTasksToFile:
    """Tests for sync_tasks_to_file function."""

    def test_sync_disabled(self, tmp_path):
        """Test sync does nothing when disabled."""
        config = {"things3": {"enabled": False}}
        output_path = tmp_path / "tasks.md"

        result = sync_tasks_to_file(output_path, config)

        assert result is False
        assert not output_path.exists()

    def test_sync_startup_disabled(self, tmp_path):
        """Test sync respects sync_on_startup setting."""
        config = {"things3": {"enabled": True, "sync_on_startup": False}}
        output_path = tmp_path / "tasks.md"

        result = sync_tasks_to_file(output_path, config)

        assert result is False
        assert not output_path.exists()

    @patch("packages.integrations.things3.task_sync.fetch_tasks")
    def test_sync_success(self, mock_fetch, tmp_path):
        """Test successful sync writes markdown file."""
        config = {
            "things3": {
                "enabled": True,
                "sync_on_startup": True,
                "max_tasks_per_list": 50,
            }
        }
        output_path = tmp_path / "tasks.md"

        mock_fetch.return_value = {
            "inbox": [Task(title="Task 1")],
            "today": [Task(title="Task 2")],
            "upcoming": [],
        }

        result = sync_tasks_to_file(output_path, config)

        assert result is True
        assert output_path.exists()
        content = output_path.read_text()
        assert "# Tasks from Things 3" in content
        assert "Task 1" in content
        assert "Task 2" in content

    @patch("packages.integrations.things3.task_sync.fetch_tasks")
    def test_sync_handles_errors(self, mock_fetch, tmp_path):
        """Test sync handles errors gracefully."""
        config = {"things3": {"enabled": True, "sync_on_startup": True}}
        output_path = tmp_path / "tasks.md"

        mock_fetch.side_effect = Exception("Connection failed")

        result = sync_tasks_to_file(output_path, config)

        assert result is False
        assert not output_path.exists()
