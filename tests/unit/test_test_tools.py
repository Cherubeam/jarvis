"""Tests for packages.core.tools.test_tools."""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from packages.core.tools.test_tools import make_test_runner_tool


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path


@pytest.fixture
def tool(project_dir):
    return make_test_runner_tool(project_dir)


class TestRunTests:
    def test_returns_output(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="5 passed\n",
                stderr="",
                returncode=0,
            )
            result = tool.execute()
            assert "5 passed" in result

    def test_includes_stderr(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="FAILED test_foo.py\n",
                returncode=1,
            )
            result = tool.execute()
            assert "FAILED" in result

    def test_with_path(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="1 passed\n", stderr="", returncode=0)
            result = tool.execute(path="tests/unit/test_foo.py")
            # Verify the path was passed to subprocess
            call_args = mock_run.call_args[0][0]
            assert "tests/unit/test_foo.py" in call_args

    def test_verbose_flag(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="verbose output\n", stderr="", returncode=0)
            tool.execute(verbose=True)
            call_args = mock_run.call_args[0][0]
            assert "-v" in call_args

    def test_timeout_handling(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("uv", 120)
            result = tool.execute()
            assert "Error" in result
            assert "timed out" in result

    def test_uv_not_found(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = tool.execute()
            assert "Error" in result
            assert "not found" in result

    def test_output_truncation(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="x" * 15_000,
                stderr="",
                returncode=0,
            )
            result = tool.execute()
            assert "truncated" in result.lower()
            assert len(result) < 12_000  # 10KB cap + truncation message


class TestToolFormat:
    def test_tool_has_correct_name(self, tool):
        assert tool.name == "run_tests"

    def test_litellm_format(self, tool):
        fmt = tool.to_litellm_format()
        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "run_tests"


class TestSchemaValidation:
    def test_schema(self, tool):
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path", "verbose"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["properties"]["path"]["default"] == ""
        assert params["properties"]["verbose"]["type"] == "boolean"
        assert params["properties"]["verbose"]["default"] is False
        assert params["required"] == []


class TestExactOutputs:
    def test_timeout_exact(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("uv", 120)
            result = tool.execute()
        assert result == "Error: Tests timed out after 120s."

    def test_uv_not_found_exact(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = tool.execute()
        assert result == "Error: 'uv' not found on PATH."

    def test_stderr_prepended_with_newline(self, tool):
        """stderr is joined with \\n prefix, not space or other separator."""
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="OUT", stderr="ERR", returncode=1)
            result = tool.execute()
        assert result == "OUT\nERR"

    def test_empty_stderr_not_appended(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="OUT", stderr="", returncode=0)
            result = tool.execute()
        assert result == "OUT"

    def test_truncation_exact_format(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="x" * 15_000, stderr="", returncode=0)
            result = tool.execute()
        assert result.endswith("\n\n[Output truncated at 10 KB]")
        assert len(result) == 10_000 + len("\n\n[Output truncated at 10 KB]")

    def test_output_at_max_not_truncated(self, tool):
        """Output exactly at _MAX_OUTPUT is NOT truncated."""
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="y" * 10_000, stderr="", returncode=0)
            result = tool.execute()
        assert result == "y" * 10_000
        assert "truncated" not in result

    def test_cmd_construction_default(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
            tool.execute()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["uv", "run", "pytest"]

    def test_cmd_construction_with_path_and_verbose(self, tool):
        with patch("packages.core.tools.test_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
            tool.execute(path="tests/unit/test_foo.py", verbose=True)
        cmd = mock_run.call_args[0][0]
        assert cmd == ["uv", "run", "pytest", "tests/unit/test_foo.py", "-v"]
