"""
Project write tools — guarded file write access for the developer agent.

Uses the existing ConfirmationHandler ABC for diff display and user confirmation.
Writes are restricted to allowed directories and file extensions.
"""

from pathlib import Path

from packages.core.tools.base import ToolDefinition
from packages.integrations.obsidian.diff import compute_diff, format_diff_for_cli
from packages.integrations.obsidian.writer import ConfirmationHandler


def _is_safe_path(path: Path, root: Path) -> bool:
    """Check that resolved path is inside project root."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _check_allowed(
    rel_path: str,
    allowed_dirs: list[str],
    allowed_extensions: list[str],
) -> str | None:
    """Validate path against allowed dirs and extensions. Returns error string or None."""
    # Check extension
    suffix = Path(rel_path).suffix.lower()
    if suffix not in allowed_extensions:
        return f"Error: File type '{suffix}' not allowed. Allowed: {', '.join(allowed_extensions)}"

    # Check directory
    for allowed in allowed_dirs:
        if rel_path.startswith(allowed):
            return None

    return f"Error: Path '{rel_path}' not in allowed directories: {', '.join(allowed_dirs)}"


def make_project_write_tools(
    project_root: Path,
    confirmation_handler: ConfirmationHandler,
    allowed_dirs: list[str],
    allowed_extensions: list[str] | None = None,
) -> list[ToolDefinition]:
    """Create project file write tools with scope restrictions.

    Args:
        project_root: Absolute path to the JARVIS project root.
        confirmation_handler: Handler for diff display and write confirmation.
        allowed_dirs: List of allowed directory prefixes (e.g. ['packages/agents/', 'data/prompts/']).
        allowed_extensions: Allowed file extensions (default: ['.md', '.yaml', '.yml']).

    Returns:
        List of ToolDefinitions for guarded file writes.
    """
    root = project_root.resolve()
    extensions = allowed_extensions or [".md", ".yaml", ".yml"]
    tools: list[ToolDefinition] = []

    # --- write_file ---

    def _write_file(path: str, content: str, reasoning: str = "") -> str:
        """Create a new file. Refuses to overwrite existing files."""
        target = (root / path).resolve()
        if not _is_safe_path(target, root):
            return f"Error: Path '{path}' is outside the project directory."

        error = _check_allowed(path, allowed_dirs, extensions)
        if error:
            return error

        if target.exists():
            return f"Error: File already exists: {path}. Use edit_file to modify it."

        # Show diff (new file = diff against empty)
        diff = compute_diff(path, "", content)

        if reasoning:
            print(f"\n{reasoning}")
        confirmation_handler.present_diff(diff)
        if not confirmation_handler.get_confirmation("Create this file?"):
            return "Write cancelled by user."

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Created: {path}"

    tools.append(ToolDefinition(
        name="write_file",
        description=(
            "Create a new project file. Path is relative to project root. "
            "Shows a diff and requires user confirmation. "
            "Cannot overwrite existing files — use edit_file instead."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root.",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of why this file is being created.",
                },
            },
            "required": ["path", "content"],
        },
        execute=_write_file,
    ))

    # --- edit_file ---

    def _edit_file(path: str, new_content: str, reasoning: str = "") -> str:
        """Replace an existing file's content."""
        target = (root / path).resolve()
        if not _is_safe_path(target, root):
            return f"Error: Path '{path}' is outside the project directory."

        error = _check_allowed(path, allowed_dirs, extensions)
        if error:
            return error

        if not target.exists():
            return f"Error: File not found: {path}. Use write_file for new files."

        original = target.read_text(encoding="utf-8")
        diff = compute_diff(path, original, new_content)

        if reasoning:
            print(f"\n{reasoning}")
        confirmation_handler.present_diff(diff)
        if not confirmation_handler.get_confirmation("Apply this edit?"):
            return "Edit cancelled by user."

        target.write_text(new_content, encoding="utf-8")
        return f"Updated: {path}"

    tools.append(ToolDefinition(
        name="edit_file",
        description=(
            "Edit an existing project file by replacing its content. "
            "Shows a diff and requires user confirmation."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root.",
                },
                "new_content": {
                    "type": "string",
                    "description": "Complete new content for the file.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of what changed and why.",
                },
            },
            "required": ["path", "new_content"],
        },
        execute=_edit_file,
    ))

    # --- create_directory ---

    def _create_directory(path: str) -> str:
        """Create a directory in the project."""
        target = (root / path).resolve()
        if not _is_safe_path(target, root):
            return f"Error: Path '{path}' is outside the project directory."

        error = _check_allowed(path + "/placeholder.md", allowed_dirs, extensions)
        if error:
            # Strip the extension error part since we're creating a directory
            for allowed in allowed_dirs:
                if path.startswith(allowed.rstrip("/")):
                    break
            else:
                return f"Error: Path '{path}' not in allowed directories: {', '.join(allowed_dirs)}"

        target.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {path}"

    tools.append(ToolDefinition(
        name="create_directory",
        description="Create a directory in the project. No confirmation needed.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to project root.",
                },
            },
            "required": ["path"],
        },
        execute=_create_directory,
    ))

    return tools
