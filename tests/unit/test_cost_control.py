"""Unit tests for CostGuard and cost control."""

import pytest
import threading

from packages.core.cost_control import CostBudget, CostGuard, BudgetExceededError


@pytest.mark.unit
class TestCostBudget:

    def test_default_values(self):
        budget = CostBudget()
        assert budget.max_per_task_usd == 1.00
        assert budget.max_per_session_usd == 5.00
        assert budget.max_concurrent_agents == 3

    def test_custom_values(self):
        budget = CostBudget(max_per_task_usd=0.50, max_per_session_usd=2.00)
        assert budget.max_per_task_usd == 0.50


@pytest.mark.unit
class TestCostGuard:

    def test_check_within_budget_passes(self):
        guard = CostGuard(CostBudget(max_per_session_usd=5.00))
        guard.check_before_request("writer-1")  # No exception

    def test_session_budget_exceeded(self):
        guard = CostGuard(CostBudget(max_per_session_usd=0.10))
        guard.record_cost(0.08, "writer-1")
        guard.record_cost(0.03, "writer-1")

        with pytest.raises(BudgetExceededError, match="Session"):
            guard.check_before_request("writer-1")

    def test_task_budget_exceeded(self):
        guard = CostGuard(CostBudget(max_per_task_usd=0.05))
        guard.record_cost(0.06, "writer-1", task_id="task-1")

        with pytest.raises(BudgetExceededError, match="Task"):
            guard.check_before_request("writer-1", task_id="task-1")

    def test_workflow_budget_exceeded(self):
        guard = CostGuard(CostBudget(max_per_workflow_usd=0.10))
        guard.record_cost(0.11, "writer-1", workflow_id="wf-1")

        with pytest.raises(BudgetExceededError, match="Workflow"):
            guard.check_before_request("writer-1", workflow_id="wf-1")

    def test_independent_task_budgets(self):
        guard = CostGuard(CostBudget(max_per_task_usd=0.10))
        guard.record_cost(0.09, "writer-1", task_id="task-1")

        # Different task should be fine
        guard.check_before_request("writer-2", task_id="task-2")

    def test_record_cost_updates_session(self):
        guard = CostGuard(CostBudget())
        guard.record_cost(0.01, "writer-1")
        guard.record_cost(0.02, "writer-1")
        assert guard.session_cost == pytest.approx(0.03)

    def test_get_task_cost(self):
        guard = CostGuard(CostBudget())
        guard.record_cost(0.01, "writer-1", task_id="t1")
        guard.record_cost(0.02, "writer-1", task_id="t1")
        assert guard.get_task_cost("t1") == pytest.approx(0.03)
        assert guard.get_task_cost("t2") == 0.0

    def test_summary(self):
        guard = CostGuard(CostBudget(max_per_session_usd=5.0))
        guard.record_cost(0.05, "writer-1", task_id="t1")
        s = guard.summary()
        assert s["session_cost_usd"] == pytest.approx(0.05)
        assert "t1" in s["task_costs"]

    def test_thread_safety(self):
        guard = CostGuard(CostBudget(max_per_session_usd=100.0))
        errors = []

        def record_many():
            try:
                for _ in range(100):
                    guard.record_cost(0.001, "worker")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert guard.session_cost == pytest.approx(1.0)

    def test_budget_exceeded_error_message(self):
        err = BudgetExceededError("Session", 5.0, 5.5)
        assert "Session" in str(err)
        assert "5.5" in str(err)
