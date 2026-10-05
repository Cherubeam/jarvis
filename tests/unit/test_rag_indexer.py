"""
Unit tests for ConversationIndexer.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from packages.core.rag.embed_limits import MAX_EMBED_TOKENS, count_tokens
from packages.core.rag.indexer import (
    _date_str_to_int,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_v1_conversation(conv_id: str, messages: list[dict], session_start: str = "2026-02-20T10:00:00") -> dict:
    """Return a minimal schema-v1.0.0 conversation dict."""
    return {
        "schema_version": "1.0.0",
        "id": conv_id,
        "title": "Test conversation",
        "session_start": session_start,
        "session_end": session_start,
        "messages": messages,
        "tags": [],
        "metadata": {},
    }


def _make_messages(pairs: list[tuple[str, str]]) -> list[dict]:
    """Build a flat message list from (user, assistant) pairs."""
    msgs = []
    for i, (user_text, asst_text) in enumerate(pairs, start=1):
        msgs.append(
            {
                "id": f"msg_{i * 2 - 1:03d}",
                "role": "user",
                "content": [{"type": "text", "text": user_text}],
                "timestamp": "2026-02-20T10:00:00",
                "metadata": {},
            }
        )
        msgs.append(
            {
                "id": f"msg_{i * 2:03d}",
                "role": "assistant",
                "content": [{"type": "text", "text": asst_text}],
                "timestamp": "2026-02-20T10:00:01",
                "metadata": {},
            }
        )
    return msgs


# ---------------------------------------------------------------------------
# _extract_pairs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractPairs:
    def _make_indexer(self):
        """Create a ConversationIndexer with a fully mocked ChromaDB."""
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.rag.indexer import ConversationIndexer

            indexer = ConversationIndexer.__new__(ConversationIndexer)
            indexer.db_path = Path("/tmp/fake_rag")
            indexer.embedding_model = "openrouter/openai/text-embedding-3-small"
            indexer.api_key = None
            indexer.api_base = None
            indexer._client = mock_chroma.PersistentClient.return_value
            indexer._collection = mock_collection
            return indexer

    def test_single_user_assistant_pair(self):
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([("Hello", "Hi there!")]),
        )
        pairs = indexer._extract_pairs(conv)

        assert len(pairs) == 1
        assert pairs[0]["id"] == "conv_20260220_100000_abc123_pair_0"
        assert pairs[0]["document"] == "User: Hello\n\nAssistant: Hi there!"
        # Verify all expected metadata keys are present
        expected_keys = {
            "conv_id",
            "session_date",
            "session_date_int",
            "pair_index",
            "user_snippet",
            "assistant_snippet",
            "title",
            "doc_hash",
        }
        assert set(pairs[0]["metadata"].keys()) == expected_keys

    def test_multiple_pairs_in_order(self):
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages(
                [
                    ("First question", "First answer"),
                    ("Second question", "Second answer"),
                    ("Third question", "Third answer"),
                ]
            ),
        )
        pairs = indexer._extract_pairs(conv)

        assert len(pairs) == 3
        assert pairs[0]["metadata"]["pair_index"] == 0
        assert pairs[1]["metadata"]["pair_index"] == 1
        assert pairs[2]["metadata"]["pair_index"] == 2

    def test_session_date_extracted_from_session_start(self):
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([("Q", "A")]),
            session_start="2026-02-20T10:00:00",
        )
        pairs = indexer._extract_pairs(conv)

        assert pairs[0]["metadata"]["session_date"] == "2026-02-20"
        assert pairs[0]["metadata"]["session_date_int"] == 20260220

    def test_session_date_falls_back_to_conv_id(self):
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260315_120000_xyz789",
            _make_messages([("Q", "A")]),
        )
        # Remove session_start so fallback is used
        conv.pop("session_start", None)
        pairs = indexer._extract_pairs(conv)

        assert pairs[0]["metadata"]["session_date"] == "2026-03-15"
        assert pairs[0]["metadata"]["session_date_int"] == 20260315

    def test_snippets_capped_at_200_chars(self):
        indexer = self._make_indexer()
        long_text = "x" * 300
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([(long_text, long_text)]),
        )
        pairs = indexer._extract_pairs(conv)

        assert len(pairs[0]["metadata"]["user_snippet"]) == 200
        assert len(pairs[0]["metadata"]["assistant_snippet"]) == 200

    def test_user_message_without_following_assistant_still_indexed(self):
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            [
                {
                    "id": "msg_001",
                    "role": "user",
                    "content": [{"type": "text", "text": "Lone user message"}],
                    "timestamp": "2026-02-20T10:00:00",
                    "metadata": {},
                }
            ],
        )
        pairs = indexer._extract_pairs(conv)

        assert len(pairs) == 1
        assert pairs[0]["document"] == "User: Lone user message\n\nAssistant: "

    def test_empty_user_message_skipped(self):
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            [
                {
                    "id": "msg_001",
                    "role": "user",
                    "content": [{"type": "text", "text": "   "}],
                    "timestamp": "2026-02-20T10:00:00",
                    "metadata": {},
                }
            ],
        )
        pairs = indexer._extract_pairs(conv)
        assert pairs == []

    def test_conv_id_override_used_when_provided(self):
        """When conv_id is passed explicitly (e.g. from filepath.stem fallback),
        it must be used for pair IDs instead of the conversation dict's id."""
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "",  # empty id in the conversation dict
            _make_messages([("Q", "A")]),
        )
        # Simulate the fallback conv_id that index_new derives from the filename
        pairs = indexer._extract_pairs(conv, conv_id="2026-01-07_11-15-16")
        assert pairs[0]["id"] == "2026-01-07_11-15-16_pair_0"
        assert pairs[0]["metadata"]["conv_id"] == "2026-01-07_11-15-16"

    def test_title_stored_in_metadata(self):
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([("Q", "A")]),
        )
        conv["title"] = "My Test Session"
        pairs = indexer._extract_pairs(conv)

        assert pairs[0]["metadata"]["title"] == "My Test Session"

    def test_long_pair_produces_multiple_chunks(self):
        """A message pair whose document exceeds MAX_EMBED_TOKENS must be
        split into multiple entries with _chunk_N suffixed IDs."""
        indexer = self._make_indexer()
        long_text = '{"a":1,' * 3000  # dense text: ~12,000 tokens in 21,000 chars
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([(long_text, "Short answer")]),
        )
        pairs = indexer._extract_pairs(conv)

        assert len(pairs) > 1
        expected_keys = {
            "conv_id",
            "session_date",
            "session_date_int",
            "pair_index",
            "user_snippet",
            "assistant_snippet",
            "title",
            "doc_hash",
            "chunk_index",
            "total_chunks",
        }
        for i, pair in enumerate(pairs):
            assert pair["id"] == f"conv_20260220_100000_abc123_pair_0_chunk_{i}"
            assert pair["metadata"]["chunk_index"] == i
            assert pair["metadata"]["total_chunks"] == len(pairs)
            assert count_tokens(pair["document"]) <= MAX_EMBED_TOKENS
            assert set(pair["metadata"].keys()) == expected_keys

    def test_short_pair_keeps_original_id_format(self):
        """Short documents must NOT get a _chunk_0 suffix."""
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([("Hello", "Hi!")]),
        )
        pairs = indexer._extract_pairs(conv)

        assert len(pairs) == 1
        assert pairs[0]["id"] == "conv_20260220_100000_abc123_pair_0"
        assert "chunk_index" not in pairs[0]["metadata"]


