"""Unit tests for the vault semantic search tool."""

from __future__ import annotations

from unittest.mock import MagicMock

from packages.core.tools.cortex_search import _MAX_OUTPUT_CHARS, make_cortex_search_tool


def _make_tool(mock_client: MagicMock):
    """Create a cortex search tool with a mocked client."""
    return make_cortex_search_tool(mock_client)


class TestCortexSearchTool:
    def test_search_formats_results(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {"path": "Projects/Alpha.md", "heading": "Overview", "score": 0.92, "content": "Alpha project details."},
                {"path": "Notes/Beta.md", "heading": "", "score": 0.85, "content": "Beta notes here."},
            ],
            "count": 2,
        }
        tool = _make_tool(mock_client)
        output = tool.execute(query="alpha project")

        assert "Projects/Alpha.md" in output
        assert "> Overview" in output
        assert "0.92" in output
        assert "Alpha project details." in output
        assert "Notes/Beta.md" in output
        assert "Beta notes here." in output

    def test_search_service_down(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = None
        tool = _make_tool(mock_client)

        output = tool.execute(query="anything")

        assert "unreachable" in output.lower()
        assert "search_notes" in output

    def test_search_empty_results(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [], "count": 0}
        tool = _make_tool(mock_client)

        output = tool.execute(query="nonexistent")

        assert "No results found" in output

    def test_search_clamps_n_results(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [], "count": 0}
        tool = _make_tool(mock_client)

        # Test clamping to max 20
        tool.execute(query="test", n_results=50)
        _, kwargs = mock_client.search.call_args
        assert kwargs["n_results"] == 20

        # Test clamping to min 1
        tool.execute(query="test", n_results=-5)
        _, kwargs = mock_client.search.call_args
        assert kwargs["n_results"] == 1

    def test_search_passes_path_prefix(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [], "count": 0}
        tool = _make_tool(mock_client)

        tool.execute(query="test", path_prefix="Projects/")

        mock_client.search.assert_called_once()
        _, kwargs = mock_client.search.call_args
        assert kwargs["path_prefix"] == "Projects/"

    def test_search_truncates_long_output(self) -> None:
        mock_client = MagicMock()
        # Create results that exceed _MAX_OUTPUT_CHARS
        long_content = "x" * 3000
        mock_client.search.return_value = {
            "results": [
                {"path": f"Note{i}.md", "heading": "", "score": 0.9, "content": long_content}
                for i in range(5)
            ],
            "count": 5,
        }
        tool = _make_tool(mock_client)

        output = tool.execute(query="test")

        assert len(output) <= _MAX_OUTPUT_CHARS + 200  # small margin for joining
