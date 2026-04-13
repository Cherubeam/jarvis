"""Tests for packages.core.tools.vault_write_tools."""

import pytest
from pathlib import Path

from packages.core.filesystem_access import AccessLevel, AccessRule, FilesystemGuard
from packages.integrations.obsidian.vault import VaultConfig
from packages.integrations.obsidian.diff import VaultDiff
from packages.integrations.obsidian.writer import ConfirmationHandler
from packages.core.tools.vault_write_tools import make_vault_write_tools


class MockConfirmationHandler(ConfirmationHandler):
    def __init__(self, confirm: bool = True):
        self.confirm = confirm
        self.presented_diff: VaultDiff | None = None

    def present_diff(self, diff: VaultDiff) -> None:
        self.presented_diff = diff

    def get_confirmation(self, prompt: str = "Apply this change?") -> bool:
        return self.confirm


def _guard(*rules: tuple[Path, AccessLevel]) -> FilesystemGuard:
    return FilesystemGuard([AccessRule(path=p, access=a) for p, a in rules])


# ==================== With target_dir ====================


@pytest.fixture
def vault_with_target(tmp_path):
    """Vault with a target directory and template."""
    target = tmp_path / "Patterns"
    target.mkdir()
    template_dir = tmp_path / "Templates"
    template_dir.mkdir()
    template = template_dir / "Pattern Template.md"
    template.write_text("---\ntype: pattern\n---\n\n", encoding="utf-8")

    guard = _guard(
        (target.resolve(), AccessLevel.READ_WRITE),
        (template_dir.resolve(), AccessLevel.READ),
    )
    config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
    return config, target, template


@pytest.fixture
def tools_with_target(vault_with_target):
    config, target, template = vault_with_target
    handler = MockConfirmationHandler(confirm=True)
    tools = make_vault_write_tools(
        config, handler,
        target_dir="Patterns",
        template_path="Templates/Pattern Template.md",
    )
    return tools, target, template, handler, config


# ==================== Without target_dir ====================


@pytest.fixture
def vault_no_target(tmp_path):
    """Vault without a target directory."""
    guard = _guard((tmp_path.resolve(), AccessLevel.READ_WRITE))
    config = VaultConfig(vault_path=tmp_path, filesystem_guard=guard)
    return config


@pytest.fixture
def tools_no_target(vault_no_target):
    handler = MockConfirmationHandler(confirm=True)
    tools = make_vault_write_tools(vault_no_target, handler)
    return tools, vault_no_target, handler


def _get_tool(tools_list, name):
    return next((t for t in tools_list if t.name == name), None)


# ==================== make_vault_write_tools ====================


@pytest.mark.unit
class TestMakeVaultWriteTools:
    def test_with_target_returns_three_tools(self, tools_with_target):
        tools, *_ = tools_with_target
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert names == {"create_note", "edit_note", "list_notes_in_dir"}

    def test_without_target_returns_two_tools(self, tools_no_target):
        tools, *_ = tools_no_target
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"create_note", "edit_note"}

    def test_all_have_litellm_format(self, tools_with_target):
        tools, *_ = tools_with_target
        for t in tools:
            fmt = t.to_litellm_format()
            assert fmt["type"] == "function"
            assert "name" in fmt["function"]

    # --- Schema validation (kills dict key/value mutations) ---

    def test_create_note_schema(self, tools_with_target):
        tools, *_ = tools_with_target
        tool = _get_tool(tools, "create_note")
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path", "content", "use_template"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["properties"]["content"]["type"] == "string"
        assert params["properties"]["use_template"]["type"] == "boolean"
        assert params["properties"]["use_template"]["default"] is True
        assert params["required"] == ["path", "content"]

    def test_edit_note_schema(self, tools_with_target):
        tools, *_ = tools_with_target
        tool = _get_tool(tools, "edit_note")
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path", "new_content", "reasoning"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["properties"]["new_content"]["type"] == "string"
        assert params["properties"]["reasoning"]["type"] == "string"
        assert params["required"] == ["path", "new_content"]

    def test_list_notes_in_dir_schema(self, tools_with_target):
        tools, *_ = tools_with_target
        tool = _get_tool(tools, "list_notes_in_dir")
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"subfolder"}
        assert params["properties"]["subfolder"]["type"] == "string"
        assert params["required"] == []


# ==================== create_note ====================


