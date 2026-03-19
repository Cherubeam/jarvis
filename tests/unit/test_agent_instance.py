"""Unit tests for AgentInstance."""

import pytest

from packages.core.agent_instance import AgentInstance, _instance_counters


@pytest.fixture(autouse=True)
def reset_counters():
    """Reset instance counters between tests."""
    _instance_counters.clear()
    yield
    _instance_counters.clear()


@pytest.mark.unit
class TestAgentInstance:

    def test_create_generates_sequential_ids(self):
        a1 = AgentInstance.create(role="writer")
        a2 = AgentInstance.create(role="writer")
        a3 = AgentInstance.create(role="researcher")

        assert a1.instance_id == "writer-1"
        assert a2.instance_id == "writer-2"
        assert a3.instance_id == "researcher-1"

    def test_create_with_task(self):
        instance = AgentInstance.create(
            role="writer",
            task_id="task-abc",
            task_description="Write a blog post",
        )
        assert instance.task_id == "task-abc"
        assert instance.task_description == "Write a blog post"
        assert instance.status == "idle"

    def test_label_priority(self):
        # display_name > instance_id > role
        instance = AgentInstance.create(role="writer", display_name="Clara")
        assert instance.label == "Clara"

        instance2 = AgentInstance.create(role="writer")
        assert instance2.label == "writer-2"

    def test_record_cost(self):
        instance = AgentInstance.create(role="writer")
        instance.record_cost(0.01)
        instance.record_cost(0.02)
        assert instance.cost_spent_usd == pytest.approx(0.03)

    def test_budget_not_exceeded(self):
        instance = AgentInstance.create(role="writer", cost_budget_usd=1.0)
        instance.record_cost(0.5)
        assert not instance.is_over_budget()
        assert instance.budget_remaining() == pytest.approx(0.5)

    def test_budget_exceeded(self):
        instance = AgentInstance.create(role="writer", cost_budget_usd=0.10)
        instance.record_cost(0.15)
        assert instance.is_over_budget()
        assert instance.budget_remaining() == 0.0

    def test_unlimited_budget(self):
        instance = AgentInstance.create(role="writer")
        instance.record_cost(100.0)
        assert not instance.is_over_budget()
        assert instance.budget_remaining() is None

    def test_to_dict(self):
        instance = AgentInstance.create(role="writer", task_id="t1")
        d = instance.to_dict()
        assert d["instance_id"] == "writer-1"
        assert d["role"] == "writer"
        assert d["task_id"] == "t1"
        assert d["status"] == "idle"
        assert "created_at" in d
