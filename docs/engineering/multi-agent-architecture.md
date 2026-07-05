# Multi-Agent Scaling Architecture for JARVIS

## 1. Context and Motivation

JARVIS is currently a single-threaded, CLI-based personal assistant where one agent runs at a time. The delegation system (`delegate_to_agent` tool) lets JARVIS hand off to specialist agents sequentially, but there is no support for:

- **Parallel execution**: Running multiple agent instances concurrently (e.g., 3 "Writer" agents on different tasks)
- **Coordinated workflows**: A DAG of agent steps where one agent's output feeds into the next
- **Always-on operation**: Running agents as background services in a homelab environment
- **Multi-consumer output**: Routing agent output to CLI, Web UI, or activity feeds simultaneously

This document is the **comprehensive, self-contained reference** for scaling JARVIS to multi-agent operation. It covers what has been implemented (event decoupling — the `WEB` prerequisite), what comes next (Scenarios A/B/C), and all critical design decisions including review feedback. Much of the always-on/multi-agent work here is now tracked under the `AON` initiative (see roadmap).

**Infrastructure context**: No existing homelab. Docker Compose is the starting deployment target, with Kubernetes as a later upgrade path.

---

## 2. Event Decoupling — `WEB` prerequisite (Implemented)

**Status**: Complete and integrated. All 31 existing tests pass. Fully backward compatible.

Event decoupling separates streaming output from direct `print()` calls, enabling multiple consumers to subscribe to agent output. This is the **prerequisite for all multi-agent scenarios**.

### What Was Built

**`packages/core/events.py`** — Typed event dataclasses:
- `TextChunk` — A chunk of streaming text from an LLM response
- `ToolCallStarted` — An agent is invoking a tool
- `ToolResult` — Result from a tool execution
- `UsageReport` — Token usage and cost for a completed LLM call
- `DelegationRequested` — An agent requested delegation to another agent
- `AgentStarted` — An agent instance has started processing
- `AgentFinished` — An agent instance has completed processing

All events carry an `instance_id` field (defaults to `""`) for future multi-instance routing.

**`packages/core/stream_handler.py`** — Modified to emit events:
- Added `on_event: Callable[[Event], None] | None` callback parameter
- Added `instance_id: str` parameter
- `stream()` emits typed events alongside existing `on_chunk`/`on_tool_call` callbacks
- **Backward compatible**: existing code that doesn't pass `on_event` works unchanged

**`packages/core/settings.py`** — Typed configuration loader (PR-8a, supersedes the deleted `packages/core/app.py`):
- `load_config(project_root) -> Settings` — reads `default.yaml` + `local.yaml`, deep-merges, validates via pydantic-settings
- All sections (`models`, `paths`, `cli`, `outcomes`, `things3`, `evaluation`, `rag`, `routing`, `summarization`, `obsidian`, `mcp`, `filesystem`, `cortex`, `readwise`, `pattern_cards`, `developer`) are typed sub-models with `Field(description=...)` documentation suitable for the Settings GUI

Other shared bootstrap helpers (`build_session`, agent/skill discovery, LLM client init) live in `apps/cli/session_factory.py` and are reused by both the CLI and the GUI.

### What Remains

- **Move print statements from `StreamHandler` into CLI adapter**: Currently, `StreamHandler` still contains some direct output. The dual-callback approach (`on_chunk` + `on_event`) maintains backward compatibility, but a clean separation would have `StreamHandler` emit events only, with the CLI adapter handling all display. This is deferred because the current approach works and the refactor is non-trivial.

### Files

| File | Status | Description |
|------|--------|-------------|
| `packages/core/events.py` | New | Typed event dataclasses |
| `packages/core/stream_handler.py` | Modified | `on_event` + `instance_id` added |
| `packages/core/settings.py` | New (PR-8a) | Typed pydantic-settings loader |
| `tests/unit/test_events.py` | New | Event dataclass tests |
| `tests/unit/test_stream_handler_events.py` | New | Event emission tests |

---

## 3. Scenario A: Parallel Agents on Local Machine

### Goal

Multiple agent instances running concurrently on a single machine, sharing a thread pool.

### Concurrency Model: `concurrent.futures.ThreadPoolExecutor`

