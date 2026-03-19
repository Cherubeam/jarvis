# Multi-Agent Scaling Architecture for JARVIS

## Context

JARVIS is currently a single-threaded, CLI-based personal assistant where one agent runs at a time. As the number of agents grows, we want to enable:
- Multiple instances of the same agent role (e.g., 3 "Writer" agents with different tasks)
- Agent-to-agent communication beyond JARVIS-as-hub
- 24/7 operation in a Homelab/Kubernetes environment
- Proper display in CLI and upcoming Web UI

This document serves as both **architectural vision** and **implementation-ready blueprint**. Each scenario is self-contained and can be picked up and built when the time comes. All three scenarios are equally important -- none is deprioritized.

**Infrastructure context**: No existing homelab. Docker Compose is the starting deployment target, with Kubernetes as a later upgrade path.

---

## Prerequisite: Phase 6A (Event Decoupling)

**Every scenario below requires Phase 6A from the roadmap.** Without it, streaming output is coupled to `print()` and there is no way to multiplex agent output for concurrent consumers.

Phase 6A deliverables:
1. `packages/core/events.py` -- typed event dataclasses (`TextChunk`, `ToolCallStarted`, `ToolResult`, `UsageReport`, `DelegationRequested`, `AgentFinished`)
2. `StreamHandler.stream()` emits events via `on_event` callback alongside existing `on_chunk`/`on_tool_call` (backward compatible)
3. `packages/core/app.py` -- shared bootstrap extracted from `apps/cli/main.py`
4. CLI adapter consumes events (behavior unchanged)

**Why this is non-negotiable**: `StreamHandler` currently uses `self.on_chunk` and `self.on_tool_call` callbacks tightly coupled to a single consumer. Multiple concurrent agents each need their own event stream routed to the right display panel.

---

## Cross-Cutting Concern: Agent Identity

### Problem
Agent identity = role name (`writer`). There is no instance concept. `AgentMeta.name` is the unique key.

### AgentInstance wrapper

```python
# packages/core/agent_instance.py
@dataclass
class AgentInstance:
    instance_id: str          # "writer-1", "writer-2", or UUID
    role: str                 # "writer" (maps to AgentMeta.name)
    display_name: str | None  # Human-friendly name (display-only)
    task_id: str | None       # What this instance is working on
    status: str               # "idle", "running", "completed", "failed"
    created_at: datetime
    cost_budget_usd: float | None
    cost_spent_usd: float     # Running total
```

**Key decision**: This wraps around `BaseAgent`/`DataDrivenAgent` -- those classes remain unchanged. Instance management (scheduling, budgets, lifecycle) is an orthogonal concern from LLM interaction.

**Display names**: Human names ("Paul", "Clara") are a UI display layer concern, not embedded in code/logs/schemas. Use functional identifiers everywhere in code and logs (`writer-001`, `writer-002`). Map to display names in the CLI/Web UI rendering layer only.

---

## Cross-Cutting Concern: Structured Inter-Agent Communication

### Problem
When agents pass output to downstream agents in a workflow, free-form text is unreliable. A Researcher's output might be a narrative, a bullet list, or a data dump.

### Structured Output Schemas

Each workflow step can declare an **output schema** that the agent must conform to. This uses LLM structured output features (JSON mode / `response_format` in LiteLLM).

#### How It Works

1. **Schema injection**: When a step has `output_schema`, the schema is appended to the agent's task prompt
2. **LLM enforcement**: The `LLMClient` passes `response_format` to LiteLLM
3. **Validation**: Output is validated against the schema. After 2 failures, the step fails.
4. **Downstream substitution**: Downstream steps can reference `{research.output.summary}` -- specific fields from the structured output.

#### When NOT Needed

- Single-agent delegation (output consumed by human)
- Final workflow step (output goes to user)
- Creative tasks (free-form prose, not JSON)

---

## Scenario A: Parallel Agents on Local Machine

### Goal
Multiple agent instances running concurrently on a single machine.

### Concurrency Model: `concurrent.futures.ThreadPoolExecutor`

