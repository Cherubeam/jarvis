"""
Unit tests for Readwise tool definitions.
"""

from unittest.mock import patch, MagicMock

import pytest

from packages.core.tools.base import ToolDefinition


@pytest.mark.unit
class TestMakeReadwiseToolsGuard:
    """CLI availability guard tests."""

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    def test_returns_empty_when_cli_missing(self, mock_avail):
        mock_avail.return_value = False
        from packages.core.tools.readwise_tools import make_readwise_tools

        result = make_readwise_tools({})
        assert result == []

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    @patch("packages.core.tools.readwise_tools.ReadwiseClient")
    def test_returns_tools_when_cli_available(self, mock_client_cls, mock_avail):
        mock_avail.return_value = True
        from packages.core.tools.readwise_tools import make_readwise_tools

        tools = make_readwise_tools({})
        assert len(tools) == 6
        assert all(isinstance(t, ToolDefinition) for t in tools)

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    @patch("packages.core.tools.readwise_tools.ReadwiseClient")
    def test_tool_names(self, mock_client_cls, mock_avail):
        mock_avail.return_value = True
        from packages.core.tools.readwise_tools import make_readwise_tools

        tools = make_readwise_tools({})
        names = {t.name for t in tools}
        assert names == {
            "search_reading_list",
            "search_highlights",
            "get_document_details",
            "save_to_reader",
            "tag_readwise_document",
            "move_readwise_document",
        }


@pytest.mark.unit
class TestReadwiseToolSchemas:
    """Tests for tool parameter schemas."""

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    @patch("packages.core.tools.readwise_tools.ReadwiseClient")
    def test_search_reading_list_schema(self, mock_client_cls, mock_avail):
        mock_avail.return_value = True
        from packages.core.tools.readwise_tools import make_readwise_tools

        tools = make_readwise_tools({})
        search_tool = next(t for t in tools if t.name == "search_reading_list")

        params = search_tool.parameters
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert params["required"] == ["query"]
        assert "location" in params["properties"]
        assert "category" in params["properties"]

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    @patch("packages.core.tools.readwise_tools.ReadwiseClient")
    def test_search_highlights_schema(self, mock_client_cls, mock_avail):
        mock_avail.return_value = True
        from packages.core.tools.readwise_tools import make_readwise_tools

        tools = make_readwise_tools({})
        tool = next(t for t in tools if t.name == "search_highlights")

        assert tool.parameters["required"] == ["query"]

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    @patch("packages.core.tools.readwise_tools.ReadwiseClient")
    def test_save_to_reader_schema(self, mock_client_cls, mock_avail):
        mock_avail.return_value = True
        from packages.core.tools.readwise_tools import make_readwise_tools

        tools = make_readwise_tools({})
        tool = next(t for t in tools if t.name == "save_to_reader")

        assert tool.parameters["required"] == ["url"]


@pytest.mark.unit
class TestReadwiseToolExecution:
    """Tests that tool execute functions delegate to the client."""

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    @patch("packages.core.tools.readwise_tools.ReadwiseClient")
    def test_search_reading_list_delegates(self, mock_client_cls, mock_avail):
        mock_avail.return_value = True
        mock_client = MagicMock()
        mock_client.search_documents.return_value = '[{"title": "AI Article"}]'
        mock_client_cls.return_value = mock_client

        from packages.core.tools.readwise_tools import make_readwise_tools

        tools = make_readwise_tools({})
        search_tool = next(t for t in tools if t.name == "search_reading_list")

        result = search_tool.execute(query="ai agents")
        assert result == '[{"title": "AI Article"}]'
        mock_client.search_documents.assert_called_once_with(
            "ai agents",
            location="",
            category="",
        )

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    @patch("packages.core.tools.readwise_tools.ReadwiseClient")
    def test_search_highlights_delegates(self, mock_client_cls, mock_avail):
        mock_avail.return_value = True
        mock_client = MagicMock()
        mock_client.search_highlights.return_value = '[{"text": "highlight"}]'
        mock_client_cls.return_value = mock_client

        from packages.core.tools.readwise_tools import make_readwise_tools

        tools = make_readwise_tools({})
        tool = next(t for t in tools if t.name == "search_highlights")

        result = tool.execute(query="systems thinking")
        assert result == '[{"text": "highlight"}]'
        mock_client.search_highlights.assert_called_once_with("systems thinking")

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    @patch("packages.core.tools.readwise_tools.ReadwiseClient")
    def test_save_to_reader_delegates(self, mock_client_cls, mock_avail):
        mock_avail.return_value = True
        mock_client = MagicMock()
        mock_client.create_document.return_value = '{"id": "new123"}'
        mock_client_cls.return_value = mock_client

        from packages.core.tools.readwise_tools import make_readwise_tools

        tools = make_readwise_tools({})
        tool = next(t for t in tools if t.name == "save_to_reader")

        result = tool.execute(url="https://example.com")
        assert "new123" in result
        mock_client.create_document.assert_called_once_with("https://example.com")

    @patch("packages.core.tools.readwise_tools.is_cli_available")
    @patch("packages.core.tools.readwise_tools.ReadwiseClient")
    def test_search_with_filters_passes_through(self, mock_client_cls, mock_avail):
        mock_avail.return_value = True
        mock_client = MagicMock()
        mock_client.search_documents.return_value = "[]"
        mock_client_cls.return_value = mock_client

        from packages.core.tools.readwise_tools import make_readwise_tools

        tools = make_readwise_tools({})
        search_tool = next(t for t in tools if t.name == "search_reading_list")

        search_tool.execute(query="test", location="inbox", category="article")
        mock_client.search_documents.assert_called_once_with(
            "test",
            location="inbox",
            category="article",
        )
