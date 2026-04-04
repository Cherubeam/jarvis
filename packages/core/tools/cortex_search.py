"""Vault semantic search tool — searches the Obsidian vault via Cortex API."""

from __future__ import annotations

from packages.core.tools.base import ToolDefinition
from packages.integrations.cortex.client import CortexClient

_MAX_OUTPUT_CHARS = 6_000


def make_cortex_search_tool(client: CortexClient) -> ToolDefinition:
    """Create a search_vault_semantic ToolDefinition."""

    def _search(
        query: str,
        n_results: int = 5,
        path_prefix: str | None = None,
    ) -> str:
        result = client.search(query, n_results=max(1, min(int(n_results), 20)), path_prefix=path_prefix)

        if result is None:
            return (
                "Cortex service is unreachable. "
                "Try search_notes (glob-based) as a fallback, or check that Cortex is running."
            )

        items = result.get("results", [])
        if not items:
            return "No results found in the vault for this query."

        parts: list[str] = []
        total_chars = 0

        for item in items:
            path = item.get("path", "unknown")
            heading = item.get("heading", "")
            score = item.get("score", 0.0)
            content = item.get("content", "")

            header = f"--- {path}"
            if heading:
                header += f" > {heading}"
            header += f" (score: {score:.2f}) ---"

            block = f"{header}\n{content}"

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
        name="search_vault_semantic",
        description=(  # pragma: no mutate
            "Search the Obsidian vault using semantic similarity (meaning-based, not keyword). "  # pragma: no mutate
            "Use this to find notes by concept or topic, even when exact words don't match. "  # pragma: no mutate
            "For exact filename or path searches, use search_notes instead."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query describing what to search for.",  # pragma: no mutate
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 20).",  # pragma: no mutate
                    "default": 5,
                },
                "path_prefix": {
                    "type": "string",
                    "description": "Optional path prefix to filter results (e.g. 'Projects/' or 'Literature Notes/').",  # pragma: no mutate
                },
            },
            "required": ["query"],
        },
        execute=_search,
    )
