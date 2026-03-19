"""
Task queue for parallel agent execution.

Uses concurrent.futures.ThreadPoolExecutor to run multiple agent
instances concurrently. Each agent runs in its own thread with
its own StreamHandler, MetricsTracker, and event callbacks.
"""

import logging
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

from packages.core.agent_instance import AgentInstance
from packages.core.cost_control import BudgetExceededError, CostGuard
from packages.core.events import AgentFinished, AgentStarted, Event

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """A unit of work to be executed by an agent.

    Attributes:
        task_id: Unique identifier for this task.
        role: Agent role to handle this (maps to AgentMeta.name).
        description: The task/prompt to give the agent.
        context: Optional context to inject before the task.
        priority: Higher = executed sooner (for future priority queuing).
        cost_budget_usd: Per-task cost budget (None = use global default).
        status: Current task status.
        assigned_to: Instance ID of the agent handling this.
        result: Task result text after completion.
        error: Error message if task failed.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: str = ""
    description: str = ""
    context: str | None = None
    priority: int = 0
    cost_budget_usd: float | None = None
    status: str = "pending"  # pending, assigned, running, completed, failed, cancelled
    assigned_to: str | None = None
    result: str = ""
    error: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TaskResult:
    """Result of a completed task."""
    task_id: str
    instance_id: str
    status: str  # completed, failed, cancelled
    result_text: str = ""
    cost_usd: float = 0.0
    error: str = ""


class TaskQueue:
    """Manages concurrent agent task execution via ThreadPoolExecutor.

    Each submitted task creates an AgentInstance, instantiates the agent,
    and runs it in a thread pool worker.

    Args:
        max_workers: Maximum concurrent agent threads.
        cost_guard: Optional CostGuard for budget enforcement.
        on_event: Optional callback for agent lifecycle events.
        agent_factory: Callable that creates an agent from (role, extra_tools).
            Must return an object with a .run(message, stream_handler) method.
        stream_handler_factory: Callable that creates a (StreamHandler, MetricsTracker)
            pair for a given instance_id.
    """

    def __init__(
        self,
        max_workers: int = 3,
        cost_guard: CostGuard | None = None,
        on_event: Callable[[Event], None] | None = None,
        agent_factory: Callable | None = None,
        stream_handler_factory: Callable | None = None,
    ):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cost_guard = cost_guard
        self._on_event = on_event
        self._agent_factory = agent_factory
        self._stream_handler_factory = stream_handler_factory

        self._instances: dict[str, AgentInstance] = {}
        self._tasks: dict[str, Task] = {}
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()

    def submit(self, task: Task) -> str:
        """Submit a task for execution.

        Creates an AgentInstance, assigns the task, and submits
        to the thread pool.

        Args:
            task: The task to execute.

        Returns:
            The task_id.

        Raises:
            ValueError: If agent_factory or stream_handler_factory is not set.
        """
        if self._agent_factory is None or self._stream_handler_factory is None:
            raise ValueError(
                "TaskQueue requires agent_factory and stream_handler_factory to be set"
            )

        instance = AgentInstance.create(
            role=task.role,
            task_id=task.task_id,
            task_description=task.description,
            cost_budget_usd=task.cost_budget_usd,
        )

        task.status = "assigned"
        task.assigned_to = instance.instance_id

        with self._lock:
            self._instances[instance.instance_id] = instance
            self._tasks[task.task_id] = task

        future = self._executor.submit(self._run_task, task, instance)
        future.add_done_callback(lambda f: self._on_task_done(task.task_id, f))

        with self._lock:
            self._futures[task.task_id] = future

        return task.task_id

    def _run_task(self, task: Task, instance: AgentInstance) -> TaskResult:
        """Execute a task in a worker thread."""
        instance.status = "running"
        task.status = "running"

        if self._on_event:
            self._on_event(AgentStarted(
                instance_id=instance.instance_id,
                role=instance.role,
                task=task.description,
            ))

        try:
            # Check budget before starting
            if self._cost_guard:
                self._cost_guard.check_before_request(
                    instance_id=instance.instance_id,
                    task_id=task.task_id,
                )

            # Create agent and stream handler for this thread
            agent = self._agent_factory(task.role)
            stream_handler, metrics = self._stream_handler_factory(instance.instance_id)

            # Build the message with optional context
            message = task.description
            if task.context:
                message = f"[Context]: {task.context}\n\n[Task]: {task.description}"

            # Run the agent
            result = agent.run(message, stream_handler, print_chunks=False)

            # Record cost
            instance.record_cost(result.cost_usd)
            if self._cost_guard:
                self._cost_guard.record_cost(
                    result.cost_usd,
                    instance_id=instance.instance_id,
                    task_id=task.task_id,
                )

            instance.status = "completed"
            task.status = "completed"
            task.result = result.text

            return TaskResult(
                task_id=task.task_id,
                instance_id=instance.instance_id,
                status="completed",
                result_text=result.text,
                cost_usd=result.cost_usd,
            )

        except BudgetExceededError as e:
            instance.status = "failed"
            task.status = "failed"
            task.error = str(e)
            logger.warning("Task %s failed: %s", task.task_id, e)

            return TaskResult(
                task_id=task.task_id,
                instance_id=instance.instance_id,
                status="failed",
                error=str(e),
                cost_usd=instance.cost_spent_usd,
            )

        except Exception as e:
            instance.status = "failed"
            task.status = "failed"
            task.error = str(e)
            logger.exception("Task %s failed with unexpected error", task.task_id)

            return TaskResult(
                task_id=task.task_id,
                instance_id=instance.instance_id,
                status="failed",
                error=str(e),
                cost_usd=instance.cost_spent_usd,
            )

    def _on_task_done(self, task_id: str, future: Future) -> None:
        """Callback when a task future completes."""
        try:
            result = future.result()
        except Exception as e:
            result = TaskResult(
                task_id=task_id,
                instance_id="unknown",
                status="failed",
                error=str(e),
            )

        if self._on_event:
            with self._lock:
                instance = None
                task = self._tasks.get(task_id)
                if task and task.assigned_to:
                    instance = self._instances.get(task.assigned_to)

            self._on_event(AgentFinished(
                instance_id=result.instance_id,
                role=instance.role if instance else "",
                status=result.status,
                result_text=result.result_text,
                cost_usd=result.cost_usd,
                error=result.error,
            ))

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending or running task.

        Returns True if the task was successfully cancelled.
        Note: ThreadPoolExecutor can only cancel tasks that haven't started yet.
        """
        with self._lock:
            future = self._futures.get(task_id)
            task = self._tasks.get(task_id)

        if future is None:
            return False

        cancelled = future.cancel()
        if cancelled and task:
            task.status = "cancelled"
            if task.assigned_to:
                with self._lock:
                    instance = self._instances.get(task.assigned_to)
                if instance:
                    instance.status = "cancelled"

        return cancelled

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def get_instance(self, instance_id: str) -> AgentInstance | None:
        """Get an agent instance by ID."""
        with self._lock:
            return self._instances.get(instance_id)

    def status(self) -> list[dict]:
        """Get status of all tasks and instances."""
        with self._lock:
            return [
                {
                    "task_id": task.task_id,
                    "role": task.role,
                    "status": task.status,
                    "assigned_to": task.assigned_to,
                    "description": task.description[:80],
                    "cost_usd": (
                        self._instances[task.assigned_to].cost_spent_usd
                        if task.assigned_to and task.assigned_to in self._instances
                        else 0.0
                    ),
                }
                for task in self._tasks.values()
            ]

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the thread pool."""
        self._executor.shutdown(wait=wait)
