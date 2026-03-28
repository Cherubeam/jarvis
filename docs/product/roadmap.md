# Product Roadmap

## Phase 1: Foundation & Metrics

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
- [x] 8 golden test conversations defined

---

## Phase 2: Evaluation & Quality Metrics

**Status**: ✅ Complete
**Timeline**: Completed Late January 2026

### Features

#### Testing Infrastructure

- [x] Golden test conversation suite (8 cases)
- [x] Automated test runner (pytest)
- [x] LLM-as-judge for automated quality evaluation
  - 33 unit tests (evaluator + storage)
  - Structured JSON results + markdown reports
  - Historical trend tracking
  - Cost management (~$0.41/run)
  - On-demand via `--evaluate` flag
- [x] Baseline quality metrics across different models

#### Things 3 Integration (Phase A — Context Awareness)

- [x] Task sync module with `things.py` (SQLite) — replaced AppleScript
- [x] Auto-sync tasks to tasks.md on startup
- [x] 5-minute task cache to optimize performance
- [x] Grouped markdown output (area > project > tasks)
- [ ] Phase B (Interactive management) — Moved to Phase 5C

#### Metrics Implementation

- [x] Latency tracking (TTFT, total latency per response)
- [x] Response quality scoring (manual → automated)
- [x] Context utilization analysis
- [x] Cost per conversation type benchmarks

#### Model Comparison

- [x] Benchmark 3-5 models on golden test suite
- [x] Compare quality vs. cost tradeoffs
- [x] Document model-specific behaviors
- [x] Default model recommendation (Claude Sonnet 4.5)

---

## Phase 3: Context & Integrations

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

#### Obsidian Integration

- [x] Vault reader with path validation and symlink protection
- [x] `> [!JARVIS]` callout block parser
- [x] Diff computation with CLI (colored) and API (JSON) formatters
- [x] `ConfirmationHandler` ABC for GUI-ready write confirmation
- [x] `/daily-summary` CLI command
- [x] Nested daily note paths (`path_format` with strftime)
- [x] 83 tests (73 unit + 10 integration)

---

## Phase 4: Agent Framework

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

## Phase 5: Agent Capabilities

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

### 5A: Skills / Capabilities

**Status**: ✅ Complete

Vendor-portable, SKILL.md-driven task specifications. Skills use markdown as the primary artifact — compatible with Claude, ChatGPT, and any LLM out of the box.

**Structure**: `packages/skills/` (separate from agents — agents are general-purpose conversational partners, skills are task-specific workflows with defined inputs and outputs)

