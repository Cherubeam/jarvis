"""Unit tests for WorkflowExecutor."""

import pytest

from packages.core.cost_control import CostBudget, CostGuard
from packages.core.workflow import Workflow, WorkflowStep
from packages.core.workflow_executor import WorkflowExecutor, WorkflowResult


def _make_agent_runner(results: dict[str, str] | None = None, cost: float = 0.01):
    """Create a mock agent runner that returns predefined results."""
    default_results = results or {}

    def runner(role: str, task: str, instance_id: str) -> tuple[str, float]:
        if role in default_results:
            return default_results[role], cost
        return f"Output from {role}: {task[:50]}", cost

    return runner


@pytest.mark.unit
class TestWorkflowExecutor:

    def test_simple_sequential_workflow(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="researcher", task="Research {topic}"),
            WorkflowStep(step_id="b", role="writer", task="Write about {a.output}", depends_on=["a"]),
        ])

        executor = WorkflowExecutor(agent_runner=_make_agent_runner())
        result = executor.run(wf, {"topic": "AI"})

        assert result.status == "completed"
        assert len(result.completed_steps) == 2
        assert result.total_cost_usd == pytest.approx(0.02)

    def test_input_substitution(self):
        calls = []

        def runner(role, task, instance_id):
            calls.append((role, task))
            return f"result-{role}", 0.0

        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="s1", role="researcher", task="Research {topic}"),
        ])

        executor = WorkflowExecutor(agent_runner=runner)
        executor.run(wf, {"topic": "quantum computing"})

        assert calls[0][1] == "Research quantum computing"

    def test_output_substitution(self):
        calls = []

        def runner(role, task, instance_id):
            calls.append((role, task))
            if role == "researcher":
                return "key findings here", 0.0
            return "written article", 0.0

        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="research", role="researcher", task="Research {topic}"),
            WorkflowStep(step_id="write", role="writer", task="Write using: {research.output}", depends_on=["research"]),
        ])

        executor = WorkflowExecutor(agent_runner=runner)
        executor.run(wf, {"topic": "AI"})

        assert "key findings here" in calls[1][1]

    def test_failed_step_aborts_workflow(self):
        def failing_runner(role, task, instance_id):
            if role == "researcher":
                raise RuntimeError("API error")
            return "ok", 0.0

        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="researcher", task="Research"),
            WorkflowStep(step_id="b", role="writer", task="Write", depends_on=["a"]),
        ])

        executor = WorkflowExecutor(agent_runner=failing_runner)
        result = executor.run(wf, {})

        assert result.status == "failed"
        assert "a" in result.failed_steps
        # Step b should not have been attempted (depends on a)
        assert "b" not in result.step_results or result.step_results["b"].status == "skipped"

    def test_skip_on_failure(self):
        def failing_runner(role, task, instance_id):
            if role == "researcher":
                raise RuntimeError("API error")
            return "ok", 0.0

        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="researcher", task="Research", on_failure="skip"),
            WorkflowStep(step_id="b", role="writer", task="Write"),
        ])

        executor = WorkflowExecutor(agent_runner=failing_runner)
        result = executor.run(wf, {})

        assert result.step_results["a"].status == "failed"
        assert result.step_results["b"].status == "completed"

    def test_unmet_dependencies_skipped(self):
        """When step a fails with on_failure=abort, the workflow aborts
        and downstream step b is never reached."""
        def failing_runner(role, task, instance_id):
            if role == "researcher":
                raise RuntimeError("fail")
            return "ok", 0.0

        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="researcher", task="Research"),
            WorkflowStep(step_id="b", role="writer", task="Write", depends_on=["a"]),
        ])

        executor = WorkflowExecutor(agent_runner=failing_runner)
        result = executor.run(wf, {})

        assert result.status == "failed"
        assert result.step_results["a"].status == "failed"
        # Step b is not in results because abort breaks the loop
        assert "b" not in result.step_results

    def test_cost_guard_enforcement(self):
        guard = CostGuard(CostBudget(max_per_workflow_usd=0.01))
        guard.record_cost(0.02, "pre", workflow_id="test")

        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="writer", task="Write"),
        ])

        executor = WorkflowExecutor(
            agent_runner=_make_agent_runner(),
            cost_guard=guard,
        )
        result = executor.run(wf, {})

        assert result.status == "partial"
        assert result.step_results["a"].status == "failed"
        assert "budget" in result.step_results["a"].error.lower()

    def test_approval_handler_approved(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="writer", task="Write", requires_approval=True),
        ])

        executor = WorkflowExecutor(
            agent_runner=_make_agent_runner(),
            approval_handler=lambda step, wf: True,
        )
        result = executor.run(wf, {})
        assert result.step_results["a"].status == "completed"

    def test_approval_handler_denied(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="writer", task="Write", requires_approval=True),
        ])

        executor = WorkflowExecutor(
            agent_runner=_make_agent_runner(),
            approval_handler=lambda step, wf: False,
        )
        result = executor.run(wf, {})
        assert result.step_results["a"].status == "skipped"
        assert "approval" in result.step_results["a"].error.lower()

    def test_structured_output_parsing(self):
        def json_runner(role, task, instance_id):
            return '{"title": "My Post", "body": "Content here"}', 0.01

        wf = Workflow(name="test", steps=[
            WorkflowStep(
                step_id="a",
                role="writer",
                task="Write",
                output_schema={
                    "type": "object",
                    "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
                    "required": ["title", "body"],
                },
            ),
        ])

        executor = WorkflowExecutor(agent_runner=json_runner)
        result = executor.run(wf, {})

        assert result.step_results["a"].structured_output is not None
        assert result.step_results["a"].structured_output["title"] == "My Post"

    def test_structured_output_field_substitution(self):
        calls = []

        def runner(role, task, instance_id):
            calls.append((role, task))
            if role == "researcher":
                return '{"summary": "Key insight about AI", "confidence": "high"}', 0.0
            return "written", 0.0

        wf = Workflow(name="test", steps=[
            WorkflowStep(
                step_id="research",
                role="researcher",
                task="Research",
                output_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                },
            ),
            WorkflowStep(
                step_id="write",
                role="writer",
                task="Write based on: {research.output.summary}",
                depends_on=["research"],
            ),
        ])

        executor = WorkflowExecutor(agent_runner=runner)
        executor.run(wf, {})

        assert "Key insight about AI" in calls[1][1]

    def test_parallel_independent_steps(self):
        """Independent steps should all complete (even though run sequentially)."""
        executed = []

        def runner(role, task, instance_id):
            executed.append(role)
            return f"done-{role}", 0.01

        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="researcher", task="Research"),
            WorkflowStep(step_id="b", role="writer", task="Write"),
            WorkflowStep(step_id="c", role="reviewer", task="Review", depends_on=["a", "b"]),
        ])

        executor = WorkflowExecutor(agent_runner=runner)
        result = executor.run(wf, {})

        assert result.status == "completed"
        assert len(result.completed_steps) == 3
