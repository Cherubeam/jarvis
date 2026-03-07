"""Tests for packages.core.tools.blog_tools."""

import pytest
from pathlib import Path

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


@pytest.fixture
def blog_vault(tmp_path):
    """Create a vault with blog dir and template."""
    blog_dir = tmp_path / "03 – Areas" / "02 – Substack"
    blog_dir.mkdir(parents=True)
    template_dir = tmp_path / "99 – Meta" / "00 – Templates"
    template_dir.mkdir(parents=True)
    template = template_dir / "(TEMPLATE) Blog Post.md"
    template.write_text("---\ntitle: \"\"\ntags: []\n---\n\n", encoding="utf-8")

    config = VaultConfig(
        vault_path=tmp_path,
        allowed_dirs=[blog_dir.resolve(), template_dir.resolve()],
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

    def test_empty_directory(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "list_blog_posts")
        result = tool.execute()
        assert "No blog posts found" in result

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


# ==================== read_blog_post ====================


@pytest.mark.unit
class TestReadBlogPost:
    def test_reads_file_content(self, tools):
        tool_list, blog_dir, *_ = tools
        (blog_dir / "test.md").write_text("# Test Post\n\nHello world.")

        tool = _get_tool(tool_list, "read_blog_post")
        result = tool.execute(path="03 – Areas/02 – Substack/test.md")

        assert "# Test Post" in result
        assert "Hello world." in result

    def test_file_not_found(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "read_blog_post")
        result = tool.execute(path="03 – Areas/02 – Substack/missing.md")
        assert "Error" in result

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

    def test_rejects_existing_file(self, tools):
        tool_list, blog_dir, *_ = tools
        (blog_dir / "exists.md").write_text("already here")

        tool = _get_tool(tool_list, "create_blog_post")
        result = tool.execute(filename="exists.md", content="new")

        assert "already exists" in result

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

    def test_file_not_found(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "edit_blog_post")
        result = tool.execute(
            path="03 – Areas/02 – Substack/ghost.md",
            new_content="content",
        )
        assert "not found" in result.lower()

    def test_rejects_template_edit(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "edit_blog_post")
        result = tool.execute(
            path="99 – Meta/00 – Templates/(TEMPLATE) Blog Post.md",
            new_content="hacked template",
        )
        assert "template" in result.lower()
        assert "read-only" in result.lower()

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
