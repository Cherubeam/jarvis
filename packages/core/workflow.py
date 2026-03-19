"""
Workflow definition and DAG validation.

Workflows are Directed Acyclic Graphs of agent steps. Each step declares
which agent role executes it, the task prompt, dependencies, and optional
output schema for structured inter-agent communication.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class WorkflowValidationError(Exception):
    """Raised when a workflow definition is invalid."""


@dataclass
class WorkflowStep:
    """A single step in a workflow DAG.

    Attributes:
        step_id: Unique identifier within the workflow.
        role: Agent role to execute this step (maps to AgentMeta.name).
        task: Task prompt template. May contain {step_id.output} placeholders.
        depends_on: List of step_ids that must complete before this step.
        output_schema: Optional JSON Schema for structured output.
        input_context: Optional mapping of context variables from upstream steps.
        max_iterations: Max agentic loop iterations for this step.
        on_failure: Failure handling mode.
        requires_approval: Whether to pause for human approval before executing.
    """
    step_id: str = ""
    role: str = ""
    task: str = ""
    depends_on: list[str] = field(default_factory=list)
    output_schema: dict | None = None
    input_context: dict[str, str] | None = None
    max_iterations: int = 1
    on_failure: str = "abort"  # abort, retry, skip
    requires_approval: bool = False


@dataclass
class Workflow:
    """A workflow DAG definition.

    Attributes:
        name: Workflow name (used for identification and logging).
        steps: Ordered list of workflow steps.
        max_total_cost_usd: Maximum cost budget for the entire workflow.
        description: Optional human-readable description.
    """
    name: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    max_total_cost_usd: float = 3.00
    description: str = ""

    def validate(self) -> None:
        """Validate the workflow definition.

        Checks:
        1. All step_ids are unique.
        2. All depends_on references point to existing steps.
        3. The dependency graph is acyclic (topological sort succeeds).
        4. All steps have a role and task.

        Raises:
            WorkflowValidationError: If any validation check fails.
        """
        if not self.steps:
            raise WorkflowValidationError("Workflow has no steps")

        # Check unique step_ids
        ids = [s.step_id for s in self.steps]
        if len(ids) != len(set(ids)):
            dupes = [sid for sid in ids if ids.count(sid) > 1]
            raise WorkflowValidationError(f"Duplicate step_ids: {set(dupes)}")

        id_set = set(ids)

        for step in self.steps:
            if not step.step_id:
                raise WorkflowValidationError("Step missing step_id")
            if not step.role:
                raise WorkflowValidationError(f"Step '{step.step_id}' missing role")
            if not step.task:
                raise WorkflowValidationError(f"Step '{step.step_id}' missing task")

            for dep in step.depends_on:
                if dep not in id_set:
                    raise WorkflowValidationError(
                        f"Step '{step.step_id}' depends on unknown step '{dep}'"
                    )

        # Topological sort to detect cycles
        self.topological_order()

    def topological_order(self) -> list[str]:
        """Return step_ids in topological order.

        Raises:
            WorkflowValidationError: If the graph contains a cycle.
        """
        # Build adjacency: step -> set of dependencies
        deps: dict[str, set[str]] = {
            s.step_id: set(s.depends_on) for s in self.steps
        }
        order: list[str] = []
        visited: set[str] = set()
        in_stack: set[str] = set()

        def visit(node: str) -> None:
            if node in in_stack:
                raise WorkflowValidationError(
                    f"Cycle detected involving step '{node}'"
                )
            if node in visited:
                return
            in_stack.add(node)
            for dep in deps.get(node, set()):
                visit(dep)
            in_stack.remove(node)
            visited.add(node)
            order.append(node)

        for step in self.steps:
            visit(step.step_id)

        return order

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """Get a step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_ready_steps(self, completed: set[str]) -> list[WorkflowStep]:
        """Get steps whose dependencies are all satisfied.

        Args:
            completed: Set of step_ids that have completed.

        Returns:
            List of steps ready to execute.
        """
        ready = []
        for step in self.steps:
            if step.step_id in completed:
                continue
            if all(dep in completed for dep in step.depends_on):
                ready.append(step)
        return ready


def load_workflow(path: Path) -> Workflow:
    """Load a workflow from a YAML file.

    Args:
        path: Path to the workflow YAML file.

    Returns:
        A validated Workflow instance.

    Raises:
        WorkflowValidationError: If the workflow is invalid.
        FileNotFoundError: If the file doesn't exist.
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise WorkflowValidationError(f"Empty workflow file: {path}")

    steps = []
    for step_data in data.get("steps", []):
        steps.append(WorkflowStep(
            step_id=step_data.get("step_id", ""),
            role=step_data.get("role", ""),
            task=step_data.get("task", ""),
            depends_on=step_data.get("depends_on", []),
            output_schema=step_data.get("output_schema"),
            input_context=step_data.get("input_context"),
            max_iterations=step_data.get("max_iterations", 1),
            on_failure=step_data.get("on_failure", "abort"),
            requires_approval=step_data.get("requires_approval", False),
        ))

    workflow = Workflow(
        name=data.get("name", path.stem),
        steps=steps,
        max_total_cost_usd=data.get("max_total_cost_usd", 3.00),
        description=data.get("description", ""),
    )

    workflow.validate()
    return workflow
