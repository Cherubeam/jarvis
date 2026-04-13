"""Tests for packages.core.tools.blog_tools."""

import pytest
from pathlib import Path
from unittest.mock import patch

from packages.core.filesystem_access import AccessLevel, AccessRule, FilesystemGuard
from packages.integrations.obsidian.vault import VaultConfig
from packages.integrations.obsidian.diff import VaultDiff
from packages.integrations.obsidian.writer import ConfirmationHandler
from packages.core.tools.blog_tools import make_blog_tools


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


@pytest.fixture
def blog_vault(tmp_path):
    """Create a vault with blog dir and template."""
    blog_dir = tmp_path / "03 – Areas" / "02 – Substack"
    blog_dir.mkdir(parents=True)
    template_dir = tmp_path / "99 – Meta" / "00 – Templates"
    template_dir.mkdir(parents=True)
    template = template_dir / "(TEMPLATE) Blog Post.md"
    template.write_text("---\ntitle: \"\"\ntags: []\n---\n\n", encoding="utf-8")

    guard = _guard(
        (blog_dir.resolve(), AccessLevel.READ_WRITE),
        (template_dir.resolve(), AccessLevel.READ),  # templates are read-only
    )
    config = VaultConfig(
        vault_path=tmp_path,
        filesystem_guard=guard,
    )
    return config, blog_dir, template


@pytest.fixture
def tools(blog_vault):
    config, blog_dir, template = blog_vault
    handler = MockConfirmationHandler(confirm=True)
    return make_blog_tools(
        config, handler,
        blog_dir="03 – Areas/02 – Substack",
        template_path="99 – Meta/00 – Templates/(TEMPLATE) Blog Post.md",
    ), blog_dir, template, handler


def _get_tool(tools_list, name):
    return next(t for t in tools_list if t.name == name)


# ==================== make_blog_tools ====================


@pytest.mark.unit
class TestMakeBlogTools:
    def test_returns_four_tools(self, tools):
        tool_list, *_ = tools
        assert len(tool_list) == 4

    def test_tool_names(self, tools):
        tool_list, *_ = tools
        names = {t.name for t in tool_list}
        assert names == {"list_blog_posts", "read_blog_post", "create_blog_post", "edit_blog_post"}

    def test_all_have_litellm_format(self, tools):
        tool_list, *_ = tools
        for t in tool_list:
            fmt = t.to_litellm_format()
            assert fmt["type"] == "function"
            assert "name" in fmt["function"]

    def test_all_have_descriptions(self, tools):
        """Every tool must have a non-None, non-empty description string."""
        tool_list, *_ = tools
        for t in tool_list:
            assert isinstance(t.description, str), f"{t.name} description is not a string"
            assert len(t.description) > 0, f"{t.name} has empty description"

    def test_list_tool_schema(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "list_blog_posts")
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"subfolder"}
        assert params["properties"]["subfolder"]["type"] == "string"
        assert params["required"] == []

    def test_read_tool_schema(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "read_blog_post")
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["required"] == ["path"]

    def test_create_tool_schema(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "create_blog_post")
        params = tool.parameters
        assert params["type"] == "object"
        props = params["properties"]
        assert set(props.keys()) == {"filename", "content", "use_template"}
        assert props["filename"]["type"] == "string"
        assert props["content"]["type"] == "string"
        assert props["use_template"]["type"] == "boolean"
        assert props["use_template"]["default"] is True
        assert params["required"] == ["filename", "content"]

    def test_edit_tool_schema(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "edit_blog_post")
        params = tool.parameters
        assert params["type"] == "object"
        props = params["properties"]
        assert set(props.keys()) == {"path", "new_content", "reasoning"}
        assert props["path"]["type"] == "string"
        assert props["new_content"]["type"] == "string"
        assert props["reasoning"]["type"] == "string"
        assert params["required"] == ["path", "new_content"]


# ==================== list_blog_posts ====================


@pytest.mark.unit
class TestListBlogPosts:
    def test_lists_markdown_files(self, tools):
        tool_list, blog_dir, *_ = tools
        (blog_dir / "post-one.md").write_text("# One")
        (blog_dir / "post-two.md").write_text("# Two")

        tool = _get_tool(tool_list, "list_blog_posts")
        result = tool.execute()

        assert "post-one.md" in result
        assert "post-two.md" in result
        # Verify clean newline-separated format (no extra characters around separator)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            assert line == line.strip()  # no leading/trailing whitespace or junk
            assert "XX" not in line  # no mutation artifacts
            assert line.endswith(".md")  # each line is a clean path

    def test_empty_directory(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "list_blog_posts")
        result = tool.execute()
        assert result == "No blog posts found."

    def test_subfolder_filter(self, tools):
        tool_list, blog_dir, *_ = tools
        sub = blog_dir / "drafts"
        sub.mkdir()
        (sub / "draft.md").write_text("# Draft")
        (blog_dir / "published.md").write_text("# Published")

        tool = _get_tool(tool_list, "list_blog_posts")
        result = tool.execute(subfolder="drafts")

        assert "draft.md" in result
        assert "published.md" not in result

    def test_recursive_listing(self, tools):
        tool_list, blog_dir, *_ = tools
        sub = blog_dir / "nested"
        sub.mkdir()
        (sub / "deep.md").write_text("# Deep")

        tool = _get_tool(tool_list, "list_blog_posts")
        result = tool.execute()

        assert "deep.md" in result

    def test_paths_are_vault_relative(self, tools):
        """Listed paths include the blog_dir prefix (vault-relative, not blog-dir-relative)."""
        tool_list, blog_dir, *_ = tools
        (blog_dir / "post.md").write_text("# Post")

        tool = _get_tool(tool_list, "list_blog_posts")
        result = tool.execute()

        # Path should be relative to vault root, including the blog dir
        assert "03 – Areas/02 – Substack/post.md" in result


