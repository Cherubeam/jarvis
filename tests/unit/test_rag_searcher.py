"""
Unit tests for ConversationSearcher.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from packages.core.rag.searcher import _MAX_EMBED_CHARS, _date_str_to_int, _invert_date


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
        assert result == {"session_date_int": {"$gte": 20260201}}

    def test_date_to_only(self, tmp_path):
        s = self._searcher(tmp_path)
        result = s._build_where_filter(None, "2026-02-28")
        assert result == {"session_date_int": {"$lte": 20260228}}

    def test_both_dates_produces_and_filter(self, tmp_path):
        s = self._searcher(tmp_path)
        result = s._build_where_filter("2026-02-01", "2026-02-28")
        assert result == {
            "$and": [
                {"session_date_int": {"$gte": 20260201}},
                {"session_date_int": {"$lte": 20260228}},
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

    def test_long_query_truncated_before_embedding(self, tmp_path):
        """Queries exceeding _MAX_EMBED_CHARS must be truncated before the
        embedding call, otherwise the provider returns a token-limit error."""
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=1)
        mock_collection.query.return_value = _fake_chroma_result(1)

        long_query = "q" * (_MAX_EMBED_CHARS + 5000)
        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2, 0.3]}])
            searcher.search(long_query)

        call_kwargs = mock_embed.call_args
        texts_sent = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")
        assert all(len(t) <= _MAX_EMBED_CHARS for t in texts_sent)

    def test_recency_tiebreaker_prefers_newer_at_same_distance(self, tmp_path):
        """When two results have the same bucketed distance, the newer one should come first."""
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=3)

        # Three results with distances that round to the same bucket (0.05)
        chroma_result = {
            "documents": [["doc old", "doc mid", "doc new"]],
            "metadatas": [[
                {"conv_id": "c_old", "session_date": "2026-01-10", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "c_mid", "session_date": "2026-02-15", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "c_new", "session_date": "2026-02-27", "user_snippet": "", "assistant_snippet": "", "title": ""},
            ]],
            "distances": [[0.051, 0.054, 0.052]],  # all round to 0.05
        }
        mock_collection.query.return_value = chroma_result

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
            results = searcher.search("test query")

        assert len(results) == 3
        # Newest first within same distance bucket
        assert results[0].conv_id == "c_new"
        assert results[1].conv_id == "c_mid"
        assert results[2].conv_id == "c_old"

    def test_dedup_keeps_best_per_conv_id(self, tmp_path):
        """With deduplicate=True (default), only the best result per conv_id is kept."""
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=6)

        # Two conversations, each with 3 chunks at varying distances
        chroma_result = {
            "documents": [["doc_a1", "doc_a2", "doc_a3", "doc_b1", "doc_b2", "doc_b3"]],
            "metadatas": [[
                {"conv_id": "conv_a", "session_date": "2026-02-20", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "conv_a", "session_date": "2026-02-20", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "conv_a", "session_date": "2026-02-20", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "conv_b", "session_date": "2026-02-25", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "conv_b", "session_date": "2026-02-25", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "conv_b", "session_date": "2026-02-25", "user_snippet": "", "assistant_snippet": "", "title": ""},
            ]],
            "distances": [[0.01, 0.05, 0.10, 0.02, 0.06, 0.11]],
        }
        mock_collection.query.return_value = chroma_result

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
            results = searcher.search("test query", n_results=5)

        # Should have exactly 2 results (one per conv_id)
        assert len(results) == 2
        conv_ids = [r.conv_id for r in results]
        assert "conv_a" in conv_ids
        assert "conv_b" in conv_ids
        # Best from conv_a (dist 0.01) should come first
        assert results[0].conv_id == "conv_a"
        assert results[0].document == "doc_a1"

    def test_dedup_disabled_returns_all(self, tmp_path):
        """With deduplicate=False, multiple results from the same conv are kept."""
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=4)

        chroma_result = {
            "documents": [["doc1", "doc2", "doc3", "doc4"]],
            "metadatas": [[
                {"conv_id": "conv_a", "session_date": "2026-02-20", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "conv_a", "session_date": "2026-02-20", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "conv_b", "session_date": "2026-02-25", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "conv_b", "session_date": "2026-02-25", "user_snippet": "", "assistant_snippet": "", "title": ""},
            ]],
            "distances": [[0.01, 0.02, 0.03, 0.04]],
        }
        mock_collection.query.return_value = chroma_result

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
            results = searcher.search("test query", n_results=4, deduplicate=False)

        assert len(results) == 4

    def test_over_fetch_multiplier_when_deduplicating(self, tmp_path):
        """When deduplicate=True, ChromaDB should be asked for n_results*3."""
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=100)
        mock_collection.query.return_value = _fake_chroma_result(2)

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
            searcher.search("query", n_results=5, deduplicate=True)

        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["n_results"] == 15  # 5 * 3

    def test_no_over_fetch_when_dedup_disabled(self, tmp_path):
        """When deduplicate=False, ChromaDB should be asked for exactly n_results."""
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=100)
        mock_collection.query.return_value = _fake_chroma_result(2)

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
            searcher.search("query", n_results=5, deduplicate=False)

        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["n_results"] == 5

    def test_distance_still_dominates_over_recency(self, tmp_path):
        """A clearly closer result should rank first even if it's older."""
        searcher, mock_collection = _make_searcher(tmp_path, collection_count=2)

        chroma_result = {
            "documents": [["doc close old", "doc far new"]],
            "metadatas": [[
                {"conv_id": "c_close", "session_date": "2026-01-01", "user_snippet": "", "assistant_snippet": "", "title": ""},
                {"conv_id": "c_far", "session_date": "2026-02-27", "user_snippet": "", "assistant_snippet": "", "title": ""},
            ]],
            "distances": [[0.02, 0.15]],  # different buckets
        }
        mock_collection.query.return_value = chroma_result

        with patch("packages.core.rag.searcher.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
            results = searcher.search("test query")

        assert results[0].conv_id == "c_close"
        assert results[1].conv_id == "c_far"


# ---------------------------------------------------------------------------
# _invert_date helper
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDateStrToInt:
    def test_converts_iso_date(self):
        assert _date_str_to_int("2026-02-27") == 20260227

    def test_empty_string_returns_zero(self):
        assert _date_str_to_int("") == 0

    def test_none_returns_zero(self):
        assert _date_str_to_int(None) == 0


@pytest.mark.unit
class TestInvertDate:
    def test_inverts_digits(self):
        assert _invert_date("2026-02-27") == "7973-97-72"

    def test_preserves_sort_order(self):
        dates = ["2026-01-10", "2026-02-15", "2026-02-27"]
        inverted = [_invert_date(d) for d in dates]
        # Ascending inverted should give descending original dates
        assert sorted(inverted) == [_invert_date("2026-02-27"), _invert_date("2026-02-15"), _invert_date("2026-01-10")]