**Not asyncio. Not multiprocessing.** Rationale:
- LLM calls are I/O-bound — threads excel at this
- No async rewrite needed — the entire codebase stays sync
- Shared memory for event communication (no serialization overhead)
- Each agent already gets its own `ToolRegistry`, `StreamHandler`, and `MetricsTracker`

### Components to Build

#### AgentInstance Wrapper

```python
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

**Key decision**: This wraps around `BaseAgent`/`DataDrivenAgent` — those classes remain unchanged. Instance management (scheduling, budgets, lifecycle) is an orthogonal concern from LLM interaction.

**Display names**: Human names are a UI display layer concern, not embedded in code/logs. Use functional identifiers everywhere in code and logs (`writer-001`, `writer-002`). Map to display names in the CLI/Web UI rendering layer only.

#### TaskQueue

```python
class TaskQueue:
    def __init__(self, max_workers: int = 3): ...
    def submit(self, task: Task) -> str: ...
    def cancel(self, task_id: str) -> bool: ...
    def status(self) -> list[dict]: ...
```

Wraps `ThreadPoolExecutor`. Manages agent instance lifecycle, cost tracking, and event routing.

#### CostGuard

Thread-safe budget enforcement for per-task, per-session, and per-workflow cost limits. Checks budget before each LLM call. Uses `threading.Lock` for thread safety.

```python
class CostGuard:
    def check_budget(self, task_id: str, estimated_cost: float) -> bool: ...
    def record_spend(self, task_id: str, actual_cost: float) -> None: ...
```

**Cost estimation approach** (Critical #8): Before each LLM call, estimate cost from `prompt_tokens * input_price`. This is imprecise (no way to know completion length) but sufficient for guardrails. Use a multiplier (e.g., 2x prompt cost) as the estimate. If a task exceeds its budget, the next LLM call is blocked and the task fails gracefully with the output so far.

#### RateLimiter

Token bucket algorithm for API call throttling across concurrent agents.

```python
class RateLimiter:
    def __init__(self, calls_per_minute: int = 30): ...
    def acquire(self) -> None: ...  # blocks until token available
```

### CLI Display: Activity Feed

**Decision (Important #4 — CLI feed unreadable)**: Do NOT interleave streaming output from parallel agents. A single scrolling feed with mixed streams is unreadable. Instead:

- Show only the "primary" agent streaming in real-time
- Buffer other agents' output; display results sequentially when complete
- Status line shows agent count and progress (e.g., `[writer-1: streaming] [researcher-1: running] [reviewer-1: queued]`)

### Thread Safety Audit (Critical #1)

Before implementing Scenario A, audit these classes for mutable state that must be per-instance:

| Class | Mutable State | Resolution |
|-------|--------------|------------|
| `StreamHandler` | `on_chunk`, `on_tool_call`, `on_event`, metrics | Already per-instance — safe |
| `LLMClient.set_model()` | `self.default_model` | Must NOT share a single `LLMClient` across threads. Create one per agent instance, or remove `set_model()` in favor of passing model per-call |
| `ConversationLogger` | Message accumulator, session metadata | Must be per-instance. Each agent instance gets its own logger |
| `CLIConfirmationHandler` | Stdin access | Cannot run in parallel — tool approval must be serialized or queued |
| `MetricsTracker` | Latency lists, counters | Already per-instance via `init_stream_handler()` — safe |

**Action**: Resolve `LLMClient.set_model()` and `CLIConfirmationHandler` before starting Scenario A implementation.

### Cancellation Strategy (Important #6)

Use `threading.Event` for cooperative cancellation:

```python
class AgentInstance:
    cancel_event: threading.Event

    def should_stop(self) -> bool:
        return self.cancel_event.is_set()
```

Each iteration of the agentic loop checks `should_stop()`. On cancellation, the agent finishes its current LLM call (no mid-stream abort) and returns partial results. Timeout: if an agent doesn't respond within N seconds after cancellation, the thread is abandoned (not killed — Python threads can't be killed cleanly).

---

## 4. Scenario B: Homelab with Always-On Agents (Vision)

**This scenario is architectural vision only. It should NOT influence the design of Scenarios A and C.**

### Architecture

- **Docker Compose** (starting deployment target) → **Kubernetes** (later upgrade path)
- **Redis Streams** as message broker between services
- Worker processes pulling tasks from a shared queue
- Each worker runs one agent instance

### Key Differences from Scenario A

| Aspect | Scenario A (Local) | Scenario B (Homelab) |
|--------|-------------------|---------------------|
| Process model | Threads in one process | Separate containers |
| Communication | Shared memory (`queue.Queue`) | Redis Streams |
| State | In-memory | Redis + filesystem |
| Scaling | Limited by local CPU/RAM | Add containers |
| Availability | On-demand (CLI session) | Always-on |

### MessageBroker Protocol

When Scenario B is needed, implement a `MessageBroker` protocol that abstracts communication:

```python
class MessageBroker(Protocol):
    def publish(self, channel: str, event: Event) -> None: ...
    def subscribe(self, channel: str) -> Iterator[Event]: ...
