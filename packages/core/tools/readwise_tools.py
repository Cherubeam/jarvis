"""
Readwise tools — search reading list, highlights, and manage documents.

Uses the Readwise CLI subprocess wrapper for data access.
"""

import logging

from packages.core.tools.base import ToolDefinition
from packages.integrations.readwise.client import ReadwiseClient, is_cli_available

logger = logging.getLogger(__name__)


def make_readwise_tools(config: dict) -> list[ToolDefinition]:
    """Create Readwise tools for reading list search and management.

    Args:
        config: The readwise section of the config dict.

    Returns:
        List of ToolDefinitions. Empty list if CLI is not installed.
    """
    if not is_cli_available():
        logger.info("Readwise tools skipped: CLI not installed")  # pragma: no mutate
        return []

    client = ReadwiseClient(
        cache_ttl_seconds=config.get("cache_ttl_seconds", 300),
    )
    tools: list[ToolDefinition] = []

    # --- search_reading_list ---

    def _search_reading_list(
        query: str,
        location: str = "",
        category: str = "",
    ) -> str:
        return client.search_documents(
            query, location=location, category=category,
        )

    tools.append(
        ToolDefinition(
            name="search_reading_list",
            description=(  # pragma: no mutate
                "Search the user's Readwise Reader library by keyword or topic. "
                "Returns document titles, summaries, URLs, tags, and metadata. "
                "Use 'location' to filter: 'inbox', 'later', 'shortlist', 'archive'. "
                "Use 'category' to filter: 'article', 'email', 'rss', 'pdf', 'epub', "
                "'tweet', 'video', 'podcast', 'audiobook'."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query — topic, keyword, or phrase.",  # pragma: no mutate
                    },
                    "location": {
                        "type": "string",
                        "description": "Filter by location: 'inbox', 'later', 'shortlist', 'archive', or '' for all.",  # pragma: no mutate
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category: 'article', 'email', 'rss', 'pdf', 'epub', 'tweet', 'video', 'podcast', 'audiobook', or '' for all.",  # pragma: no mutate
                    },
                },
                "required": ["query"],
            },
            execute=_search_reading_list,
        )
    )

    # --- search_highlights ---

    def _search_highlights(query: str) -> str:
        return client.search_highlights(query)

    tools.append(
        ToolDefinition(
            name="search_highlights",
            description=(  # pragma: no mutate
                "Search across all of the user's Readwise highlights by keyword or topic. "
                "Returns matching highlights with their source document info."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query — topic, keyword, or phrase.",  # pragma: no mutate
                    },
                },
                "required": ["query"],
            },
            execute=_search_highlights,
        )
    )

    # --- get_document_details ---

    def _get_document_details(document_id: str) -> str:
        return client.get_document_details(document_id)

    tools.append(
        ToolDefinition(
            name="get_document_details",
            description=(  # pragma: no mutate
                "Get full details for a specific Readwise Reader document by its ID. "
                "Returns title, author, content, highlights, tags, and metadata."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The Readwise document ID.",  # pragma: no mutate
                    },
                },
                "required": ["document_id"],
            },
            execute=_get_document_details,
        )
    )

    # --- save_to_reader ---

    def _save_to_reader(url: str) -> str:
        return client.create_document(url)

    tools.append(
        ToolDefinition(
            name="save_to_reader",
            description=(  # pragma: no mutate
                "Save a URL to the user's Readwise Reader library. "
                "The article will appear in their inbox for later reading."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to save to Reader.",  # pragma: no mutate
                    },
                },
                "required": ["url"],
            },
            execute=_save_to_reader,
        )
    )

    # --- tag_document ---

    def _tag_document(document_id: str, tags: str) -> str:
        return client.tag_document(document_id, tags)

    tools.append(
        ToolDefinition(
            name="tag_readwise_document",
            description=(  # pragma: no mutate
                "Add tags to a Readwise Reader document. "
                "Tags are comma-separated (e.g. 'ai,research,to-review')."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The Readwise document ID.",  # pragma: no mutate
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tags to add.",  # pragma: no mutate
                    },
                },
                "required": ["document_id", "tags"],
            },
            execute=_tag_document,
        )
    )

    # --- move_document ---

    def _move_document(document_id: str, location: str) -> str:
        return client.move_document(document_id, location)

    tools.append(
        ToolDefinition(
            name="move_readwise_document",
            description=(  # pragma: no mutate
                "Move a Readwise Reader document to a different location. "
                "Locations: 'inbox' (new), 'later', 'shortlist', 'archive'."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The Readwise document ID.",  # pragma: no mutate
                    },
                    "location": {
                        "type": "string",
                        "description": "Target location: 'inbox', 'later', 'shortlist', or 'archive'.",  # pragma: no mutate
                    },
                },
                "required": ["document_id", "location"],
            },
            execute=_move_document,
        )
    )

    return tools
