"""Outcome indexer and searcher — semantic recall over reviewed outcomes.

Indexes only outcomes with `status: reviewed` — pending items have no
feedback signal and would pollute search results.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import litellm

from packages.core import frontmatter

_EMBED_BATCH_SIZE = 64
_COLLECTION_NAME = "outcomes"


def _build_document(meta: dict, body: str) -> str:
    """Build the text that gets embedded for semantic search."""
    parts = [
        f"What: {meta.get('what', '')}",
        f"Why: {meta.get('why', '')}",
    ]
    success = meta.get("success_looks_like", "")
    if success:
        parts.append(f"Success looks like: {success}")
    parts.append(f"Outcome: {meta.get('outcome', '')} (rated {meta.get('quality', '')}/5)")
    if body.strip():
        parts.append(f"Retrospective: {body.strip()}")
    return "\n".join(parts)


def _load_reviewed(outcomes_dir: Path) -> list[tuple[str, dict, str]]:
    """Return (outcome_id, meta, body) for every reviewed outcome file.

    Malformed files are silently skipped.
    """
    out: list[tuple[str, dict, str]] = []
    if not outcomes_dir.exists():
        return out
    for path in sorted(outcomes_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            meta, body = frontmatter.parse(text)
        except Exception:
            continue
        if meta.get("status") != "reviewed":
            continue
        out.append((path.stem, meta, body))
    return out


@dataclass
class OutcomeResult:
    """A single outcome search result."""

    outcome_id: str
    what: str
    why: str
    outcome: str
    quality: int
    retrospective: str
    revisit_at: str
    conversation_id: str
    distance: float


class OutcomeIndexer:
    """Index reviewed outcomes into ChromaDB for semantic recall."""

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

    def index_new(self, outcomes_dir: str | Path) -> int:
        """Embed and upsert any reviewed outcomes not yet in ChromaDB.

        Also removes entries whose source file has been deleted or reverted
        to non-reviewed status.

        Returns the number of newly indexed outcomes.
        """
        outcomes_dir = Path(outcomes_dir)
        reviewed = _load_reviewed(outcomes_dir)
        reviewed_ids = {r[0] for r in reviewed}

        already_indexed = self._get_indexed_ids()
        stale = already_indexed - reviewed_ids
        if stale:
            self._collection.delete(ids=list(stale))

        to_index = [r for r in reviewed if r[0] not in already_indexed]
        if not to_index:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []
        for outcome_id, meta, body in to_index:
            ids.append(outcome_id)
            documents.append(_build_document(meta, body))
            metadatas.append(
                {
                    "outcome_id": outcome_id,
                    "what": str(meta.get("what", "")),
                    "why": str(meta.get("why", "")),
                    "outcome": str(meta.get("outcome", "")),
                    "quality": int(meta.get("quality", 0)),
                    "revisit_at": str(meta.get("revisit_at", "")),
                    "reviewed_at": str(meta.get("reviewed_at", "")),
                    "conversation_id": str(meta.get("conversation_id", "")),
                    "retrospective": body.strip(),
                }
            )

        for i in range(0, len(ids), _EMBED_BATCH_SIZE):
            batch_ids = ids[i : i + _EMBED_BATCH_SIZE]
            batch_docs = documents[i : i + _EMBED_BATCH_SIZE]
            batch_metas = metadatas[i : i + _EMBED_BATCH_SIZE]
            embeddings = self._embed_batch(batch_docs)
            self._collection.upsert(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_docs,
                metadatas=batch_metas,
            )

        return len(to_index)

    def _get_indexed_ids(self) -> set[str]:
        if self._collection.count() == 0:
            return set()
        result = self._collection.get(include=["metadatas"])
        return {m["outcome_id"] for m in result["metadatas"] if m.get("outcome_id")}

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
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


class OutcomeSearcher:
    """Search indexed outcomes by semantic similarity."""

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

    def search(self, query: str, n_results: int = 5) -> list[OutcomeResult]:
        if self._collection.count() == 0:
            return []

        embedding = self._embed(query)
        raw = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["metadatas", "distances"],
        )

        results: list[OutcomeResult] = []
        for meta, distance in zip(raw["metadatas"][0], raw["distances"][0], strict=True):
            results.append(
                OutcomeResult(
                    outcome_id=meta.get("outcome_id", ""),
                    what=meta.get("what", ""),
                    why=meta.get("why", ""),
                    outcome=meta.get("outcome", ""),
                    quality=int(meta.get("quality", 0)),
                    retrospective=meta.get("retrospective", ""),
                    revisit_at=meta.get("revisit_at", ""),
                    conversation_id=meta.get("conversation_id", ""),
                    distance=float(distance),
                )
            )
        return results

    def _embed(self, text: str) -> list[float]:
        kwargs: dict = {
            "model": self.embedding_model,
            "input": [text],
            "api_key": self.api_key,
            "encoding_format": "float",
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        response = litellm.embedding(**kwargs)
        return response.data[0]["embedding"]
