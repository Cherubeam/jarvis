"""
Codebase read tools — read-only access to JARVIS source files.

Factory pattern: make_codebase_tools() returns closures that capture project_root.
"""

import re
from pathlib import Path

from packages.core.tools.base import ToolDefinition

_MAX_FILE_BYTES = 50_000  # 50 KB cap
_MAX_SEARCH_RESULTS = 50


def _is_safe_path(path: Path, root: Path) -> bool:
    """Check that resolved path is inside project root (no traversal)."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def make_codebase_tools(project_root: Path) -> list[ToolDefinition]:
    """Create read-only codebase exploration tools.

    Args:
        project_root: Absolute path to the JARVIS project root.

    Returns:
        List of ToolDefinitions for codebase reading.
    """
    root = project_root.resolve()
    tools: list[ToolDefinition] = []

    # --- read_source_file ---

    def _read_source_file(path: str) -> str:
        """Read a project file. Path is relative to project root."""
        target = (root / path).resolve()
        if not _is_safe_path(target, root):
            return f"Error: Path '{path}' is outside the project directory."
        if not target.is_file():
            return f"Error: File not found: {path}"
        if target.stat().st_size > _MAX_FILE_BYTES:
            return f"Error: File too large ({target.stat().st_size} bytes, max {_MAX_FILE_BYTES})."
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Error: Cannot read binary file: {path}"

    tools.append(ToolDefinition(
        name="read_source_file",
        description=(
            "Read any file in the JARVIS project. "
            "Path is relative to the project root. "
            "Returns the file content as text. Max 50KB."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root (e.g. 'packages/core/tools/base.py').",
                },
            },
            "required": ["path"],
        },
        execute=_read_source_file,
    ))

    # --- search_code ---

    def _search_code(pattern: str, glob: str = "**/*.py", max_results: int = _MAX_SEARCH_RESULTS) -> str:
        """Regex search across project files."""
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        max_results = min(max_results, _MAX_SEARCH_RESULTS)
        matches: list[str] = []

        for filepath in sorted(root.glob(glob)):
            if not filepath.is_file() or not _is_safe_path(filepath, root):
                continue
            # Skip common non-source dirs
            rel = filepath.relative_to(root)
            parts = rel.parts
            if any(p in (".venv", "__pycache__", ".git", "node_modules") for p in parts):
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    matches.append(f"{rel}:{i}: {line.rstrip()}")
                    if len(matches) >= max_results:
                        return "\n".join(matches) + f"\n\n[Truncated at {max_results} results]"

        if not matches:
            return f"No matches found for pattern '{pattern}' in '{glob}'."
        return "\n".join(matches)

    tools.append(ToolDefinition(
        name="search_code",
        description=(
            "Search project files using a regex pattern. "
            "Returns file:line matches. Use glob to filter file types."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for.",
                },
                "glob": {
                    "type": "string",
                    "description": "Glob pattern for files to search (default: '**/*.py').",
                    "default": "**/*.py",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matches to return (default: 50).",
                    "default": 50,
                },
            },
            "required": ["pattern"],
        },
        execute=_search_code,
    ))

    # --- list_directory ---

    def _list_directory(path: str = "", pattern: str = "*") -> str:
        """List directory contents with type indicators."""
        target = (root / path).resolve() if path else root
        if not _is_safe_path(target, root):
            return f"Error: Path '{path}' is outside the project directory."
        if not target.is_dir():
            return f"Error: Not a directory: {path}"

        entries: list[str] = []
        for item in sorted(target.glob(pattern)):
            if item.name.startswith(".") and item.name != ".gitignore":
                continue
            if item.name in ("__pycache__", ".venv", "node_modules"):
                continue
            rel = item.relative_to(root)
            if item.is_dir():
                entries.append(f"{rel}/")
            else:
                entries.append(str(rel))

        if not entries:
            return f"Empty directory: {path or '.'}"
        return "\n".join(entries)

    tools.append(ToolDefinition(
        name="list_directory",
        description=(
            "List contents of a project directory. "
            "Path is relative to project root (empty string for root). "
            "Returns entries with / suffix for directories."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to project root (default: root).",
                    "default": "",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter entries (default: '*').",
                    "default": "*",
                },
            },
            "required": [],
        },
        execute=_list_directory,
    ))

    # --- read_architecture_map ---

    def _read_architecture_map() -> str:
        """Read the codebase map file."""
        map_path = root / "data" / "codebase_map.md"
        if not map_path.is_file():
            return "Error: Codebase map not found. Run scripts/generate_codebase_map.py to generate it."
        return map_path.read_text(encoding="utf-8")

    tools.append(ToolDefinition(
        name="read_architecture_map",
        description=(
            "Read the codebase architecture map — a compact summary of all modules, "
            "agents, tools, skills, and config structure."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        execute=_read_architecture_map,
    ))

    return tools
