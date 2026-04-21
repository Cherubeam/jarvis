"""
Git tools — safe, read-heavy git operations for the developer agent.

Factory pattern: make_git_tools() returns closures that capture project_root.
Intentionally limited: no push, merge, rebase, or delete.
"""

import re
import subprocess
from pathlib import Path

from packages.core.tools.base import ToolDefinition

_BRANCH_PREFIX_RE = re.compile(r"^(feat|fix)/jarvis-")
_COMMIT_TAG = "[JARVIS-auto]"
_TIMEOUT = 30  # seconds


def _run_git(args: list[str], cwd: Path) -> str:
    """Run a git command and return stdout. Returns error string on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr.strip() or result.stdout.strip()}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"Error: git {args[0]} timed out after {_TIMEOUT}s."
    except FileNotFoundError:
        return "Error: git not found on PATH."


def make_git_tools(project_root: Path) -> list[ToolDefinition]:
    """Create git operation tools scoped to the project root.

    Args:
        project_root: Absolute path to the JARVIS project root.

    Returns:
        List of ToolDefinitions for git operations.
    """
    root = project_root.resolve()
    tools: list[ToolDefinition] = []

    # --- git_status ---

    def _git_status() -> str:
        return _run_git(["status", "--short"], root) or "Working tree clean."

    tools.append(
        ToolDefinition(
            name="git_status",
            description="Show git working tree status (short format).",  # pragma: no mutate
            parameters={"type": "object", "properties": {}, "required": []},
            execute=_git_status,
        )
    )

    # --- git_diff ---

    def _git_diff(staged: bool = False) -> str:
        args = ["diff", "--staged"] if staged else ["diff"]
        output = _run_git(args, root)
        return output or "No differences."

    tools.append(
        ToolDefinition(
            name="git_diff",
            description="Show git diff. Set staged=true for staged changes.",  # pragma: no mutate
            parameters={
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "Show staged changes only (default: false).",  # pragma: no mutate
                        "default": False,
                    },
                },
                "required": [],
            },
            execute=_git_diff,
        )
    )

    # --- git_branch ---

    def _git_branch(name: str) -> str:
        if not _BRANCH_PREFIX_RE.match(name):
            return (
                f"Error: Branch name must start with 'feat/jarvis-' or 'fix/jarvis-'. Got: {name}"
            )
        return _run_git(["switch", "-c", name], root)

    tools.append(
        ToolDefinition(
            name="git_branch",
            description=(
                "Create and switch to a new git branch. "  # pragma: no mutate
                "Name must start with 'feat/jarvis-' or 'fix/jarvis-'."  # pragma: no mutate
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Branch name (e.g. 'feat/jarvis-add-greeting-agent').",  # pragma: no mutate
                    },
                },
                "required": ["name"],
            },
            execute=_git_branch,
        )
    )

    # --- git_add ---

    def _git_add(paths: list[str]) -> str:
        if not paths:
            return "Error: No paths specified."
        # Validate no wildcard / -A usage
        for p in paths:
            if p in ("-A", "--all", "."):
                return "Error: Cannot use '-A', '--all', or '.' — specify files explicitly."
        return _run_git(["add", *paths], root)

    tools.append(
        ToolDefinition(
            name="git_add",
            description="Stage specific files for commit. Never stages all files — list paths explicitly.",  # pragma: no mutate
            parameters={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths to stage.",  # pragma: no mutate
                    },
                },
                "required": ["paths"],
            },
            execute=_git_add,
        )
    )

    # --- git_commit ---

    def _git_commit(message: str) -> str:
        if not message.strip():
            return "Error: Commit message cannot be empty."
        tagged_message = f"{message.strip()} {_COMMIT_TAG}"
        return _run_git(["commit", "-m", tagged_message], root)

    tools.append(
        ToolDefinition(
            name="git_commit",
            description=(
                "Create a git commit with the given message. "  # pragma: no mutate
                "Automatically appends [JARVIS-auto] tag."  # pragma: no mutate
            ),
            parameters={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Commit message (without the [JARVIS-auto] tag).",  # pragma: no mutate
                    },
                },
                "required": ["message"],
            },
            execute=_git_commit,
        )
    )

    # --- git_log ---

    def _git_log(n: int = 10) -> str:
        n = min(n, 50)
        return _run_git(["log", "--oneline", f"-{n}"], root)

    tools.append(
        ToolDefinition(
            name="git_log",
            description="Show recent git commit history (oneline format).",  # pragma: no mutate
            parameters={
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "Number of commits to show (default: 10, max: 50).",  # pragma: no mutate
                        "default": 10,
                    },
                },
                "required": [],
            },
            execute=_git_log,
        )
    )

    return tools
