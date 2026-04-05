"""
Unit tests for Things 3 write tools.
Tests create_task, complete_task, and update_task tool factory.
"""

from unittest.mock import MagicMock, patch

import pytest

from packages.core.tools.base import ToolDefinition


@pytest.mark.unit
class TestMakeThings3Tools:
    """Tests for make_things3_tools factory."""

    @patch("packages.core.tools.things3_tools.sys")
    def test_returns_empty_on_non_darwin(self, mock_sys):
        """Factory returns empty list on non-macOS platforms."""
        mock_sys.platform = "linux"
        from packages.core.tools.things3_tools import make_things3_tools

        result = make_things3_tools({})
        assert result == []

    @patch("packages.core.tools.things3_tools.sys")
    def test_returns_three_tools(self, mock_sys):
        """Factory returns exactly 3 tools on macOS."""
        mock_sys.platform = "darwin"
        from packages.core.tools.things3_tools import make_things3_tools

        tools = make_things3_tools({})
        assert len(tools) == 3

    @patch("packages.core.tools.things3_tools.sys")
    def test_tool_names(self, mock_sys):
        """Tools have correct names."""
        mock_sys.platform = "darwin"
        from packages.core.tools.things3_tools import make_things3_tools

        tools = make_things3_tools({})
        names = [t.name for t in tools]
        assert names == ["create_task", "complete_task", "update_task"]

    @patch("packages.core.tools.things3_tools.sys")
    def test_tools_are_tool_definitions(self, mock_sys):
        """All returned tools are ToolDefinition instances."""
        mock_sys.platform = "darwin"
        from packages.core.tools.things3_tools import make_things3_tools

        tools = make_things3_tools({})
        for tool in tools:
            assert isinstance(tool, ToolDefinition)

    @patch("packages.core.tools.things3_tools.sys")
    def test_descriptions_mention_best_effort(self, mock_sys):
        """Tool descriptions mention best-effort nature."""
        mock_sys.platform = "darwin"
        from packages.core.tools.things3_tools import make_things3_tools

        tools = make_things3_tools({})
        for tool in tools:
            assert "best-effort" in tool.description


@pytest.mark.unit
class TestCreateTask:
    """Tests for create_task tool."""

    def _get_create_tool(self):
        with patch("packages.core.tools.things3_tools.sys") as mock_sys:
            mock_sys.platform = "darwin"
            from packages.core.tools.things3_tools import make_things3_tools
            tools = make_things3_tools({})
        return tools[0]

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_create_task_title_only(self, mock_cache_cls, mock_open):
        """Create task with just a title."""
        tool = self._get_create_tool()
        result = tool.execute(title="Buy milk")

        assert "Requested task creation for 'Buy milk'" in result
        assert "Changes may take a moment" in result
        mock_open.assert_called_once()

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_create_task_with_list_name(self, mock_cache_cls, mock_open):
        """Create task with list_name shows project in response."""
        tool = self._get_create_tool()
        result = tool.execute(title="Review PR", list_name="JARVIS")

        assert "in 'JARVIS'" in result

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_create_task_invalidates_cache(self, mock_cache_cls, mock_open):
        """Cache is invalidated after successful creation."""
        tool = self._get_create_tool()
        tool.execute(title="Task")

        # The cache was created inside make_things3_tools, so we check via the mock
        mock_cache_cls.return_value.invalidate.assert_called()

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=False)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_create_task_failure(self, mock_cache_cls, mock_open):
        """Returns error when URL open fails."""
        tool = self._get_create_tool()
        result = tool.execute(title="Task")

        assert result.startswith("Error:")
        mock_cache_cls.return_value.invalidate.assert_not_called()

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_create_task_all_params(self, mock_cache_cls, mock_open):
        """All parameters are forwarded to things.url."""
        tool = self._get_create_tool()
        result = tool.execute(
            title="Task",
            notes="Some notes",
            when="today",
            deadline="2026-04-10",
            tags="work,urgent",
            list_name="JARVIS",
        )

        assert "Requested task creation" in result
        # Verify the URL was generated with all params by checking it was called
        mock_open.assert_called_once()
        url_arg = mock_open.call_args[0][0]
        assert "title=Task" in url_arg
        assert "notes=" in url_arg
        assert "when=today" in url_arg
        assert "deadline=2026-04-10" in url_arg
        assert "tags=" in url_arg
        assert "list=JARVIS" in url_arg

    def test_create_task_required_param(self):
        """create_task requires title parameter."""
        tool = self._get_create_tool()
        assert "title" in tool.parameters["required"]


