"""
Unit tests for the make_conversation_recall_tool factory.
"""

import sys
from datetime import date

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_search_result(
    conv_id="conv_20260220_100000_abc",
    session_date="2026-02-20",
    user_text="What's the plan?",
    assistant_text="Here is the plan.",
    title="",
    distance=0.1,
):
    from packages.core.rag.searcher import SearchResult

    return SearchResult(
        conv_id=conv_id,
        session_date=session_date,
        document=f"User: {user_text}\n\nAssistant: {assistant_text}",
        user_snippet=user_text[:200],
        assistant_snippet=assistant_text[:200],
        title=title,
        distance=distance,
    )


# ---------------------------------------------------------------------------
# Factory raises ImportError when chromadb absent
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMakeConversationRecallToolImportError:
    def test_raises_import_error_when_chromadb_missing(self, tmp_path):
        """make_conversation_recall_tool should raise ImportError if chromadb is missing."""
        # Temporarily hide chromadb from sys.modules
        saved = sys.modules.pop("chromadb", None)
        # Also block the import inside ConversationSearcher
        with patch.dict("sys.modules", {"chromadb": None}):
            with pytest.raises(ImportError):
                from packages.core.tools.conversation_recall import make_conversation_recall_tool

                make_conversation_recall_tool(tmp_path / "db", "test-model")

        # Restore chromadb if it was present
        if saved is not None:
            sys.modules["chromadb"] = saved


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRecallToolOutput:
    def _make_tool(self, tmp_path, mock_results):
        """Build a ToolDefinition with a mocked ConversationSearcher."""
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = len(mock_results)
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            with patch(
                "packages.core.rag.searcher.ConversationSearcher.search", return_value=mock_results
            ):
                from packages.core.tools.conversation_recall import make_conversation_recall_tool

                tool = make_conversation_recall_tool(tmp_path / "db", "test-model", api_key="key")

        return tool

    def _call_tool(self, tool, query, date_from=None, date_to=None, mock_results=None):
        """Call the tool's execute function with a patched searcher.search."""
        if mock_results is None:
            mock_results = []

        # Find the ConversationSearcher instance captured in the closure
        searcher = None
        for cell in tool.execute.__closure__ or []:
            try:
                obj = cell.cell_contents
                if hasattr(obj, "search"):
                    searcher = obj
                    break
            except ValueError:
                pass

        kwargs = {"query": query}
        if date_from:
            kwargs["date_from"] = date_from
        if date_to:
            kwargs["date_to"] = date_to

        if searcher is not None:
            with patch.object(searcher, "search", return_value=mock_results):
                return tool.execute(**kwargs)

        return tool.execute(**kwargs)

    def test_tool_definition_structure(self, tmp_path):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            tool = make_conversation_recall_tool(tmp_path / "db", "test-model")

        assert tool.name == "recall_conversations"
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"query", "date_from", "date_to", "n_results"}
        assert params["properties"]["query"]["type"] == "string"
        assert params["properties"]["date_from"]["type"] == "string"
        assert params["properties"]["date_to"]["type"] == "string"
        assert params["properties"]["n_results"]["type"] == "integer"
        assert params["properties"]["n_results"]["default"] == 10
        assert params["required"] == ["query"]
        assert callable(tool.execute)

    def test_description_contains_todays_date(self, tmp_path):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            tool = make_conversation_recall_tool(tmp_path / "db", "test-model")

        today_str = date.today().strftime("%A, %Y-%m-%d")
        assert today_str in tool.description
        assert "date_from" in tool.description
        assert "date_to" in tool.description

    def test_no_results_returns_friendly_message(self, tmp_path):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            tool = make_conversation_recall_tool(tmp_path / "db", "test-model")

        result = self._call_tool(tool, "anything", mock_results=[])
        assert result == "No relevant past conversations found."

    def test_single_result_formatted_correctly(self, tmp_path):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            tool = make_conversation_recall_tool(tmp_path / "db", "test-model")

        r = _make_search_result(
            conv_id="conv_20260220_100000_abc",
            session_date="2026-02-20",
            user_text="How does ChromaDB work?",
            assistant_text="ChromaDB is a vector database.",
        )
        output = self._call_tool(tool, "ChromaDB", mock_results=[r])

        expected = (
            "--- 2026-02-20 (conv_20260220_100000_abc) ---\n"
            "User: How does ChromaDB work?\n\n"
            "Assistant: ChromaDB is a vector database."
        )
        assert output == expected

    def test_multiple_results_joined_with_double_newline(self, tmp_path):
        """Multiple results are separated by \\n\\n."""
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            tool = make_conversation_recall_tool(tmp_path / "db", "test-model")

        results = [
            _make_search_result(
                conv_id="conv_a", session_date="2026-01-01", user_text="Q1", assistant_text="A1"
            ),
            _make_search_result(
                conv_id="conv_b", session_date="2026-01-02", user_text="Q2", assistant_text="A2"
            ),
        ]
        output = self._call_tool(tool, "test", mock_results=results)

        blocks = output.split("\n\n")
        # Each result has a header + "User: ...\n\nAssistant: ..." => multiple \n\n
        # The two results are separated by \n\n
        assert "--- 2026-01-01 (conv_a) ---" in output
        assert "--- 2026-01-02 (conv_b) ---" in output

    def test_n_results_clamping(self, tmp_path):
        """n_results is clamped to [1, 20]."""
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            tool = make_conversation_recall_tool(tmp_path / "db", "test-model")

        searcher = None
        for cell in tool.execute.__closure__ or []:
            try:
                obj = cell.cell_contents
                if hasattr(obj, "search"):
                    searcher = obj
                    break
            except ValueError:
                pass

        assert searcher is not None

        with patch.object(searcher, "search", return_value=[]) as mock_search:
            # n_results=50 should clamp to 20
            tool.execute(query="test", n_results=50)
            assert mock_search.call_args[1]["n_results"] == 20

            # n_results=-5 should clamp to 1
            tool.execute(query="test", n_results=-5)
            assert mock_search.call_args[1]["n_results"] == 1

            # n_results=0 should clamp to 1
            tool.execute(query="test", n_results=0)
            assert mock_search.call_args[1]["n_results"] == 1

    def test_output_capped_at_6000_chars(self, tmp_path):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            tool = make_conversation_recall_tool(tmp_path / "db", "test-model")

        # Create 5 results with very large documents
        results = [
            _make_search_result(
                conv_id=f"conv_2026022{i}_100000_abc",
                session_date=f"2026-02-2{i}",
                user_text="x" * 1500,
                assistant_text="y" * 1500,
            )
            for i in range(5)
        ]
        output = self._call_tool(tool, "query", mock_results=results)

        # Allow for a small overhead from truncation notices
        assert len(output) <= 6_200
