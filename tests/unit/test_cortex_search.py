"""Unit tests for the vault semantic search tool."""

from __future__ import annotations

from unittest.mock import MagicMock

from packages.core.tools.cortex_search import _MAX_OUTPUT_CHARS, make_cortex_search_tool


def _make_tool(mock_client: MagicMock):
    """Create a cortex search tool with a mocked client."""
    return make_cortex_search_tool(mock_client)


class TestCortexSearchTool:
    # --- Schema validation ---

    def test_schema(self) -> None:
        mock_client = MagicMock()
        tool = _make_tool(mock_client)
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"query", "n_results", "path_prefix"}
        assert params["properties"]["query"]["type"] == "string"
        assert params["properties"]["n_results"]["type"] == "integer"
        assert params["properties"]["n_results"]["default"] == 5
        assert params["properties"]["path_prefix"]["type"] == "string"
        assert params["required"] == ["query"]

    def test_tool_name(self) -> None:
        mock_client = MagicMock()
        tool = _make_tool(mock_client)
        assert tool.name == "search_vault_semantic"

    # --- Result formatting ---

    def test_search_formats_results(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {
                    "path": "Projects/Alpha.md",
                    "heading": "Overview",
                    "score": 0.92,
                    "content": "Alpha project details.",
                },
                {
                    "path": "Notes/Beta.md",
                    "heading": "",
                    "score": 0.85,
                    "content": "Beta notes here.",
                },
            ],
            "count": 2,
        }
        tool = _make_tool(mock_client)
        output = tool.execute(query="alpha project")

        expected = (
            "--- Projects/Alpha.md > Overview (score: 0.92) ---\n"
            "Alpha project details."
            "\n\n"
            "--- Notes/Beta.md (score: 0.85) ---\n"
            "Beta notes here."
        )
        assert output == expected

    def test_search_service_down(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = None
        tool = _make_tool(mock_client)

        output = tool.execute(query="anything")

        assert output == (
            "Cortex service is unreachable. "
            "Try search_notes (glob-based) as a fallback, or check that Cortex is running."
        )

    def test_search_empty_results(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [], "count": 0}
        tool = _make_tool(mock_client)

        output = tool.execute(query="nonexistent")

        assert output == "No results found in the vault for this query."

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

        # Test boundary: exactly 20 stays 20
        tool.execute(query="test", n_results=20)
        _, kwargs = mock_client.search.call_args
        assert kwargs["n_results"] == 20

        # Test boundary: exactly 1 stays 1
        tool.execute(query="test", n_results=1)
        _, kwargs = mock_client.search.call_args
        assert kwargs["n_results"] == 1

        # Test boundary: 0 clamps to 1
        tool.execute(query="test", n_results=0)
        _, kwargs = mock_client.search.call_args
        assert kwargs["n_results"] == 1

        # Test boundary: 21 clamps to 20
        tool.execute(query="test", n_results=21)
        _, kwargs = mock_client.search.call_args
        assert kwargs["n_results"] == 20

    def test_search_passes_path_prefix(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [], "count": 0}
        tool = _make_tool(mock_client)

        tool.execute(query="test", path_prefix="Projects/")

        mock_client.search.assert_called_once()
        _, kwargs = mock_client.search.call_args
        assert kwargs["path_prefix"] == "Projects/"

    def test_missing_result_fields_use_defaults(self) -> None:
        """Result items missing optional fields should use defaults."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [{}],  # All fields missing
            "count": 1,
        }
        tool = _make_tool(mock_client)
        output = tool.execute(query="test")

        # Defaults: path="unknown", heading="" (omitted), score=0.0, content=""
        assert "--- unknown (score: 0.00) ---" in output

    def test_results_joined_with_double_newline(self) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {"path": "A.md", "heading": "", "score": 0.9, "content": "aaa"},
                {"path": "B.md", "heading": "", "score": 0.8, "content": "bbb"},
            ],
            "count": 2,
        }
        tool = _make_tool(mock_client)
        output = tool.execute(query="test")

        # Two blocks separated by \n\n
        blocks = output.split("\n\n")
        assert len(blocks) == 2
        assert blocks[0].startswith("--- A.md")
        assert blocks[1].startswith("--- B.md")

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

    def test_truncation_marker_text(self) -> None:
        """Truncated results should end with [truncated] marker."""
        mock_client = MagicMock()
        long_content = "y" * 4000
        mock_client.search.return_value = {
            "results": [
                {"path": f"Note{i}.md", "heading": "", "score": 0.9, "content": long_content}
                for i in range(5)
            ],
            "count": 5,
        }
        tool = _make_tool(mock_client)
        output = tool.execute(query="test")

        assert "[truncated]" in output
