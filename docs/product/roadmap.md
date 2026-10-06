# Product Roadmap

## Naming

Workstreams follow the **initiative / milestone** scheme from
[ADR-033](decisions.md#adr-033-initiative--milestone-naming-scheme), which
replaces the old overloaded "Phase N" numbering:

- **Initiative** — a long-lived theme, identified by a short mnemonic **code**
  (e.g. `AON`), allocated once and never reused.
- **Milestone** — a shippable chunk inside an initiative, `CODE-NN` (e.g.
  `AON-01`). Numbers are allocated in creation order and **never renumbered**;
  sequence is expressed by `Status` and document order, not by the number.
- Branches/PRs reference the milestone: `feat/aon-01-websocket-auth`.

Legacy "Phase N" names still appear in `changelog.md` and past ADRs (history is
kept intact); the crosswalk below and in ADR-033 keeps them resolvable.

| Legacy | Code | Initiative |
|---|---|---|
| Phase 1 | `FND` | Foundation & Metrics |
| Phase 2 | `EVAL` | Evaluation & Quality Metrics |
| Phase 3 | `CTX` | Context & Integrations |
| Phase 4 | `AGENT` | Agent Framework |
| Phase 5 | `CAP` | Agent Capabilities |
| Phase 6 (+ "GUI Phase 1–8") | `WEB` | Web Interface |
| Phase 7 | `TOK` | Context-Window Management & Search |
| Phase 8 | `OPS` | System Monitoring & Optimization |
| Phase 9 | `UX` | UX Enhancements |
| Phase 10 | `TUNE` | Fine-tuning (optional) |
| Dev-agent Phase 1–3 | `DEV` | Developer Agent — retired 2026-09-30 ([ADR-039](decisions.md#adr-039-retire-the-developer-agent); ideas in `developer-agent-roadmap.md`) |
| — | `AON` | Always-On & Loop Engineering |
| — | `HUB` | Context Hub — Cortex/memory via MCP (see [ADR-034](decisions.md#adr-034-context-hub-positioning--rent-coding-harnesses-own-the-context)) |

---

## Current focus (2026-10-05, evening)

Order of work after the September review ([dossier](../research/jarvis-deep-research-dossier.html),
[ADR-040](decisions.md#adr-040-what-jarvis-is-for--an-owned-daily-assistant-and-a-place-to-learn)).
Each step names its milestone below; this list only sets the order.

1. **Finish AON-01.** Done: GUI auth, vault oversight, atomic saves, GUI
   approvals reach the running turn (2026-10-04). **Next: measurement** — one
   parser over the conversation JSON for the native-session count, the monthly
   spend report and the TOK caching baseline. Then the OpenRouter data policy
   (Marco's account), the cost ledger, tool descriptions, the dead CLI copy.
   The caching baseline needs real use first: on 2026-10-05 only 2 native
   messages carried billed usage (recorded since PR #73, 2026-09-29).
2. **Daily use: the conversation archive.** Done (HUB-03): data home, indexes
   local, context files and memory in the vault with dates and sources, Claude
   import refreshed, Claude Code transcripts kept 365 days (all 90 sessions
   since April restored). Claude Code session importer, proposal-based memory
   importer, Claude projects mapped to vault notes by ID, raw exports in the
   data home (all 2026-10-05). **Next: conversation recall via Cortex (HUB-02)**,
   so Claude Code and other MCP clients can search the archive.
3. **TOK caching steps 2–4**, if the baseline shows cacheable spend.
4. **AON-02** — the shared turn runner, then front ends and jobs. Learning and
   daily use count as reasons (ADR-040), with a named learning goal.

Write-ups are optional per topic; Marco decides which to write.

Native JARVIS sessions per month (2026): Feb 15 · Mar 20 · Apr 2 · May–Aug 0 ·
Sep 4. Imported conversations are not counted.

---

## FND — Foundation & Metrics

*Legacy: Phase 1*

**Status**: ✅ Complete
**Timeline**: Completed January 2026

### Features

- [x] Basic CLI interface with streaming responses
- [x] Context system (profile.md, preferences.md, current_focus.md)
- [x] Conversation logging to timestamped JSON files
- [x] Token usage tracking per request and session
- [x] Cost calculation using OpenRouter pricing API
- [x] Session metrics saved to conversation JSON
- [x] LiteLLM integration for provider flexibility
- [x] Automatic cost fallback via LiteLLM pricing
- [x] Testing framework setup (pytest, coverage, fixtures)
- [x] Comprehensive test suite (run `uv run pytest` for current counts)
- [x] Mutation testing via mutmut (test quality auditing)
- [x] 8 golden test conversations defined (initial set; current suite: [tests/golden/README.md](../../tests/golden/README.md))

---

## EVAL — Evaluation & Quality Metrics

*Legacy: Phase 2*

**Status**: ✅ Complete
**Timeline**: Completed Late January 2026

### Features

#### Testing Infrastructure

- [x] Golden test conversation suite (initially 8 cases)
- [x] Automated test runner (pytest)
- [x] LLM-as-judge for automated quality evaluation
  - 33 unit tests (evaluator + storage)
  - Structured JSON results + markdown reports
  - Historical trend tracking
  - Cost management (~$0.41/run at the time; current cost: [tests/golden/README.md](../../tests/golden/README.md#cost-management))
  - On-demand via `--evaluate` flag
- [x] Baseline quality metrics across different models

#### Things 3 Integration (Context Awareness)

- [x] Task sync module with `things.py` (SQLite) — replaced AppleScript
- [x] Task sync via the `JARVIS Things Export` Shortcut, no Full Disk Access — replaced `things.py` (ADR-037, 2026-09-28)
- [x] Auto-sync tasks to tasks.md on startup
- [x] 5-minute task cache to optimize performance
- [x] Grouped markdown output (area > project > tasks)
- [x] ~~Write tools (`create_task`, `complete_task`, `update_task`)~~ — removed 2026-09-28: read-only for now (ADR-037). Revisit via the Things URL scheme with the auth token in `.env` when writes are wanted
- [ ] Shrink the task context: Things tasks are ~51% of the system prompt (~3,600 of ~7,100 tokens, 2026-09-28) and go out with every request. Task IDs dropped (~19% of `tasks.md`); next, if still too big: limit Upcoming to the next 14 days, then shorter notes (notes are ~39%) in `format_tasks_as_markdown` (`packages/integrations/things3/task_sync.py`)
- [ ] Things from a host other than the Things Mac (MCP over HTTP, or a scheduled export to a shared volume). **Trigger:** JARVIS runs off the Mac (e.g. in a container)

#### Metrics Implementation

- [x] Latency tracking (TTFT, total latency per response)
- [x] Response quality scoring (manual → automated)
- [x] Context utilization analysis
- [x] Cost per conversation type benchmarks

#### Model Comparison

- [x] Benchmark 3-5 models on golden test suite
- [x] Compare quality vs. cost tradeoffs
- [x] Document model-specific behaviors
- [x] Default model recommendation (Claude Sonnet 4.5; superseded — see below)
- [x] **2026-09 model refresh** — 10 models × 15 golden results, Opus 5.5 judge + Gemini 3.8 Flash second judge; default → GPT-6 Luna, `quality` → Opus 5.5 ([models.md](../research/models.md)). Harness fixes: multi-turn history, judge from config, token caps, `required_verbatim`, writing cases 13–14 — 2026-09-25

---

## CTX — Context & Integrations

*Legacy: Phase 3*

**Status**: ✅ Complete
**Timeline**: Completed February 2026

### Features

#### Context Builder Enhancements

- [x] Selective context loading via YAML frontmatter (`active`, `topics`, `summary`)
- [x] Project index with active/inactive tiered loading
- [x] Context utilization analyzer script

#### Conversation Schema v1.0.0

- [x] Schema versioning, typed content blocks, message identity
- [x] `metadata: {}` escape hatches at every level
- [x] Read-time migration for backward compatibility
- [x] 52 unit tests for memory module

#### Conversation Imports

- [x] ChatGPT bulk import with CLI filters
- [x] Claude conversation import with date filters
- [x] Claude context import (memories, projects)
- [x] Shared importer utilities (`ImportSummary`, `make_conv_id`)
- [x] Refresh the archive: Claude re-imported 2026-10-01 (31 new, 7 continued; 126 total, newest 2026-09-24). ChatGPT is low priority *(S)*
- [ ] Check that imported conversations are listed and searchable in the GUI history *(S)*
- [ ] More sources, one at a time, each with its own trigger: Claude Code sessions, Codex, Gemini *(M each)*
- [ ] Make re-importing routine (a documented monthly step or a scheduled job under AON-02) *(S)*

#### Obsidian Integration

- [x] Vault reader with path validation and symlink protection
- [x] `> [!JARVIS]` callout block parser
- [x] Diff computation with CLI (colored) and API (JSON) formatters
- [x] `ConfirmationHandler` ABC for GUI-ready write confirmation
- [x] `/daily-summary` CLI command
- [x] Nested daily note paths (`path_format` with strftime)
- [x] 83 tests (73 unit + 10 integration)

---

## AGENT — Agent Framework

*Legacy: Phase 4*

**Status**: ✅ Complete
**Timeline**: Completed February 2026

### Features

- [x] `StreamHandler` extracted from CLI into `packages/core/stream_handler.py`
- [x] `BaseAgent.run()` and `BaseAgent.load_prompt()` methods
- [x] Agent registry with filesystem-based auto-discovery
- [x] Three specialized agents: Writer (`/write`), Researcher (`/research`), Simplifier (`/simplify`)
- [x] Slash-command routing in CLI via agent registry
- [x] `--agent <name>` standalone mode
- [x] Convention: folder in `packages/agents/` with `agent.py` + `prompts/system.md`
- [x] JARVIS persona prompt (movie-inspired voice, guardrails against sycophancy)
- [x] ADR-014: convention-based discovery

---

## CAP — Agent Capabilities

*Legacy: Phase 5 (sub-phases 5A…5K)*

**Status**: 🔄 In Progress
**Timeline**: February–June 2026

### Done

- [x] Function calling & tool support (`ToolDefinition`, `ToolRegistry`, `execute_tool_calls()`)
- [x] Web fetch tool (httpx + trafilatura, 50KB cap)
- [x] Agentic loop in `StreamHandler` (max 5 iterations, non-streaming tools → streaming final answer)
- [x] RAG / Conversation recall (ChromaDB + LiteLLM embeddings)
- [x] Enhanced CLI terminal UX (rich rendering, prompt_toolkit, colored output)
- [x] RAG date filtering fix (integer metadata migration)
- [x] RAG deduplication (per-conversation, over-fetch 3x)

### Skills / Capabilities *(legacy 5A)*

**Status**: ✅ Complete

Vendor-portable, SKILL.md-driven task specifications. Skills use markdown as the primary artifact — compatible with Claude, ChatGPT, and any LLM out of the box.

**Structure**: `packages/skills/` (separate from agents — agents are general-purpose conversational partners, skills are task-specific workflows with defined inputs and outputs)

```
packages/skills/
  base.py              # BaseSkill class (parses SKILL.md, optional skill.py)
  registry.py          # Discovery: scans for SKILL.md files (not Python imports)
  <skill-name>/         # kebab-case, e.g. obsidian-note-creator/
    SKILL.md           # Capability spec — the portable artifact (Mode 1: SKILL.md only)
  content-evaluator/
    SKILL.md           # Capability spec
    skill.py           # Optional: JARVIS execution config (Mode 2: SKILL.md + skill.py)
    resources/
      rubric.md
```

**Key design choice**: SKILL.md uses Claude's native format (YAML frontmatter with `name` + `description`, markdown body as prompt). No JARVIS-specific frontmatter fields — all execution config lives in the optional `skill.py`. See ADR-017.

- [x] SKILL.md-first skill definition format (vendor-portable capability specs)
- [x] Filesystem-based skill registry (scans for SKILL.md, not Python imports)
- [x] Two modes: SKILL.md only (zero Python) and SKILL.md + skill.py (custom execution)
- [x] First skills:
  - [x] Nano Banana Pro image prompt generator (SKILL.md only)
  - [x] Content evaluation workflow (SKILL.md + skill.py with rubric resource)
- [x] ~~Slash-command routing for skills~~ (removed in Unreleased)
- [x] ~~`/skills` listing command~~ (removed in Unreleased)
- [x] ~~`--skill <name>` standalone mode~~ (removed in Unreleased)
- [x] 30 unit tests

### Filesystem Access Control *(legacy 5F)*

- [x] `FilesystemGuard` with `AccessLevel` enum and `AccessRule` dataclass
- [x] Most-specific-path-wins resolution replacing flat `allowed_dirs`
- [x] `load_filesystem_guard()` factory for YAML config
- [x] `VaultConfig` updated (`filesystem_guard` replaces `allowed_dirs`)
- [x] 24 tests in `test_filesystem_access.py`

### Knowledge Base / Deck-Skills *(legacy 5E)*

- [x] CardIndexer + CardSearcher (RAG for static reference content in ChromaDB)
- [x] TacticsAgent (cross-deck Pip Decks coaching orchestrator)
- [x] Deck-skill pattern (SKILL.md + skill.py + deck.yaml + resources/cards/)
- [x] `search_tactics` tool for cross-deck card search
- [x] Auto-discovery of deck-skills via `deck.yaml` presence
- [x] 25 new tests
- [x] Navigator Agent (`/navigator`) — personal alignment and structured review coaching
- [x] Architecture simplification: data-driven agents via meta.yaml, dual-path registry
- [x] Agent-to-skill delegation (implemented via agent-skill binding in `meta.yaml`)

### Developer Agent *(legacy 5G)*

*Retired 2026-09-30 ([ADR-039](decisions.md#adr-039-retire-the-developer-agent)); the items below are history.*

- [x] Developer Agent (`/develop`) — self-improvement agent with codebase read tools, git operations, guarded file writes, and test runner
- [x] 14 tools across four modules (codebase, git, project writes, tests)
- [x] Extended agentic loop (`max_iterations: 20`) for multi-step edit-test-fix cycles

### Cortex — Vault Semantic Search *(legacy 5H)*

**Status**: ✅ Complete (JARVIS side)

Opt-in semantic search over the Obsidian vault via the external Cortex service (`cherubeam/cortex`). See ADR-029.

- [x] Vault-Only MVP — `CortexClient`, `search_vault_semantic` tool, graceful degradation, 14 tests *(retired by HUB-01: Cortex is now consumed as an MCP server, `mcp_cortex__search_knowledge`)*
- [x] `refresh_index()` method for on-demand reindexing
- [x] Project knowledge migrated to Obsidian — context_builder no longer loads `projects/` statically

Further Cortex evolution (Readwise, Zotero, MCP, Inbox Processor) is tracked in the [`cherubeam/cortex` roadmap](https://github.com/Cherubeam/cortex/blob/main/docs/roadmap.md).

### Pattern Card Generator *(legacy 5I)*

**Status**: ✅ Complete

Visual card generator for workshop facilitation — turns Obsidian pattern notes into playing-card-style PNG/HTML cards.

- [x] `card_renderer.py` — pattern parser, HTML/CSS templates, WeasyPrint PNG rendering
- [x] `card_generator_tools.py` — `generate_card`, `generate_deck`, `generate_image_prompts` tools
- [x] Pattern Card Generator agent (`/pattern-cards`) with 15-iteration agentic loop
- [x] Two-track image support: Track A (manual prompts for Gemini UI), Track B (API via litellm, opt-in)
- [x] Category-based color coding, poker-card proportions (750x1050px)
- [x] `pattern_cards` config section in `default.yaml`
- [x] 56 unit tests

### Outcome Tracking *(legacy 5K)*

**Status**: ✅ Complete (v1, released in 0.16.0)

Closed loop on advice JARVIS gives. JARVIS autonomously captures concrete recommendations via `track_recommendation`; the user scores items past their revisit date via `/outcomes`; scored outcomes feed back into RAG so future conversations retrieve relevant past lessons. See ADR for scope decisions.

- [x] `track_recommendation` shared tool — writes pending outcome files to `data/outcomes/` with `conversation_id` linking back to source session
- [x] `packages/core/frontmatter.py` — YAML frontmatter parse/dump + atomic write
- [x] `packages/core/date_utils.py` — relative date parsing (`"1 month"`, `"next week"`, ISO, etc.)
- [x] `/outcomes` interactive CLI command — per-item prompts (outcome/quality/note), atomic writes, Ctrl-C safe
- [x] `OutcomeIndexer` + `OutcomeSearcher` — ChromaDB collection, indexes only reviewed items, deletes stale entries
- [x] `recall_outcomes` shared tool — semantic search over past reviewed outcomes, gated on `rag.enabled`
- [x] JARVIS orchestrator directive — teaches when to call `track_recommendation` (actionable + timeframe, not opinions/hypotheticals)
- [x] `outcomes:` config section + default `filesystem.access_rules` for out-of-the-box operation
- [x] 95 unit tests across 6 files

**Deferred to v2**: heartbeat/cron auto-reminders, social graph, identity-diff snapshots, per-conversation auto-injection into system prompts, specialist agents (navigator, writer) calling `track_recommendation`. v1 does not backfill past transcripts — only from-now items are tracked. *(Heartbeat/cron auto-reminders are now tracked under `AON`.)*

### Readwise / Reading Assistant *(legacy 5J)*

**Status**: ✅ Complete (released in 0.15.0)

CLI-first Readwise Reader integration: library search, highlight recall, inbox triage, and document tagging via the `@readwise/cli` npm subprocess. See changelog entry for 0.15.0.

- [x] 6 Readwise tools: `search_reading_list`, `search_highlights`, `get_document_details`, `save_to_reader`, `tag_readwise_document`, `move_readwise_document`
- [x] Reading assistant agent (`/reading`) — library search, recaps, highlight synthesis
- [x] Reader persona support — `data/context/reader_persona.md` loaded into every agent's system prompt
- [x] Graceful degradation when the Readwise CLI is not installed or not authenticated

### Agent Orchestration *(legacy 5B)*

- [x] JARVIS delegation — sub-conversations with specialist agents (implemented in 0.10.0+Unreleased)
- [x] Agent-to-agent handoff with conversation context (Unreleased)
- [x] Specialist hand-back: `hand_back_to_jarvis` ends an interactive CLI session and JARVIS routes the request again, at most once ([ADR-038](decisions.md#adr-038-specialist-hand-back--jarvis-stays-the-only-router)) — 2026-09-29
- [ ] Deterministic content pipeline (review → cover image → publish/promote) as a Scenario C Tier 1 workflow with steps that wait for the user. **Trigger**: the same sequence run by hand a third time, or a second deterministic process appears (ADR-038)
- [ ] LLM-based intent detection and auto-routing — trigger-gated since ADR-038: build only if specialists keep missing out-of-scope requests despite hand-back
- [ ] Error recovery and fallbacks

### Extended Tools *(legacy 5C)*

- [ ] Playwright-based fetch for JS-rendered pages
- [ ] Tool approval/permission UI
- [x] ~~Things 3 write operations as tools (`things3_tools`)~~ — removed 2026-09-28, read-only for now (ADR-037)
- [x] Obsidian write operations as tools (implemented in 0.10.0)
- [x] Web search integration (`web_search`, DuckDuckGo, in `web_tools`)

### Intelligent Model Routing *(legacy 5D)*

- [x] Task complexity classification (heuristic, `packages/core/model_router.py`, opt-in via `routing.enabled`)
- [x] Route simple tasks → cheap models, complex → expensive models (presets `fast`/`balanced`/`quality`)
- [x] Per-agent models (`meta.yaml` `model:`; writer and substack_publisher → `quality`) — 2026-09-27
- [ ] Skills: send `SkillConfig.temperature` to the model like agents do since v0.26.1 (`packages/skills/base.py` `run()` calls `stream_handler.stream()` without it; same for the `/daily-summary` calls in `apps/cli/main.py` and `apps/gui/server/bridge.py`). Decide first whether the 0.7 default should be sent at all (agents send only an explicit value)
- [x] OpenRouter Auto Router as an opt-in session model (`models.auto_router`, ADR-036) — 2026-09-27
- [ ] Cost savings tracking

---

## WEB — Web Interface

*Legacy: Phase 6 (and the eight "GUI Phase 1–8" sub-phases in the changelog)*

**Status**: ✅ Core shipped — see [`docs/engineering/gui.md`](../engineering/gui.md).
**Timeline**: 2026-04-19 → 2026-04-25
**Goal**: Add a graphical peer to the CLI that shares the same agents, tools, conversation files, and approval flow.

The build was sliced into eight chronological sub-phases, now milestones
**`WEB-01`…`WEB-08`**: Chat shell, Conversations browser, Dashboard/Home,
Sidebar Timeline, Agents overview+detail, Prompt Editor, `/daily-summary` +
`/outcomes` handlers, Settings editor. They appear as "GUI Phase 1–8" in the
changelog and in older engineering-note history — historical labels kept intact
per ADR-033. Each landed on its own feature branch, merged via
`gh pr merge --rebase`. The groupings below organize their deliverables by layer.

### Design Foundations

- [x] UI design principles — [`docs/design/principles.md`](../design/principles.md)
- [x] UI voice & tone guide — [`docs/design/voice-and-tone.md`](../design/voice-and-tone.md)
- [x] Design tokens (colors, typography, spacing) — [`docs/design/tokens.md`](../design/tokens.md)
- [x] Component inventory — [`docs/design/components.md`](../design/components.md)

### Event Decoupling (prerequisite)

- [x] Define event dataclasses in `packages/core/events.py` (`TextChunk`, `ToolCallStarted`, `ToolResult`, `UsageReport`, `AgentStarted`, `AgentFinished`, `DelegationRequested`)
- [x] `StreamHandler.stream()` emits typed events via `on_event` callback (backward compatible -- existing `on_chunk`/`on_tool_call` unchanged)
- [x] Extract shared bootstrapping from `main.py` -> `apps/cli/session_factory.build_session` (CLI + GUI reuse)
- [x] Keep CLI working exactly as before (thin adapter consuming events)
- [x] Typed configuration via `pydantic-settings` (`packages/core/settings.py`) — released in 0.20.0; see ADR-032
- [ ] Move print statements from `StreamHandler` into CLI adapter (deferred — backward compat maintained via dual callback approach)

### API Layer (FastAPI + WebSocket)

- [x] FastAPI backend under `apps/gui/server/` (released in 0.17.0)
- [x] WebSocket transport at `/ws/chat` — chosen over SSE for bi-directional approval flow (vault-write confirms must round-trip from server back to client)
- [x] REST routes:
  - `GET /api/agents`, `GET /api/agents/{id}` — registry + detail (0.19.0)
  - `GET /api/agents/{id}/prompt*` (×7) — Prompt Editor (0.19.0)
  - `GET /api/agents/{id}/includes*` (×6) — prompt-include editor (0.20.0)
  - `GET /api/conversations*` — Conversations index + detail + facets (0.17.0)
  - `GET /api/home` — Dashboard composite (0.17.0)
  - `GET /api/outcomes/pending`, `POST /api/outcomes/{id}/review` — Outcomes (0.19.0)
  - `GET /api/settings`, `GET /api/settings/schema`, `PUT /api/settings` — Settings (0.20.0)

### Frontend (React 18 + Vite + TypeScript)

- [x] Chat shell with streaming responses, tool-call cards, vault-write approval diffs, command palette, Tweaks panel (0.17.0)
- [x] Conversations browser (two-pane History view + live Sidebar) (0.17.0)
- [x] Dashboard / Home (greeting, Things 3 tasks, cost-this-week, resume, recent, quick-start) (0.17.0)
- [x] Sidebar Timeline mode toggle (0.17.0)
- [x] Agents overview grid + Agent Detail with 14-day cost sparkline (0.19.0)
- [x] Agent Prompt Editor (Prompt / Versions / Stats / Context tabs) (0.19.0)
- [x] Outcomes scoring view (0.19.0)
- [x] Settings editor with 16-section 2-pane layout, customized-dot overrides, model-validator error display, managed-header guard (0.20.0)
- [x] Prompt-include editor (Includes tab) (0.20.0)
- [ ] Interactive delegation sub-loops (deferred) — must include specialist hand-back (ADR-038)

**Design principle**: Keep the core sync. Add async at the web boundary only. See [gui-architecture-notes.md](../research/gui-architecture-notes.md) for rationale and [docs/engineering/gui.md](../engineering/gui.md) for architecture + rebuild instructions.

---

## AON — Always-On & Loop Engineering

**Status**: 🔄 In progress — AON-01 underway (GUI auth 2026-09-05; approvals and atomic saves 2026-10-04)
**Motivation**: 2026-07-04 deep-research review (codebase audit + verified web research), amended 2026-07-31 by an adversarial re-check against newer developments (loop-engineering discipline, cache-economics results, memory-benchmark audits). See ADR-033 for the naming scheme this initiative introduces.

**Goal**: Make JARVIS safe to leave running, reachable without a terminal, and
able to run loops (autonomous, scheduled, and feedback) — without violating the
local-first principle. Milestones are ordered by value-per-effort; IDs are
stable and will not be renumbered as the plan evolves.

### AON-01 — Harden (safety rails & shared core)

**Status**: 🔄 In progress · **Effort**: M · **Risk**: Low

Make the existing system safe to leave running and cheap to extend. Each item is one feature branch / PR (`feat/aon-01-<slug>`).

- [x] **WebSocket origin allowlist + token auth** — one ASGI middleware gates every `/api/*` route, `/ws/chat`, and `/docs`; derived-value cookie for browsers, `Authorization: Bearer` for scripts ([ADR-035](decisions.md#adr-035-gui-authentication--derived-value-cookie--origin-allowlist)). Also fixed two approval-hijack holes in `confirmation.py` and closed the `app.py`/`state.py`/`chat_ws.py` mutation blind spot (115 unkilled mutants → 84 new tests) *(S)* ✅ 2026-09-05
- [x] **Vault-write oversight fixes** (found during the 2026-09 model refresh, not originally planned): the GUI approval card now shows the real diff and path (it showed nothing); changed links are listed above every vault diff; writes and previews are refused when the note changed on disk since the agent read it (Art. 14(4)(c), OWASP LLM05/LLM06) *(S)* ✅ 2026-09-25
- [x] ~~Confirmation gate on the pytest runner in `packages/core/tools/test_tools.py`~~ — closed by deletion: the developer agent and its pytest runner were retired ([ADR-039](decisions.md#adr-039-retire-the-developer-agent)) ✅ 2026-09-30
- [ ] Persisted SQLite cost ledger + per-loop caps in `StreamHandler`/`LLMClient`: each loop gets a **deterministic stop condition** (tests pass / score threshold) + turn cap + dollar ceiling — a dollar-only ceiling lets a stuck loop burn its budget on garbage iterations. Ledger also counts cache-keepalive spend (see AON-04) so keepalives self-terminate *(S)*
- [x] Fix the confirmation deadlock: the turn runs as a task so `chat_ws.py` receives approvals and cancels mid-turn; an unanswered approval is rejected after 10 minutes. Reproduced first with WebSocket tests (`test_chat_ws_approvals.py`: approval mid-turn, two writes in one turn, cancel mid-turn), which failed before the fix *(M)* ✅ 2026-10-04
- [x] Reset `WebConfirmationHandler` state per approval, not per turn, so a second vault write in the same turn asks again instead of replaying the first decision; a discarded handler (tab closed, turn ended, cancel) rejects later writes without asking *(S)* ✅ 2026-10-04
- [ ] Rewrite tool descriptions across `packages/core/tools/*` (cheapest quality lever) *(S)*
- [x] Atomic conversation saves (write-temp-then-rename via `frontmatter.write_atomic`) in `memory.py`, both importers, the billed-usage backfill and the card renderer *(S)* ✅ 2026-10-02
- [ ] Count native sessions per week and per front end from the archive (`paths.conversations_dir`), excluding imports (`metadata.import_source`) — the usage measure from ADR-040 *(S)*
- [ ] Check and document the OpenRouter account data policy (data collection, zero retention, provider allowlist); Auto Router turns let OpenRouter pick the provider *(S)*
- [ ] Read-only monthly spend report from the billed-usage fields, sharing parsing code with the TOK caching baseline *(S)*
- [ ] Delete the dead tool-assembly copy in `apps/cli/main.py` (`_assemble_agent_tools`, `_make_agent_vault_tools` at the top, shadowed by the `session_factory` imports in `main()`); repoint `tests/unit/test_cli_agents.py` *(S)*

*Token impact: neutral-to-negative (budget cap + better tool descriptions reduce waste).*

### AON-02 — Unify (session refactor + first loop + Telegram)

**Status**: 📋 Planned · **Effort**: L · **Risk**: Medium

One core, many front ends, one safe scheduled job.

- [ ] Extract a shared `TurnRunner` + headless session factory into `packages/core` (de-duplicate `apps/cli/main.py` ↔ `apps/gui/server/bridge.py` and StreamHandler's twin loops) — the refactor everything else rides on. It absorbs the delegation transitions: delegate, specialist hand-back (ADR-038, CLI-only today) and the spawn-and-consume mode below. TurnRunner **pins the tool set + prompt-prefix ordering per session** (any mid-session tool-list change invalidates the cached prefix — this is where cache savings are won or lost) *(L)*
- [ ] Session-per-conversation replacing the global GuiSession (`apps/gui/server/app.py`, `state.py`) *(M)*
- [ ] `PolicyConfirmationHandler` with a whitelist + persisted approval inbox (headless-safe) *(M)*
- [ ] `jarvis run-job` CLI + launchd LaunchAgent; first job = read-only morning briefing; refresh tasks.md per run *(M)*
- [ ] Read-only **verifier subagent** with fresh context that checks the briefing's output before it's sent (the missing piece from the loop-engineering taxonomy; first consumer of a spawn-and-consume-summary delegation mode — note `delegate.py` is terminal-handoff-only today) *(S)*
- [ ] Telegram bot via long polling as a thin `TurnRunner` client; Tailscale Serve for the GUI. **Content policy**: notifications and approval pings via Telegram; anything vault-derived stays on the Tailscale-only GUI (bot chats are not E2E-encrypted) *(M)*

*Token impact: +$2–6/month for a daily briefing; bounded by the AON-01 ledger.*

### AON-03 — Guard (evals that guard the loop)

**Status**: 📋 Planned · **Effort**: M · **Risk**: Low

Change loop code without flying blind.

- [ ] Route golden evals through the real `TurnRunner`/`StreamHandler` + `context_builder` (remove the reimplemented loop and hardcoded prompt in `tests/golden/` — reuse the AON-02 TurnRunner with mock tools, not a second harness) *(M)*
- [ ] Replace fabricated fallback judge scores with hard failures — **both** fabrication paths in `tests/golden/evaluator.py` (`_fallback_evaluation` *and* `_fallback_parse`); read the baseline `result_storage.py` already writes for CI regression gating *(S)*
- [ ] Calibrate the judge against ~25 hand-labeled transcripts using **Cohen's kappa** (raw agreement overstates judge quality by 33–41pp); recalibrate only when divergence exceeds ~20–25% — a stop condition, not an open-ended project. (No answer-ordering randomization — that's a pairwise-judge mitigation; ours is pointwise.) *(S)*
- [ ] Fix `evaluate_tool_calls` to assert **ordering** (it claims ordered checking but matches by name only); reuse the assertion for scheduled-job checks *(S)*
- [ ] Deterministic output checks for each scheduled job; source new golden cases from **real failure transcripts** (already persisted via `memory.py`) and tag capability-vs-regression so CI gates only on regression *(S)*
- [ ] **Harness evals**: does a checkpointed loop survive a kill? does trimming preserve task intent? Plus injection-containment tests (did the *guards* hold, not did the model notice) — cheap additions, prerequisites for AON-04's longer loops *(S)*
- [ ] Automate the outcome-review loop (`apps/cli/review.py`) as the second scheduled job, with typed fact extraction into the vault. **Quarantine the writes**: extractions land in a staging file requiring human approval before entering prompt-feeding paths (`context_builder.py` feeds vault markdown straight into system prompts — unquarantined auto-writes are a self-reinforcing injection channel). Fact frontmatter gets temporal fields (`valid_at`/`superseded_by`) and extraction is wikilink-aware — the vault already is a graph *(M)*

*Token impact: one golden eval run per change ([cost](../../tests/golden/README.md#cost-management)) + pennies for judges — negligible.*

### AON-04 — Host (headless Mac + deeper autonomy)

**Status**: 📋 Planned · **Effort**: M–L · **Risk**: Medium

Dedicated always-on box; loops that run longer, safely.

- [ ] **Secrets hygiene before the box goes always-on**: `config/local.yaml` holds plaintext API keys and the pattern will grow (OpenRouter, Telegram) — on an unencrypted always-on disk with FileVault off. Move to Keychain or 0600 env files outside the repo; document the physical-theft acceptance *(S)*
- [ ] Headless Mac (mini/spare) as a LaunchAgent: auto-login, FileVault off, `pmset -a sleep 0`, auto-restart, Tailscale-only access (standalone `tailscaled`, not the App Store build) *(M)*
- [ ] ~~Route `FilesystemGuard` through **all** write tools (close the bypass in `codebase_tools.py`, `project_write_tools.py`, `git_tools.py`)~~ — closed by deletion ([ADR-039](decisions.md#adr-039-retire-the-developer-agent), 2026-09-30); still open: add a quarantined web-digest job *(M)*
- [ ] **MCP transport policy**: stdio/local-only by default; network transports (SSE/HTTP) are deliberate opt-in (`mcp/client.py` supports all three; thousands of exposed MCP servers are catalogued, roughly half unauthenticated) *(S)*
- [ ] Wire the existing `history.py:trim_tool_results` into StreamHandler's within-loop iterations — **batched at a token threshold, cache-aware** (per-turn sliding-window trimming mutates old messages and invalidates the cached prefix; don't rebuild what exists). Cache-friendly prompt assembly: static prefix first, dynamic content last. Note: Anthropic's native context-management beta is rejected by OpenRouter, so hand-rolling is correct here; a direct-Anthropic path is optional for long loops only *(M)*
- [ ] Cache **keepalive pings at ~240s** during approval waits (the circulating 30s convention is ~8× too expensive), only within the break-even horizon; spend counted by the AON-01 ledger *(S)*
- [ ] Raise the iteration cap only alongside file-based checkpoints (JSON task list + progress notes + git) **and** the AON-03 harness evals passing; MCP reconnection in `mcp/client.py` — re-pin the tool set on reconnect to protect the cache *(M)*
- [ ] Optional hardening: sandbox-runtime + credential-injecting egress proxy so the agent never holds API keys *(L — only if unattended scope grows)*

*Token impact: net negative — caching + batched clearing should more than fund longer loops (savings depend on the pinned tool set + stable prefix; treat vendor percentages as upper bounds, not forecasts).*

### AON-05 — Voice & proactivity (optional)

**Status**: 💡 Optional · **Effort**: L · **Risk**: Low

Do this only when AON-01…04 feel boring.

- [ ] Local speech pipeline (Pipecat or HF speech-to-speech: local STT → TurnRunner → local TTS) as another thin `TurnRunner` client on the always-on Mac. (Dropped the earlier Home Assistant + ESP32 shape: adopting a home-automation platform for a wake word is over-engineering when HA isn't otherwise in use; revisit HA Voice PE only if HA arrives for other reasons) *(L)*
- [ ] Proactive Telegram notifications from scheduled jobs (approval-inbox digests, outcome summaries) — subject to the AON-02 content policy *(M)*

---

## HUB — Context Hub (Cortex/Memory via MCP)

**Status**: 🔄 In progress — HUB-01 ✅ 2026-09-05; HUB-03 ✅ 2026-10-05; HUB-02 next; allocated 2026-08-19
**Motivation**: [ADR-034](decisions.md#adr-034-context-hub-positioning--rent-coding-harnesses-own-the-context) — harnesses are commodities, the context is the moat. JARVIS's vault index (Cortex, [ADR-029](decisions.md#adr-029-cortex--shared-knowledge-layer-for-the-cherubeam-ecosystem)), context files, and typed memory should be reachable from **every** agent tool (Claude Code, Codex, OpenCode, Cowork) instead of copy-pasted between them.

**Goal**: One canonical personal-context store, exposed as an MCP server, consumed by JARVIS and external harnesses alike. Ends the copy-paste problem; realizes ADR-029's "MCP-ready" clause.

### HUB-01 — Cortex as MCP server

**Status**: ✅ Complete (2026-09-05)

Expose the existing Cortex API (`cherubeam/cortex`) as an MCP server (stdio/local-only per the `AON-04` transport policy).

- [x] MCP server wrapper over `POST /search` (`cortex-mcp` stdio entry point in `cherubeam/cortex`; tools `search_knowledge` + `index_status`)
- [x] Read-only by design — no write tools in v1 (`index/refresh` deliberately excluded per the source policy above)
- [x] Registered in Claude Code (user scope via `claude mcp add`) and verified from a real coding session — first real use immediately surfaced a retrieval-quality gap, fixed and verified in `cherubeam/cortex` (contextual embedding headers, chunk caps, schema fingerprint, stale pruning; eval strict 6/6)
- [x] JARVIS consumes the same server via its existing MCP client (new generic `shared: true` flag on `mcp.servers` entries routes a server's tools into every agent's shared toolset); bespoke `search_vault_semantic` HTTP path, `packages/integrations/cortex/`, and `cortex.*` settings retired

### HUB-02 — Context & memory surface

**Status**: 📋 Planned · **Effort**: M · **Risk**: Medium

Extend the server beyond search to JARVIS's curated context.

- [ ] Read tools for context files (`profile.md`, `preferences.md`, `current_focus.md`) and typed memory facts (the `AON-03` extraction output, post-quarantine only)
- [ ] Conversation-recall search (scoped, opt-in — most private data class). Moved up by ADR-040: the imported archive is only reachable from JARVIS's own index today, not from Claude Code. **Next (prepared 2026-10-05).** Starting point: Cortex has a `Source` plugin protocol (`src/cortex/sources/base.py`: discover, needs_update, extract, compute_state) with one Obsidian source, one ChromaDB collection (`knowledge`) and two MCP tools (`search_knowledge`, `index_status`). The archive is 358 conversation JSON files (schema v1.0.0) in `03 Resources/AI Conversation Archive/conversations/` (`paths.conversations_dir`); JARVIS's own index embeds user→assistant pairs with a per-pair `doc_hash` (`packages/core/rag/indexer.py`). **Decided 2026-10-05: one index.** Cortex holds the only index of the archive; JARVIS's `recall_conversations` moves to Cortex and its own RAG index (`packages/core/rag/indexer.py`, `~/Library/Application Support/JARVIS/indexes/rag`) is retired once Cortex covers query, date range and result count. Open decisions: separate collection or a `source` filter; a separate opt-in tool (e.g. `search_conversations`) vs a parameter on `search_knowledge`; which sources (native, Claude, Claude Code, ChatGPT) are exposed
- [ ] Access story before anything non-local: stdio-only default stands; any network transport is a deliberate, authenticated opt-in

### HUB-03 — Data homes, memory in the vault, import hub

**Status**: ✅ Complete 2026-10-05 (v0.31.0, v0.32.0) — data, indexes, machine state, context files and memory frontmatter 2026-10-03; Claude Code session importer, proposal-based memory importer, project mapping and the archive folder 2026-10-05 · **Effort**: M · **Risk**: Medium (moves private data)

Put each kind of data in one home ([ADR-041](decisions.md#adr-041-where-each-kind-of-data-lives)).

- [x] Data-home path: `/Users/marcobraun/Documents/03 Resources/JARVIS/data` (2026-10-02); conversations and raw exports moved to `03 Resources/AI Conversation Archive/` on 2026-10-05 (ADR-041 amendment)
- [x] Mark the folder "Keep Downloaded" in Finder (or turn off "Optimize Mac Storage") before anything moves *(S)* ✅ 2026-10-02
- [x] Atomic conversation saves first (AON-01 item), so iCloud never uploads a half-written file *(S)* ✅ 2026-10-02
- [x] Scripts, importers and the GUI token read their paths from settings (`paths.*`, new `gui.token_file`) instead of defaulting to `data/…` *(S)* ✅ 2026-10-02
- [x] Move conversations, outcomes, prompt history and pattern-card output to the data home via `local.yaml`; outcomes get their own read-write access rule (the old `data/outcomes` rule was lost because `local.yaml` replaces the whole rule list) *(S)* ✅ 2026-10-03
- [x] Indexes in `~/Library/Application Support/JARVIS/indexes/` (RAG) and `~/Library/Application Support/Cortex/indexes/` (ChromaDB plus index state, `indexing.state_dir`); copied while stopped instead of rebuilt *(S)* ✅ 2026-10-03
- [x] Move CLI history and GUI token to `~/Library/Application Support/JARVIS/` (token file mode `600`; created on next GUI start) *(S)* ✅ 2026-10-03
- [x] Context file names, tasks path and frontmatter stripping are configurable (prerequisite for the memory folder): `paths.context_files`, `paths.tasks_file`; frontmatter is stripped before the prompt *(S)* ✅ 2026-10-03
- [x] Point `paths.tasks_file` to `~/Library/Caches/JARVIS/tasks.md` in `local.yaml`, so the generated tasks file doesn't follow the context files into the vault *(S)* ✅ 2026-10-03
- [x] Memory folder in the vault: context files moved to `07 – Personal System/JARVIS/` (`JARVIS Soul.md`, `Memory/*.md`) via `paths.context_dir` and `paths.context_files`, with a read-write access rule for that folder only; the system prompt built from the vault is byte-identical to the old one *(M)* ✅ 2026-10-03
- [x] Memory notes carry `created`/`updated`/`source`/`review-by` frontmatter (schema in `docs/engineering/deployment.md#context-files`); invalid frontmatter now logs a warning; the unused `paths.learned_facts` setting is removed *(S)* ✅ 2026-10-03
- [x] Brainstorm note (written by Claude, 2026-04-18) moved to the JARVIS project folder `02 – Projects/Private/JARVIS/Brainstorms/` with discovery frontmatter (`type`, `status`, `summary`, `source`, `assist: [prose]`) *(S)* ✅ 2026-10-03
- [x] RAG re-embeds conversation pairs that were added or changed after indexing (per-pair `doc_hash`), so re-imports and resumed sessions reach recall *(S)* ✅ 2026-10-05
- [x] Replace `claude_context.py` with `scripts/import_claude_memory.py`: reads the 2026-09 memory-file format, a model drafts add/update proposals per memory note, facts older than the note are conflicts, each change needs a yes in the CLI (Art. 14) and is logged (Art. 12); the old importer is removed *(M)* ✅ 2026-10-05
- [x] Keep raw exports in the data home (`paths.imports_dir`); skip login history and account data. Done for Claude exports via the memory importer *(S)* ✅ 2026-10-05
- [x] Map Claude projects to vault notes by ID instead of keeping project copies: `claude-project: <uuid>` in the note's frontmatter (7 project notes, 2026-10-05); the memory importer proposes project facts to that note *(S)* ✅ 2026-10-05
- [x] Claude Code session importer (`scripts/import_claude_code.py`): one turn per typed prompt, tool calls as one-line summaries, tool results as size stubs except subagent reports (kept verbatim), subagent transcripts counted but not imported; desktop titles matched by `cliSessionId` or by cwd and start time (≤ 2 s) for the seven entries without one. Transcripts are kept 365 days since 2026-10-04 (`cleanupPeriodDays`) *(M)* ✅ 2026-10-05

### Source policy — index, don't proxy (2026-08-20)

The rule for "should Cortex integrate source X?":

- **Ingest for recall — yes.** Cortex's value is the one deduplicated semantic
  index across sources (ADR-029 source plugins: vault, Readwise, later
  Zotero/Miro). Cross-source "what do I know about X?" is the thing no direct
  connection provides, and embedding costs are paid once instead of per-tool.
- **Proxy for actions — no.** Transactional operations (Readwise tagging/
  saving/daily review, Miro board edits) go through that source's **own** MCP
  server, registered directly in each client (JARVIS `mcp.servers`, Claude
  Code `.mcp.json`). Wrapping a maintained official MCP in Cortex is the same
  commodity-treadmill mistake as building our own coding harness, one layer
  down (ADR-034).
- **Raw access stays.** Claude Code reading vault markdown from the filesystem
  is exact, live, and free — semantic search complements grep, it doesn't
  replace it.

> **Scope guard (ADR-034)**: `HUB` exports context; it does not grow into a
> workflow or execution API. Harnesses bring their own loops, sources bring
> their own MCPs.

---

## TOK — Context-Window Management & Search

*Legacy: Phase 7*

**Status**: 🔄 In Progress

### Features

- [x] Intelligent truncation strategies (tool result trimming in main loop + delegates)
- [x] Summarization for old conversation context
- [x] Non-streaming mode for prompt caching (workaround for LiteLLM streaming bug) — *superseded 2026-09-30: the "bug" was LiteLLM's usage estimate, not broken caching*
- [x] Billed usage for streamed turns: logs reconciled against OpenRouter's billing records (PR #73)
- [ ] **Prompt caching for conversation history**: baseline on billed logs → second `cache_control` breakpoint on the last message → `session_id` on every OpenRouter call → cache-write parsing. Plan and cache busters: [token-economics-next-steps.md](../research/token-economics-next-steps.md#step-c-reopened-prompt-caching-state-and-plan-2026-09-30) *(M)*
- [ ] Token budget management
- [ ] Full-text + semantic search over conversations
- [ ] Conversation export and statistics

---

## OPS — System Monitoring & Optimization

*Legacy: Phase 8*

**Status**: Not Started

### Features

- [ ] Structured logging and error categorization
- [ ] Continuous quality monitoring
- [ ] Prompt optimization based on metrics
- [ ] Cost optimization recommendations

---

## UX — UX Enhancements

*Legacy: Phase 9*

**Status**: Not Started

### Features

- [ ] Rich TUI improvements
- [ ] Profile switching (work/personal)
- [x] Model presets (fast/quality/balanced) ✅ — `--model` flag + `/model` command
- [ ] Export & sharing

---

## TUNE — Fine-tuning (Optional)

*Legacy: Phase 10*

**Status**: Not Started
**Timeline**: Only if needed (2027+)

### Prerequisites

- [ ] Collected 1000+ high-quality interactions
- [ ] Identified specific capability gaps
- [ ] Evaluated: prompting alone insufficient
- [ ] Cost-benefit analysis completed

### Features

- [ ] Data preparation for fine-tuning
- [ ] Fine-tuned model training
- [ ] A/B testing vs. base models
- [ ] Cost and quality evaluation

**Note**: Fine-tuning is a last resort. Most problems should be solved through better prompting, RAG, or agent design.

---

## Backlog

### High Priority

- [ ] Conversation export to multiple formats
- [ ] Conversation statistics dashboard
- [ ] Multi-model comparison UI
- [ ] Cost tracking over time

### Medium Priority

- [ ] Voice input/output *(now scoped under `AON-05`)*
- [ ] API server mode (for integrations) *(context access now scoped under `HUB`; anything beyond that is out per ADR-034's scope guard)*
- [ ] MCP servers log "disconnect error: Attempted to exit cancel scope in a different task than it was entered in" on every `/exit` (seen 2026-10-03 for `cortex` and `n8n`). Likely cause, not yet verified: `MCPClientManager.shutdown()` (`packages/integrations/mcp/client.py`) runs each `disconnect()` as a new task via `_run_async`, while the stdio connection's anyio context was entered in the connect task, so it must be exited in that same task. Harmless so far (the servers still stop), but it hides real shutdown errors *(S)*

> Dropped 2026-07-31: *Mobile companion app* — Telegram (`AON-02`) plus the GUI
> over Tailscale reaches parity at near-zero build cost.

### Low Priority / Future Ideas

- [ ] Multi-user support
- [ ] Cloud sync (optional, end-to-end encrypted)
- [ ] Plugin system for community extensions
- [ ] Integration marketplace

> **Note**: The former "HEARTBEAT.md — proactive agent loop" backlog item
> (cron-triggered task monitoring, inspired by the OpenClaw pattern) is now
> tracked as first-class work under the `AON` initiative above.

---

## Roadmap Principles

1. **Ship small, iterate fast**: Each milestone delivers usable value
2. **Metrics-driven**: Measure before optimizing
3. **User needs first**: Build features that solve real problems
4. **Technical excellence**: Maintain code quality and documentation
5. **Flexibility**: Adjust based on learnings and user feedback

---

*Last updated: 2026-09-30*