# ---------------------------------------------------------------------------
# index_new
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIndexNew:
    def _setup(self, tmp_path, already_indexed_ids=None, existing_metas=None):
        """Return (indexer, mock_collection) with mocked chromadb.

        ``already_indexed_ids`` indexes pair 0 of each conversation without a hash (as before
        hashes existed); ``existing_metas`` gives the full metadata list instead.
        """
        mock_chroma_module = MagicMock()
        mock_collection = MagicMock()

        # Simulate _get_indexed_pairs and _migrate_date_metadata returning the pre-existing records
        if existing_metas is None:
            existing_metas = [
                {"conv_id": cid, "session_date": "2026-01-01", "session_date_int": 20260101, "pair_index": 0}
                for cid in (already_indexed_ids or [])
            ]
        existing_ids = [f"id_{i}" for i in range(len(existing_metas))]
        mock_collection.count.return_value = len(existing_metas)
        mock_collection.get.return_value = {"ids": existing_ids, "metadatas": existing_metas}
        mock_chroma_module.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma_module}):
            from packages.core.rag.indexer import ConversationIndexer

            indexer = ConversationIndexer.__new__(ConversationIndexer)
            indexer.db_path = tmp_path / "chroma"
            indexer.embedding_model = "test-model"
            indexer.api_key = None
            indexer.api_base = None
            indexer._client = mock_chroma_module.PersistentClient.return_value
            indexer._collection = mock_collection

        return indexer, mock_collection

    def _write_conv(self, tmp_path: Path, filename: str, conv: dict):
        f = tmp_path / filename
        f.write_text(json.dumps(conv))
        return f

    def test_indexes_new_conversation(self, tmp_path):
        indexer, mock_collection = self._setup(tmp_path)

        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([("Hello", "Hi!")]),
        )
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", conv)

        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2, 0.3]}])
            n_new = indexer.index_new(tmp_path)

        assert n_new == 1
        mock_collection.upsert.assert_called_once()

    def test_long_documents_chunked_before_embedding(self, tmp_path):
        """Documents exceeding MAX_EMBED_TOKENS must be chunked (not truncated)
        before the embedding call, with every chunk within the limit."""
        indexer, mock_collection = self._setup(tmp_path)

        long_text = '{"a":1,' * 3000  # dense text: ~12,000 tokens in 21,000 chars
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([(long_text, "Short answer")]),
        )
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", conv)

        def _fake_embed(**kwargs):
            n = len(kwargs["input"])
            return MagicMock(data=[{"embedding": [0.1, 0.2, 0.3]} for _ in range(n)])

        with patch("packages.core.rag.indexer.litellm.embedding", side_effect=_fake_embed) as mock_embed:
            n_new = indexer.index_new(tmp_path)

        assert n_new == 1
        # Verify multiple chunks were sent and all are within the limit
        call_kwargs = mock_embed.call_args
        texts_sent = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")
        assert len(texts_sent) > 1, "Long document should produce multiple chunks"
        assert all(count_tokens(t) <= MAX_EMBED_TOKENS for t in texts_sent)

    def test_no_duplicate_ids_when_conversations_lack_id_field(self, tmp_path):
        """Conversations without an 'id' field should use filepath.stem as
        the conv_id fallback, producing unique pair IDs across files."""
        indexer, mock_collection = self._setup(tmp_path)

        # Two conversations with empty id — simulates legacy files
        for name, q, a in [
            ("2026-01-07_11-15-16.json", "Hello", "Hi"),
            ("2026-01-07_13-44-39.json", "Bye", "See ya"),
        ]:
            conv = _make_v1_conversation("", _make_messages([(q, a)]))
            conv.pop("id")  # completely absent
            self._write_conv(tmp_path, name, conv)

        def _fake_embed(**kwargs):
            n = len(kwargs["input"])
            return MagicMock(data=[{"embedding": [0.1, 0.2, 0.3]} for _ in range(n)])

        with patch("packages.core.rag.indexer.litellm.embedding", side_effect=_fake_embed):
            n_new = indexer.index_new(tmp_path)

        assert n_new == 2
        # Collect all IDs that were upserted
        all_ids = []
        for c in mock_collection.upsert.call_args_list:
            all_ids.extend(c.kwargs.get("ids") or c[1].get("ids", []))
        assert len(all_ids) == len(set(all_ids)), f"Duplicate IDs found: {all_ids}"

    def test_skips_already_indexed_conversation(self, tmp_path):
        indexer, mock_collection = self._setup(
            tmp_path,
            already_indexed_ids=["conv_20260220_100000_abc123"],
        )

        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([("Hello", "Hi!")]),
        )
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", conv)

        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            n_new = indexer.index_new(tmp_path)

        assert n_new == 0
        mock_embed.assert_not_called()
        mock_collection.upsert.assert_not_called()

    def _indexed_meta(self, indexer, conv: dict, pair_index: int) -> dict:
        """Metadata of a pair exactly as index_new would have stored it."""
        pair = indexer._extract_pairs(conv)[pair_index]
        return {**pair["metadata"]}

    def test_appended_pair_embedded_alone(self, tmp_path):
        conv_id = "conv_20260220_100000_abc123"
        old = _make_v1_conversation(conv_id, _make_messages([("Q1", "A1")]))
        probe, _ = self._setup(tmp_path)
        meta = self._indexed_meta(probe, old, 0)
        indexer, mock_collection = self._setup(tmp_path, existing_metas=[meta])

        grown = _make_v1_conversation(conv_id, _make_messages([("Q1", "A1"), ("Q2", "A2")]))
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", grown)

        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
            n = indexer.index_new(tmp_path)

        assert n == 1
        assert mock_embed.call_args.kwargs["input"] == ["User: Q2\n\nAssistant: A2"]
        assert mock_collection.upsert.call_args.kwargs["ids"] == [f"{conv_id}_pair_1"]
        mock_collection.delete.assert_not_called()

    def test_changed_pair_reembedded_and_old_chunks_deleted(self, tmp_path):
        conv_id = "conv_20260220_100000_abc123"
        old = _make_v1_conversation(conv_id, _make_messages([("Q1", "A1 partial")]))
        probe, _ = self._setup(tmp_path)
        meta = self._indexed_meta(probe, old, 0)
        indexer, mock_collection = self._setup(tmp_path, existing_metas=[meta])

        finished = _make_v1_conversation(conv_id, _make_messages([("Q1", "A1 partial, then done")]))
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", finished)

        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
            n = indexer.index_new(tmp_path)

        assert n == 1
        mock_collection.delete.assert_called_once_with(ids=["id_0"])
        upserted_meta = mock_collection.upsert.call_args.kwargs["metadatas"][0]
        assert upserted_meta["doc_hash"] != meta["doc_hash"]
        assert len(upserted_meta["doc_hash"]) == 16

    def test_unchanged_hashed_pair_skipped(self, tmp_path):
        conv_id = "conv_20260220_100000_abc123"
        conv = _make_v1_conversation(conv_id, _make_messages([("Q1", "A1")]))
        probe, _ = self._setup(tmp_path)
        indexer, mock_collection = self._setup(tmp_path, existing_metas=[self._indexed_meta(probe, conv, 0)])
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", conv)

        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            assert indexer.index_new(tmp_path) == 0

        mock_embed.assert_not_called()
        mock_collection.delete.assert_not_called()

    def test_pair_indexed_without_hash_is_trusted(self, tmp_path):
        """Pairs indexed before doc_hash existed are not re-embedded even if the text differs."""
        conv_id = "conv_20260220_100000_abc123"
        indexer, mock_collection = self._setup(tmp_path, already_indexed_ids=[conv_id])
        conv = _make_v1_conversation(conv_id, _make_messages([("Q1", "changed answer")]))
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", conv)

        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            assert indexer.index_new(tmp_path) == 0

        mock_embed.assert_not_called()

    def test_multi_chunk_pair_deletes_every_old_chunk(self, tmp_path):
        conv_id = "conv_20260220_100000_abc123"
        metas = [
            {"conv_id": conv_id, "pair_index": 0, "doc_hash": "old", "chunk_index": 0, "session_date_int": 1},
            {"conv_id": conv_id, "pair_index": 0, "doc_hash": "old", "chunk_index": 1, "session_date_int": 1},
            {"conv_id": "other", "pair_index": 0, "doc_hash": "x", "session_date_int": 1},
        ]
        indexer, mock_collection = self._setup(tmp_path, existing_metas=metas)
        conv = _make_v1_conversation(conv_id, _make_messages([("Q1", "A1")]))
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", conv)

        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
            assert indexer.index_new(tmp_path) == 1

        mock_collection.delete.assert_called_once_with(ids=["id_0", "id_1"])

    def test_returns_zero_for_empty_directory(self, tmp_path):
        indexer, mock_collection = self._setup(tmp_path)
        n_new = indexer.index_new(tmp_path / "nonexistent")
        assert n_new == 0

    def test_skips_conversation_with_no_messages(self, tmp_path):
        indexer, mock_collection = self._setup(tmp_path)

        conv = _make_v1_conversation("conv_20260220_100000_abc123", [])
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", conv)

        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            n_new = indexer.index_new(tmp_path)

        assert n_new == 0
        mock_embed.assert_not_called()

    def test_migrate_adds_session_date_int_to_existing_records(self, tmp_path):
        """_migrate_date_metadata should add session_date_int to records that lack it."""
        mock_chroma_module = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        # Simulate existing records WITHOUT session_date_int
        mock_collection.get.return_value = {
            "ids": ["id_0", "id_1"],
            "metadatas": [
                {"conv_id": "conv_a", "session_date": "2026-02-20"},
                {"conv_id": "conv_b", "session_date": "2026-01-15"},
            ],
        }
        mock_chroma_module.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma_module}):
            from packages.core.rag.indexer import ConversationIndexer

            indexer = ConversationIndexer.__new__(ConversationIndexer)
            indexer._collection = mock_collection

        indexer._migrate_date_metadata()

        mock_collection.update.assert_called_once()
        call_kwargs = mock_collection.update.call_args[1]
        assert call_kwargs["ids"] == ["id_0", "id_1"]
        assert call_kwargs["metadatas"][0]["session_date_int"] == 20260220
        assert call_kwargs["metadatas"][1]["session_date_int"] == 20260115

    def test_migrate_skips_records_that_already_have_date_int(self, tmp_path):
        """_migrate_date_metadata should not update records that already have session_date_int."""
        mock_chroma_module = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_collection.get.return_value = {
            "ids": ["id_0"],
            "metadatas": [
                {"conv_id": "conv_a", "session_date": "2026-02-20", "session_date_int": 20260220},
            ],
        }
        mock_chroma_module.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma_module}):
            from packages.core.rag.indexer import ConversationIndexer

            indexer = ConversationIndexer.__new__(ConversationIndexer)
            indexer._collection = mock_collection

        indexer._migrate_date_metadata()

        mock_collection.update.assert_not_called()

    def test_indexes_only_new_among_multiple(self, tmp_path):
        indexer, mock_collection = self._setup(
            tmp_path,
            already_indexed_ids=["conv_20260219_090000_old111"],
        )

        old_conv = _make_v1_conversation(
            "conv_20260219_090000_old111",
            _make_messages([("Old Q", "Old A")]),
        )
        new_conv = _make_v1_conversation(
            "conv_20260220_100000_new222",
            _make_messages([("New Q", "New A")]),
        )
        self._write_conv(tmp_path, "2026-02-19_09-00-00.json", old_conv)
        self._write_conv(tmp_path, "2026-02-20_10-00-00.json", new_conv)

        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2, 0.3]}])
            n_new = indexer.index_new(tmp_path)

        assert n_new == 1


