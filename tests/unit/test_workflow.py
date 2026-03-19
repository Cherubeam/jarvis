"""Unit tests for Workflow and WorkflowStep."""

import pytest
from pathlib import Path
from unittest.mock import patch

from packages.core.workflow import (
    Workflow,
    WorkflowStep,
    WorkflowValidationError,
    load_workflow,
)


@pytest.mark.unit
class TestWorkflowStep:

    def test_defaults(self):
        step = WorkflowStep(step_id="s1", role="writer", task="Write")
        assert step.depends_on == []
        assert step.output_schema is None
        assert step.max_iterations == 1
        assert step.on_failure == "abort"
        assert not step.requires_approval


@pytest.mark.unit
class TestWorkflow:

    def _simple_workflow(self):
        return Workflow(
            name="test",
            steps=[
                WorkflowStep(step_id="a", role="researcher", task="Research"),
                WorkflowStep(step_id="b", role="writer", task="Write", depends_on=["a"]),
            ],
        )

    def test_validate_passes_for_valid_dag(self):
        wf = self._simple_workflow()
        wf.validate()  # No exception

    def test_validate_rejects_empty_workflow(self):
        wf = Workflow(name="empty")
        with pytest.raises(WorkflowValidationError, match="no steps"):
            wf.validate()

    def test_validate_rejects_missing_step_id(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(role="writer", task="Write"),
        ])
        with pytest.raises(WorkflowValidationError, match="missing step_id"):
            wf.validate()

    def test_validate_rejects_missing_role(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", task="Write"),
        ])
        with pytest.raises(WorkflowValidationError, match="missing role"):
            wf.validate()

    def test_validate_rejects_missing_task(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="writer"),
        ])
        with pytest.raises(WorkflowValidationError, match="missing task"):
            wf.validate()

    def test_validate_rejects_duplicate_step_ids(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="writer", task="Write"),
            WorkflowStep(step_id="a", role="researcher", task="Research"),
        ])
        with pytest.raises(WorkflowValidationError, match="Duplicate"):
            wf.validate()

    def test_validate_rejects_unknown_dependency(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="writer", task="Write", depends_on=["nonexistent"]),
        ])
        with pytest.raises(WorkflowValidationError, match="unknown step"):
            wf.validate()

    def test_validate_rejects_cycles(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="writer", task="Write", depends_on=["b"]),
            WorkflowStep(step_id="b", role="researcher", task="Research", depends_on=["a"]),
        ])
        with pytest.raises(WorkflowValidationError, match="Cycle"):
            wf.validate()

    def test_topological_order_simple(self):
        wf = self._simple_workflow()
        order = wf.topological_order()
        assert order.index("a") < order.index("b")

    def test_topological_order_diamond(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="start", role="r", task="Start"),
            WorkflowStep(step_id="left", role="r", task="Left", depends_on=["start"]),
            WorkflowStep(step_id="right", role="r", task="Right", depends_on=["start"]),
            WorkflowStep(step_id="end", role="r", task="End", depends_on=["left", "right"]),
        ])
        order = wf.topological_order()
        assert order.index("start") < order.index("left")
        assert order.index("start") < order.index("right")
        assert order.index("left") < order.index("end")
        assert order.index("right") < order.index("end")

    def test_get_step(self):
        wf = self._simple_workflow()
        assert wf.get_step("a").role == "researcher"
        assert wf.get_step("nonexistent") is None

    def test_get_ready_steps(self):
        wf = self._simple_workflow()
        ready = wf.get_ready_steps(completed=set())
        assert [s.step_id for s in ready] == ["a"]

        ready = wf.get_ready_steps(completed={"a"})
        assert [s.step_id for s in ready] == ["b"]

    def test_get_ready_steps_parallel(self):
        wf = Workflow(name="test", steps=[
            WorkflowStep(step_id="a", role="r", task="A"),
            WorkflowStep(step_id="b", role="r", task="B"),
            WorkflowStep(step_id="c", role="r", task="C", depends_on=["a", "b"]),
        ])
        ready = wf.get_ready_steps(completed=set())
        assert len(ready) == 2
        ids = {s.step_id for s in ready}
        assert ids == {"a", "b"}


@pytest.mark.unit
class TestLoadWorkflow:

    def test_load_workflow(self, tmp_path):
        wf_file = tmp_path / "test.yaml"
        wf_file.write_text("""
name: test_workflow
max_total_cost_usd: 2.00
steps:
  - step_id: research
    role: researcher
    task: "Research {topic}"
  - step_id: write
    role: writer
    task: "Write about {topic}"
    depends_on: [research]
""")
        wf = load_workflow(wf_file)
        assert wf.name == "test_workflow"
        assert wf.max_total_cost_usd == 2.0
        assert len(wf.steps) == 2
        assert wf.steps[1].depends_on == ["research"]

    def test_load_workflow_with_all_fields(self, tmp_path):
        wf_file = tmp_path / "full.yaml"
        wf_file.write_text("""
name: full_test
steps:
  - step_id: s1
    role: writer
    task: "Write"
    on_failure: skip
    requires_approval: true
    max_iterations: 3
    output_schema:
      type: object
      properties:
        title:
          type: string
      required: [title]
""")
        wf = load_workflow(wf_file)
        step = wf.steps[0]
        assert step.on_failure == "skip"
        assert step.requires_approval is True
        assert step.max_iterations == 3
        assert step.output_schema is not None

    def test_load_invalid_workflow_raises(self, tmp_path):
        wf_file = tmp_path / "bad.yaml"
        wf_file.write_text("""
name: bad
steps:
  - step_id: a
    role: writer
    task: "Write"
    depends_on: [nonexistent]
""")
        with pytest.raises(WorkflowValidationError):
            load_workflow(wf_file)
