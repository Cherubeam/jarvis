"""
Suggest improvements tool — shows a preview diff without writing to disk.

Generic tool that works with any file in the vault's allowed directories.
Uses the closure pattern to capture VaultConfig and ConfirmationHandler.
"""

from packages.core.tools.base import ToolDefinition
from packages.integrations.obsidian.diff import compute_diff
from packages.integrations.obsidian.vault import VaultConfig, read_note
from packages.integrations.obsidian.writer import ConfirmationHandler


def make_suggest_improvements_tool(
    vault_config: VaultConfig,
    confirmation_handler: ConfirmationHandler,
) -> ToolDefinition:
    """Create a tool that shows suggested improvements as a preview diff.

    Args:
        vault_config: Vault configuration with path validation.
        confirmation_handler: Handler for diff display (present_diff only).

    Returns:
        A ToolDefinition for previewing suggested improvements.
    """

    def _suggest(path: str, improved_content: str, reasoning: str = "") -> str:
        full_path = (vault_config.vault_path / path).resolve()

        if not full_path.exists():
            return f"Error: File not found: {path}"

        try:
            original = read_note(full_path, vault_config)
        except PermissionError as e:
            return f"Error: {e}"

        rel_path = str(full_path.relative_to(vault_config.vault_path))
        diff = compute_diff(rel_path, original, improved_content)

        if not diff.diff_lines:
            return "No changes to suggest — the content looks good as-is."

        if reasoning:
            print(f"\n{reasoning}")

        confirmation_handler.present_diff(diff)

        return (
            f"Suggested improvements displayed to user ({diff.summary}). "
            "The changes have NOT been applied. The user can discuss them, "
            "ask for modifications, or request applying via edit_blog_post."
        )

    return ToolDefinition(
        name="suggest_improvements",
        description=(
            "Show suggested improvements to a file as a colored diff — preview only, "
            "nothing is written. Use this to propose concrete changes the user can "
            "review and discuss before deciding to apply them."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to the vault root.",
                },
                "improved_content": {
                    "type": "string",
                    "description": "The complete improved content for the file.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of what was changed and why (shown to user before the diff).",
                },
            },
            "required": ["path", "improved_content"],
        },
        execute=_suggest,
    )
