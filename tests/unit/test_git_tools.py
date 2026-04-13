"""Tests for packages.core.tools.git_tools."""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from packages.core.tools.git_tools import make_git_tools, _run_git


@pytest.fixture
def git_dir(tmp_path):
    """Create a temporary git repo."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)
    return tmp_path


@pytest.fixture
def tools(git_dir):
    """Create git tools from the test repo."""
    return {t.name: t for t in make_git_tools(git_dir)}


class TestGitStatus:
    def test_clean_repo(self, tools):
        result = tools["git_status"].execute()
        assert "clean" in result.lower()

    def test_dirty_repo(self, tools, git_dir):
        (git_dir / "new_file.txt").write_text("hello")
        result = tools["git_status"].execute()
        assert "new_file.txt" in result


class TestGitDiff:
    def test_no_diff_on_clean_repo(self, tools):
        result = tools["git_diff"].execute()
        assert "No differences" in result

    def test_unstaged_diff(self, tools, git_dir):
        (git_dir / "README.md").write_text("# Changed\n")
        result = tools["git_diff"].execute()
        assert "Changed" in result

    def test_staged_diff(self, tools, git_dir):
        (git_dir / "README.md").write_text("# Staged\n")
        subprocess.run(["git", "add", "README.md"], cwd=git_dir, capture_output=True)
        result = tools["git_diff"].execute(staged=True)
        assert "Staged" in result


class TestGitBranch:
    def test_create_valid_branch(self, tools):
        result = tools["git_branch"].execute(name="feat/jarvis-test-branch")
        assert "Error" not in result

    def test_reject_invalid_prefix(self, tools):
        result = tools["git_branch"].execute(name="my-branch")
        assert "Error" in result
        assert "feat/jarvis-" in result

    def test_reject_no_prefix(self, tools):
        result = tools["git_branch"].execute(name="test")
        assert "Error" in result


class TestGitAdd:
    def test_add_specific_file(self, tools, git_dir):
        (git_dir / "new.txt").write_text("hello")
        result = tools["git_add"].execute(paths=["new.txt"])
        assert "Error" not in result

    def test_reject_dash_a(self, tools):
        result = tools["git_add"].execute(paths=["-A"])
        assert "Error" in result

    def test_reject_dot(self, tools):
        result = tools["git_add"].execute(paths=["."])
        assert "Error" in result

    def test_reject_empty(self, tools):
        result = tools["git_add"].execute(paths=[])
        assert "Error" in result


class TestGitCommit:
    def test_commit_with_auto_tag(self, tools, git_dir):
        (git_dir / "new.txt").write_text("hello")
        subprocess.run(["git", "add", "new.txt"], cwd=git_dir, capture_output=True)
        result = tools["git_commit"].execute(message="test commit")
        assert "Error" not in result

        # Verify the tag is in the commit message
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=git_dir, capture_output=True, text=True,
        )
        assert "[JARVIS-auto]" in log.stdout

    def test_reject_empty_message(self, tools):
        result = tools["git_commit"].execute(message="")
        assert "Error" in result


class TestGitLog:
    def test_shows_commits(self, tools):
        result = tools["git_log"].execute()
        assert "initial" in result

    def test_respects_n_limit(self, tools):
        result = tools["git_log"].execute(n=1)
        lines = [l for l in result.strip().split("\n") if l]
        assert len(lines) == 1


class TestRunGit:
    def test_timeout_handling(self, tmp_path):
        with patch("packages.core.tools.git_tools.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 30)
            result = _run_git(["status"], tmp_path)
            assert "Error" in result
            assert "timed out" in result

    def test_git_not_found(self, tmp_path):
        with patch("packages.core.tools.git_tools.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = _run_git(["status"], tmp_path)
            assert "Error" in result
            assert "not found" in result


class TestToolFormat:
    def test_factory_returns_six_tools(self, git_dir):
        tools = make_git_tools(git_dir)
        assert len(tools) == 6
        names = {t.name for t in tools}
        assert names == {"git_status", "git_diff", "git_branch", "git_add", "git_commit", "git_log"}


class TestSchemaValidation:
    def test_git_status_schema(self, tools):
        params = tools["git_status"].parameters
        assert params["type"] == "object"
        assert params["properties"] == {}
        assert params["required"] == []

    def test_git_diff_schema(self, tools):
        params = tools["git_diff"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"staged"}
        assert params["properties"]["staged"]["type"] == "boolean"
        assert params["properties"]["staged"]["default"] is False
        assert params["required"] == []

    def test_git_branch_schema(self, tools):
        params = tools["git_branch"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"name"}
        assert params["properties"]["name"]["type"] == "string"
        assert params["required"] == ["name"]

    def test_git_add_schema(self, tools):
        params = tools["git_add"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"paths"}
        assert params["properties"]["paths"]["type"] == "array"
        assert params["properties"]["paths"]["items"] == {"type": "string"}
        assert params["required"] == ["paths"]

    def test_git_commit_schema(self, tools):
        params = tools["git_commit"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"message"}
        assert params["properties"]["message"]["type"] == "string"
        assert params["required"] == ["message"]

    def test_git_log_schema(self, tools):
        params = tools["git_log"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"n"}
        assert params["properties"]["n"]["type"] == "integer"
        assert params["properties"]["n"]["default"] == 10
        assert params["required"] == []


class TestExactOutputs:
    def test_clean_status_exact(self, tools):
        result = tools["git_status"].execute()
        assert result == "Working tree clean."

    def test_no_diff_exact(self, tools):
        result = tools["git_diff"].execute()
        assert result == "No differences."

    def test_invalid_branch_exact(self, tools):
        result = tools["git_branch"].execute(name="bad-name")
        assert result == "Error: Branch name must start with 'feat/jarvis-' or 'fix/jarvis-'. Got: bad-name"

    def test_empty_paths_exact(self, tools):
        result = tools["git_add"].execute(paths=[])
        assert result == "Error: No paths specified."

    def test_reject_all_flag_exact(self, tools):
        result = tools["git_add"].execute(paths=["--all"])
        assert result == "Error: Cannot use '-A', '--all', or '.' — specify files explicitly."

    def test_reject_dot_exact(self, tools):
        result = tools["git_add"].execute(paths=["."])
        assert result == "Error: Cannot use '-A', '--all', or '.' — specify files explicitly."

    def test_empty_commit_exact(self, tools):
        result = tools["git_commit"].execute(message="")
        assert result == "Error: Commit message cannot be empty."

    def test_whitespace_commit_exact(self, tools):
        result = tools["git_commit"].execute(message="   ")
        assert result == "Error: Commit message cannot be empty."

    def test_timeout_error_exact(self, tmp_path):
        with patch("packages.core.tools.git_tools.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 30)
            result = _run_git(["status"], tmp_path)
        assert result == "Error: git status timed out after 30s."

    def test_git_not_found_exact(self, tmp_path):
        with patch("packages.core.tools.git_tools.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = _run_git(["status"], tmp_path)
        assert result == "Error: git not found on PATH."

    def test_log_capped_at_50(self, tools):
        """n > 50 is clamped to 50."""
        with patch("packages.core.tools.git_tools._run_git") as mock_run:
            mock_run.return_value = "log output"
            tools["git_log"].execute(n=100)
            args = mock_run.call_args[0][0]
            assert "-50" in args
