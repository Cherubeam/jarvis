"""
Agent instance identity and lifecycle management.

AgentInstance wraps around BaseAgent/DataDrivenAgent to add instance-level
concerns: unique identity, status tracking, cost budgets. The underlying
agent classes remain unchanged.
"""

from dataclasses import dataclass, field
from datetime import datetime


_instance_counters: dict[str, int] = {}


def _next_instance_id(role: str) -> str:
    """Generate the next sequential instance ID for a role.

    Example: "writer-1", "writer-2", "researcher-1".
    """
    count = _instance_counters.get(role, 0) + 1
    _instance_counters[role] = count
    return f"{role}-{count}"


@dataclass
class AgentInstance:
    """Runtime wrapper around an agent, providing instance-level identity and tracking.

    Attributes:
        instance_id: Unique runtime identifier (e.g., "writer-1").
        role: Technical role name, maps to AgentMeta.name.
        display_name: Optional human-friendly name (display-only, UI concern).
        task_id: What this instance is working on.
        task_description: Human-readable task description.
        status: Current lifecycle status.
        created_at: When this instance was created.
        cost_budget_usd: Maximum cost budget for this instance (None = unlimited).
        cost_spent_usd: Running total of cost spent.
    """
    instance_id: str
    role: str
    display_name: str | None = None
    task_id: str | None = None
    task_description: str = ""
    status: str = "idle"  # idle, running, completed, failed, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    cost_budget_usd: float | None = None
    cost_spent_usd: float = 0.0

    @classmethod
    def create(
        cls,
        role: str,
        task_id: str | None = None,
        task_description: str = "",
        display_name: str | None = None,
        cost_budget_usd: float | None = None,
    ) -> "AgentInstance":
        """Create a new agent instance with an auto-generated instance_id."""
        return cls(
            instance_id=_next_instance_id(role),
            role=role,
            display_name=display_name,
            task_id=task_id,
            task_description=task_description,
            cost_budget_usd=cost_budget_usd,
        )

    @property
    def label(self) -> str:
        """Display label: display_name > instance_id > role."""
        return self.display_name or self.instance_id or self.role

    def record_cost(self, cost_usd: float) -> None:
        """Record cost spent by this instance."""
        self.cost_spent_usd += cost_usd

    def is_over_budget(self) -> bool:
        """Check if this instance has exceeded its cost budget."""
        if self.cost_budget_usd is None:
            return False
        return self.cost_spent_usd >= self.cost_budget_usd

    def budget_remaining(self) -> float | None:
        """Return remaining budget in USD, or None if unlimited."""
        if self.cost_budget_usd is None:
            return None
        return max(0.0, self.cost_budget_usd - self.cost_spent_usd)

    def to_dict(self) -> dict:
        """Serialize instance state for status reporting."""
        return {
            "instance_id": self.instance_id,
            "role": self.role,
            "display_name": self.display_name,
            "task_id": self.task_id,
            "task_description": self.task_description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "cost_budget_usd": self.cost_budget_usd,
            "cost_spent_usd": self.cost_spent_usd,
        }