```

- `InProcessBroker` for Scenario A (wraps `queue.Queue`)
- `RedisBroker` for Scenario B (wraps Redis Streams)

**Decision (Simplification #10-13 — don't build ahead)**: Do NOT build `MessageBroker`, `Dockerfile`, or `docker-compose.yaml` until Scenario B is actually needed. Build Scenario A cleanly with direct `queue.Queue` wiring. Add the abstraction layer only when the second implementation (Redis) is needed.

---

## 5. Scenario C: Agent Communication & Workflows

### Agent Autonomy: Progressive Tiers

#### Tier 1: Strict DAG Workflows (Start Here)

Workflows defined as Directed Acyclic Graphs. Edges represent data flow. Infinite loops are impossible by construction (validated at definition time via topological sort).

```yaml
# Example: write-and-review.yaml
name: write_and_review
description: Research a topic, write a blog post, and review it
max_total_cost_usd: 3.00
steps:
  - step_id: research
    role: researcher
    task: "Research the topic: {topic}"
    output_schema:
      type: object
      properties:
        summary: { type: string }
        sources: { type: array, items: { type: string } }
      required: [summary, sources]

  - step_id: draft
    role: writer
    task: "Write a blog post about {topic}. Research: {research.output.summary}"
    depends_on: [research]

  - step_id: review
    role: content_reviewer
    task: "Review this draft: {draft.output}"
    depends_on: [draft]
    on_failure: skip  # Don't abort the whole workflow if review fails
```

#### Tier 2: DAG + Bounded Dynamic Requests (Future)

Allow agents to request additional steps at runtime, but bounded:
- Maximum N dynamic steps per workflow
- Dynamic steps must be approved by a cost check
- No cycles — dynamic steps can only depend on completed steps

#### Tier 3: Fully Dynamic Agent Mesh (Research Phase)

Free-form agent-to-agent communication. Requires extensive safety mechanisms. Not planned for implementation — research only.

### Structured Inter-Agent Communication (Important #9)

When agents pass output to downstream agents in a workflow, free-form text is unreliable.

**Schema injection**: When a step has `output_schema`, the schema is appended to the agent's task prompt with instructions to respond in JSON.

**Provider fallback**: Not all providers support `response_format` / JSON mode. Fallback strategy:
1. Use `response_format: { type: "json_object" }` if provider supports it (Anthropic, OpenAI)
2. Otherwise, append "Respond with valid JSON matching this schema: ..." to the prompt
3. Validate output against schema. After 2 parse failures, the step fails.

**When NOT needed**: Single-agent delegation (output consumed by human), final workflow step, or creative tasks (free-form prose).

### Workflow Executor

DAG-based execution engine:

1. Parse workflow YAML and validate (topological sort — reject cycles)
2. Identify steps with no dependencies → run concurrently via TaskQueue
3. As steps complete, check which downstream steps have all dependencies satisfied → submit them
4. Substitute `{step_id.output}` and `{step_id.output.field}` references in task prompts
5. Enforce `max_total_cost_usd` across all steps

### Error Recovery (Important #7)

Each step declares an `on_failure` mode:

| Mode | Behavior |
|------|----------|
| `abort` (default) | Stop the entire workflow, return partial results |
| `skip` | Mark step as failed, continue with downstream steps (they receive empty output) |
| `retry` | Retry the step up to N times (with backoff) |

The workflow executor emits `AgentFinished` events with `status: "failed"` so the CLI/UI can display failures.

### Tool Conflicts (Important #5)

When parallel agents share filesystem access (e.g., two writers editing Obsidian notes):

**Decision**: Use file-level locks via `fcntl.flock()` (Unix) or `msvcrt.locking()` (Windows). The `FilesystemGuard` already validates paths — extend it to acquire/release advisory locks around write operations. This prevents concurrent agents from corrupting the same file.

### Conversation Logging (Critical #3)

Each agent instance gets its own `ConversationLogger` instance, writing to a separate file:
- Pattern: `data/conversations/YYYY/YYYY-MM-DD_HH-MM-SS_{instance_id}.json`
- Workflow runs get a parent log that references child instance logs
- No shared mutable state between loggers

---

## 6. Unified Safety Model (All Scenarios)

| Control | Scope | Enforced By |
|---------|-------|-------------|
| Cost budgets | Per-task, per-session, per-workflow | `CostGuard` |
| Rate limits | Per-minute API calls (all agents combined) | `RateLimiter` |
| Iteration limits | Per-agent agentic loop | `StreamHandler` (`max_iterations`) |
| DAG acyclicity | Per-workflow definition | Topological sort at validation time |
| Human approval gates | Optional per workflow step | Workflow executor |
| Max concurrent agents | Global thread pool size | `TaskQueue` |
| File locks | Per-file write access | `FilesystemGuard` extension |

---

## 7. Implementation Order

```
Event Decoupling (WEB)              ✅ DONE
    │
    ├── Remaining: Move print statements into CLI adapter (deferred)
    │
    ├──→ Scenario A: Parallel Local
    │       1. Thread safety audit (resolve LLMClient.set_model, CLI confirmation)
    │       2. AgentInstance wrapper
    │       3. CostGuard (thread-safe budgets)
    │       4. RateLimiter (token bucket)
    │       5. TaskQueue (ThreadPoolExecutor)
    │       6. CLI activity feed (/run command)
    │
    └──→ Scenario C: Workflows        (can develop in parallel with A)
            1. Workflow + WorkflowStep YAML definitions + validation
            2. Structured output schemas + provider fallback
            3. WorkflowExecutor (sequential first, then concurrent via TaskQueue)
            4. run_workflow tool for JARVIS
            5. Error recovery modes (abort/skip/retry)
            6. File-level locks for concurrent write access