# ==================== read_blog_post ====================


@pytest.mark.unit
class TestReadBlogPost:
    def test_reads_file_content(self, tools):
        tool_list, blog_dir, *_ = tools
        (blog_dir / "test.md").write_text("# Test Post\n\nHello world.")

        tool = _get_tool(tool_list, "read_blog_post")
        result = tool.execute(path="03 – Areas/02 – Substack/test.md")

        assert result == "# Test Post\n\nHello world."

    def test_file_not_found(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "read_blog_post")
        result = tool.execute(path="03 – Areas/02 – Substack/missing.md")
        assert result == "Error: File not found: 03 – Areas/02 – Substack/missing.md"

    def test_reads_template(self, tools):
        tool_list, blog_dir, template, *_ = tools
        tool = _get_tool(tool_list, "read_blog_post")
        result = tool.execute(path="99 – Meta/00 – Templates/(TEMPLATE) Blog Post.md")
        assert "title" in result


# ==================== create_blog_post ====================


@pytest.mark.unit
class TestCreateBlogPost:
    def test_creates_new_file(self, tools):
        tool_list, blog_dir, *_ = tools
        tool = _get_tool(tool_list, "create_blog_post")
        result = tool.execute(filename="new-post.md", content="# My Post\n\nGreat content.", use_template=False)

        assert "Successfully" in result
        assert (blog_dir / "new-post.md").exists()

    def test_creates_with_template(self, tools):
        tool_list, blog_dir, *_ = tools
        tool = _get_tool(tool_list, "create_blog_post")
        result = tool.execute(filename="templated.md", content="# My Post", use_template=True)

        content = (blog_dir / "templated.md").read_text(encoding="utf-8")
        assert "title" in content  # from template
        assert "# My Post" in content  # user content
        # Template must come BEFORE user content, separated by \n\n
        title_pos = content.index("title")
        post_pos = content.index("# My Post")
        assert title_pos < post_pos
        assert "\n\n# My Post" in content  # double newline separator
        # Template trailing newlines must be stripped (rstrip), not leading (lstrip)
        assert not content.startswith("\n")  # template content starts at beginning

    def test_default_uses_template(self, tools):
        """use_template defaults to True — omitting it should prepend template."""
        tool_list, blog_dir, *_ = tools
        tool = _get_tool(tool_list, "create_blog_post")
        # Call WITHOUT use_template — should default to True
        result = tool.execute(filename="default-template.md", content="# Default Post")
        content = (blog_dir / "default-template.md").read_text(encoding="utf-8")
        assert "title" in content  # template was prepended

    def test_template_rstrip_only_newlines(self, blog_vault):
        """rstrip must strip only newlines, not all whitespace; must strip trailing not leading."""
        config, blog_dir, template = blog_vault
        # Template with trailing spaces+newlines — rstrip("\n") preserves spaces
        template.write_text("---\ntitle: \"\"\n---\n  \n", encoding="utf-8")
        handler = MockConfirmationHandler(confirm=True)
        tool_list = make_blog_tools(
            config, handler,
            blog_dir="03 – Areas/02 – Substack",
            template_path="99 – Meta/00 – Templates/(TEMPLATE) Blog Post.md",
        )
        tool = _get_tool(tool_list, "create_blog_post")
        tool.execute(filename="rstrip-test.md", content="# Body", use_template=True)
        content = (blog_dir / "rstrip-test.md").read_text(encoding="utf-8")
        # rstrip("\n") leaves trailing spaces, then \n\n is appended
        # "---\ntitle: \"\"\n---\n  " + "\n\n" + "# Body"
        assert "  \n\n# Body" in content  # trailing spaces preserved before separator

    def test_template_requires_both_conditions(self, tools):
        """Template is only used when use_template=True AND template file exists."""
        tool_list, blog_dir, template, *_ = tools
        tool = _get_tool(tool_list, "create_blog_post")
        # use_template=False should skip template even if file exists
        result = tool.execute(filename="no-template.md", content="# Plain Post", use_template=False)
        content = (blog_dir / "no-template.md").read_text(encoding="utf-8")
        assert "title" not in content  # template NOT prepended
        assert content == "# Plain Post"

    def test_rejects_existing_file(self, tools):
        tool_list, blog_dir, *_ = tools
        (blog_dir / "exists.md").write_text("already here")

        tool = _get_tool(tool_list, "create_blog_post")
        result = tool.execute(filename="exists.md", content="new")

        assert result == "Error: File already exists: exists.md. Use edit_blog_post to modify it."

    def test_rejected_by_user(self, blog_vault):
        config, blog_dir, template = blog_vault
        handler = MockConfirmationHandler(confirm=False)
        tool_list = make_blog_tools(
            config, handler,
            blog_dir="03 – Areas/02 – Substack",
            template_path="99 – Meta/00 – Templates/(TEMPLATE) Blog Post.md",
        )
        tool = _get_tool(tool_list, "create_blog_post")
        result = tool.execute(filename="rejected.md", content="content", use_template=False)

        assert "cancelled" in result.lower()
        assert not (blog_dir / "rejected.md").exists()