@pytest.mark.unit
class TestCreateNote:
    def test_creates_new_file_in_target_dir(self, tools_with_target):
        tools, target, *_ = tools_with_target
        tool = _get_tool(tools, "create_note")
        result = tool.execute(path="My New Pattern.md", content="# My Pattern", use_template=False)

        assert "Successfully" in result
        assert (target / "My New Pattern.md").exists()

    def test_creates_with_template(self, tools_with_target):
        tools, target, *_ = tools_with_target
        tool = _get_tool(tools, "create_note")
        result = tool.execute(path="Templated.md", content="# Pattern Body", use_template=True)

        content = (target / "Templated.md").read_text(encoding="utf-8")
        assert "type: pattern" in content  # from template
        assert "# Pattern Body" in content  # user content
        # Template and content are joined with \n\n (double newline separator)
        assert "---\n\n# Pattern Body" in content

    def test_creates_without_target_dir(self, tools_no_target):
        tools, config, handler = tools_no_target
        tool = _get_tool(tools, "create_note")
        result = tool.execute(path="root-note.md", content="# Root Note", use_template=False)

        assert "Successfully" in result
        assert (config.vault_path / "root-note.md").exists()

    def test_rejects_existing_file(self, tools_with_target):
        tools, target, *_ = tools_with_target
        (target / "exists.md").write_text("already here")

        tool = _get_tool(tools, "create_note")
        result = tool.execute(path="exists.md", content="new")

        assert result == "Error: File already exists: exists.md. Use edit_note to modify it."

    def test_rejected_by_user(self, vault_with_target):
        config, target, template = vault_with_target
        handler = MockConfirmationHandler(confirm=False)
        tools = make_vault_write_tools(
            config, handler,
            target_dir="Patterns",
            template_path="Templates/Pattern Template.md",
        )
        tool = _get_tool(tools, "create_note")
        result = tool.execute(path="rejected.md", content="content", use_template=False)

        assert "cancelled" in result.lower()
        assert not (target / "rejected.md").exists()

    def test_creates_subdirectories(self, tools_with_target):
        tools, target, *_ = tools_with_target
        tool = _get_tool(tools, "create_note")
        result = tool.execute(
            path="Sub Category/Deep Pattern.md",
            content="# Deep",
            use_template=False,
        )

        assert "Successfully" in result
        assert (target / "Sub Category" / "Deep Pattern.md").exists()

    def test_strips_redundant_target_dir_prefix(self, tools_with_target):
        """Agent passes 'Patterns/Note.md' with target_dir='Patterns' — should not double-nest."""
        tools, target, *_ = tools_with_target
        tool = _get_tool(tools, "create_note")
        result = tool.execute(
            path="Patterns/My Pattern.md",
            content="# Pattern",
            use_template=False,
        )

        assert "Successfully" in result
        # File lands at target/My Pattern.md, NOT target/Patterns/My Pattern.md
        assert (target / "My Pattern.md").exists()
        assert not (target / "Patterns" / "My Pattern.md").exists()

    def test_rejects_path_traversal(self, tools_with_target):
        """Agent passes '../../etc/passwd' — should be rejected."""
        tools, target, *_ = tools_with_target
        tool = _get_tool(tools, "create_note")
        result = tool.execute(
            path="../../etc/passwd",
            content="hacked",
            use_template=False,
        )

        assert result == "Error: Path '../../etc/passwd' escapes the target directory."

    def test_rejects_path_traversal_without_target(self, tools_no_target):
        """Path traversal is also blocked without a target_dir."""
        tools, config, handler = tools_no_target
        tool = _get_tool(tools, "create_note")
        result = tool.execute(
            path="../../etc/passwd",
            content="hacked",
            use_template=False,
        )
        assert result == "Error: Path '../../etc/passwd' escapes the target directory."

    def test_default_use_template_true(self, tools_with_target):
        """Omitting use_template should default to True and prepend template."""
        tools, target, *_ = tools_with_target
        tool = _get_tool(tools, "create_note")
        # Call without use_template — should default to True
        result = tool.execute(path="Defaulted.md", content="# Body")

        assert "Successfully" in result
        content = (target / "Defaulted.md").read_text(encoding="utf-8")
        assert "type: pattern" in content  # template prepended

    def test_template_read_error(self, tools_with_target):
        """When template file can't be read, returns error message and skips template."""
        tools, target, template, handler, config = tools_with_target
        # Make template unreadable by deleting it (FileNotFoundError path)
        template.unlink()
        # Create fresh tools pointing to the now-missing template
        new_tools = make_vault_write_tools(
            config, handler,
            target_dir="Patterns",
            template_path="Templates/Pattern Template.md",
        )
        tool = _get_tool(new_tools, "create_note")
        result = tool.execute(path="NoTemplate.md", content="# Body", use_template=True)
        # Template missing: falls through to creating without template
        # (template_full_path.is_file() returns False, so no error — just no template)
        assert "Successfully" in result
        content = (target / "NoTemplate.md").read_text(encoding="utf-8")
        assert content == "# Body"