Scenario B: Homelab                   (only when always-on operation is needed)
    1. MessageBroker protocol + InProcessBroker
    2. Dockerfile + docker-compose.yaml
    3. RedisBroker implementation
    4. Worker process entrypoint
```

**Build order**: event decoupling → Scenario A + Scenario C (in parallel) → Scenario B

### Verification Criteria

**Scenario A is done when:**
- [ ] Multiple agents run concurrently without corrupting shared state
- [ ] Cost budgets prevent runaway spending
- [ ] Rate limiting prevents API throttling
- [ ] CLI shows agent status without interleaving streams
- [ ] Cancellation stops an agent within one iteration
- [ ] All existing tests still pass (no regressions)

**Scenario C is done when:**
- [ ] Workflow YAML is validated (cycles rejected)
- [ ] Steps execute in dependency order
- [ ] Independent steps run concurrently
- [ ] Structured output is validated and substituted
- [ ] `on_failure` modes work correctly
- [ ] File locks prevent concurrent write corruption
- [ ] `run_workflow` tool is available to JARVIS

**Scenario B is done when:**
- [ ] Agents run in Docker containers
- [ ] Redis Streams carries events between containers
- [ ] System recovers from container restarts

---

## 8. Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Threading over asyncio | Keeps core sync, avoids rewrite, sufficient for I/O-bound LLM calls |
| Agent code stays unchanged | `BaseAgent`, `DataDrivenAgent`, `agent_from_meta()` untouched — instance management is orthogonal |
| Strict DAG first, dynamic later | Start with safest pattern (no cycles possible) |
| Direct wiring over EventBus | Start with `queue.Queue` and direct calls. Add EventBus only if needed |
| Cost controls are mandatory | `CostGuard` is not optional. Every scenario enforces per-task budgets |
| Docker Compose before K8s | No existing infra. Start simple |
| Don't build ahead | Scenarios A/B/C code should only be built when needed. Event decoupling is the only prerequisite that was implemented early (because it also serves the Web UI) |
| No interleaved streaming | Parallel agent output displayed sequentially, not mixed (Important #4) |
| Per-instance logging | Each agent instance writes to its own conversation log (Critical #3) |
| File-level locks for writes | `fcntl.flock()` advisory locks prevent concurrent file corruption (Important #5) |

---

*This is a living document — update as implementation progresses.*

*Last updated: 2026-03-19*
