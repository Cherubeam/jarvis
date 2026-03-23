"""
Web search tool — search the web using DuckDuckGo.

Uses ddgs for zero-config web search (no API key required).
All errors are returned as strings so the LLM can reason about failures.
"""

from ddgs import DDGS

from packages.core.tools.base import ToolDefinition

_MAX_RESULTS = 10
_MAX_OUTPUT_CHARS = 4_000


def _search_web(query: str, max_results: int = 5) -> str:
    """Search the web and return formatted results."""
    try:
        clamped = max(1, min(int(max_results), _MAX_RESULTS))
        results = DDGS().text(query, max_results=clamped)
    except Exception as e:
        return f"Error: Web search failed: {e}. Do not retry — use a different approach or answer from your existing knowledge."

    if not results:
        return "No results found."

    parts = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("href", "")
        snippet = r.get("body", "")
        parts.append(f"{i}. **{title}**\n   {url}\n   {snippet}")

    output = "\n\n".join(parts)
    if len(output) > _MAX_OUTPUT_CHARS:
        output = output[:_MAX_OUTPUT_CHARS] + "\n\n[Results truncated]"
    return output


WEB_SEARCH_TOOL = ToolDefinition(
    name="web_search",
    description=(
        "Search the web for information. Returns titles, URLs, and snippets. "
        "Use this to find current information, research topics, or discover URLs "
        "that can then be fetched with fetch_url for full content."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (default 5, max 10).",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    execute=_search_web,
)
