"""
Cost control and budget enforcement for multi-agent execution.

CostGuard is checked before each LLM call to ensure per-task and
per-session budgets are not exceeded. Thread-safe for concurrent agents.
"""

import threading
from dataclasses import dataclass, field


class BudgetExceededError(Exception):
    """Raised when a cost budget has been exceeded."""

    def __init__(self, budget_type: str, limit: float, spent: float):
        self.budget_type = budget_type
        self.limit = limit
        self.spent = spent
        super().__init__(
            f"{budget_type} budget exceeded: ${spent:.4f} spent of ${limit:.4f} limit"
        )


@dataclass
class CostBudget:
    """Cost budget configuration.

    Attributes:
        max_per_task_usd: Maximum cost per individual task/agent run.
        max_per_session_usd: Maximum cost across all tasks in a session.
        max_per_workflow_usd: Maximum cost for an entire workflow execution.
        max_concurrent_agents: Maximum number of concurrent agent instances.
    """
    max_per_task_usd: float = 1.00
    max_per_session_usd: float = 5.00
    max_per_workflow_usd: float = 3.00
    max_concurrent_agents: int = 3


class CostGuard:
    """Enforces cost budgets across concurrent agent executions.

    Thread-safe: uses a lock for session-level cost aggregation.
    """

    def __init__(self, budget: CostBudget):
        self.budget = budget
        self._session_cost: float = 0.0
        self._task_costs: dict[str, float] = {}  # task_id -> cost
        self._workflow_costs: dict[str, float] = {}  # workflow_id -> cost
        self._lock = threading.Lock()

    @property
    def session_cost(self) -> float:
        """Total cost spent in this session."""
        with self._lock:
            return self._session_cost

    def check_before_request(
        self,
        instance_id: str,
        task_id: str | None = None,
        workflow_id: str | None = None,
        estimated_cost: float = 0.0,
    ) -> None:
        """Check if a request is within budget before making an LLM call.

        Args:
            instance_id: The agent instance making the request.
            task_id: Optional task ID for per-task budget enforcement.
            workflow_id: Optional workflow ID for per-workflow budget enforcement.
            estimated_cost: Estimated cost of the upcoming request.

        Raises:
            BudgetExceededError: If any budget would be exceeded.
        """
        with self._lock:
            # Check session budget
            if self._session_cost + estimated_cost > self.budget.max_per_session_usd:
                raise BudgetExceededError(
                    "Session", self.budget.max_per_session_usd, self._session_cost,
                )

            # Check per-task budget
            if task_id is not None:
                task_cost = self._task_costs.get(task_id, 0.0)
                if task_cost + estimated_cost > self.budget.max_per_task_usd:
                    raise BudgetExceededError(
                        f"Task '{task_id}'", self.budget.max_per_task_usd, task_cost,
                    )

            # Check per-workflow budget
            if workflow_id is not None:
                wf_cost = self._workflow_costs.get(workflow_id, 0.0)
                if wf_cost + estimated_cost > self.budget.max_per_workflow_usd:
                    raise BudgetExceededError(
                        f"Workflow '{workflow_id}'", self.budget.max_per_workflow_usd, wf_cost,
                    )

    def record_cost(
        self,
        cost_usd: float,
        instance_id: str,
        task_id: str | None = None,
        workflow_id: str | None = None,
    ) -> None:
        """Record cost after a completed LLM call.

        Args:
            cost_usd: Cost of the completed call.
            instance_id: The agent instance that made the call.
            task_id: Optional task ID.
            workflow_id: Optional workflow ID.
        """
        with self._lock:
            self._session_cost += cost_usd

            if task_id is not None:
                self._task_costs[task_id] = self._task_costs.get(task_id, 0.0) + cost_usd

            if workflow_id is not None:
                self._workflow_costs[workflow_id] = (
                    self._workflow_costs.get(workflow_id, 0.0) + cost_usd
                )

    def get_task_cost(self, task_id: str) -> float:
        """Get total cost for a specific task."""
        with self._lock:
            return self._task_costs.get(task_id, 0.0)

    def get_workflow_cost(self, workflow_id: str) -> float:
        """Get total cost for a specific workflow."""
        with self._lock:
            return self._workflow_costs.get(workflow_id, 0.0)

    def summary(self) -> dict:
        """Get a summary of all cost tracking."""
        with self._lock:
            return {
                "session_cost_usd": self._session_cost,
                "session_budget_usd": self.budget.max_per_session_usd,
                "task_costs": dict(self._task_costs),
                "workflow_costs": dict(self._workflow_costs),
            }