**Not asyncio. Not multiprocessing.** Rationale:
- LLM calls are I/O-bound -- threads excel at this
- No async rewrite needed -- the entire codebase stays sync
- Shared memory for event communication (no serialization overhead)
- Each agent already gets its own `ToolRegistry`, `StreamHandler`, and `MetricsTracker`

### Task Queue

```python
# packages/core/task_queue.py
class TaskQueue:
    def __init__(self, max_workers: int = 3): ...
    def submit(self, task: Task) -> str: ...
    def cancel(self, task_id: str) -> bool: ...
    def status(self) -> list[dict]: ...
```

### CLI Display: Activity Feed

A single scrolling feed with agent name prefixes. Do NOT interleave streaming output from parallel agents. Options:
- Show only the "primary" agent in real-time, buffer others for display when complete
- Parallel agents run silently, results presented sequentially when all finish

### Cost Controls

`CostGuard` enforces per-task and per-session budgets before each LLM call.

---

## Scenario B: Homelab with Always-On Agents (Vision)

**This scenario remains as architectural vision. It should NOT influence the design of Scenarios A and C.**

Architecture: Docker Compose (start) -> Kubernetes (later), with Redis Streams as message broker, worker processes pulling tasks.

Build A cleanly. Add B infrastructure only when 24/7 operation is actually needed.

---

## Scenario C: Agent Communication & Workflows

### Agent Autonomy: Progressive Approach

#### Tier 1: Strict DAG Workflows (Start Here)

Workflows defined as Directed Acyclic Graphs. Edges represent data flow. Infinite loops are impossible by construction.

```yaml
# packages/workflows/write-and-review.yaml
name: write_and_review
max_total_cost_usd: 3.00
steps:
  - step_id: research
    role: researcher
    task: "Research the topic: {topic}"
  - step_id: draft
    role: writer
    task: "Write a blog post about {topic}. Sources: {research.output}"
    depends_on: [research]
```

#### Tier 2: DAG + Bounded Dynamic Requests (Future)
#### Tier 3: Fully Dynamic Agent Mesh (Research Phase)

### Workflow Executor

DAG-based execution engine that runs independent steps concurrently via TaskQueue.

### Safety Mechanisms

1. DAGs are acyclic by definition -- validated at definition time
2. Cost controls via `CostGuard`
3. Bounded iteration limits per step
4. Human approval gates (optional per step)

---

## Unified Safety Model (All Scenarios)

1. **Cost budgets** (per-task, per-session, per-workflow) -- enforced by `CostGuard`
2. **Rate limits** (per-minute, per-hour) -- enforced by `RateLimiter`
3. **Iteration limits** (existing `max_iterations` on agents) -- enforced by `StreamHandler`
4. **DAG acyclicity** (Scenario C, Tier 1) -- enforced at workflow validation time
5. **Human approval gates** (optional per workflow step) -- enforced by executor
6. **Max concurrent agents** -- enforced by `TaskQueue` thread pool size

---

## Implementation Order

```
Phase 6A: Event Decoupling          <-- prerequisite for everything
    |
    +--> Scenario A: Parallel Local
    |       1. AgentInstance
    |       2. TaskQueue (ThreadPool)
    |       3. CostGuard
    |       4. CLI activity feed (/run command)
    |
    +--> Scenario C: Workflows     <-- can develop in parallel with A
            1. Workflow + WorkflowStep (YAML) + validation
            2. WorkflowExecutor (sequential first, then concurrent via TaskQueue)
            3. run_workflow tool for JARVIS
            4. Rate limiter
```

**Build order**: Phase 6A -> Scenario A + Scenario C (in parallel) -> Scenario B

---

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Threading over asyncio | Keeps core sync, avoids rewrite, sufficient for I/O-bound LLM calls |
| Agent code stays unchanged | `BaseAgent`, `DataDrivenAgent`, `agent_from_meta()` untouched |
| Strict DAG first, dynamic later | Start with safest pattern |
| Direct wiring over EventBus | Start with `queue.Queue` and direct calls. Add EventBus only if needed |
| Cost controls are mandatory | `CostGuard` is not optional. Every scenario enforces per-task budgets |
| Docker Compose before K8s | No existing infra. Start simple |

---

*This is a living document -- update as implementation progresses.*
