"""Tests for packages.core.tools.mutation_tools."""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from packages.core.tools.mutation_tools import make_mutation_tools


@pytest.fixture
def project_dir(tmp_path):
    # Create a pyproject.toml so mutation_tools can update it
    (tmp_path / "pyproject.toml").write_text(
        'paths_to_mutate = ["packages/core/"]\n'
    )
    return tmp_path


@pytest.fixture
def tools(project_dir):
    return {t.name: t for t in make_mutation_tools(project_dir)}


@pytest.fixture
def run_tool(tools):
    return tools["run_mutation_tests"]


@pytest.fixture
def show_tool(tools):
    return tools["show_mutation_results"]


class TestRunMutationTests:
    def test_returns_output(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Legend: killed survived\n2 killed, 1 survived\n",
                stderr="",
                returncode=0,
            )
            result = run_tool.execute(module="packages/core/foo.py")
            assert "killed" in result

    def test_module_updates_pyproject(self, run_tool, project_dir):
        # Create a pyproject.toml for the tool to update
        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text('paths_to_mutate = ["packages/core/"]\nother = true\n')
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok\n", stderr="", returncode=0)
            run_tool.execute(module="packages/core/context_builder.py")
            # Verify pyproject was updated
            content = pyproject.read_text()
            assert "packages/core/context_builder.py" in content

    def test_mutmut_run_command(self, run_tool, project_dir):
        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text('paths_to_mutate = ["packages/core/"]\n')
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok\n", stderr="", returncode=0)
            run_tool.execute(module="packages/core/foo.py")
            cmd = mock_run.call_args[0][0]
            assert "mutmut" in cmd
            assert "run" in cmd

    def test_includes_stderr(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="Error: some problem\n",
                returncode=1,
            )
            result = run_tool.execute(module="packages/core/foo.py")
            assert "Error: some problem" in result

    def test_timeout_handling(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("uv", 300)
            result = run_tool.execute(module="packages/core/foo.py")
            assert "timed out" in result
            assert "300" in result

    def test_uv_not_found(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = run_tool.execute(module="packages/core/foo.py")
            assert "not found" in result

    def test_output_truncation(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="x" * 15_000,
                stderr="",
                returncode=0,
            )
            result = run_tool.execute(module="packages/core/foo.py")
            assert "truncated" in result.lower()
            assert len(result) < 12_000


class TestShowMutationResults:
    def test_summary_output(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Survived: 3\nKilled: 10\n",
                stderr="",
                returncode=0,
            )
            result = show_tool.execute()
            assert "Survived" in result
            assert "Killed" in result

    def test_calls_results_without_id(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok\n", stderr="", returncode=0)
            show_tool.execute()
            cmd = mock_run.call_args[0][0]
            assert "results" in cmd

    def test_calls_show_with_id(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="--- a/foo.py\n+++ b/foo.py\n-  return True\n+  return False\n",
                stderr="",
                returncode=0,
            )
            result = show_tool.execute(mutant_id="42")
            cmd = mock_run.call_args[0][0]
            assert "show" in cmd
            assert "42" in cmd
            assert "return" in result

    def test_status_filter(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="foo.py: survived\nbar.py: killed\nbaz.py: survived\n",
                stderr="",
                returncode=0,
            )
            result = show_tool.execute(status_filter="survived")
            assert "survived" in result
            assert "killed" not in result

    def test_status_filter_no_matches(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="foo.py: killed\n",
                stderr="",
                returncode=0,
            )
            result = show_tool.execute(status_filter="survived")
            assert "No mutants" in result

    def test_timeout_handling(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("uv", 120)
            result = show_tool.execute()
            assert "timed out" in result

    def test_output_truncation(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="x" * 15_000,
                stderr="",
                returncode=0,
            )
            result = show_tool.execute()
            assert "truncated" in result.lower()


class TestToolFormat:
    def test_returns_two_tools(self, tools):
        assert len(tools) == 2

    def test_tool_names(self, tools):
        assert "run_mutation_tests" in tools
        assert "show_mutation_results" in tools

    def test_run_tool_requires_module(self, run_tool):
        assert "module" in run_tool.parameters.get("required", [])

    def test_show_tool_no_required_params(self, show_tool):
        assert show_tool.parameters.get("required", []) == []

    def test_litellm_format(self, run_tool):
        fmt = run_tool.to_litellm_format()
        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "run_mutation_tests"


class TestSchemaValidation:
    def test_run_tool_schema(self, run_tool):
        params = run_tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"module", "test_path"}
        assert params["properties"]["module"]["type"] == "string"
        assert params["properties"]["test_path"]["type"] == "string"
        assert params["properties"]["test_path"]["default"] == ""
        assert params["required"] == ["module"]

    def test_show_tool_schema(self, show_tool):
        params = show_tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"mutant_id", "status_filter"}
        assert params["properties"]["mutant_id"]["type"] == "string"
        assert params["properties"]["mutant_id"]["default"] == ""
        assert params["properties"]["status_filter"]["type"] == "string"
        assert params["properties"]["status_filter"]["default"] == ""
        assert params["required"] == []


class TestExactOutputs:
    def test_run_timeout_exact(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("uv", 300)
            result = run_tool.execute(module="packages/core/foo.py")
        assert result == "Error: Mutation testing timed out after 300s. Try a smaller module or narrower test scope."

    def test_run_uv_not_found_exact(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = run_tool.execute(module="packages/core/foo.py")
        assert result == "Error: 'uv' not found on PATH."

    def test_show_timeout_exact(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("uv", 120)
            result = show_tool.execute()
        assert result == "Error: Command timed out after 120s."

    def test_show_uv_not_found_exact(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = show_tool.execute()
        assert result == "Error: 'uv' not found on PATH."

    def test_run_stderr_with_newline(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="OUT", stderr="ERR", returncode=1)
            result = run_tool.execute(module="packages/core/foo.py")
        assert result == "OUT\nERR"

    def test_run_empty_stderr_not_appended(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="OUT", stderr="", returncode=0)
            result = run_tool.execute(module="packages/core/foo.py")
        assert result == "OUT"

    def test_show_stderr_with_newline(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="OUT", stderr="ERR", returncode=1)
            result = show_tool.execute()
        assert result == "OUT\nERR"

    def test_run_truncation_exact(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="x" * 15_000, stderr="", returncode=0)
            result = run_tool.execute(module="packages/core/foo.py")
        assert result.endswith("\n\n[Output truncated at 10 KB]")
        assert len(result) == 10_000 + len("\n\n[Output truncated at 10 KB]")

    def test_show_truncation_exact(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="y" * 15_000, stderr="", returncode=0)
            result = show_tool.execute()
        assert result.endswith("\n\n[Output truncated at 10 KB]")

    def test_status_filter_no_match_exact(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="foo: killed\n", stderr="", returncode=0)
            result = show_tool.execute(status_filter="survived")
        assert result == "No mutants with status 'survived'."

    def test_status_filter_case_insensitive(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="foo: SURVIVED\nbar: killed\n", stderr="", returncode=0)
            result = show_tool.execute(status_filter="survived")
        assert "SURVIVED" in result
        assert "killed" not in result

    def test_status_filter_ignored_with_mutant_id(self, show_tool):
        """When mutant_id is provided, status_filter is ignored."""
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="diff output\n", stderr="", returncode=0)
            result = show_tool.execute(mutant_id="42", status_filter="survived")
        assert result == "diff output\n"  # No filtering applied

    def test_pyproject_update_error(self, project_dir):
        """Error updating pyproject.toml returns error message."""
        pyproject = project_dir / "pyproject.toml"
        pyproject.unlink()  # Remove so read_text fails
        tools = {t.name: t for t in make_mutation_tools(project_dir)}
        result = tools["run_mutation_tests"].execute(module="packages/core/foo.py")
        assert result.startswith("Error updating pyproject.toml:")

    def test_run_cmd_construction(self, run_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
            run_tool.execute(module="packages/core/foo.py")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["uv", "run", "mutmut", "run"]

    def test_show_cmd_results(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
            show_tool.execute()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["uv", "run", "mutmut", "results"]

    def test_show_cmd_with_id(self, show_tool):
        with patch("packages.core.tools.mutation_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
            show_tool.execute(mutant_id="99")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["uv", "run", "mutmut", "show", "99"]