# ---------------------------------------------------------------------------
# _date_str_to_int boundary conditions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDateStrToInt:
    def test_valid_date(self):
        assert _date_str_to_int("2026-02-20") == 20260220

    def test_invalid_date_returns_zero(self):
        assert _date_str_to_int("not-a-date") == 0

    def test_empty_string_returns_zero(self):
        assert _date_str_to_int("") == 0

    def test_none_returns_zero(self):
        assert _date_str_to_int(None) == 0


# ---------------------------------------------------------------------------
# delete_conversation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteConversation:
    def _make_indexer(self):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.rag.indexer import ConversationIndexer

            indexer = ConversationIndexer.__new__(ConversationIndexer)
            indexer.db_path = Path("/tmp/fake_rag")
            indexer.embedding_model = "openrouter/openai/text-embedding-3-small"
            indexer.api_key = None
            indexer.api_base = None
            indexer._client = mock_chroma.PersistentClient.return_value
            indexer._collection = mock_collection
            return indexer

    def test_returns_zero_for_empty_id(self):
        indexer = self._make_indexer()
        assert indexer.delete_conversation("") == 0
        indexer._collection.delete.assert_not_called()

    def test_deletes_matching_chunks_by_metadata(self):
        indexer = self._make_indexer()
        indexer._collection.get.return_value = {
            "ids": ["conv_X_pair_0", "conv_X_pair_1", "conv_X_pair_2"],
        }

        n = indexer.delete_conversation("conv_X")

        assert n == 3
        indexer._collection.get.assert_called_once_with(where={"conv_id": "conv_X"}, include=[])
        indexer._collection.delete.assert_called_once_with(ids=["conv_X_pair_0", "conv_X_pair_1", "conv_X_pair_2"])

    def test_returns_zero_when_no_chunks_match(self):
        indexer = self._make_indexer()
        indexer._collection.get.return_value = {"ids": []}

        n = indexer.delete_conversation("conv_never_indexed")

        assert n == 0
        indexer._collection.delete.assert_not_called()

    def test_returns_zero_when_collection_get_raises(self):
        indexer = self._make_indexer()
        indexer._collection.get.side_effect = RuntimeError("backend exploded")

        n = indexer.delete_conversation("conv_X")

        assert n == 0
        indexer._collection.delete.assert_not_called()