# ==================== edit_blog_post ====================


@pytest.mark.unit
class TestEditBlogPost:
    def test_edits_existing_file(self, tools):
        tool_list, blog_dir, *_ = tools
        post = blog_dir / "post.md"
        post.write_text("# Old Title\n\nOld content.")

        tool = _get_tool(tool_list, "edit_blog_post")
        result = tool.execute(
            path="03 – Areas/02 – Substack/post.md",
            new_content="# New Title\n\nNew content.",
            reasoning="Improved the title",
        )

        assert "Successfully" in result
        assert post.read_text(encoding="utf-8") == "# New Title\n\nNew content."

    def test_reasoning_passed_through(self, blog_vault):
        """Reasoning argument must be forwarded to write_note, not dropped."""
        config, blog_dir, template = blog_vault
        handler = MockConfirmationHandler(confirm=True)
        tool_list = make_blog_tools(
            config, handler,
            blog_dir="03 – Areas/02 – Substack",
            template_path="99 – Meta/00 – Templates/(TEMPLATE) Blog Post.md",
        )
        post = blog_dir / "reason-test.md"
        post.write_text("old content")

        tool = _get_tool(tool_list, "edit_blog_post")
        with patch("packages.core.tools.blog_tools.write_note", wraps=__import__("packages.integrations.obsidian.writer", fromlist=["write_note"]).write_note) as mock_write:
            tool.execute(
                path="03 – Areas/02 – Substack/reason-test.md",
                new_content="new content",
                reasoning="Improved clarity",
            )
            mock_write.assert_called_once()
            assert mock_write.call_args.kwargs.get("reasoning") == "Improved clarity" or \
                   (len(mock_write.call_args.args) > 4 and mock_write.call_args.args[4] == "Improved clarity")

    def test_reasoning_default_is_empty(self, blog_vault):
        """Default reasoning should be empty string, not some other value."""
        config, blog_dir, template = blog_vault
        handler = MockConfirmationHandler(confirm=True)
        tool_list = make_blog_tools(
            config, handler,
            blog_dir="03 – Areas/02 – Substack",
            template_path="99 – Meta/00 – Templates/(TEMPLATE) Blog Post.md",
        )
        post = blog_dir / "no-reason.md"
        post.write_text("old content")

        tool = _get_tool(tool_list, "edit_blog_post")
        with patch("packages.core.tools.blog_tools.write_note", wraps=__import__("packages.integrations.obsidian.writer", fromlist=["write_note"]).write_note) as mock_write:
            tool.execute(
                path="03 – Areas/02 – Substack/no-reason.md",
                new_content="new content",
            )
            mock_write.assert_called_once()
            # reasoning kwarg should be "" (empty string), not None or "XXXX"
            assert mock_write.call_args.kwargs.get("reasoning") == ""

    def test_file_not_found(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "edit_blog_post")
        result = tool.execute(
            path="03 – Areas/02 – Substack/ghost.md",
            new_content="content",
        )
        assert result == "Error: File not found: 03 – Areas/02 – Substack/ghost.md. Use create_blog_post for new files."

    def test_rejects_template_edit(self, tools):
        """Template dir has read-only access — edits are blocked by validate_write."""
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "edit_blog_post")
        result = tool.execute(
            path="99 – Meta/00 – Templates/(TEMPLATE) Blog Post.md",
            new_content="hacked template",
        )
        assert result == "Error: Cannot edit this file (read-only)."

    def test_rejected_by_user(self, blog_vault):
        config, blog_dir, template = blog_vault
        post = blog_dir / "post.md"
        post.write_text("original content")
        handler = MockConfirmationHandler(confirm=False)
        tool_list = make_blog_tools(
            config, handler,
            blog_dir="03 – Areas/02 – Substack",
            template_path="99 – Meta/00 – Templates/(TEMPLATE) Blog Post.md",
        )
        tool = _get_tool(tool_list, "edit_blog_post")
        result = tool.execute(
            path="03 – Areas/02 – Substack/post.md",
            new_content="modified",
        )

        assert "cancelled" in result.lower()
        assert post.read_text(encoding="utf-8") == "original content"
