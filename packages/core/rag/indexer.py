"""
Conversation indexer — embeds and stores conversation message-pairs in ChromaDB.

Scans data/conversations/*.json on startup, skips already-indexed conversations,
and upserts new chunks into the "conversations" collection.
"""

from pathlib import Path

import litellm

from packages.core.memory import ConversationLogger, _extract_text_from_content

_EMBED_BATCH_SIZE = 64
_MAX_EMBED_CHARS = 24_000  # ~8K tokens; text-embedding-3-small limit is 8 191 tokens
_CHUNK_OVERLAP_CHARS = 2_400  # ~10 % of _MAX_EMBED_CHARS


def _date_str_to_int(date_str: str) -> int:
    """Convert 'YYYY-MM-DD' → YYYYMMDD integer for ChromaDB numeric filtering."""
    try:
        return int(date_str.replace("-", ""))
    except (ValueError, AttributeError):
        return 0


def _chunk_document(text: str, max_chars: int = _MAX_EMBED_CHARS, overlap: int = _CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split *text* into overlapping windows of at most *max_chars* characters.

    Short documents (≤ max_chars) are returned as-is in a single-element list.
    """
    if len(text) <= max_chars:
        return [text]

    step = max_chars - overlap
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        start += step
    return chunks


class ConversationIndexer:
    """Index conversation files into ChromaDB for semantic search."""

    def __init__(
        self,
        db_path: str | Path,
        embedding_model: str,
        api_key: str | None = None,
        api_base: str | None = None,
    ):
        import chromadb

        self.db_path = Path(db_path)
        self.embedding_model = embedding_model
        self.api_key = api_key
        self.api_base = api_base

        self.db_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.db_path))
        self._collection = self._client.get_or_create_collection(
            name="conversations",
            metadata={"hnsw:space": "cosine"},
        )

    def index_new(self, conversations_dir: str | Path) -> int:
        """Scan conversations_dir, embed and index any not yet in ChromaDB.

        Returns the number of newly indexed conversations.
        """
        conversations_dir = Path(conversations_dir)
        if not conversations_dir.exists():
            return 0

        self._migrate_date_metadata()
        already_indexed = self._get_indexed_conv_ids()

        new_count = 0
        all_ids: list[str] = []
        all_documents: list[str] = []
        all_metadatas: list[dict] = []

        for filepath in sorted(conversations_dir.rglob("*.json")):
            conversation = self._load_conversation(filepath)
            if conversation is None:
                continue

            conv_id = conversation.get("id") or filepath.stem
            if conv_id in already_indexed:
                continue

            pairs = self._extract_pairs(conversation, conv_id=conv_id)
            if not pairs:
                continue

            for pair in pairs:
                all_ids.append(pair["id"])
                all_documents.append(pair["document"])
                all_metadatas.append(pair["metadata"])

            new_count += 1

        if not all_ids:
            return 0

        # Embed and upsert in batches
        for i in range(0, len(all_ids), _EMBED_BATCH_SIZE):
            batch_ids = all_ids[i : i + _EMBED_BATCH_SIZE]
            batch_docs = all_documents[i : i + _EMBED_BATCH_SIZE]
            batch_metas = all_metadatas[i : i + _EMBED_BATCH_SIZE]

            embeddings = self._embed_batch(batch_docs)
            self._collection.upsert(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_docs,
                metadatas=batch_metas,
            )

        return new_count

    def _load_conversation(self, filepath: Path) -> dict | None:
        """Load and migrate a conversation file. Returns None on error or if empty."""
        try:
            data = ConversationLogger.load(filepath)
        except Exception:
            return None

        if not data.get("messages"):
            return None

        return data

    def _extract_pairs(self, conversation: dict, *, conv_id: str | None = None) -> list[dict]:
        """Build message-pair chunks from consecutive user+assistant turns."""
        messages = conversation.get("messages", [])
        conv_id = conv_id or conversation.get("id") or ""
        title = conversation.get("title") or ""

        # Extract session date from session_start or conv_id
        session_date = ""
        session_start = conversation.get("session_start", "")
        if session_start:
            session_date = session_start[:10]  # "YYYY-MM-DD"
        elif conv_id.startswith("conv_") and len(conv_id) >= 13:
            # conv_YYYYMMDD_... → "YYYY-MM-DD"
            raw = conv_id[5:13]
            if len(raw) == 8 and raw.isdigit():
                session_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

        pairs = []
        pair_index = 0
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg.get("role") == "user":
                user_text = _extract_text_from_content(msg.get("content", []))
                if not isinstance(msg.get("content"), list):
                    user_text = str(msg.get("content", ""))

                # Look for the next assistant message
                assistant_text = ""
                if i + 1 < len(messages) and messages[i + 1].get("role") == "assistant":
                    asst_msg = messages[i + 1]
                    assistant_text = _extract_text_from_content(asst_msg.get("content", []))
                    if not isinstance(asst_msg.get("content"), list):
                        assistant_text = str(asst_msg.get("content", ""))
                    i += 2
                else:
                    i += 1

                if not user_text.strip():
                    continue

                doc = f"User: {user_text}\n\nAssistant: {assistant_text}"
                chunks = _chunk_document(doc)
                for chunk_idx, chunk in enumerate(chunks):
                    if len(chunks) == 1:
                        chunk_id = f"{conv_id}_pair_{pair_index}"
                        chunk_meta = {}
                    else:
                        chunk_id = f"{conv_id}_pair_{pair_index}_chunk_{chunk_idx}"
                        chunk_meta = {"chunk_index": chunk_idx, "total_chunks": len(chunks)}

                    pairs.append(
                        {
                            "id": chunk_id,
                            "document": chunk,
                            "metadata": {
                                "conv_id": conv_id,
                                "session_date": session_date,
                                "session_date_int": _date_str_to_int(session_date),
                                "pair_index": pair_index,
                                "user_snippet": user_text[:200],
                                "assistant_snippet": assistant_text[:200],
                                "title": title,
                                **chunk_meta,
                            },
                        }
                    )
                pair_index += 1
            else:
                i += 1

        return pairs

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using LiteLLM."""
        kwargs: dict = {
            "model": self.embedding_model,
            "input": texts,
            "api_key": self.api_key,
            "encoding_format": "float",
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        response = litellm.embedding(**kwargs)
        return [item["embedding"] for item in response.data]

    def _migrate_date_metadata(self) -> None:
        """Add session_date_int to records that are missing it (one-time migration)."""
        if self._collection.count() == 0:
            return

        result = self._collection.get(include=["metadatas"])
        ids_to_update: list[str] = []
        metas_to_update: list[dict] = []

        for doc_id, meta in zip(result["ids"], result["metadatas"], strict=True):
            if meta.get("session_date_int"):
                continue
            session_date = meta.get("session_date", "")
            ids_to_update.append(doc_id)
            metas_to_update.append({**meta, "session_date_int": _date_str_to_int(session_date)})

        if ids_to_update:
            self._collection.update(ids=ids_to_update, metadatas=metas_to_update)

    def _get_indexed_conv_ids(self) -> set[str]:
        """Return the set of conv_ids already in the ChromaDB collection."""
        count = self._collection.count()
        if count == 0:
            return set()

        # Fetch all metadatas (no embeddings needed)
        result = self._collection.get(include=["metadatas"])
        return {m["conv_id"] for m in result["metadatas"] if m.get("conv_id")}