@pytest.mark.unit
class TestCompleteTask:
    """Tests for complete_task tool."""

    def _get_complete_tool(self):
        with patch("packages.core.tools.things3_tools.sys") as mock_sys:
            mock_sys.platform = "darwin"
            from packages.core.tools.things3_tools import make_things3_tools
            tools = make_things3_tools({})
        return tools[1]

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_complete_task_success(self, mock_cache_cls, mock_open):
        """Complete task with valid UUID."""
        tool = self._get_complete_tool()
        result = tool.execute(uuid="ABC123")

        assert "Requested completion of task ABC123" in result
        assert "Changes may take a moment" in result
        mock_open.assert_called_once()

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_complete_task_invalidates_cache(self, mock_cache_cls, mock_open):
        """Cache is invalidated after successful completion."""
        tool = self._get_complete_tool()
        tool.execute(uuid="ABC123")

        mock_cache_cls.return_value.invalidate.assert_called()

    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_complete_task_empty_uuid(self, mock_cache_cls):
        """Returns error for empty UUID."""
        tool = self._get_complete_tool()
        result = tool.execute(uuid="")

        assert result.startswith("Error:")
        assert "uuid" in result.lower()

    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_complete_task_whitespace_uuid(self, mock_cache_cls):
        """Returns error for whitespace-only UUID."""
        tool = self._get_complete_tool()
        result = tool.execute(uuid="   ")

        assert result.startswith("Error:")

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_complete_task_strips_uuid(self, mock_cache_cls, mock_open):
        """UUID is stripped of whitespace."""
        tool = self._get_complete_tool()
        tool.execute(uuid="  ABC123  ")

        url_arg = mock_open.call_args[0][0]
        assert "id=ABC123" in url_arg

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=False)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_complete_task_failure(self, mock_cache_cls, mock_open):
        """Returns error when URL open fails."""
        tool = self._get_complete_tool()
        result = tool.execute(uuid="ABC123")

        assert result.startswith("Error:")
        mock_cache_cls.return_value.invalidate.assert_not_called()

    def test_complete_task_required_param(self):
        """complete_task requires uuid parameter."""
        tool = self._get_complete_tool()
        assert "uuid" in tool.parameters["required"]


@pytest.mark.unit
class TestUpdateTask:
    """Tests for update_task tool."""

    def _get_update_tool(self):
        with patch("packages.core.tools.things3_tools.sys") as mock_sys:
            mock_sys.platform = "darwin"
            from packages.core.tools.things3_tools import make_things3_tools
            tools = make_things3_tools({})
        return tools[2]

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_update_task_success(self, mock_cache_cls, mock_open):
        """Update task with valid UUID and title."""
        tool = self._get_update_tool()
        result = tool.execute(uuid="ABC123", title="Updated title")

        assert "Requested update for task ABC123" in result
        assert "Changes may take a moment" in result

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_update_task_invalidates_cache(self, mock_cache_cls, mock_open):
        """Cache is invalidated after successful update."""
        tool = self._get_update_tool()
        tool.execute(uuid="ABC123", title="New")

        mock_cache_cls.return_value.invalidate.assert_called()

    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_update_task_empty_uuid(self, mock_cache_cls):
        """Returns error for empty UUID."""
        tool = self._get_update_tool()
        result = tool.execute(uuid="")

        assert result.startswith("Error:")

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=True)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_update_task_all_params(self, mock_cache_cls, mock_open):
        """All parameters are forwarded to things.url."""
        tool = self._get_update_tool()
        tool.execute(
            uuid="ABC123",
            title="New title",
            notes="New notes",
            when="tomorrow",
            deadline="2026-05-01",
            tags="updated",
        )

        url_arg = mock_open.call_args[0][0]
        assert "id=ABC123" in url_arg
        assert "title=" in url_arg
        assert "notes=" in url_arg
        assert "when=tomorrow" in url_arg
        assert "deadline=2026-05-01" in url_arg
        assert "tags=updated" in url_arg

    @patch("packages.core.tools.things3_tools._open_things_url", return_value=False)
    @patch("packages.core.tools.things3_tools.TaskSyncCache")
    def test_update_task_failure(self, mock_cache_cls, mock_open):
        """Returns error when URL open fails."""
        tool = self._get_update_tool()
        result = tool.execute(uuid="ABC123", title="New")

        assert result.startswith("Error:")

    def test_update_task_required_param(self):
        """update_task requires uuid parameter."""
        tool = self._get_update_tool()
        assert "uuid" in tool.parameters["required"]
