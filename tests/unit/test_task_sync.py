"""
Unit tests for task_sync module.
Tests task synchronization from Things 3 via MCP.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from task_sync import (
    MCPThings3Client,
    Task,
    TaskSyncCache,
    fetch_tasks_async,
    format_tasks_as_markdown,
    parse_task_response,
    sync_tasks_to_file,
)


@pytest.mark.unit
class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation(self):
        """Test creating a Task object."""
        task = Task(
            title="Test Task",
            notes="Test notes",
            due_date="2026-01-25",
            when_date="2026-01-20",
            tags="work,important",
        )
        assert task.title == "Test Task"
        assert task.notes == "Test notes"
        assert task.due_date == "2026-01-25"
        assert task.when_date == "2026-01-20"
        assert task.tags == "work,important"

    def test_task_defaults(self):
        """Test Task with default values."""
        task = Task(title="Simple Task")
        assert task.title == "Simple Task"
        assert task.notes == ""
        assert task.due_date == ""
        assert task.when_date == ""
        assert task.tags == ""


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

        # Set some data
        test_data = {"inbox": [{"title": "Task 1"}], "today": [], "upcoming": []}
        cache.set(test_data)

        # Get it back
        result = cache.get()
        assert result == test_data

    def test_cache_expiration(self, tmp_path):
        """Test cache returns None when expired."""
        cache = TaskSyncCache(cache_ttl_seconds=1)
        cache.cache_file = tmp_path / "cache.json"

        # Set data
        test_data = {"inbox": [{"title": "Task 1"}]}
        cache.set(test_data)

        # Manually modify timestamp to be old
        data = json.loads(cache.cache_file.read_text())
        old_time = datetime.now() - timedelta(seconds=10)
        data["timestamp"] = old_time.isoformat()
        cache.cache_file.write_text(json.dumps(data))

        # Should return None (expired)
        assert cache.get() is None

    def test_cache_invalid_json(self, tmp_path):
        """Test cache handles invalid JSON gracefully."""
        cache = TaskSyncCache()
        cache.cache_file = tmp_path / "cache.json"

        # Write invalid JSON
        cache.cache_file.write_text("not valid json{")

        # Should return None without crashing
        assert cache.get() is None


@pytest.mark.unit
class TestParseTaskResponse:
    """Tests for parse_task_response function."""

    def test_parse_empty_response(self):
        """Test parsing empty response."""
        assert parse_task_response("") == []
        assert parse_task_response("No todos found") == []

    def test_parse_single_task(self):
        """Test parsing single task."""
        response = "• Task One (Due: 2026-01-25, When: 2026-01-20)"
        tasks = parse_task_response(response)
        assert len(tasks) == 1
        assert tasks[0].title == "Task One"

    def test_parse_multiple_tasks(self):
        """Test parsing multiple tasks."""
        response = """Todos in Things3 inbox:
• Task One (Due: No Due Date, When: No Scheduled Date)
• Task Two (Due: 2026-01-25, When: Today)
• Task Three (Due: No Due Date, When: No Scheduled Date)"""
        tasks = parse_task_response(response)
        assert len(tasks) == 3
        assert tasks[0].title == "Task One"
        assert tasks[1].title == "Task Two"
        assert tasks[2].title == "Task Three"

    def test_parse_task_without_metadata(self):
        """Test parsing task without date metadata."""
        response = "• Simple Task"
        tasks = parse_task_response(response)
        assert len(tasks) == 1
        assert tasks[0].title == "Simple Task"

    def test_parse_mixed_format(self):
        """Test parsing response with mixed content."""
        response = """Header line
