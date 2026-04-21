"""
Conversation searcher — semantic search over indexed conversations in ChromaDB.
"""

from dataclasses import dataclass
from pathlib import Path

import litellm

_MAX_EMBED_CHARS = 24_000  # ~8K tokens; text-embedding-3-small limit is 8 191 tokens


def _date_str_to_int(date_str: str) -> int:
    """Convert 'YYYY-MM-DD' → YYYYMMDD integer for ChromaDB numeric filtering."""
    try:
        return int(date_str.replace("-", ""))
    except (ValueError, AttributeError):
        return 0


def _invert_date(session_date: str) -> str:
    """Return a string that sorts *descending* by date when sorted ascending.

    We negate lexicographic order by replacing each digit d with 9-d.
    E.g. "2026-02-27" → "7973-97-72".  This avoids importing datetime
    and handles any ISO-8601 date string.
    """
    return "".join(chr(ord("9") - ord(c) + ord("0")) if c.isdigit() else c for c in session_date)


@dataclass
class SearchResult:
    """A single search result from ChromaDB."""

    conv_id: str
    session_date: str
    document: str
    user_snippet: str
    assistant_snippet: str
    title: str
    distance: float


class ConversationSearcher:
    """Search indexed conversations by semantic similarity."""

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
            name="conversations",
            metadata={"hnsw:space": "cosine"},
        )

    def search(
        self,
        query: str,
        n_results: int = 5,
        date_from: str | None = None,
        date_to: str | None = None,
        deduplicate: bool = True,
    ) -> list[SearchResult]:
        """Embed query and return the top-n most similar conversation chunks.

        Args:
            query: Natural-language search query
            n_results: Maximum number of results to return
            date_from: Optional start date filter (YYYY-MM-DD, inclusive)
            date_to: Optional end date filter (YYYY-MM-DD, inclusive)
            deduplicate: Keep only the best result per conversation (default True)

        Returns:
            List of SearchResult sorted by relevance (closest first).
        """
        if self._collection.count() == 0:
            return []

        # Over-fetch when deduplicating so we still have enough unique conversations
        fetch_n = n_results * 3 if deduplicate else n_results

        # Embed the query
        embed_kwargs: dict = {
            "model": self.embedding_model,
            "input": [query[:_MAX_EMBED_CHARS]],
            "api_key": self.api_key,
            "encoding_format": "float",
        }
        if self.api_base:
            embed_kwargs["api_base"] = self.api_base
        response = litellm.embedding(**embed_kwargs)
        query_embedding = response.data[0]["embedding"]

        # Build optional date filter
        where = self._build_where_filter(date_from, date_to)

        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(fetch_n, self._collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            kwargs["where"] = where

        result = self._collection.query(**kwargs)

        search_results: list[SearchResult] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            search_results.append(
                SearchResult(
                    conv_id=meta.get("conv_id", ""),
                    session_date=meta.get("session_date", ""),
                    document=doc,
                    user_snippet=meta.get("user_snippet", ""),
                    assistant_snippet=meta.get("assistant_snippet", ""),
                    title=meta.get("title", ""),
                    distance=float(dist),
                )
            )

        # Recency tiebreaker: bucket distances to 2 decimal places so that
        # results with similar relevance are ordered newest-first.
        search_results.sort(
            key=lambda r: (round(r.distance, 2), _invert_date(r.session_date)),
        )

        # Per-conversation deduplication: keep only the best result per conv_id
        if deduplicate:
            seen_convs: set[str] = set()
            deduped: list[SearchResult] = []
            for r in search_results:
                if r.conv_id not in seen_convs:
                    seen_convs.add(r.conv_id)
                    deduped.append(r)
            search_results = deduped

        return search_results[:n_results]

    def _build_where_filter(
        self,
        date_from: str | None,
        date_to: str | None,
    ) -> dict | None:
        """Build a ChromaDB metadata filter for date range.

        Uses session_date_int (YYYYMMDD integer) because ChromaDB's
        $gte/$lte operators only work with numeric types.
        """
        conditions = []

        if date_from:
            conditions.append({"session_date_int": {"$gte": _date_str_to_int(date_from)}})
        if date_to:
            conditions.append({"session_date_int": {"$lte": _date_str_to_int(date_to)}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
