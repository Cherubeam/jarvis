"""
Conversation recall tool — semantic search over past conversations.

Factory function that creates a ToolDefinition backed by ConversationSearcher.
Lazy-imports chromadb so the module is importable even without the rag extra.
"""

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
    ) -> str:
        results = searcher.search(
            query,
            n_results=5,
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
        description=(
            "Search past conversations for relevant context. "
            "Use this when the user asks about previous discussions, "
            "what was talked about before, or needs context from earlier sessions. "
            "Returns excerpts from the most semantically similar past exchanges."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in past conversations.",
                },
                "date_from": {
                    "type": "string",
                    "description": "Optional start date filter (YYYY-MM-DD, inclusive).",
                },
                "date_to": {
                    "type": "string",
                    "description": "Optional end date filter (YYYY-MM-DD, inclusive).",
                },
            },
            "required": ["query"],
        },
        execute=_recall,
    )