• Task One (Due: date)
Some other text
• Task Two
Not a task line"""
        tasks = parse_task_response(response)
        assert len(tasks) == 2


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

        # Should have max_tasks + indicator
        assert "(+10 more)" in markdown
        assert "- Task 49" in markdown  # 0-49 = 50 tasks
        assert "- Task 55" not in markdown  # Beyond limit

    def test_format_includes_timestamp(self):
        """Test that timestamp is included."""
        markdown = format_tasks_as_markdown([], [], [], max_tasks=50)
        assert "*Last synced:" in markdown
        assert "2026" in markdown  # Current year


@pytest.mark.unit
class TestMCPThings3Client:
    """Tests for MCPThings3Client."""

    @pytest.mark.asyncio
    async def test_client_connect(self):
        """Test client connection starts subprocess."""
        client = MCPThings3Client()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = None
            mock_exec.return_value = mock_process

            await client.connect()

            assert mock_exec.called
            assert client.process is not None

    @pytest.mark.asyncio
    async def test_client_close(self):
        """Test client close terminates process."""
        client = MCPThings3Client()

        # Mock process
        mock_process = AsyncMock()
        client.process = mock_process

        await client.close()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """Test successful tool call."""
        client = MCPThings3Client()

        # Mock process
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()

        # Mock response
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"text": "Tool executed successfully"}]},
        }
        mock_process.stdout.readline = AsyncMock(
            return_value=(json.dumps(response) + "\n").encode()
        )

        client.process = mock_process

        result = await client.call_tool("view-inbox", {})

        assert result == "Tool executed successfully"
        assert mock_process.stdin.write.called

    @pytest.mark.asyncio
    async def test_call_tool_error_response(self):
        """Test tool call with error response."""
        client = MCPThings3Client()

        # Mock process
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()

        # Mock error response
        response = {"jsonrpc": "2.0", "id": 1, "error": {"message": "Tool failed"}}
        mock_process.stdout.readline = AsyncMock(
            return_value=(json.dumps(response) + "\n").encode()
        )

        client.process = mock_process

        with pytest.raises(RuntimeError, match="MCP tool error"):
            await client.call_tool("view-inbox", {})


@pytest.mark.unit
class TestFetchTasksAsync:
    """Tests for fetch_tasks_async function."""

    @pytest.mark.asyncio
    async def test_fetch_uses_cache(self, tmp_path):
        """Test that fetch uses cache when available."""
        config = {
            "cache_ttl_seconds": 300,
            "lists_to_include": ["Inbox"],
        }

        # Setup cache
        cache = TaskSyncCache(cache_ttl_seconds=300)
        cache.cache_file = tmp_path / "cache.json"
        cache_data = {
            "inbox": [{"title": "Cached Task"}],
            "today": [],
            "upcoming": [],
        }
        cache.set(cache_data)

        with patch("task_sync.TaskSyncCache") as mock_cache_class:
            mock_cache_instance = Mock()
            mock_cache_instance.get.return_value = cache_data
            mock_cache_class.return_value = mock_cache_instance

            result = await fetch_tasks_async(config, use_cache=True)

            assert len(result["inbox"]) == 1
            assert result["inbox"][0].title == "Cached Task"
            mock_cache_instance.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_without_cache(self):
        """Test fetch when cache is disabled."""
        config = {
            "cache_ttl_seconds": 300,
            "lists_to_include": ["Inbox"],
        }

        with patch("task_sync.MCPThings3Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.call_tool = AsyncMock(
                return_value="• Task from MCP (Due: date)"
            )
            mock_client_class.return_value = mock_client

            with patch("task_sync.TaskSyncCache") as mock_cache:
                mock_cache_instance = Mock()
                mock_cache_instance.get.return_value = None
                mock_cache.return_value = mock_cache_instance

                result = await fetch_tasks_async(config, use_cache=False)

                # Should have attempted MCP call
                mock_client.connect.assert_called_once()
                mock_client.close.assert_called_once()


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

    @patch("task_sync.asyncio.run")
    def test_sync_success(self, mock_run, tmp_path):
        """Test successful sync writes markdown file."""
        config = {
            "things3": {
                "enabled": True,
                "sync_on_startup": True,
                "max_tasks_per_list": 50,
            }
        }
        output_path = tmp_path / "tasks.md"

        # Mock fetch returning tasks
        mock_run.return_value = {
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

    @patch("task_sync.asyncio.run")
    def test_sync_handles_errors(self, mock_run, tmp_path):
        """Test sync handles errors gracefully."""
        config = {"things3": {"enabled": True, "sync_on_startup": True}}
        output_path = tmp_path / "tasks.md"

        # Mock fetch raising exception
        mock_run.side_effect = Exception("Connection failed")

        result = sync_tasks_to_file(output_path, config)

        assert result is False
        assert not output_path.exists()
