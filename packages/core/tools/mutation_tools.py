"""
Mutation testing tools — run mutmut from the developer agent.

Wraps mutmut CLI via subprocess with timeout and output cap.
"""

import subprocess
from pathlib import Path

from packages.core.tools.base import ToolDefinition

_RUN_TIMEOUT = 300  # seconds — mutation testing is slow
_SHOW_TIMEOUT = 120  # seconds — results/show are fast
_MAX_OUTPUT = 10_000  # 10 KB cap


def make_mutation_tools(project_root: Path) -> list[ToolDefinition]:
    """Create mutation testing tools scoped to the project root.

    Args:
        project_root: Absolute path to the JARVIS project root.

    Returns:
        List of ToolDefinitions for mutation testing.
    """
    root = project_root.resolve()

    def _run_mutation_tests(module: str, test_path: str = "") -> str:
        """Run mutmut on a specific module.

        Note: mutmut 3.x reads paths_to_mutate from pyproject.toml.
        This tool updates the config before running to scope to the
        requested module.
        """
        # Update pyproject.toml to target this specific module
        pyproject = root / "pyproject.toml"
        try:
            text = pyproject.read_text()
            import re

            text = re.sub(
                r"paths_to_mutate = \[.*?\]",
                f'paths_to_mutate = ["{module}"]',
                text,
            )
            pyproject.write_text(text)
        except Exception as e:
            return f"Error updating pyproject.toml: {e}"

        cmd = ["uv", "run", "mutmut", "run"]

        try:
            result = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=_RUN_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return (
                f"Error: Mutation testing timed out after {_RUN_TIMEOUT}s. Try a smaller module or narrower test scope."
            )
        except FileNotFoundError:
            return "Error: 'uv' not found on PATH."

        output = result.stdout + ("\n" + result.stderr if result.stderr else "")

        if len(output) > _MAX_OUTPUT:
            output = output[:_MAX_OUTPUT] + f"\n\n[Output truncated at {_MAX_OUTPUT // 1000} KB]"

        return output

    def _show_mutation_results(mutant_id: str = "", status_filter: str = "") -> str:
        """Show mutation testing results or a specific mutant diff."""
        if mutant_id:
            cmd = ["uv", "run", "mutmut", "show", mutant_id]
        else:
            cmd = ["uv", "run", "mutmut", "results"]

        try:
            result = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=_SHOW_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {_SHOW_TIMEOUT}s."
        except FileNotFoundError:
            return "Error: 'uv' not found on PATH."

        output = result.stdout + ("\n" + result.stderr if result.stderr else "")

        if status_filter and not mutant_id:
            lines = output.splitlines()
            filtered = [ln for ln in lines if status_filter.lower() in ln.lower()]
            output = "\n".join(filtered) if filtered else f"No mutants with status '{status_filter}'."

        if len(output) > _MAX_OUTPUT:
            output = output[:_MAX_OUTPUT] + f"\n\n[Output truncated at {_MAX_OUTPUT // 1000} KB]"

        return output

    run_tool = ToolDefinition(
        name="run_mutation_tests",
        description=(
            "Run mutation testing (mutmut) on a specific module. "  # pragma: no mutate
            "Mutates the source code and checks if tests catch the changes. "  # pragma: no mutate
            "Always target a single file for reasonable run times."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Path to the module to mutate, relative to project root (e.g. 'packages/core/context_builder.py'). Always target a single file.",  # pragma: no mutate
                },
                "test_path": {
                    "type": "string",
                    "description": "Specific test file to run against the mutants (e.g. 'tests/unit/test_context_builder.py'). Faster than running all tests.",  # pragma: no mutate
                    "default": "",
                },
            },
            "required": ["module"],
        },
        execute=_run_mutation_tests,
    )

    show_tool = ToolDefinition(
        name="show_mutation_results",
        description=(
            "Show mutation testing results. Without mutant_id, shows a summary "  # pragma: no mutate
            "of all mutants (survived/killed/timeout). With mutant_id, shows "  # pragma: no mutate
            "the specific mutation diff."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "mutant_id": {
                    "type": "string",
                    "description": "ID of a specific mutant to inspect (e.g. '42'). Omit for summary.",  # pragma: no mutate
                    "default": "",
                },
                "status_filter": {
                    "type": "string",
                    "description": "Filter results by status: 'survived', 'killed', or 'timeout'. Only applies to summary view.",  # pragma: no mutate
                    "default": "",
                },
            },
            "required": [],
        },
        execute=_show_mutation_results,
    )

    return [run_tool, show_tool]
