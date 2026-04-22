"""Tests for packages.core.tools.project_write_tools."""

import pytest

from packages.core.tools.project_write_tools import make_project_write_tools


class StubConfirmationHandler:
    """Test confirmation handler that auto-approves or auto-rejects."""

    def __init__(self, approve: bool = True):
        self.approve = approve
        self.diffs_presented: list = []

    def present_diff(self, diff):
        self.diffs_presented.append(diff)

    def get_confirmation(self, prompt=""):
        return self.approve


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project structure."""
    (tmp_path / "packages" / "agents").mkdir(parents=True)
    (tmp_path / "data" / "prompts").mkdir(parents=True)
    (tmp_path / "config").mkdir()
    (tmp_path / "packages" / "agents" / "existing.yaml").write_text("name: test\n")
    return tmp_path


@pytest.fixture
def allowed_dirs():
    return ["packages/agents/", "data/prompts/", "config/"]


@pytest.fixture
def tools_approve(project_dir, allowed_dirs):
    handler = StubConfirmationHandler(approve=True)
    return {
        t.name: t
        for t in make_project_write_tools(
            project_dir,
            handler,
            allowed_dirs,
        )
    }


@pytest.fixture
def tools_reject(project_dir, allowed_dirs):
    handler = StubConfirmationHandler(approve=False)
    return {
        t.name: t
        for t in make_project_write_tools(
            project_dir,
            handler,
            allowed_dirs,
        )
    }


class TestWriteFile:
    def test_create_new_file(self, tools_approve, project_dir):
        result = tools_approve["write_file"].execute(
            path="packages/agents/test.yaml",
            content="name: test-agent\n",
        )
        assert "Created" in result
        assert (project_dir / "packages/agents/test.yaml").exists()

    def test_refuse_overwrite(self, tools_approve):
        result = tools_approve["write_file"].execute(
            path="packages/agents/existing.yaml",
            content="new content\n",
        )
        assert "Error" in result
        assert "already exists" in result

    def test_reject_disallowed_dir(self, tools_approve):
        result = tools_approve["write_file"].execute(
            path="apps/cli/hack.md",
            content="bad content\n",
        )
        assert "Error" in result
        assert "not in allowed" in result

    def test_reject_disallowed_extension(self, tools_approve):
        result = tools_approve["write_file"].execute(
            path="packages/agents/hack.py",
            content="import os\n",
        )
        assert "Error" in result
        assert "not allowed" in result

    def test_user_can_cancel(self, tools_reject):
        result = tools_reject["write_file"].execute(
            path="packages/agents/new.yaml",
            content="test\n",
        )
        assert "cancelled" in result

    def test_creates_parent_dirs(self, tools_approve, project_dir):
        result = tools_approve["write_file"].execute(
            path="packages/agents/new_agent/meta.yaml",
            content="name: new\n",
        )
        assert "Created" in result
        assert (project_dir / "packages/agents/new_agent/meta.yaml").exists()

    def test_path_traversal_blocked(self, tools_approve):
        result = tools_approve["write_file"].execute(
            path="../../../tmp/evil.yaml",
            content="bad\n",
        )
        assert "Error" in result


class TestEditFile:
    def test_edit_existing_file(self, tools_approve, project_dir):
        result = tools_approve["edit_file"].execute(
            path="packages/agents/existing.yaml",
            new_content="name: updated\n",
        )
        assert "Updated" in result
        assert (project_dir / "packages/agents/existing.yaml").read_text() == "name: updated\n"

    def test_edit_nonexistent_file(self, tools_approve):
        result = tools_approve["edit_file"].execute(
            path="packages/agents/nonexistent.yaml",
            new_content="test\n",
        )
        assert "Error" in result
        assert "not found" in result

    def test_user_can_cancel_edit(self, tools_reject):
        result = tools_reject["edit_file"].execute(
            path="packages/agents/existing.yaml",
            new_content="changed\n",
        )
        assert "cancelled" in result


class TestCreateDirectory:
    def test_create_new_dir(self, tools_approve, project_dir):
        result = tools_approve["create_directory"].execute(
            path="packages/agents/new_agent",
        )
        assert "Created" in result
        assert (project_dir / "packages/agents/new_agent").is_dir()

    def test_create_nested_dir(self, tools_approve, project_dir):
        result = tools_approve["create_directory"].execute(
            path="packages/agents/deep/nested/dir",
        )
        assert "Created" in result

    def test_reject_disallowed_dir(self, tools_approve):
        result = tools_approve["create_directory"].execute(
            path="apps/new",
        )
        assert "Error" in result


class TestToolFormat:
    def test_factory_returns_three_tools(self, project_dir, allowed_dirs):
        handler = StubConfirmationHandler()
        tools = make_project_write_tools(project_dir, handler, allowed_dirs)
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert names == {"write_file", "edit_file", "create_directory"}


class TestSchemaValidation:
    """Schema validation kills dict key/value mutations in parameter definitions."""

    def test_write_file_schema(self, tools_approve):
        params = tools_approve["write_file"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path", "content", "reasoning"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["properties"]["content"]["type"] == "string"
        assert params["properties"]["reasoning"]["type"] == "string"
        assert params["required"] == ["path", "content"]

    def test_edit_file_schema(self, tools_approve):
        params = tools_approve["edit_file"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path", "new_content", "reasoning"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["properties"]["new_content"]["type"] == "string"
        assert params["properties"]["reasoning"]["type"] == "string"
        assert params["required"] == ["path", "new_content"]

    def test_create_directory_schema(self, tools_approve):
        params = tools_approve["create_directory"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["required"] == ["path"]


class TestExactErrorMessages:
    """Exact error string assertions kill string content mutations."""

    def test_write_file_path_traversal_exact(self, tools_approve):
        result = tools_approve["write_file"].execute(path="../../../tmp/evil.yaml", content="x")
        assert result == "Error: Path '../../../tmp/evil.yaml' is outside the project directory."

    def test_write_file_overwrite_exact(self, tools_approve):
        result = tools_approve["write_file"].execute(path="packages/agents/existing.yaml", content="x")
        assert result == "Error: File already exists: packages/agents/existing.yaml. Use edit_file to modify it."

    def test_write_file_disallowed_dir_exact(self, tools_approve):
        result = tools_approve["write_file"].execute(path="apps/cli/hack.md", content="x")
        assert result.startswith("Error: Path 'apps/cli/hack.md' not in allowed directories:")

    def test_write_file_disallowed_ext_exact(self, tools_approve):
        result = tools_approve["write_file"].execute(path="packages/agents/hack.py", content="x")
        assert result.startswith("Error: File type '.py' not allowed.")

    def test_edit_file_not_found_exact(self, tools_approve):
        result = tools_approve["edit_file"].execute(path="packages/agents/ghost.yaml", new_content="x")
        assert result == "Error: File not found: packages/agents/ghost.yaml. Use write_file for new files."

    def test_write_success_format(self, tools_approve):
        result = tools_approve["write_file"].execute(path="packages/agents/new.yaml", content="name: t\n")
        assert result == "Created: packages/agents/new.yaml"

    def test_edit_success_format(self, tools_approve):
        result = tools_approve["edit_file"].execute(path="packages/agents/existing.yaml", new_content="name: new\n")
        assert result == "Updated: packages/agents/existing.yaml"

    def test_create_directory_success_format(self, tools_approve):
        result = tools_approve["create_directory"].execute(path="packages/agents/newdir")
        assert result == "Created directory: packages/agents/newdir"

    def test_write_cancelled_format(self, tools_reject):
        result = tools_reject["write_file"].execute(path="packages/agents/new.yaml", content="x")
        assert result == "Write cancelled by user."

    def test_edit_cancelled_format(self, tools_reject):
        result = tools_reject["edit_file"].execute(path="packages/agents/existing.yaml", new_content="x")
        assert result == "Edit cancelled by user."

    def test_default_extensions(self, project_dir, allowed_dirs):
        """Default allowed extensions include .md, .yaml, .yml."""
        handler = StubConfirmationHandler(approve=True)
        tools = {t.name: t for t in make_project_write_tools(project_dir, handler, allowed_dirs)}
        # .md should work
        result = tools["write_file"].execute(path="packages/agents/readme.md", content="# Hi")
        assert result == "Created: packages/agents/readme.md"
        # .yml should work
        result2 = tools["write_file"].execute(path="packages/agents/config.yml", content="x: 1")
        assert result2 == "Created: packages/agents/config.yml"
