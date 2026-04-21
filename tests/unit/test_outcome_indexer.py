"""Tests for packages.core.rag.outcome_indexer and tools.outcome_recall."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from packages.core import frontmatter
from packages.core.rag.outcome_indexer import (
    OutcomeResult,
    _build_document,
    _load_reviewed,
)


def _write_outcome(
    tmp_path: Path,
    name: str,
    status: str = "reviewed",
    what: str = "Do X",
    why: str = "Because",
    outcome: str = "happened",
    quality: int = 4,
    success_looks_like: str = "",
    body: str = "it worked",
) -> Path:
    meta = {
        "created_at": "2026-04-18T14:32:00",
        "revisit_at": "2026-05-18",
        "status": status,
        "what": what,
        "why": why,
        "success_looks_like": success_looks_like,
        "conversation_id": "c1",
    }
    if status == "reviewed":
        meta["reviewed_at"] = "2026-05-18T19:12:00"
        meta["outcome"] = outcome
        meta["quality"] = quality
    path = tmp_path / name
    path.write_text(frontmatter.dump(meta, body), encoding="utf-8")
    return path


# --- _build_document ---


def test_build_document_includes_core_fields():
    meta = {
        "what": "Migrate auth",
        "why": "Legal compliance",
        "outcome": "happened",
        "quality": 4,
    }
    doc = _build_document(meta, "rollback-free deploy")
    assert "What: Migrate auth" in doc
    assert "Why: Legal compliance" in doc
    assert "Outcome: happened (rated 4/5)" in doc
    assert "Retrospective: rollback-free deploy" in doc


def test_build_document_omits_success_when_empty():
    meta = {"what": "X", "why": "Y", "outcome": "partial", "quality": 3}
    doc = _build_document(meta, "")
    assert "Success looks like" not in doc


def test_build_document_includes_success_when_set():
    meta = {
        "what": "X",
        "why": "Y",
        "outcome": "didnt",
        "quality": 2,
        "success_looks_like": "zero errors",
    }
    doc = _build_document(meta, "")
    assert "Success looks like: zero errors" in doc


def test_build_document_omits_empty_retrospective():
    meta = {"what": "X", "why": "Y", "outcome": "happened", "quality": 5}
    doc = _build_document(meta, "   ")
    assert "Retrospective" not in doc


# --- _load_reviewed ---


def test_load_reviewed_returns_empty_when_dir_missing(tmp_path: Path):
    assert _load_reviewed(tmp_path / "nope") == []


def test_load_reviewed_filters_pending(tmp_path: Path):
    _write_outcome(tmp_path, "pending.md", status="pending")
    _write_outcome(tmp_path, "reviewed.md", status="reviewed")
    result = _load_reviewed(tmp_path)
    assert len(result) == 1
    assert result[0][0] == "reviewed"


def test_load_reviewed_skips_malformed(tmp_path: Path):
    (tmp_path / "bad.md").write_text("---\nbroken: yaml: here\n---\nbody", encoding="utf-8")
    _write_outcome(tmp_path, "ok.md", status="reviewed")
    result = _load_reviewed(tmp_path)
    assert [r[0] for r in result] == ["ok"]


def test_load_reviewed_returns_id_meta_body(tmp_path: Path):
    _write_outcome(
        tmp_path,
        "test-outcome.md",
        status="reviewed",
        what="Ship it",
        body="worked out",
    )
    result = _load_reviewed(tmp_path)
    assert len(result) == 1
    outcome_id, meta, body = result[0]
    assert outcome_id == "test-outcome"
    assert meta["what"] == "Ship it"
    assert body == "worked out"


# --- OutcomeIndexer (mocked chromadb) ---


def _mocked_indexer(already_indexed_ids=None):
    mock_chroma = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = len(already_indexed_ids or [])
    mock_collection.get.return_value = {
        "ids": list(already_indexed_ids or []),
        "metadatas": [{"outcome_id": oid} for oid in (already_indexed_ids or [])],
    }
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
        mock_collection
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        from packages.core.rag.outcome_indexer import OutcomeIndexer

        indexer = OutcomeIndexer.__new__(OutcomeIndexer)
        indexer.db_path = Path("/tmp/fake-rag")
        indexer.embedding_model = "openrouter/openai/text-embedding-3-small"
        indexer.api_key = None
        indexer.api_base = None
        indexer._client = mock_chroma.PersistentClient.return_value
        indexer._collection = mock_collection
    return indexer, mock_collection


def test_index_new_embeds_reviewed_outcomes(tmp_path: Path):
    _write_outcome(tmp_path, "a.md", status="reviewed", what="Migrate A")
    _write_outcome(tmp_path, "b.md", status="pending", what="Plan B")

    indexer, mock_collection = _mocked_indexer(already_indexed_ids=set())

    fake_embedding_response = MagicMock()
    fake_embedding_response.data = [{"embedding": [0.1, 0.2, 0.3]}]
    with patch("litellm.embedding", return_value=fake_embedding_response) as mock_embed:
        count = indexer.index_new(tmp_path)

    assert count == 1
    mock_embed.assert_called_once()
    mock_collection.upsert.assert_called_once()
    call_kwargs = mock_collection.upsert.call_args.kwargs
    assert call_kwargs["ids"] == ["a"]
    assert "Migrate A" in call_kwargs["documents"][0]
    assert call_kwargs["metadatas"][0]["outcome_id"] == "a"


def test_index_new_skips_already_indexed(tmp_path: Path):
    _write_outcome(tmp_path, "a.md", status="reviewed")
    _write_outcome(tmp_path, "b.md", status="reviewed")

    indexer, mock_collection = _mocked_indexer(already_indexed_ids={"a"})

    fake_response = MagicMock()
    fake_response.data = [{"embedding": [0.1]}]
    with patch("litellm.embedding", return_value=fake_response):
        count = indexer.index_new(tmp_path)

    assert count == 1
    call_kwargs = mock_collection.upsert.call_args.kwargs
    assert call_kwargs["ids"] == ["b"]


def test_index_new_deletes_stale_entries(tmp_path: Path):
    _write_outcome(tmp_path, "a.md", status="reviewed")
    # 'gone' was previously indexed but its file no longer exists
    indexer, mock_collection = _mocked_indexer(already_indexed_ids={"a", "gone"})

    fake_response = MagicMock()
    fake_response.data = [{"embedding": [0.1]}]
    with patch("litellm.embedding", return_value=fake_response):
        indexer.index_new(tmp_path)

    mock_collection.delete.assert_called_once_with(ids=["gone"])


def test_index_new_returns_zero_when_nothing_to_index(tmp_path: Path):
    indexer, mock_collection = _mocked_indexer(already_indexed_ids=set())

    with patch("litellm.embedding") as mock_embed:
        count = indexer.index_new(tmp_path)

    assert count == 0
    mock_embed.assert_not_called()
    mock_collection.upsert.assert_not_called()


def test_index_new_writes_quality_as_int(tmp_path: Path):
    _write_outcome(tmp_path, "a.md", status="reviewed", quality=3)
    indexer, mock_collection = _mocked_indexer(already_indexed_ids=set())

    fake_response = MagicMock()
    fake_response.data = [{"embedding": [0.1]}]
    with patch("litellm.embedding", return_value=fake_response):
        indexer.index_new(tmp_path)

    meta = mock_collection.upsert.call_args.kwargs["metadatas"][0]
    assert meta["quality"] == 3
    assert isinstance(meta["quality"], int)


# --- OutcomeSearcher ---


def test_searcher_returns_empty_when_collection_empty():
    mock_chroma = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
        mock_collection
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        from packages.core.rag.outcome_indexer import OutcomeSearcher

        searcher = OutcomeSearcher("/tmp", "model")
        results = searcher.search("anything")

    assert results == []


def test_searcher_builds_results_from_raw():
    mock_chroma = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 1
    mock_collection.query.return_value = {
        "metadatas": [
            [
                {
                    "outcome_id": "o1",
                    "what": "Do X",
                    "why": "Because",
                    "outcome": "happened",
                    "quality": 4,
                    "retrospective": "worked out",
                    "revisit_at": "2026-05-18",
                    "conversation_id": "c1",
                },
            ]
        ],
        "distances": [[0.25]],
    }
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
        mock_collection
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        from packages.core.rag.outcome_indexer import OutcomeSearcher

        searcher = OutcomeSearcher("/tmp", "model")
        fake_response = MagicMock()
        fake_response.data = [{"embedding": [0.1]}]
        with patch("litellm.embedding", return_value=fake_response):
            results = searcher.search("X")

    assert len(results) == 1
    assert results[0] == OutcomeResult(
        outcome_id="o1",
        what="Do X",
        why="Because",
        outcome="happened",
        quality=4,
        retrospective="worked out",
        revisit_at="2026-05-18",
        conversation_id="c1",
        distance=0.25,
    )


# --- make_outcome_recall_tool ---


def test_recall_tool_schema():
    mock_chroma = MagicMock()
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value.count.return_value = 0

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        from packages.core.tools.outcome_recall import make_outcome_recall_tool

        tool = make_outcome_recall_tool("/tmp", "model")

    assert tool.name == "recall_outcomes"
    assert set(tool.parameters["required"]) == {"query"}
    assert set(tool.parameters["properties"].keys()) == {"query", "n_results"}


def test_recall_tool_returns_message_when_no_results():
    mock_chroma = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
        mock_collection
    )

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        from packages.core.tools.outcome_recall import make_outcome_recall_tool

        tool = make_outcome_recall_tool("/tmp", "model")
        result = tool.execute(query="anything")

    assert result == "No relevant past outcomes found."


def test_recall_tool_formats_results_with_header_and_fields():
    mock_chroma = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 1
    mock_collection.query.return_value = {
        "metadatas": [
            [
                {
                    "outcome_id": "2026-04-18-migrate",
                    "what": "Migrate auth",
                    "why": "Compliance",
                    "outcome": "happened",
                    "quality": 4,
                    "retrospective": "smooth",
                    "revisit_at": "2026-05-18",
                    "conversation_id": "c1",
                },
            ]
        ],
        "distances": [[0.3]],
    }
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
        mock_collection
    )

    fake_response = MagicMock()
    fake_response.data = [{"embedding": [0.1]}]

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        from packages.core.tools.outcome_recall import make_outcome_recall_tool

        tool = make_outcome_recall_tool("/tmp", "model")
        with patch("litellm.embedding", return_value=fake_response):
            result = tool.execute(query="auth migration")

    assert "--- 2026-04-18-migrate (outcome: happened, rated 4/5) ---" in result
    assert "What: Migrate auth" in result
    assert "Why: Compliance" in result
    assert "Retrospective: smooth" in result


def test_recall_tool_clamps_n_results():
    mock_chroma = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 1
    mock_collection.query.return_value = {"metadatas": [[]], "distances": [[]]}
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
        mock_collection
    )

    fake_response = MagicMock()
    fake_response.data = [{"embedding": [0.1]}]

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        from packages.core.tools.outcome_recall import make_outcome_recall_tool

        tool = make_outcome_recall_tool("/tmp", "model")
        with patch("litellm.embedding", return_value=fake_response):
            tool.execute(query="x", n_results=999)

    assert mock_collection.query.call_args.kwargs["n_results"] == 10
