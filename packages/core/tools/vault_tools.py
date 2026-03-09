"""
Vault read tools for JARVIS.

Factory function that creates read-only tools for accessing Obsidian vault
notes. Uses the closure pattern to capture VaultConfig.
"""

from datetime import date, datetime

from packages.core.tools.base import ToolDefinition
from packages.integrations.obsidian.vault import (
    VaultConfig,
    get_daily_note_path,
    list_notes,
    read_note,
)

MAX_CONTENT_SIZE = 50_000  # 50KB cap for note content
MAX_SEARCH_RESULTS = 100


def make_vault_tools(vault_config: VaultConfig) -> list[ToolDefinition]:
    """Create read-only vault tools scoped to the given vault.

    Args:
        vault_config: Vault configuration with path validation.

    Returns:
        List of 3 ToolDefinitions: read_note, search_notes, read_daily_note.
    """

    # --- read_note ---

    def _read_note(path: str) -> str:
        full_path = (vault_config.vault_path / path).resolve()
        try:
            content = read_note(full_path, vault_config)
        except PermissionError as e:
            return f"Error: {e}"
        except FileNotFoundError:
            return f"Error: File not found: {path}"

        if len(content) > MAX_CONTENT_SIZE:
            content = content[:MAX_CONTENT_SIZE] + "\n\n[Truncated — content exceeds 50KB]"
        return content

    read_tool = ToolDefinition(
        name="read_note",
        description="Read the full content of a note from the Obsidian vault. Path is relative to the vault root.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the note, relative to the vault root.",
                },
            },
            "required": ["path"],
        },
        execute=_read_note,
    )

    # --- search_notes ---

    def _search_notes(
        directory: str = "",
        pattern: str = "**/*.md",
        sort_by: str = "name",
        limit: int = MAX_SEARCH_RESULTS,
    ) -> str:
        target = vault_config.vault_path / directory if directory else vault_config.vault_path
        target = target.resolve()
        try:
            notes = list_notes(target, vault_config, pattern=pattern)
        except PermissionError as e:
            return f"Error: {e}"

        if not notes:
            return "No notes found."

        limit = max(1, min(limit, MAX_SEARCH_RESULTS))

        if sort_by == "modified":
            notes.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        lines = []
        for note in notes[:limit]:
            rel = note.relative_to(vault_config.vault_path)
            if sort_by == "modified":
                mtime = datetime.fromtimestamp(note.stat().st_mtime)
                lines.append(f"{mtime:%Y-%m-%d %H:%M}  {rel}")
            else:
                lines.append(str(rel))

        result = "\n".join(lines)
        if len(notes) > limit:
            result += f"\n\n[Showing {limit} of {len(notes)} results]"
        return result

    search_tool = ToolDefinition(
        name="search_notes",
        description="List notes in the Obsidian vault matching a glob pattern. Returns paths relative to the vault root. Supports sorting by name or modification time.",
        parameters={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to search in, relative to vault root. Defaults to the vault root.",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (default: '**/*.md').",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["name", "modified"],
                    "description": "Sort order: 'name' (alphabetical, default) or 'modified' (most recent first, includes timestamps).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 100, clamped 1–100).",
                },
            },
            "required": [],
        },
        execute=_search_notes,
    )

    # --- read_daily_note ---

    def _read_daily_note(date: str = "") -> str:
        target_date = date if date else None
        try:
            note_path = get_daily_note_path(vault_config, target_date)
        except ValueError:
            return f"Error: Invalid date format: {date}. Use YYYY-MM-DD."

        try:
            content = read_note(note_path, vault_config)
        except PermissionError as e:
            return f"Error: {e}"
        except FileNotFoundError:
            display_date = date if date else "today"
            return f"Error: Daily note not found for {display_date}."

        if len(content) > MAX_CONTENT_SIZE:
            content = content[:MAX_CONTENT_SIZE] + "\n\n[Truncated — content exceeds 50KB]"
        return content

    daily_tool = ToolDefinition(
        name="read_daily_note",
        description="Read today's daily note (or a specific date's note) from the Obsidian vault.",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format. Defaults to today if omitted.",
                },
            },
            "required": [],
        },
        execute=_read_daily_note,
    )

    return [read_tool, search_tool, daily_tool]
