# GUI Architecture Notes

> Notes from a conversation about restructuring Jarvis for a graphical UI (2026-02-27).
> Includes review of a Gemini-generated plan and follow-up on folder structure.

---

## Part 1: Review of Gemini's Modernization Plan

### Where Gemini is right

**The coupling diagnosis is accurate.** `StreamHandler._run_agentic_loop` has `print(f"[Tool: {call.function.name}]")` baked in (line 93), and `_stream_simple` has `print(chunk, ...)` controlled by a `print_chunks` bool. The CLI's `main.py` is also littered with `print()` for status, errors, and stats. A web adapter can't use any of this.

**The event-driven model is the right direction.** Turning `StreamHandler.stream()` into something that yields typed events (`TextChunk`, `ToolCallStarted`, `UsageReport`) instead of printing directly is the cleanest decoupling. Gemini correctly identified this as the core architectural move.

**Hexagonal / ports-and-adapters is the right pattern.** Keeping the domain (agents, LLM client, tools) agnostic and letting adapters (CLI, web) consume an event stream is textbook correct for this problem.

**FastAPI + SSE for the web backend** — solid, standard choice.

### Where we see things differently

#### 1. Async is not a hard requirement — and it's a massive migration tax

Gemini frames `async/await` as "practically a hard requirement." We disagree. The real constraint is that **LLM streaming is I/O-bound**, and you can handle that multiple ways:

- **FastAPI can run sync generators in a thread pool** via `StreamingResponse` with a sync iterator — no async rewrite needed.
- You could wrap just the web layer in `asyncio.to_thread()` calls.
- LiteLLM's sync `completion()` with `stream=True` already yields chunks lazily — this plays fine with threading.

Converting every function signature in `packages/` to `async def` is a **huge, invasive change** that touches every test (679+ of them), every agent, every tool executor. It's the kind of "rewrite everything at once" move that violates the project's own principle: "No premature optimization." You can add async later when you actually need concurrent request handling — a personal assistant likely won't need 100 concurrent WebSocket connections on day one.

**Recommendation:** Keep the core sync. Add async at the web boundary only, and only when you need it.

#### 2. The plan front-loads too much

Gemini proposes 4 phases with a full React/Next.js frontend in Phase 4. That's a lot of speculative work before validating the intermediate layers. Preferred approach:

1. **Decouple first** — make `StreamHandler` yield events instead of printing. Keep the CLI working exactly as-is by having a thin CLI consumer that prints events. This is a small, testable refactor.
2. **Add a minimal web API** — a single FastAPI endpoint that streams events as SSE. No frontend yet — just `curl` verification.
3. **Then build the frontend** — only after the API contract is stable.

This way each phase delivers a working system and you're never more than one step from "everything still works."

#### 3. The decoupling is actually simpler than presented

Looking at the actual code, the coupling is concentrated in two places:

- `StreamHandler` (2 print statements: tool UX on line 93, chunk streaming on line 116)
- `apps/cli/main.py` (all the `print()` calls for status/stats/errors)

That's it. `LLMClient` is already clean — no print statements, pure data in/out. The agents call `StreamHandler` and get back a `StreamResult`. The tool system is also clean. So the refactor is actually quite surgical:

- Make `StreamHandler.stream()` yield events
- Move the 2 prints into the CLI adapter
- Extract a thin `ChatService` or similar from `main.py` that wires up config → client → agent → logger without any UI

Gemini makes it sound like a bigger rewrite than it needs to be.

#### 4. Missing: the config/startup coupling

Gemini doesn't mention that `main.py` mixes **application bootstrapping** (config loading, RAG init, agent discovery, logger setup) with **CLI-specific I/O** (the `while True: input()` loop, print statements). Both a CLI and web app need the bootstrapping but not each other's I/O. Extracting a shared `ApplicationContext` or startup function is arguably more important than the async question and Gemini doesn't address it.

#### 5. Frontend choice is premature

