"""Outcome recall tool — semantic search over past reviewed outcomes."""

from __future__ import annotations

from pathlib import Path

from packages.core.tools.base import ToolDefinition

_MAX_OUTPUT_CHARS = 4_000


def make_outcome_recall_tool(
    db_path: str | Path,
    embedding_model: str,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ToolDefinition:
    """Create the recall_outcomes ToolDefinition backed by an OutcomeSearcher."""
    from packages.core.rag.outcome_indexer import OutcomeSearcher

    searcher = OutcomeSearcher(db_path, embedding_model, api_key, api_base)

    def _recall(query: str, n_results: int = 5) -> str:
        clamped = max(1, min(int(n_results), 10))
        results = searcher.search(query, n_results=clamped)

        if not results:
            return "No relevant past outcomes found."

        parts: list[str] = []
        total_chars = 0
        for r in results:
            header = f"--- {r.outcome_id} (outcome: {r.outcome}, rated {r.quality}/5) ---"
            lines = [header, f"What: {r.what}", f"Why: {r.why}"]
            if r.retrospective:
                lines.append(f"Retrospective: {r.retrospective}")
            block = "\n".join(lines)

            if total_chars + len(block) > _MAX_OUTPUT_CHARS:
                break
            parts.append(block)
            total_chars += len(block)

        return "\n\n".join(parts)

    return ToolDefinition(
        name="recall_outcomes",
        description=(  # pragma: no mutate
            "Search past reviewed recommendations and their outcomes for relevant "
            "lessons. Use when you're about to give advice similar to advice you "
            "may have given before — check whether past suggestions in this area "
            "worked out, and what the user said in their retrospectives. Returns "
            "matching outcomes with the original recommendation, the reason, the "
            "result (happened/didnt/partial), a quality rating (1-5), and the "
            "user's retrospective note."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What topic or situation to search for in past outcomes.",  # pragma: no mutate
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 10).",  # pragma: no mutate
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        execute=_recall,
    )
