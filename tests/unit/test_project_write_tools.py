"""Tests for packages.core.tools.project_write_tools."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

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
    return {t.name: t for t in make_project_write_tools(
        project_dir, handler, allowed_dirs,
    )}


@pytest.fixture
def tools_reject(project_dir, allowed_dirs):
    handler = StubConfirmationHandler(approve=False)
    return {t.name: t for t in make_project_write_tools(
        project_dir, handler, allowed_dirs,
    )}


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
