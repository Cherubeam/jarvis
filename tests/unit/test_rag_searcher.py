"""
Unit tests for ConversationSearcher.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_searcher(tmp_path: Path, collection_count: int = 3):
    """Return a ConversationSearcher backed by a fully mocked ChromaDB."""
    mock_chroma_module = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = collection_count
    mock_chroma_module.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

    with patch.dict("sys.modules", {"chromadb": mock_chroma_module}):
        from packages.core.rag.searcher import ConversationSearcher
        searcher = ConversationSearcher.__new__(ConversationSearcher)
        searcher.db_path = tmp_path / "chroma"
        searcher.embedding_model = "test-model"
        searcher.api_key = None
        searcher.api_base = None
        searcher._client = mock_chroma_module.PersistentClient.return_value
        searcher._collection = mock_collection

    return searcher, mock_collection


def _fake_chroma_result(n: int = 2) -> dict:
    """Build a minimal ChromaDB query result dict."""
    docs = [f"User: Q{i}\n\nAssistant: A{i}" for i in range(n)]
    metas = [
        {
            "conv_id": f"conv_2026022{i}_100000_abc",
            "session_date": f"2026-02-2{i}",
            "user_snippet": f"Q{i}",
            "assistant_snippet": f"A{i}",
            "title": f"Session {i}",
        }
        for i in range(n)
    ]
    distances = [0.05 * i for i in range(n)]
    return {
        "documents": [docs],
        "metadatas": [metas],
        "distances": [distances],
    }


# ---------------------------------------------------------------------------
# _build_where_filter
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBuildWhereFilter:
    def _searcher(self, tmp_path):
        s, _ = _make_searcher(tmp_path)
        return s

    def test_no_dates_returns_none(self, tmp_path):
        s = self._searcher(tmp_path)
        assert s._build_where_filter(None, None) is None

    def test_date_from_only(self, tmp_path):
        s = self._searcher(tmp_path)
        result = s._build_where_filter("2026-02-01", None)
        assert result == {"session_date": {"$gte": "2026-02-01"}}

    def test_date_to_only(self, tmp_path):
        s = self._searcher(tmp_path)
        result = s._build_where_filter(None, "2026-02-28")
        assert result == {"session_date": {"$lte": "2026-02-28"}}

    def test_both_dates_produces_and_filter(self, tmp_path):
        s = self._searcher(tmp_path)
        result = s._build_where_filter("2026-02-01", "2026-02-28")
        assert result == {
            "$and": [
                {"session_date": {"$gte": "2026-02-01"}},
                {"session_date": {"$lte": "2026-02-28"}},
            ]
        }


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSearch:
    def test_returns_empty_list_when_collection_empty(self, tmp_path):
        searcher, _ = _make_searcher(tmp_path, collection_count=0)

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            results = searcher.search("anything")

        assert results == []
        mock_embed.assert_not_called()

    def test_returns_search_results_with_correct_fields(self, tmp_path):
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=2)
        mock_collection.query.return_value = _fake_chroma_result(2)

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2, 0.3]}])
            results = searcher.search("some query")

        assert len(results) == 2
        r = results[0]
        assert r.conv_id == "conv_20260220_100000_abc"
        assert r.session_date == "2026-02-20"
        assert r.user_snippet == "Q0"
        assert r.assistant_snippet == "A0"
        assert r.title == "Session 0"
        assert isinstance(r.distance, float)

    def test_passes_where_filter_when_dates_provided(self, tmp_path):
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=2)
        mock_collection.query.return_value = _fake_chroma_result(1)

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2]}])
            searcher.search("query", date_from="2026-02-01", date_to="2026-02-28")

        call_kwargs = mock_collection.query.call_args[1]
        assert "where" in call_kwargs
        assert "$and" in call_kwargs["where"]

    def test_no_where_filter_when_no_dates(self, tmp_path):
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=2)
        mock_collection.query.return_value = _fake_chroma_result(1)

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2]}])
            searcher.search("query")

        call_kwargs = mock_collection.query.call_args[1]
        assert "where" not in call_kwargs

    def test_n_results_capped_at_collection_size(self, tmp_path):
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=2)
        mock_collection.query.return_value = _fake_chroma_result(2)

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2]}])
            searcher.search("query", n_results=10)

        call_kwargs = mock_collection.query.call_args[1]
        # n_results should be min(10, 2) = 2
        assert call_kwargs["n_results"] == 2
