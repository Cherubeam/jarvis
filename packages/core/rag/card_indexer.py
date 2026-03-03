"""
Card indexer — embeds and stores deck-skill card content in ChromaDB.

Scans deck-skill directories (those containing a ``deck.yaml``) for card
markdown files, and upserts them into a ``"pip_deck_cards"`` collection.

Follows the same patterns as :mod:`packages.core.rag.indexer` for
embedding and ChromaDB interaction.
"""

from pathlib import Path

import litellm
import yaml

_EMBED_BATCH_SIZE = 64
_COLLECTION_NAME = "pip_deck_cards"


class CardIndexer:
    """Index deck-skill card markdown files into ChromaDB for semantic search."""

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
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def index_new(self, deck_dirs: list[Path]) -> int:
        """Scan deck directories, embed and index any cards not yet in ChromaDB.

        Args:
            deck_dirs: List of deck-skill directories, each containing
                a ``deck.yaml`` and ``resources/cards/*.md``.

        Returns:
            The number of newly indexed cards.
        """
        already_indexed = self._get_indexed_card_ids()

        all_ids: list[str] = []
        all_documents: list[str] = []
        all_metadatas: list[dict] = []

        for deck_dir in deck_dirs:
            deck_yaml_path = deck_dir / "deck.yaml"
            if not deck_yaml_path.is_file():
                continue

            deck_meta = self._load_deck_yaml(deck_yaml_path)
            if deck_meta is None:
                continue

            deck_name = deck_meta.get("name", deck_dir.name)
            cards_dir = deck_dir / "resources" / "cards"
            card_index = {c["id"]: c for c in deck_meta.get("cards", [])}

            if not cards_dir.is_dir():
                continue

            for card_path in sorted(cards_dir.glob("*.md")):
                card_id = card_path.stem
                doc_id = f"{deck_dir.name}_{card_id}"

                if doc_id in already_indexed:
                    continue

                content = card_path.read_text(encoding="utf-8").strip()
                if not content:
                    continue

                # Build metadata from deck.yaml card entry
                card_meta = card_index.get(card_id, {})
                metadata = {
                    "deck": deck_name,
                    "deck_dir": deck_dir.name,
                    "card_id": card_id,
                    "name": card_meta.get("name", card_id),
                    "category": card_meta.get("category", ""),
                    "tags": ",".join(card_meta.get("tags", [])),
                    "when": card_meta.get("when", ""),
                }

                all_ids.append(doc_id)
                all_documents.append(content)
                all_metadatas.append(metadata)

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

        return len(all_ids)

    def _load_deck_yaml(self, path: Path) -> dict | None:
        """Load and parse a deck.yaml file. Returns None on error."""
        try:
            with open(path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return None

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

    def _get_indexed_card_ids(self) -> set[str]:
        """Return the set of document IDs already in the collection."""
        count = self._collection.count()
        if count == 0:
            return set()
        result = self._collection.get(include=[])
        return set(result["ids"])


class CardSearcher:
    """Search indexed card content by semantic similarity."""

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

        self._client = chromadb.PersistentClient(path=str(self.db_path))
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def search(
        self,
        query: str,
        n_results: int = 5,
        deck: str | None = None,
    ) -> list[dict]:
        """Embed query and return the top-n most similar cards.

        Args:
            query: Natural-language search query.
            n_results: Maximum number of results to return.
            deck: Optional deck name filter (matches ``deck_dir`` metadata).

        Returns:
            List of dicts with ``card_id``, ``deck``, ``name``,
            ``category``, ``content``, and ``distance``.
        """
        if self._collection.count() == 0:
            return []

        # Embed the query
        embed_kwargs: dict = {
            "model": self.embedding_model,
            "input": [query],
            "api_key": self.api_key,
            "encoding_format": "float",
        }
        if self.api_base:
            embed_kwargs["api_base"] = self.api_base
        response = litellm.embedding(**embed_kwargs)
        query_embedding = response.data[0]["embedding"]

        # Build optional deck filter
        where = None
        if deck:
            where = {"deck_dir": deck}

        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, self._collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            kwargs["where"] = where

        result = self._collection.query(**kwargs)

        search_results: list[dict] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            search_results.append({
                "card_id": meta.get("card_id", ""),
                "deck": meta.get("deck", ""),
                "deck_dir": meta.get("deck_dir", ""),
                "name": meta.get("name", ""),
                "category": meta.get("category", ""),
                "tags": meta.get("tags", ""),
                "when": meta.get("when", ""),
                "content": doc,
                "distance": float(dist),
            })

        return search_results
