"""
Card search tool — semantic search over indexed deck-skill cards.

Factory function that creates a ToolDefinition backed by CardSearcher.
Lazy-imports chromadb so the module is importable even without the rag extra.
"""

from pathlib import Path

from packages.core.tools.base import ToolDefinition

_MAX_OUTPUT_CHARS = 8_000


def make_card_search_tool(
    db_path: str | Path,
    embedding_model: str,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ToolDefinition:
    """Create and return a search_tactics ToolDefinition.

    Raises ImportError if chromadb is not installed.
    """
    from packages.core.rag.card_indexer import CardSearcher

    searcher = CardSearcher(db_path, embedding_model, api_key, api_base)

    def _search(
        query: str,
        deck: str | None = None,
        n_results: int = 5,
    ) -> str:
        clamped = max(1, min(int(n_results), 15))
        results = searcher.search(
            query,
            n_results=clamped,
            deck=deck or None,
        )

        if not results:
            return "No matching tactics cards found."

        parts: list[str] = []
        total_chars = 0

        for r in results:
            header = f"--- {r['name']} ({r['deck']}) [category: {r['category']}] ---"
            body = r["content"]
            block = f"{header}\n{body}"

            if total_chars + len(block) > _MAX_OUTPUT_CHARS:
                remaining = _MAX_OUTPUT_CHARS - total_chars
                if remaining > len(header) + 20:
                    block = block[:remaining] + "\n[truncated]"
                    parts.append(block)
                break

            parts.append(block)
            total_chars += len(block)

        return "\n\n".join(parts)

    return ToolDefinition(
        name="search_tactics",
        description=(
            "Search across all Pip Decks tactics cards (Storyteller Tactics, "  # pragma: no mutate
            "Workshop Tactics, Idea Tactics, etc.) for relevant techniques. "  # pragma: no mutate
            "Use this when you need to find tactics, frameworks, or exercises "  # pragma: no mutate
            "to help with storytelling, workshops, ideation, or other creative challenges. "  # pragma: no mutate
            "Returns full card content for the most relevant matches."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (e.g. 'how to open a presentation', 'brainstorming techniques').",  # pragma: no mutate
                },
                "deck": {
                    "type": "string",
                    "description": "Optional: filter to a specific deck directory name (e.g. 'storyteller-tactics').",  # pragma: no mutate
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 15).",  # pragma: no mutate
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        execute=_search,
    )
