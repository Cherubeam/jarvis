"""
Unit tests for the make_conversation_recall_tool factory.
"""

import sys
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
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            with patch("packages.core.rag.searcher.ConversationSearcher.search", return_value=mock_results):
                from packages.core.tools.conversation_recall import make_conversation_recall_tool
                tool = make_conversation_recall_tool(tmp_path / "db", "test-model", api_key="key")

        return tool

    def _call_tool(self, tool, query, date_from=None, date_to=None, mock_results=None):
        """Call the tool's execute function with a patched searcher.search."""
        if mock_results is None:
            mock_results = []

        # The execute closure captures a ConversationSearcher; patch its search method
        execute = tool.execute
        with patch("packages.core.rag.searcher.ConversationSearcher.search", return_value=mock_results):
            # We need to patch on the actual searcher instance inside the closure
            # Easier: extract the closure's searcher and patch it directly
            import gc
            searcher = None
            for cell in execute.__closure__ or []:
                try:
                    obj = cell.cell_contents
                    if hasattr(obj, "search"):
                        searcher = obj
                        break
                except ValueError:
                    pass

            if searcher is not None:
                original_search = searcher.search
                searcher.search = MagicMock(return_value=mock_results)
                try:
                    if date_from or date_to:
                        result = execute(query=query, date_from=date_from, date_to=date_to)
                    else:
                        result = execute(query=query)
                finally:
                    searcher.search = original_search
            else:
                result = execute(query=query)

        return result

    def test_tool_definition_structure(self, tmp_path):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.conversation_recall import make_conversation_recall_tool
            tool = make_conversation_recall_tool(tmp_path / "db", "test-model")

        assert tool.name == "recall_conversations"
        assert "query" in tool.parameters["properties"]
        assert "date_from" in tool.parameters["properties"]
        assert "date_to" in tool.parameters["properties"]
        assert tool.parameters["required"] == ["query"]
        assert callable(tool.execute)

    def test_no_results_returns_friendly_message(self, tmp_path):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.conversation_recall import make_conversation_recall_tool
            tool = make_conversation_recall_tool(tmp_path / "db", "test-model")

        result = self._call_tool(tool, "anything", mock_results=[])
        assert "No relevant past conversations found." in result

    def test_single_result_formatted_correctly(self, tmp_path):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

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

        assert "2026-02-20" in output
        assert "conv_20260220_100000_abc" in output
        assert "How does ChromaDB work?" in output
        assert "ChromaDB is a vector database." in output

    def test_output_capped_at_6000_chars(self, tmp_path):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

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
