"""
Test runner tool — execute pytest from the developer agent.

Runs tests via subprocess with timeout and output cap.
"""

import subprocess
from pathlib import Path

from packages.core.tools.base import ToolDefinition

_TIMEOUT = 120  # seconds
_MAX_OUTPUT = 10_000  # 10 KB cap on test output


def make_test_runner_tool(project_root: Path) -> ToolDefinition:
    """Create a test runner tool scoped to the project root.

    Args:
        project_root: Absolute path to the JARVIS project root.

    Returns:
        ToolDefinition for running pytest.
    """
    root = project_root.resolve()

    def _run_tests(path: str = "", verbose: bool = False) -> str:
        """Run pytest on the specified path (or all tests)."""
        cmd = ["uv", "run", "pytest"]
        if path:
            cmd.append(path)
        if verbose:
            cmd.append("-v")

        try:
            result = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return f"Error: Tests timed out after {_TIMEOUT}s."
        except FileNotFoundError:
            return "Error: 'uv' not found on PATH."

        output = result.stdout + ("\n" + result.stderr if result.stderr else "")

        if len(output) > _MAX_OUTPUT:
            output = output[:_MAX_OUTPUT] + f"\n\n[Output truncated at {_MAX_OUTPUT // 1000} KB]"

        return output

    return ToolDefinition(
        name="run_tests",
        description=(
            "Run pytest on the JARVIS project. "
            "Optionally specify a path to run specific tests. "
            "Returns test output including pass/fail counts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Test path relative to project root (e.g. 'tests/unit/test_codebase_tools.py'). Empty for all tests.",
                    "default": "",
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Run with verbose output (default: false).",
                    "default": False,
                },
            },
            "required": [],
        },
        execute=_run_tests,
    )
