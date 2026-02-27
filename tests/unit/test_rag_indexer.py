"""
Unit tests for ConversationIndexer.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call


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
        msgs.append({
            "id": f"msg_{i * 2 - 1:03d}",
            "role": "user",
            "content": [{"type": "text", "text": user_text}],
            "timestamp": "2026-02-20T10:00:00",
            "metadata": {},
        })
        msgs.append({
            "id": f"msg_{i * 2:03d}",
            "role": "assistant",
            "content": [{"type": "text", "text": asst_text}],
            "timestamp": "2026-02-20T10:00:01",
            "metadata": {},
        })
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
            indexer.embedding_model = "openai/text-embedding-3-small"
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
        assert "User: Hello" in pairs[0]["document"]
        assert "Assistant: Hi there!" in pairs[0]["document"]

    def test_multiple_pairs_in_order(self):
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([
                ("First question", "First answer"),
                ("Second question", "Second answer"),
                ("Third question", "Third answer"),
            ]),
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

    def test_snippets_capped_at_200_chars(self):
        indexer = self._make_indexer()
        long_text = "x" * 300
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([(long_text, long_text)]),
        )
        pairs = indexer._extract_pairs(conv)

        assert len(pairs[0]["metadata"]["user_snippet"]) <= 200
        assert len(pairs[0]["metadata"]["assistant_snippet"]) <= 200

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
        assert "User: Lone user message" in pairs[0]["document"]
        assert "Assistant: " in pairs[0]["document"]

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

    def test_title_stored_in_metadata(self):
        indexer = self._make_indexer()
        conv = _make_v1_conversation(
            "conv_20260220_100000_abc123",
            _make_messages([("Q", "A")]),
        )
        conv["title"] = "My Test Session"
        pairs = indexer._extract_pairs(conv)

        assert pairs[0]["metadata"]["title"] == "My Test Session"


# ---------------------------------------------------------------------------
# index_new
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestIndexNew:
    def _setup(self, tmp_path, already_indexed_ids=None):
        """Return (indexer, mock_collection) with mocked chromadb."""
        mock_chroma_module = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = len(already_indexed_ids or [])

        # Simulate _get_indexed_conv_ids returning the pre-existing set
        existing_metas = [{"conv_id": cid} for cid in (already_indexed_ids or [])]
        mock_collection.get.return_value = {"metadatas": existing_metas}
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

        fake_embedding = [[0.1, 0.2, 0.3]]
        with patch("packages.core.rag.indexer.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2, 0.3]}])
            n_new = indexer.index_new(tmp_path)

        assert n_new == 1
        mock_collection.upsert.assert_called_once()

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
