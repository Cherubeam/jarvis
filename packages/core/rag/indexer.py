"""
Conversation indexer — embeds and stores conversation message-pairs in ChromaDB.

Scans data/conversations/*.json on startup, skips already-indexed conversations,
and upserts new chunks into the "conversations" collection.
"""

from pathlib import Path

import litellm

from packages.core.memory import ConversationLogger, _extract_text_from_content

_EMBED_BATCH_SIZE = 64


class ConversationIndexer:
    """Index conversation files into ChromaDB for semantic search."""

    def __init__(
        self,
        db_path: str | Path,
        embedding_model: str,
        api_key: str | None = None,
    ):
        import chromadb

        self.db_path = Path(db_path)
        self.embedding_model = embedding_model
        self.api_key = api_key

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

        already_indexed = self._get_indexed_conv_ids()

        new_count = 0
        all_ids: list[str] = []
        all_documents: list[str] = []
        all_metadatas: list[dict] = []

        for filepath in sorted(conversations_dir.glob("*.json")):
            conversation = self._load_conversation(filepath)
            if conversation is None:
                continue

            conv_id = conversation.get("id") or filepath.stem
            if conv_id in already_indexed:
                continue

            pairs = self._extract_pairs(conversation)
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

    def _extract_pairs(self, conversation: dict) -> list[dict]:
        """Build message-pair chunks from consecutive user+assistant turns."""
        messages = conversation.get("messages", [])
        conv_id = conversation.get("id") or ""
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
                pairs.append({
                    "id": f"{conv_id}_pair_{pair_index}",
                    "document": doc,
                    "metadata": {
                        "conv_id": conv_id,
                        "session_date": session_date,
                        "pair_index": pair_index,
                        "user_snippet": user_text[:200],
                        "assistant_snippet": assistant_text[:200],
                        "title": title,
                    },
                })
                pair_index += 1
            else:
                i += 1

        return pairs

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using LiteLLM."""
        response = litellm.embedding(
            model=self.embedding_model,
            input=texts,
            api_key=self.api_key,
        )
        return [item["embedding"] for item in response.data]

    def _get_indexed_conv_ids(self) -> set[str]:
        """Return the set of conv_ids already in the ChromaDB collection."""
        count = self._collection.count()
        if count == 0:
            return set()

        # Fetch all metadatas (no embeddings needed)
        result = self._collection.get(include=["metadatas"])
        return {m["conv_id"] for m in result["metadatas"] if m.get("conv_id")}
