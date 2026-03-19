"""
DAG-based workflow execution engine.

Executes workflow steps in topological order. Independent steps can run
concurrently via TaskQueue (Scenario A). Supports output substitution,
structured output validation, human approval gates, and cost tracking.
"""

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from packages.core.cost_control import BudgetExceededError, CostGuard
from packages.core.workflow import Workflow, WorkflowStep

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a single workflow step."""
    step_id: str
    status: str  # completed, failed, skipped
    output: str = ""
    structured_output: dict | None = None
    cost_usd: float = 0.0
    error: str = ""


@dataclass
class WorkflowResult:
    """Result of executing an entire workflow."""
    workflow_name: str
    status: str = ""  # completed, failed, partial (set after execution)
    step_results: dict[str, StepResult] = field(default_factory=dict)
    total_cost_usd: float = 0.0

    @property
    def completed_steps(self) -> list[str]:
        return [sid for sid, r in self.step_results.items() if r.status == "completed"]

    @property
    def failed_steps(self) -> list[str]:
        return [sid for sid, r in self.step_results.items() if r.status == "failed"]


class WorkflowExecutor:
    """Execute workflows as DAGs, running independent steps concurrently.

    Args:
        agent_runner: Callable that runs a single step.
            Signature: (role: str, task: str, instance_id: str) -> (text: str, cost: float)
        cost_guard: Optional CostGuard for budget enforcement.
        approval_handler: Optional callable for human approval gates.
            Signature: (step: WorkflowStep, workflow: Workflow) -> bool
    """

    def __init__(
        self,
        agent_runner: Callable[[str, str, str], tuple[str, float]],
        cost_guard: CostGuard | None = None,
        approval_handler: Callable[[WorkflowStep, Workflow], bool] | None = None,
    ):
        self._agent_runner = agent_runner
        self._cost_guard = cost_guard
        self._approval_handler = approval_handler

    def run(self, workflow: Workflow, inputs: dict[str, str]) -> WorkflowResult:
        """Execute a workflow with the given inputs.

        Runs steps in topological order. Independent steps are executed
        sequentially in this implementation (concurrent execution via
        TaskQueue is a future enhancement).

        Args:
            workflow: The workflow to execute.
            inputs: Input variables for task template substitution.

        Returns:
            WorkflowResult with all step outcomes.
        """
        workflow.validate()

        result = WorkflowResult(workflow_name=workflow.name)
        completed: set[str] = set()
        step_outputs: dict[str, str] = {}  # step_id -> output text
        step_structured: dict[str, dict] = {}  # step_id -> structured output

        topo_order = workflow.topological_order()

        for step_id in topo_order:
            step = workflow.get_step(step_id)
            if step is None:
                continue

            # Check if all dependencies completed successfully
            unmet = [d for d in step.depends_on if d not in completed]
            if unmet:
                step_result = StepResult(
                    step_id=step_id,
                    status="skipped",
                    error=f"Unmet dependencies: {unmet}",
                )
                result.step_results[step_id] = step_result
                continue

            # Human approval gate
            if step.requires_approval and self._approval_handler:
                approved = self._approval_handler(step, workflow)
                if not approved:
                    step_result = StepResult(
                        step_id=step_id,
                        status="skipped",
                        error="Human approval denied",
                    )
                    result.step_results[step_id] = step_result
                    logger.info("Step '%s' skipped: approval denied", step_id)
                    continue

            # Substitute placeholders in task template
            task = self._substitute_task(step, inputs, step_outputs, step_structured)

            # Check budget
            if self._cost_guard:
                try:
                    self._cost_guard.check_before_request(
                        instance_id=f"workflow-{workflow.name}-{step_id}",
                        workflow_id=workflow.name,
                    )
                except BudgetExceededError as e:
                    step_result = StepResult(
                        step_id=step_id,
                        status="failed",
                        error=str(e),
                    )
                    result.step_results[step_id] = step_result
                    logger.warning("Step '%s' budget exceeded: %s", step_id, e)

                    # Budget exceeded = abort remaining steps
                    result.status = "partial"
                    break

            # Execute the step
            try:
                instance_id = f"workflow-{workflow.name}-{step_id}"
                output_text, cost = self._agent_runner(step.role, task, instance_id)

                # Record cost
                if self._cost_guard:
                    self._cost_guard.record_cost(
                        cost,
                        instance_id=instance_id,
                        workflow_id=workflow.name,
                    )
                result.total_cost_usd += cost

                # Try to parse structured output if schema is defined
                structured = None
                if step.output_schema:
                    structured = self._parse_structured_output(output_text, step)

                step_outputs[step_id] = output_text
                if structured:
                    step_structured[step_id] = structured

                step_result = StepResult(
                    step_id=step_id,
                    status="completed",
                    output=output_text,
                    structured_output=structured,
                    cost_usd=cost,
                )
                result.step_results[step_id] = step_result
                completed.add(step_id)

                logger.info(
                    "Step '%s' completed (cost: $%.4f)", step_id, cost,
                )

            except Exception as e:
                logger.exception("Step '%s' failed", step_id)

                step_result = StepResult(
                    step_id=step_id,
                    status="failed",
                    error=str(e),
                )
                result.step_results[step_id] = step_result

                # Handle failure mode
                if step.on_failure == "abort":
                    result.status = "failed"
                    break
                elif step.on_failure == "skip":
                    continue
                # retry is not implemented yet

        if result.status == "":
            if all(r.status == "completed" for r in result.step_results.values()):
                result.status = "completed"
            elif any(r.status == "completed" for r in result.step_results.values()):
                result.status = "partial"
            else:
                result.status = "failed"

        return result

    def _substitute_task(
        self,
        step: WorkflowStep,
        inputs: dict[str, str],
        step_outputs: dict[str, str],
        step_structured: dict[str, dict],
    ) -> str:
        """Substitute placeholders in a task template.

        Supports:
        - {variable} from inputs dict
        - {step_id.output} from previous step raw output
        - {step_id.output.field} from previous step structured output
        """
        task = step.task

        # Substitute input variables
        for key, value in inputs.items():
            task = task.replace(f"{{{key}}}", value)

        # Substitute step outputs: {step_id.output}
        for sid, output in step_outputs.items():
            task = task.replace(f"{{{sid}.output}}", output)

        # Substitute structured output fields: {step_id.output.field}
        for sid, structured in step_structured.items():
            for field_name, field_value in structured.items():
                placeholder = f"{{{sid}.output.{field_name}}}"
                if isinstance(field_value, (dict, list)):
                    task = task.replace(placeholder, json.dumps(field_value))
                else:
                    task = task.replace(placeholder, str(field_value))

        # Substitute input_context mappings
        if step.input_context:
            for ctx_key, ctx_template in step.input_context.items():
                resolved = ctx_template
                for key, value in inputs.items():
                    resolved = resolved.replace(f"{{{key}}}", value)
                for sid, output in step_outputs.items():
                    resolved = resolved.replace(f"{{{sid}.output}}", output)
                for sid, structured in step_structured.items():
                    for field_name, field_value in structured.items():
                        placeholder = f"{{{sid}.output.{field_name}}}"
                        if isinstance(field_value, (dict, list)):
                            resolved = resolved.replace(placeholder, json.dumps(field_value))
                        else:
                            resolved = resolved.replace(placeholder, str(field_value))
                # Inject as context at the beginning
                task = f"[{ctx_key}]: {resolved}\n\n{task}"

        # Add structured output instruction if schema is defined
        if step.output_schema:
            schema_str = json.dumps(step.output_schema, indent=2)
            task += (
                f"\n\nIMPORTANT: Respond with valid JSON matching this schema:\n"
                f"```json\n{schema_str}\n```"
            )

        return task

    def _parse_structured_output(
        self,
        output_text: str,
        step: WorkflowStep,
    ) -> dict | None:
        """Try to parse structured output from agent response.

        Attempts to extract JSON from the response text. Returns None
        if parsing fails (output is used as raw text in that case).
        """
        # Try direct JSON parse
        try:
            return json.loads(output_text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', output_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except (json.JSONDecodeError, TypeError):
                pass

        logger.warning(
            "Step '%s' has output_schema but output is not valid JSON",
            step.step_id,
        )
        return None
