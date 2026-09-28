"""
Unit tests for task_sync module.
Tests task synchronization from Things 3 via the export Shortcut.
"""

import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from packages.core.settings import Things3Settings
from packages.integrations.things3.shortcut_source import ThingsUnavailableError
from packages.integrations.things3.task_sync import (
    Task,
    TaskSyncCache,
    _split_scheduled,
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


# Shape of one item as the "JARVIS Things Export" Shortcut writes it (German Mac locale)
def _item(**overrides):
    item = {
        "id": "6Hf2qWBjWhq7B1xszwdo34",
        "title": "Review PR",
        "notes": "Check auth changes",
        "startDate": "12.03.2026, 00:00",
        "deadline": "15.03.2026, 00:00",
        "tags": "urgent\ncode-review",
        "parent": "🛠 Jarvis Dev",
    }
    item.update(overrides)
    return item


@pytest.mark.unit
class TestToTask:
    """Tests for _to_task converter (Shortcut export item → Task)."""

    def test_full_item(self):
        task = _to_task(_item())
        assert task.uuid == "6Hf2qWBjWhq7B1xszwdo34"
        assert task.title == "Review PR"
        assert task.notes == "Check auth changes"
        assert task.due_date == "2026-03-15"  # deadline → due_date, ISO
        assert task.when_date == "2026-03-12"  # startDate → when_date, ISO
        assert task.tags == "urgent, code-review"  # one tag per line → comma-space
        assert task.project == "🛠 Jarvis Dev"  # parent title (project or area)
        assert task.area == ""  # the export has no areas

    def test_empty_values(self):
        task = _to_task(_item(startDate="", deadline="", tags="", notes="", parent=""))
        assert (task.when_date, task.due_date, task.tags, task.notes, task.project) == ("", "", "", "", "")

    def test_missing_keys_default_to_empty(self):
        task = _to_task({"id": "X", "title": "T"})
        assert task.uuid == "X"
        assert task.when_date == ""

    @pytest.mark.parametrize("raw", ["12.03.2026, 00:00", "12.03.2026", "2026-03-12", "2026-03-12T00:00:00"])
    def test_accepted_date_shapes(self, raw):
        assert _to_task(_item(startDate=raw)).when_date == "2026-03-12"

    def test_unknown_date_shape_fails_loudly(self):
        with pytest.raises(ThingsUnavailableError, match="unrecognised date format"):
            _to_task(_item(startDate="March 12, 2026 at 12:00 AM"))


@pytest.mark.unit
class TestSplitScheduled:
    def test_today_includes_overdue_and_today_upcoming_is_later(self):
        today = date(2026, 3, 12)
        tasks = [
            _to_task(_item(id=i, startDate=d))
            for i, d in [("a", "11.03.2026"), ("b", "12.03.2026"), ("c", "13.03.2026")]
        ]
        today_tasks, upcoming = _split_scheduled(tasks, today)
        assert [t.uuid for t in today_tasks] == ["a", "b"]
        assert [t.uuid for t in upcoming] == ["c"]

    def test_items_without_start_date_are_dropped(self):
        today_tasks, upcoming = _split_scheduled([_to_task(_item(startDate=""))], date(2026, 3, 12))
        assert today_tasks == [] and upcoming == []


@pytest.mark.unit
class TestFetchTasks:
    """Tests for fetch_tasks (cache + Shortcut export)."""

    def _no_cache(self, mock_cache_class):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache
        return mock_cache

    def test_fetch_uses_cache(self):
        things3 = Things3Settings(enabled=True)
        cached = {"inbox": [{"title": "Cached"}], "today": [], "upcoming": []}
        with (
            patch("packages.integrations.things3.task_sync.TaskSyncCache") as mock_cache_class,
            patch("packages.integrations.things3.task_sync.run_export") as mock_export,
        ):
            mock_cache_class.return_value.get.return_value = cached
            result = fetch_tasks(things3)
        mock_export.assert_not_called()
        assert [t.title for t in result["inbox"]] == ["Cached"]

    def test_fetch_from_export_splits_and_caches(self):
        things3 = Things3Settings(enabled=True)
        today = date.today()
        export = {
            "inbox": [_item(id="i1", startDate="", deadline="")],
            "scheduled": [
                _item(id="t1", startDate=today.isoformat()),
                _item(id="u1", startDate=(today + timedelta(days=3)).isoformat()),
            ],
        }
        with (
            patch("packages.integrations.things3.task_sync.TaskSyncCache") as mock_cache_class,
            patch("packages.integrations.things3.task_sync.run_export", return_value=export),
        ):
            mock_cache = self._no_cache(mock_cache_class)
            result = fetch_tasks(things3)
        assert [t.uuid for t in result["inbox"]] == ["i1"]
        assert [t.uuid for t in result["today"]] == ["t1"]
        assert [t.uuid for t in result["upcoming"]] == ["u1"]
        cached = mock_cache.set.call_args[0][0]
        assert cached["today"][0]["uuid"] == "t1"
        assert set(cached["today"][0]) == {"title", "uuid", "notes", "due_date", "when_date", "tags", "project", "area"}

    def test_fetch_honours_lists_to_include(self):
        things3 = Things3Settings(enabled=True, lists_to_include=["Today"])
        export = {"inbox": [_item(id="i1")], "scheduled": [_item(id="t1", startDate=date.today().isoformat())]}
        with (
            patch("packages.integrations.things3.task_sync.TaskSyncCache") as mock_cache_class,
            patch("packages.integrations.things3.task_sync.run_export", return_value=export),
        ):
            self._no_cache(mock_cache_class)
            result = fetch_tasks(things3)
        assert result["inbox"] == [] and result["upcoming"] == []
        assert [t.uuid for t in result["today"]] == ["t1"]

    def test_failure_raises_and_caches_nothing(self):
        things3 = Things3Settings(enabled=True)
        with (
            patch("packages.integrations.things3.task_sync.TaskSyncCache") as mock_cache_class,
            patch(
                "packages.integrations.things3.task_sync.run_export",
                side_effect=ThingsUnavailableError("the 'shortcuts' command isn't available"),
            ),
        ):
            mock_cache = self._no_cache(mock_cache_class)
            with pytest.raises(ThingsUnavailableError):
                fetch_tasks(things3)
        mock_cache.set.assert_not_called()  # the next call retries instead of serving an empty list


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

        assert "[Due: 2026-03-15 | Tags: urgent, code-review | ID: 6Hf2qWBjWhq7B1xszwdo34]" in markdown

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
        things3 = Things3Settings(enabled=False)
        output_path = tmp_path / "tasks.md"

        result = sync_tasks_to_file(output_path, things3)

        assert result is False
        assert not output_path.exists()

    def test_sync_startup_disabled(self, tmp_path):
        """Test sync respects sync_on_startup setting."""
        things3 = Things3Settings(enabled=True, sync_on_startup=False)
        output_path = tmp_path / "tasks.md"

        result = sync_tasks_to_file(output_path, things3)

        assert result is False
        assert not output_path.exists()

    @patch("packages.integrations.things3.task_sync.fetch_tasks")
    def test_sync_success(self, mock_fetch, tmp_path):
        """Test successful sync writes markdown file."""
        things3 = Things3Settings(enabled=True, sync_on_startup=True, max_tasks_per_list=50)
        output_path = tmp_path / "tasks.md"

        mock_fetch.return_value = {
            "inbox": [Task(title="Task 1")],
            "today": [Task(title="Task 2")],
            "upcoming": [],
        }

        result = sync_tasks_to_file(output_path, things3)

        assert result is True
        assert output_path.exists()
        content = output_path.read_text()
        assert "# Tasks from Things 3" in content
        assert "Task 1" in content
        assert "Task 2" in content

    @patch("packages.integrations.things3.task_sync.fetch_tasks")
    def test_sync_handles_errors(self, mock_fetch, tmp_path):
        """Test sync handles errors gracefully."""
        things3 = Things3Settings(enabled=True, sync_on_startup=True)
        output_path = tmp_path / "tasks.md"

        mock_fetch.side_effect = Exception("Connection failed")

        result = sync_tasks_to_file(output_path, things3)

        assert result is False
        assert not output_path.exists()

    @patch("packages.integrations.things3.task_sync.fetch_tasks")
    def test_sync_keeps_previous_file_when_things_unavailable(self, mock_fetch, tmp_path):
        """A failed read must not replace real tasks with 'No tasks found'."""
        things3 = Things3Settings(enabled=True, sync_on_startup=True)
        output_path = tmp_path / "tasks.md"
        output_path.write_text("# Tasks from Things 3\n- Previous task")
        mock_fetch.side_effect = ThingsUnavailableError("the Shortcut failed")

        assert sync_tasks_to_file(output_path, things3) is False
        assert output_path.read_text() == "# Tasks from Things 3\n- Previous task"
