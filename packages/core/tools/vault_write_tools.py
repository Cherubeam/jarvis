"""
Generic vault write tools factory.

Creates scoped tools for creating and editing notes in any Obsidian vault
directory. Uses the closure pattern (like blog_tools) to capture VaultConfig
and ConfirmationHandler.
"""

from pathlib import Path

from packages.core.tools.base import ToolDefinition
from packages.integrations.obsidian.vault import VaultConfig, list_notes, read_note, validate_write
from packages.integrations.obsidian.writer import ConfirmationHandler, WriteResult, write_note


def make_vault_write_tools(
    vault_config: VaultConfig,
    confirmation_handler: ConfirmationHandler,
    target_dir: str = "",
    template_path: str = "",
) -> list[ToolDefinition]:
    """Create vault write tools scoped to the given vault and target directory.

    Args:
        vault_config: Vault configuration with path validation.
        confirmation_handler: Handler for diff display and write confirmation.
        target_dir: Target directory relative to vault root. If empty, notes
            are created relative to vault root.
        template_path: Template file path relative to vault root. If empty,
            no template is prepended.

    Returns:
        List of ToolDefinitions: create_note, edit_note, and optionally list_notes_in_dir.
    """
    if target_dir:
        target_path = vault_config.vault_path / target_dir
    else:
        target_path = vault_config.vault_path

    template_full_path = vault_config.vault_path / template_path if template_path else None

    # --- path helpers ---

    def _resolve_path(path: str) -> Path | None:
        """Resolve an agent-provided path to an absolute path within the target boundary.

        1. Strips redundant target_dir prefix if agent included it
        2. Resolves to absolute path under target_path (or vault root)
        3. Validates result stays within boundary (no '../' traversal escape)
        """
        path_obj = Path(path)
        if target_dir:
            target_dir_path = Path(target_dir)
            if path_obj.is_relative_to(target_dir_path):
                path_obj = path_obj.relative_to(target_dir_path)
            full = (target_path / path_obj).resolve()
            if not full.is_relative_to(target_path.resolve()):
                return None
        else:
            full = (vault_config.vault_path / path_obj).resolve()
            if not full.is_relative_to(vault_config.vault_path.resolve()):
                return None
        return full

    def _to_relative(absolute: Path) -> str:
        """Convert an absolute path to a target-relative string for display to the agent."""
        base = target_path if target_dir else vault_config.vault_path
        return str(absolute.relative_to(base))

    tools: list[ToolDefinition] = []

    # --- create_note ---

    def _create_note(path: str, content: str, use_template: bool = True) -> str:
        full_path = _resolve_path(path)
        if full_path is None:
            return f"Error: Path '{path}' escapes the target directory."

        if full_path.exists():
            return f"Error: File already exists: {path}. Use edit_note to modify it."

        if use_template and template_full_path and template_full_path.is_file():
            try:
                template_content = read_note(template_full_path, vault_config)
                full_content = template_content.rstrip("\n") + "\n\n" + content
            except (PermissionError, FileNotFoundError) as e:
                return f"Error reading template: {e}. Creating without template."
        else:
            full_content = content

        result: WriteResult = write_note(
            full_path, full_content, vault_config, confirmation_handler,
        )
        return result.message

    create_tool = ToolDefinition(
        name="create_note",
        description=(
            "Create a new note in the vault. "
            "Path is relative to the target directory (or vault root if no target directory is configured). "
            "Set use_template=true to prepend the configured template. "
            "Use descriptive file names with spaces (e.g. 'Concept for Method of the Year.md'). "
            "The user will see a diff and must confirm before the file is written."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "File path relative to the target directory "
                        "(e.g. 'My Pattern.md' or 'Subfolder/Note.md'). "
                        "Do NOT include the target directory prefix."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "Full markdown content for the note.",
                },
                "use_template": {
                    "type": "boolean",
                    "description": "Prepend the configured template (default: true).",
                    "default": True,
                },
            },
            "required": ["path", "content"],
        },
        execute=_create_note,
    )
    tools.append(create_tool)

    # --- edit_note ---

    def _edit_note(path: str, new_content: str, reasoning: str = "") -> str:
        full_path = (vault_config.vault_path / path).resolve()

        if not validate_write(full_path, vault_config):
            return "Error: Cannot edit this file (read-only)."

        if not full_path.exists():
            return f"Error: File not found: {path}. Use create_note for new files."

        result: WriteResult = write_note(
            full_path, new_content, vault_config, confirmation_handler,
            reasoning=reasoning,
        )
        return result.message

    edit_tool = ToolDefinition(
        name="edit_note",
        description=(
            "Edit an existing note by replacing its full content. "
            "Path is relative to the vault root. "
            "Provide reasoning to explain the changes — it will be shown alongside the diff. "
            "The user must confirm before the edit is applied."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to the vault root.",
                },
                "new_content": {
                    "type": "string",
                    "description": "The complete new content for the file.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of what changed and why (shown to user before diff).",
                },
            },
            "required": ["path", "new_content"],
        },
        execute=_edit_note,
    )
    tools.append(edit_tool)

    # --- list_notes_in_dir (only when target_dir is set) ---

    if target_dir:
        def _list_notes_in_dir(subfolder: str = "") -> str:
            target = target_path / subfolder if subfolder else target_path
            try:
                notes = list_notes(target, vault_config, pattern="**/*.md")
            except PermissionError as e:
                return f"Error: {e}"

            if not notes:
                return "No notes found."

            lines = []
            for note in notes:
                rel = _to_relative(note)
                lines.append(str(rel))
            return "\n".join(lines)

        list_tool = ToolDefinition(
            name="list_notes_in_dir",
            description=(
                "List markdown files in the target directory. "
                "Returns paths relative to the target directory — "
                "use these paths directly with create_note. "
                "Optionally filter by subfolder."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "subfolder": {
                        "type": "string",
                        "description": "Optional subfolder within the target directory to list.",
                    },
                },
                "required": [],
            },
            execute=_list_notes_in_dir,
        )
        tools.append(list_tool)

    return tools