# ==================== edit_note ====================


@pytest.mark.unit
class TestEditNote:
    def test_edits_existing_file(self, tools_with_target):
        tools, target, _, _, config = tools_with_target
        note = target / "pattern.md"
        note.write_text("# Old Content")

        tool = _get_tool(tools, "edit_note")
        result = tool.execute(
            path="Patterns/pattern.md",
            new_content="# New Content",
            reasoning="Improved clarity",
        )

        assert "Successfully" in result
        assert note.read_text(encoding="utf-8") == "# New Content"

    def test_file_not_found(self, tools_with_target):
        tools, *_ = tools_with_target
        tool = _get_tool(tools, "edit_note")
        result = tool.execute(path="Patterns/ghost.md", new_content="content")
        assert result == "Error: File not found: Patterns/ghost.md. Use create_note for new files."

    def test_rejects_read_only_edit(self, tools_with_target):
        """Template dir has read-only access — edits are blocked."""
        tools, *_ = tools_with_target
        tool = _get_tool(tools, "edit_note")
        result = tool.execute(
            path="Templates/Pattern Template.md",
            new_content="hacked",
        )
        assert result == "Error: Cannot edit this file (read-only)."

    def test_rejected_by_user(self, vault_with_target):
        config, target, template = vault_with_target
        note = target / "pattern.md"
        note.write_text("original")
        handler = MockConfirmationHandler(confirm=False)
        tools = make_vault_write_tools(
            config, handler,
            target_dir="Patterns",
            template_path="Templates/Pattern Template.md",
        )
        tool = _get_tool(tools, "edit_note")
        result = tool.execute(path="Patterns/pattern.md", new_content="modified")

        assert "cancelled" in result.lower()
        assert note.read_text(encoding="utf-8") == "original"


# ==================== list_notes_in_dir ====================


@pytest.mark.unit
class TestListNotesInDir:
    def test_lists_markdown_files(self, tools_with_target):
        tools, target, *_ = tools_with_target
        (target / "Pattern One.md").write_text("# One")
        (target / "Pattern Two.md").write_text("# Two")

        tool = _get_tool(tools, "list_notes_in_dir")
        result = tool.execute()

        assert "Pattern One.md" in result
        assert "Pattern Two.md" in result

    def test_empty_directory(self, tools_with_target):
        tools, *_ = tools_with_target
        tool = _get_tool(tools, "list_notes_in_dir")
        result = tool.execute()
        assert result == "No notes found."

    def test_subfolder_filter(self, tools_with_target):
        tools, target, *_ = tools_with_target
        sub = target / "drafts"
        sub.mkdir()
        (sub / "draft.md").write_text("# Draft")
        (target / "published.md").write_text("# Published")

        tool = _get_tool(tools, "list_notes_in_dir")
        result = tool.execute(subfolder="drafts")

        assert "draft.md" in result
        assert "published.md" not in result

    def test_paths_are_relative_to_target_dir(self, tools_with_target):
        """Listing returns target-relative paths, not vault-root-relative."""
        tools, target, *_ = tools_with_target
        sub = target / "Category"
        sub.mkdir()
        (sub / "Note.md").write_text("# Note")

        tool = _get_tool(tools, "list_notes_in_dir")
        result = tool.execute()

        # Should be "Category/Note.md", NOT "Patterns/Category/Note.md"
        assert "Category/Note.md" in result
        assert "Patterns/Category/Note.md" not in result

    def test_output_is_newline_joined(self, tools_with_target):
        """Output lines are joined by newline, not other separators."""
        tools, target, *_ = tools_with_target
        (target / "A.md").write_text("# A")
        (target / "B.md").write_text("# B")

        tool = _get_tool(tools, "list_notes_in_dir")
        result = tool.execute()

        lines = result.split("\n")
        assert len(lines) == 2
        assert all(line.endswith(".md") for line in lines)

    def test_not_available_without_target(self, tools_no_target):
        tools, *_ = tools_no_target
        tool = _get_tool(tools, "list_notes_in_dir")
        assert tool is None
