"""
Blog post tools for the Writing Agent.

Factory function that creates scoped tools for reading, creating, and editing
blog posts in the Obsidian vault. Uses the closure pattern (like conversation_recall)
to capture VaultConfig and ConfirmationHandler.
"""

from packages.core.tools.base import ToolDefinition
from packages.integrations.obsidian.vault import VaultConfig, list_notes, read_note, validate_write
from packages.integrations.obsidian.writer import ConfirmationHandler, WriteResult, write_note


def make_blog_tools(
    vault_config: VaultConfig,
    confirmation_handler: ConfirmationHandler,
    blog_dir: str,
    template_path: str,
) -> list[ToolDefinition]:
    """Create blog post tools scoped to the given vault and blog directory.

    Args:
        vault_config: Vault configuration with path validation.
        confirmation_handler: Handler for diff display and write confirmation.
        blog_dir: Blog directory relative to vault root (e.g. "03 – Areas/02 – Substack").
        template_path: Template file path relative to vault root.

    Returns:
        List of 4 ToolDefinitions: list, read, create, edit.
    """
    blog_path = vault_config.vault_path / blog_dir
    template_full_path = vault_config.vault_path / template_path

    # --- list_blog_posts ---

    def _list_blog_posts(subfolder: str = "") -> str:
        target = blog_path / subfolder if subfolder else blog_path
        try:
            notes = list_notes(target, vault_config, pattern="**/*.md")
        except PermissionError as e:
            return f"Error: {e}"

        if not notes:
            return "No blog posts found."

        lines = []
        for note in notes:
            rel = note.relative_to(vault_config.vault_path)
            lines.append(str(rel))
        return "\n".join(lines)

    list_tool = ToolDefinition(
        name="list_blog_posts",
        description="List markdown files in the blog posts directory. Optionally filter by subfolder.",  # pragma: no mutate
        parameters={
            "type": "object",
            "properties": {
                "subfolder": {
                    "type": "string",
                    "description": "Optional subfolder within the blog directory to list.",  # pragma: no mutate
                },
            },
            "required": [],
        },
        execute=_list_blog_posts,
    )

    # --- read_blog_post ---

    def _read_blog_post(path: str) -> str:
        full_path = (vault_config.vault_path / path).resolve()
        try:
            content = read_note(full_path, vault_config)
        except PermissionError as e:
            return f"Error: {e}"
        except FileNotFoundError:
            return f"Error: File not found: {path}"
        return content

    read_tool = ToolDefinition(
        name="read_blog_post",
        description="Read the full content of a blog post or template. Path is relative to the vault root.",  # pragma: no mutate
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to the vault root.",  # pragma: no mutate
                },
            },
            "required": ["path"],
        },
        execute=_read_blog_post,
    )

    # --- create_blog_post ---

    def _create_blog_post(filename: str, content: str, use_template: bool = True) -> str:
        target_path = (blog_path / filename).resolve()

        if target_path.exists():
            return f"Error: File already exists: {filename}. Use edit_blog_post to modify it."

        if use_template and template_full_path.is_file():
            try:
                template_content = read_note(template_full_path, vault_config)
                # Prepend template, then append provided content
                full_content = template_content.rstrip("\n") + "\n\n" + content
            except (PermissionError, FileNotFoundError) as e:
                return f"Error reading template: {e}. Creating without template."
        else:
            full_content = content

        result: WriteResult = write_note(
            target_path,
            full_content,
            vault_config,
            confirmation_handler,
        )
        return result.message

    create_tool = ToolDefinition(
        name="create_blog_post",
        description=(  # pragma: no mutate
            "Create a new blog post in the blog directory. "  # pragma: no mutate
            "Set use_template=true to prepend the blog post template. "  # pragma: no mutate
            "The user will see a diff and must confirm before the file is written."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename for the new post (e.g. 'my-new-post.md').",  # pragma: no mutate
                },
                "content": {
                    "type": "string",
                    "description": "Full markdown content for the blog post.",  # pragma: no mutate
                },
                "use_template": {
                    "type": "boolean",
                    "description": "Prepend the blog post template (default: true).",  # pragma: no mutate
                    "default": True,
                },
            },
            "required": ["filename", "content"],
        },
        execute=_create_blog_post,
    )

    # --- edit_blog_post ---

    def _edit_blog_post(path: str, new_content: str, reasoning: str = "") -> str:
        full_path = (vault_config.vault_path / path).resolve()

        # Write guard: reject edits to paths without write access
        if not validate_write(full_path, vault_config):
            return "Error: Cannot edit this file (read-only)."

        if not full_path.exists():
            return f"Error: File not found: {path}. Use create_blog_post for new files."

        result: WriteResult = write_note(
            full_path,
            new_content,
            vault_config,
            confirmation_handler,
            reasoning=reasoning,
        )
        return result.message

    edit_tool = ToolDefinition(
        name="edit_blog_post",
        description=(  # pragma: no mutate
            "Edit an existing blog post by replacing its full content. "  # pragma: no mutate
            "Provide reasoning to explain the changes — it will be shown alongside the diff. "  # pragma: no mutate
            "The user must confirm before the edit is applied. "  # pragma: no mutate
            "Cannot edit template files (read-only)."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to the vault root.",  # pragma: no mutate
                },
                "new_content": {
                    "type": "string",
                    "description": "The complete new content for the file.",  # pragma: no mutate
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of what changed and why (shown to user before diff).",  # pragma: no mutate
                },
            },
            "required": ["path", "new_content"],
        },
        execute=_edit_blog_post,
    )

    return [list_tool, read_tool, create_tool, edit_tool]
