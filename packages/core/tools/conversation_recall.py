"""
Conversation recall tool — semantic search over past conversations.

Factory function that creates a ToolDefinition backed by ConversationSearcher.
Lazy-imports chromadb so the module is importable even without the rag extra.
"""

from datetime import date
from pathlib import Path

from packages.core.tools.base import ToolDefinition

_MAX_OUTPUT_CHARS = 6_000


def make_conversation_recall_tool(
    db_path: str | Path,
    embedding_model: str,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ToolDefinition:
    """Create and return a recall_conversations ToolDefinition.

    Raises ImportError if chromadb is not installed.
    """
    # Eagerly import to surface missing dependency at setup time, not at call time.
    from packages.core.rag.searcher import ConversationSearcher  # noqa: F401 (import check)

    searcher = ConversationSearcher(db_path, embedding_model, api_key, api_base)

    def _recall(
        query: str,
        date_from: str | None = None,
        date_to: str | None = None,
        n_results: int = 10,
    ) -> str:
        # Clamp to [1, 20]
        clamped = max(1, min(int(n_results), 20))
        results = searcher.search(
            query,
            n_results=clamped,
            date_from=date_from or None,
            date_to=date_to or None,
        )

        if not results:
            return "No relevant past conversations found."

        parts: list[str] = []
        total_chars = 0

        for r in results:
            header = f"--- {r.session_date} ({r.conv_id}) ---"
            body = r.document
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
        name="recall_conversations",
        description=(  # pragma: no mutate
            "Search past conversations for relevant context. "  # pragma: no mutate
            f"Today is {date.today().strftime('%A, %Y-%m-%d')}. "  # pragma: no mutate
            "IMPORTANT: When the user asks about a time period "  # pragma: no mutate
            "(this week, last month, yesterday, recently, etc.), "  # pragma: no mutate
            "you MUST set date_from and/or date_to to restrict results to that period. "  # pragma: no mutate
            "For broad queries like weekly summaries, request more results with n_results. "  # pragma: no mutate
            "Returns excerpts from the most semantically similar past exchanges."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in past conversations.",  # pragma: no mutate
                },
                "date_from": {
                    "type": "string",
                    "description": "Optional start date filter (YYYY-MM-DD, inclusive).",  # pragma: no mutate
                },
                "date_to": {
                    "type": "string",
                    "description": "Optional end date filter (YYYY-MM-DD, inclusive).",  # pragma: no mutate
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 10, max 20).",  # pragma: no mutate
                    "default": 10,
                },
            },
            "required": ["query"],
        },
        execute=_recall,
    )