Gemini mentions React/Vite or Next.js. That's fine eventually, but the plan should acknowledge this is a decision for later. You might want Tauri for a desktop app, or a simple HTMX setup, or something else entirely. The backend event-stream design should be frontend-agnostic, and that's worth stating explicitly.

### Summary table

| Aspect | Gemini | Our view |
|--------|--------|----------|
| Coupling diagnosis | Correct | Agree, but it's more contained than implied |
| Event-driven architecture | Correct | Agree fully |
| Async everywhere | "Hard requirement" | Disagree — keep core sync, async at boundary |
| Migration scope | 4 big phases | Smaller incremental steps |
| Config/bootstrap extraction | Not mentioned | Critical missing piece |
| Frontend choice | React/Next.js | Premature — design backend to be agnostic |

The core insight (decouple via events, hexagonal architecture) is sound. The execution plan is where we diverge — smaller steps, less rewriting, and deferring async until it's actually needed.

---

## Part 2: Folder Structure — frontend/backend split?

### The current layout is already close

```
apps/cli/          → entry point (frontend)
packages/core/     → business logic (backend)
packages/agents/   → agent logic (backend)
packages/integrations/  → external services
packages/telemetry/     → metrics
config/            → configuration
data/              → runtime data
```

The `apps/` vs `packages/` split is essentially frontend vs backend already. The issue isn't folder structure — it's that some backend logic leaks into `apps/cli/main.py` (bootstrapping, config wiring) and some frontend logic leaks into `packages/core/stream_handler.py` (those print statements).

### Renaming to frontend/backend would hurt more than help

**1. You'd have multiple frontends but one backend.** If you add `apps/web/` alongside `apps/cli/`, the pattern `apps/<frontend-name>/` already communicates this naturally. Renaming to `frontend/` implies there's only one.

**2. "Backend" is vague.** The `packages/` directory has clear semantic divisions — `core`, `agents`, `integrations`, `telemetry`. Collapsing them under a generic `backend/` folder loses that clarity. The current structure tells you *what* the code does, not just *where* it runs.

**3. It's a breaking change for no functional gain.** Every import path changes, every test, every doc reference. High cost, zero capability improvement.

### What to actually do

The structural change that *does* make sense is extracting the shared bootstrapping from `main.py` into a reusable place:

```
apps/
  cli/main.py          → CLI input loop + print logic only
  web/main.py           → FastAPI + SSE (future)
packages/
  core/
    app.py              → shared startup: config, client, agent, logger wiring
    stream_handler.py   → yields events instead of printing
    llm_client.py       → unchanged (already clean)
  agents/               → unchanged
  integrations/         → unchanged
  telemetry/            → unchanged
```

The key addition is something like `packages/core/app.py` (or `bootstrap.py`, or `service.py`) that both `apps/cli/main.py` and a future `apps/web/main.py` can import to get a fully configured agent + logger + tools without duplicating 100 lines of setup code.

### Other best practices

**Shared event types.** Define event dataclasses (`TextChunk`, `ToolCallEvent`, `UsageReport`, etc.) in a dedicated module like `packages/core/events.py`. Both CLI and web adapters import from the same contract.

**Keep `apps/` thin.** Each app in `apps/` should be a thin adapter — just translating between the user-facing interface (terminal, HTTP) and the core event stream. If an `apps/` file is longer than ~100 lines, something probably belongs in `packages/`.

**Don't split prematurely.** Adding `apps/web/` before you need it creates dead code to maintain. Add it when you build it. The *preparation* is making `packages/` UI-agnostic (the event refactor), not pre-creating empty folders.

**One `pyproject.toml` is fine for now.** Some people jump to splitting into multiple packages with separate `pyproject.toml` files early. For a personal project with 2-3 entry points, a single monorepo with `apps/` and `packages/` is simpler and the tooling (`uv run`, pytest) already works well with it.

### Short answer

Don't reorganize into `frontend/backend` folders. The `apps/` vs `packages/` split already serves that purpose. The real work is making `packages/` fully UI-agnostic (event-based stream handler, extracted bootstrap logic) so that adding `apps/web/` later is trivial.
