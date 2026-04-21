"""
Diff computation and formatting for Obsidian vault writes.

UI-agnostic: produces structured diffs that can be rendered for CLI or API.
Uses only stdlib difflib — no new dependencies.
"""

import difflib
from dataclasses import dataclass, field


@dataclass
class DiffLine:
    """A single line in a diff."""

    type: str  # "unchanged", "added", "removed"
    content: str
    line_number: int | None = None  # Line number in the original or proposed file


@dataclass
class VaultDiff:
    """A computed diff between original and proposed vault content."""

    file_path: str  # Relative path within vault
    original_content: str
    proposed_content: str
    diff_lines: list[DiffLine] = field(default_factory=list)
    summary: str = ""


def compute_diff(
    file_path: str,
    original: str,
    proposed: str,
    context_lines: int = 3,
) -> VaultDiff:
    """Compute a unified diff between original and proposed content.

    Args:
        file_path: Relative path within vault (for display).
        original: Original file content.
        proposed: Proposed file content.
        context_lines: Number of context lines around changes.

    Returns:
        VaultDiff with parsed diff lines and summary.
    """
    original_lines = original.splitlines(keepends=True)
    proposed_lines = proposed.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        proposed_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=context_lines,
    )

    diff_lines: list[DiffLine] = []
    added_count = 0
    removed_count = 0
    line_num = 0

    for line in diff:
        # Skip the file headers
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            # Parse hunk header for line numbers
            diff_lines.append(DiffLine(type="unchanged", content=line.rstrip("\n")))
            continue

        content = line.rstrip("\n")
        if line.startswith("+"):
            diff_lines.append(DiffLine(type="added", content=content[1:]))
            added_count += 1
        elif line.startswith("-"):
            diff_lines.append(DiffLine(type="removed", content=content[1:]))
            removed_count += 1
        else:
            diff_lines.append(DiffLine(type="unchanged", content=content[1:] if content else ""))
            line_num += 1

    # Build summary
    parts = []
    if added_count:
        parts.append(f"+{added_count} line{'s' if added_count != 1 else ''}")
    if removed_count:
        parts.append(f"-{removed_count} line{'s' if removed_count != 1 else ''}")
    summary = ", ".join(parts) if parts else "No changes"

    return VaultDiff(
        file_path=file_path,
        original_content=original,
        proposed_content=proposed,
        diff_lines=diff_lines,
        summary=summary,
    )


def format_diff_for_cli(diff: VaultDiff) -> str:
    """Format a VaultDiff for colored terminal output.

    Uses ANSI escape codes for coloring.
    """
    if not diff.diff_lines:
        return f"  {diff.file_path}: No changes"

    lines = [f"  {diff.file_path} ({diff.summary})", ""]

    GREEN = "\033[32m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    RESET = "\033[0m"

    for dl in diff.diff_lines:
        if dl.type == "added":
            lines.append(f"  {GREEN}+ {dl.content}{RESET}")
        elif dl.type == "removed":
            lines.append(f"  {RED}- {dl.content}{RESET}")
        elif dl.content.startswith("@@"):
            lines.append(f"  {CYAN}{dl.content}{RESET}")
        else:
            lines.append(f"    {dl.content}")

    return "\n".join(lines)


def format_diff_for_api(diff: VaultDiff) -> dict:
    """Format a VaultDiff as a JSON-serializable dictionary for GUI/API use."""
    return {
        "file_path": diff.file_path,
        "summary": diff.summary,
        "has_changes": bool(diff.diff_lines),
        "lines": [{"type": dl.type, "content": dl.content} for dl in diff.diff_lines],
    }