```
packages/skills/
  base.py              # BaseSkill class (parses SKILL.md, optional skill.py)
  registry.py          # Discovery: scans for SKILL.md files (not Python imports)
  nano_banana_pro/
    SKILL.md           # Capability spec — the portable artifact (Mode 1: SKILL.md only)
  content_evaluator/
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

### 5F: Filesystem Access Control

- [x] `FilesystemGuard` with `AccessLevel` enum and `AccessRule` dataclass
- [x] Most-specific-path-wins resolution replacing flat `allowed_dirs`
- [x] `load_filesystem_guard()` factory for YAML config
- [x] `VaultConfig` updated (`filesystem_guard` replaces `allowed_dirs`)
- [x] 24 tests in `test_filesystem_access.py`

### 5E: Knowledge Base / Deck-Skills

- [x] CardIndexer + CardSearcher (RAG for static reference content in ChromaDB)
- [x] TacticsAgent (cross-deck Pip Decks coaching orchestrator)
- [x] Deck-skill pattern (SKILL.md + skill.py + deck.yaml + resources/cards/)
- [x] `search_tactics` tool for cross-deck card search
- [x] Auto-discovery of deck-skills via `deck.yaml` presence
- [x] 25 new tests
- [x] Navigator Agent (`/navigator`) — personal alignment and structured review coaching
- [x] Architecture simplification: data-driven agents via meta.yaml, dual-path registry
- [x] Agent-to-skill delegation (implemented via agent-skill binding in `meta.yaml`)

### 5G: Developer Agent

- [x] Developer Agent (`/develop`) — self-improvement agent with codebase read tools, git operations, guarded file writes, and test runner
- [x] 14 tools across four modules (codebase, git, project writes, tests)
- [x] Extended agentic loop (`max_iterations: 20`) for multi-step edit-test-fix cycles

### 5H: Cortex — Vault Semantic Search

**Status**: ✅ Complete (JARVIS side)

Opt-in semantic search over the Obsidian vault via the external Cortex service (`cherubeam/cortex`). See ADR-029.

- [x] Phase 1: Vault-Only MVP — `CortexClient`, `search_vault_semantic` tool, graceful degradation, 14 tests
- [x] `refresh_index()` method for on-demand reindexing
- [x] Project knowledge migrated to Obsidian — context_builder no longer loads `projects/` statically

Further Cortex evolution (Readwise, Zotero, MCP, Inbox Processor) is tracked in the [`cherubeam/cortex` roadmap](https://github.com/Cherubeam/cortex/blob/main/docs/roadmap.md).

### 5B: Agent Orchestration

- [x] JARVIS delegation — sub-conversations with specialist agents (implemented in 0.10.0+Unreleased)
- [x] Agent-to-agent handoff with conversation context (Unreleased)
- [ ] LLM-based intent detection and auto-routing
- [ ] Error recovery and fallbacks

### 5C: Extended Tools

- [ ] Playwright-based fetch for JS-rendered pages
- [ ] Tool approval/permission UI
- [ ] Things 3 write operations as tools (Phase B — simpler now with SQLite read access)
- [x] Obsidian write operations as tools (implemented in 0.10.0)
- [ ] Web search integration

### 5D: Intelligent Model Routing

- [ ] Task complexity classification
- [ ] Route simple tasks → cheap models, complex → expensive models
- [ ] Cost savings tracking

---

## Phase 6: Web Interface

**Status**: Not Started
**Timeline**: Mid 2026
**Goal**: Add a web UI following the 3-step approach from [gui-architecture-notes.md](../research/gui-architecture-notes.md)

### Design Foundations

- [x] UI design principles — [`docs/design/principles.md`](../design/principles.md)
- [x] UI voice & tone guide — [`docs/design/voice-and-tone.md`](../design/voice-and-tone.md)
- [x] Design tokens (colors, typography, spacing) — [`docs/design/tokens.md`](../design/tokens.md)
- [x] Component inventory — [`docs/design/components.md`](../design/components.md)

### 6A: Event Decoupling (prerequisite)

- [x] Define event dataclasses in `packages/core/events.py` (`TextChunk`, `ToolCallStarted`, `ToolResult`, `UsageReport`, `AgentStarted`, `AgentFinished`, `DelegationRequested`)
- [x] `StreamHandler.stream()` emits typed events via `on_event` callback (backward compatible -- existing `on_chunk`/`on_tool_call` unchanged)
- [x] Extract shared bootstrapping from `main.py` -> `packages/core/app.py`
- [x] Keep CLI working exactly as before (thin adapter consuming events)
- [ ] Move print statements from `StreamHandler` into CLI adapter (deferred -- backward compat maintained via dual callback approach)

### 6B: API Layer

- [ ] FastAPI backend with SSE streaming (`apps/web/`)
- [ ] Single endpoint streaming events — verify with `curl`
- [ ] Conversation history API
- [ ] Session management

### 6C: Frontend

- [ ] Chat UI with streaming responses (framework decision deferred to implementation time)
- [ ] Conversation history browser
- [ ] Session switching

**Design principle**: Keep the core sync. Add async at the web boundary only. See [gui-architecture-notes.md](../research/gui-architecture-notes.md) for rationale.

---

## Phase 7: Context Window Management & Search

**Status**: In Progress

### Features

- [x] Intelligent truncation strategies (tool result trimming in main loop + delegates)
- [x] Summarization for old conversation context
- [x] Non-streaming mode for prompt caching (workaround for LiteLLM streaming bug)
- [ ] Token budget management
- [ ] Full-text + semantic search over conversations
- [ ] Conversation export and statistics

---

## Phase 8: System Monitoring & Optimization

**Status**: Not Started

### Features

- [ ] Structured logging and error categorization
- [ ] Continuous quality monitoring
- [ ] Prompt optimization based on metrics
- [ ] Cost optimization recommendations

---

## Phase 9: UX Enhancements

**Status**: Not Started

### Features

- [ ] Rich TUI improvements
- [ ] Profile switching (work/personal)
- [x] Model presets (fast/quality/balanced) ✅ — `--model` flag + `/model` command
- [ ] Export & sharing

---

## Phase 10: Fine-tuning (Optional)

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

- [ ] Mobile companion app
- [ ] Voice input/output
- [ ] API server mode (for integrations)

### Low Priority / Future Ideas

- [ ] HEARTBEAT.md — Proactive agent loop (cron-triggered task monitoring, inspired by OpenClaw pattern). Requires daemon/scheduler component; Jarvis is currently CLI-only.
- [ ] Multi-user support
- [ ] Cloud sync (optional, end-to-end encrypted)
- [ ] Plugin system for community extensions
- [ ] Integration marketplace

---

## Roadmap Principles

1. **Ship small, iterate fast**: Each phase delivers usable value
2. **Metrics-driven**: Measure before optimizing
3. **User needs first**: Build features that solve real problems
4. **Technical excellence**: Maintain code quality and documentation
5. **Flexibility**: Adjust based on learnings and user feedback

---

*Last updated: 2026-03-26*

