# Changelog

All notable changes to Jarvis will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **JARVIS GUI — Phase 1 (Chat shell)** — local desktop GUI peer to the CLI. Launch with `uv run jarvis-gui` (binds `127.0.0.1:8123`, auto-opens the browser; `--no-browser` to skip). Uses the same agents, tools, vault, conversation JSON, and approval flow as the CLI.
  - **Architecture**: FastAPI + WebSocket backend under `apps/gui/server/`; React 18 + Vite + TypeScript frontend under `apps/gui/web/` (bundle committed under `dist/` so fresh clones don't need Node).
  - **`apps/cli/session_factory.build_session()`**: the pre-loop wiring from `apps/cli/main.py` (config, agents, tool groups, logger, stream handler) lifted into a reusable factory parameterized on `ConfirmationHandler`. CLI now calls it with `CLIConfirmationHandler()`; GUI calls it with a `WebConfirmationHandler` bound per turn. No CLI behavior changes.
  - **WebStreamHandler** subscribes to `StreamHandler.on_event` (typed `Event` bus) and maps each event to a WS protocol dict over a bounded `janus.Queue`. Tool-call `Started`/`Result` pairs are collapsed into one wire event with `elapsed_ms`.
  - **WebConfirmationHandler** mirrors the two-method `ConfirmationHandler` ABC (`present_diff` buffers, `get_confirmation` blocks the worker thread on a `threading.Event`); resolved asynchronously by the client's `approval_decision` message. `discard()` releases blocked workers on disconnect / takeover.
  - **Bridge** orchestrates one turn end-to-end — builds history with `trim_tool_results` + `summarize_history`, runs `agent.run()` in `asyncio.to_thread`, emits chunk / tool_call / delegation / text / totals events, persists to `ConversationLogger`, saves the conversation file every turn.
  - **Visual fidelity**: ports JARVIS GUI.html v6 tokens verbatim (dark-first near-black surfaces, cyan default accent, mono-forward typography, 96px speaker-label gutter, CLI-transcript rows with colored left border). Acronym-aware `speakerLabel()` (OKR, MCP, RAG, LLM...). Stats line format exact (`[N tokens | $cost | TTFT: Nms | Total: Nms]`). Cost color brightens above $0.05 in the status bar.
  - **Chat-view features**: streaming text with chunk-level updates, tool-call cards (card/inline/dim variants), delegation notices, vault-write approval with diff + approve/reject, RAG recall cards, thinking indicator, Cmd+K/` `/` command palette over all 16 agents, live-mutating Tweaks panel (7 axes including accent-hue swap).
  - **Cut from Phase 1** (deferred to later phases): sidebar timeline mode; Dashboard / Agents / Conversations / Settings / Prompt-editor views (stubbed via the left rail); interactive delegation sub-loops; `/daily-summary` and `/outcomes` slash commands (CLI-only for now — GUI emits a "use the CLI" system event).
  - **Tests**: 12 new unit tests for `WebStreamHandler`, `WebConfirmationHandler`, and the WS protocol; all 1844 pre-existing tests still pass.
- **Outcome tracking (Phase 5K)** — closed loop on advice JARVIS gives. Adds `track_recommendation` shared tool that captures actionable recommendations as markdown files under `data/outcomes/` with YAML frontmatter (what, why, revisit_at, success_looks_like, conversation_id). Every captured item links back to the originating conversation.
- **`/outcomes` CLI command** — interactive scoring of pending outcomes past their revisit date. Prompts for outcome (happened/didnt/partial), quality (1–5), and a retrospective note. Atomic writes so interrupted sessions don't corrupt files; Ctrl-C mid-flow preserves earlier files.
- **`recall_outcomes` shared tool** — semantic search over reviewed outcomes via a new `OutcomeIndexer` and `OutcomeSearcher` (ChromaDB collection `outcomes`). Only reviewed items are indexed — pending advice has no feedback signal.
- **`packages/core/frontmatter.py`** — YAML frontmatter utilities: `parse`, `dump` (preserves key order), and `write_atomic` (tmp-file + `os.replace`). `parse_frontmatter` in `context_builder.py` becomes a thin re-export for backward compatibility.
- **`packages/core/date_utils.py`** — `parse_relative_date()` accepting `"N day(s)"`, `"N week(s)"`, `"N month(s)"` (30-day), `"N year(s)"` (365-day), `"tomorrow"`, `"next week"`, `"next month"`, and ISO dates.
- **`outcomes:` config section** in `config/default.yaml` (`enabled: true` default, `dir: data/outcomes`). Ships a default `filesystem.access_rules` entry so the tool works out-of-the-box; breaks the empty-default convention deliberately for a framework-level feature.
- **JARVIS orchestrator directive** — when `track_recommendation` is wired up, the system prompt gains an "Outcome Tracking" section teaching JARVIS to call the tool only for actionable advice with a timeframe (not opinions, hypotheticals, or lookups).

### Test coverage
- 95 new unit tests: `test_date_utils.py` (21), `test_frontmatter.py` (13), `test_outcome_tools.py` (18), `test_review_command.py` (18), `test_outcome_indexer.py` (19), `test_jarvis_agent.py` (+4).

---

## [0.15.0] - 2026-04-13

### Added
- **Readwise integration** — CLI-based access to Readwise Reader library and highlights via 6 new tools: `search_reading_list`, `search_highlights`, `get_document_details`, `save_to_reader`, `tag_readwise_document`, `move_readwise_document`. Uses the `@readwise/cli` npm package as a subprocess wrapper with JSON parsing, rate limit handling, and graceful degradation when CLI is not installed.
- **Reading assistant agent** (`/reading`) — Readwise-powered agent for library search, inbox triage, reading recaps, highlight synthesis, and document management.
- **Reader persona support** — Context builder now loads `data/context/reader_persona.md` into all agents' system prompts, making every agent reading-aware. Generate via Readwise's `build-persona` skill or manually.
- **`readwise:` config section** in `config/default.yaml` with `enabled` and `cache_ttl_seconds` settings.

### Changed
- **Mutation testing — never-targeted tools**: Strengthened `test_test_tools.py` (9 new tests), `test_mutation_tools.py` (19 new tests), and `test_card_indexer.py` (3 new/strengthened tests) with schema validation, exact error messages, stderr handling, truncation boundaries, status filter edge cases, and command construction verification.

---

## [0.14.1] - 2026-04-13

### Changed
- **Mutation testing: kill rate 62.3% → 74.6%** — 218 new tests across 14 branches, +1,172 mutants killed. Four phases targeting tool factories, core modules (history, memory), importers (chatgpt, claude, claude_context), and remaining tool factories (things3, project_write, git). Test count: 1,519 → 1,719.
- **Pragma sweep**: 64 `# pragma: no mutate` annotations added to LLM-facing description strings and pure-literal logger calls across 8 files. Suppresses equivalent mutants that don't affect code behavior.
- **Mutation testing report updated** with per-phase progress table, per-module kill breakdown, and current remaining survivors.

### Test improvements by module
- **vault_read/write_tools** (13 tests): schema validation, path traversal, default args, output format
- **cortex_search, conversation_recall, web_fetch** (7 tests): schema, clamping, truncation markers
- **codebase_tools** (17 tests): schema for all 4 tools, exact errors, binary file, dotfile hiding
- **blog_tools** (5 tests): exact error messages, property-set schemas
- **delegate, suggest_improvements, content_evaluator** (7 tests): schema, temperature override, model passthrough
- **stream_handler** (8 tests): UsageReport fields, TokenUsage accumulation, tool message keys
- **history** (25 tests): `_approx_tokens`, `_format_messages_for_summary`, trim boundary, constants
- **memory** (27 tests): agent tagging, latency boundaries, migration defaults, utilization keywords
- **chatgpt importer** (27 tests): all content_type branches, multimodal edges, null fields
- **claude importer** (15 tests): metadata keys, tool_result handling, update_conversation sync
- **claude_context importer** (24 tests): starter detection, sanitize, slugify, memory formats
- **things3_tools** (16 tests): cross-platform schema validation, parameter forwarding, cache TTL
- **project_write_tools** (14 tests): schema, exact errors, default extensions
- **git_tools** (17 tests): schema for all 6 tools, exact outputs, log cap

---

## [0.14.0] - 2026-04-12

### Added
- **Linux CI mutation testing workflow**: New GitHub Actions workflow at `.github/workflows/mutation.yml` runs mutmut on Ubuntu (where `os.fork()` is safe) via manual dispatch or a weekly Monday 06:00 UTC cron. Uploads `mutmut-results.txt`, `mutmut-summary.txt`, and `mutmut-run.log` as artifacts (90-day retention). First workflow in the repo. Free on public repos; no secrets required. This is now the only working environment for mutation testing on jarvis.
- **2026-04-11 Linux CI mutation baseline**: First full Linux sweep produced `5,696 killed / 3,477 survived / 749 no tests / 7 timeout` across 9,929 mutants — a 62.0% kill rate on testable mutants, ~5 points above the April macOS baseline. All 44 modules in `packages/core/` now covered, including the 10 previously-segfaulted on macOS. Results documented in `docs/engineering/mutation-testing-report.md`.

### Changed
- **Mutation testing report**: Documented the 2026-04-11 macOS regression — every mutant now segfaults (9,180/9,929) including modules that previously scored 76–86%. Local mutmut on macOS is effectively unusable; Linux CI is the path forward. Historical 2026-04-03 numbers preserved in the report as the last-known-good baseline.

### Fixed
- **Mutmut-blocking env-clear tests**: `test_card_renderer.py::TestEnsureHomebrewLibPath` and `test_model_resolver.py::test_empty_when_no_keys_set` used `patch.dict(os.environ, {}, clear=True)`, which wiped mutmut's `MUTANT_UNDER_TEST` env var and caused the trampoline to `KeyError` at baseline time — blocking every mutation run before it started. Scoped the env clear to just the variables each test cares about.
- **CI test-harness blockers**: Four separate issues prevented mutmut from running on Linux, all fixed:
  - `test_base_skill.py::TestBaseSkillFromSkillMd` and `test_skill_registry.py::TestDiscoverSkills` read gitignored user-local skill files — split into dedicated classes gated on file presence.
  - `test_things3_tools.py` triggered `import things` via mocked `sys.platform=darwin`, but `things-py` hits the Things 3 SQLite database on import. Skipped the affected classes on non-Darwin.
  - `mutmut html` step in the CI workflow referenced a non-existent subcommand; removed.

---

## [0.13.0] - 2026-04-12

### Added
- **Agentic golden tests**: 4 new golden tests validating tool calling (09), agent delegation (10), multi-step tool chaining (11), and tool termination (12). Tests use mock tools with canned responses and a hybrid evaluation: programmatic checks for tool call correctness + LLM judge for response quality.
- **Rich geometric monoline image prompts**: Per-pattern visual prompts with category-specific geometric patterns for the pattern card generator.
- **Show routed model in usage stats**: When model routing changes the model (e.g. quality preset), the actual model used is now shown in the usage report alongside the requested model.
- **Chat name prefix → tag parsing**: Chat importer now parses name prefixes (e.g. `[topic]`) into tags and stores Claude-generated conversation summaries.

### Changed
- **Default model switched to Qwen 3.5 Flash**: Benchmarked 7 models across 12 golden tests (8 conversation + 4 new agentic tool-use tests). Qwen 3.5 Flash scored 0.925 with 100% pass rate — higher than Claude Sonnet 4.6 (0.918, 92%) at 66x lower cost ($0.0001 vs $0.0066 per request). Quality preset remains Claude Opus 4.6 for complex tasks.

### Fixed
- **Golden test cost tracking**: Cost was always reported as $0.00 because `calculate_cost_from_litellm()` silently returned 0 for streaming responses. Now uses `get_model_pricing()` + `pricing.calculate_cost()` — the same approach as the production `StreamHandler`.
- **WeasyPrint rendering pipeline**: Replaced removed `write_png()` with PDF→PyMuPDF pipeline; fixed Homebrew library discovery on macOS so WeasyPrint finds GLib/Pango/Cairo via `DYLD_FALLBACK_LIBRARY_PATH`.
- **Card rendering polish**: Fixed card image paths, markdown rendering, text truncation limits, and footer centering in the pattern card generator.
- **Spinner glitches**: Used transient `Live` displays to prevent stale spinner frames; restart Thinking spinner after tool calls complete; remove spinner between consecutive tool calls.
- **Suppress LiteLLM debug output**: Prevented LiteLLM internal debug messages from leaking to stdout during normal operation.
- **Enum argument handling**: Use explicit `exact_match_args` for enum args in delegation test assertions, preventing false positives from fuzzy matching.
- **Dry-run importer fix**: Dry-run mode now correctly detects already-imported conversations instead of silently skipping them.

### Docs
- MCP server setup guide added to README.
- Model comparison table updated with April 2026 pricing and benchmark candidates.

---

## [0.12.0] - 2026-04-05

### Added
- **MCP Client Integration**: JARVIS can now connect to external MCP (Model Context Protocol) servers as a client. MCP server tools are bridged into the existing ToolDefinition system and appear as regular tool groups that agents can reference in `meta.yaml`. Supports stdio, SSE, and streamable HTTP transports. Adding/removing MCP servers is a config-only change (`mcp.servers` in `config/local.yaml`). Graceful degradation: unreachable servers are skipped at startup. Async/sync bridge via background event loop thread. 44 unit tests across config parsing, tool bridging, and client lifecycle.
- **Things 3 Write Tools**: Three new tools (`create_task`, `complete_task`, `update_task`) for managing Things 3 tasks via URL scheme. Available to the JARVIS orchestrator and delegate agents via `things3_tools` tool group. Task UUIDs now included in synced task context for referencing. Operations are best-effort (fire-and-forget URL scheme). Gated on `things3.enabled` config and macOS platform. 24 unit tests.
- **Mutation Testing**: Integrated mutmut for mutation testing to identify weak, redundant, or missing tests. Two developer agent tools (`run_mutation_tests`, `show_mutation_results`) wrap mutmut CLI for LLM-assisted analysis. Also usable directly via `uv run mutmut run --paths-to-mutate <module>`. Configured in `[tool.mutmut]` in pyproject.toml with fast-fail runner (`-x --tb=no -q`). 19 unit tests.
- **Pattern Card Generator** (`/pattern-cards`): New agent that generates visual "playing cards" from Obsidian pattern notes for workshop facilitation. Parses pattern frontmatter and markdown sections, renders cards as HTML/CSS + PNG via WeasyPrint. Cards show pattern name, category, intent, problem/solution summary, and related patterns with category-based color coding. Two-track image support: Track A generates image prompts for manual use in Gemini/DALL-E (`generate_image_prompts` tool); Track B auto-generates images via litellm API (opt-in, `pattern_cards.image_generation.enabled: true`). Output: `data/pattern-cards/cards/`. Config: `pattern_cards` section in `default.yaml`. Dependencies: `weasyprint`, `jinja2`. 56 unit tests.

### Fixed
- **LiteLLM Security Pin**: Pinned `litellm>=1.82,<1.82.7` to block supply-chain-compromised versions 1.82.7-1.82.8 (TeamPCP attack, March 24 2026).
- **Tool Result Trimming in Main Loop**: Extended `trim_tool_results()` to the main JARVIS conversation loop (previously only applied to delegate sessions). Reduces cumulative tool-related input tokens by ~88% in long sessions, addressing the primary cost driver for token accumulation.

### Added
- **History Summarization** (opt-in): Compresses old conversation turns using the fast model (Gemini Flash) when history exceeds a token threshold (~40K). Implements a summarize-once pattern with `[JARVIS_SUMMARY]` marker to avoid re-summarizing every turn. Enable via `summarization.enabled: true` in config.
- **Non-Streaming Mode** (opt-in): New `/stream` command toggles between streaming and non-streaming response modes. Non-streaming mode enables prompt caching via OpenRouter, which is blocked in streaming mode due to an upstream LiteLLM format inconsistency. Configure default via `models.streaming` in config. Includes `_run_agentic_loop_nonstreaming()`, `_complete_simple()`, and spinner-based display.
- **Cortex Semantic Search**: New `search_vault_semantic` tool queries the Obsidian vault by meaning (not just keywords) via the Cortex API. Gracefully degrades to a fallback message when Cortex is unreachable. Available as a shared tool to all agents when `cortex.enabled` is set in config.
- **Daily Summary Date Argument**: `/daily-summary` now accepts an optional `YYYY-MM-DD` date argument to generate summaries for past dates (e.g., `/daily-summary 2026-03-18`). Defaults to today when no date is provided.
- **Strategyzer Agent** (`/strategize`): Strategy consulting agent for competitive analysis, growth loops, pricing, unit economics, and market positioning. Binds `strategy-tactics` (deck-skill with card search) and `pm-strategist` (simple skill) for evidence-driven strategic advice.
- **Prompt Caching (Provider-Aware)**: Automatic prompt caching for Anthropic models — injects `cache_control` breakpoints into system messages when the model string contains `anthropic`. Cache token metrics (`cache_read_tokens`, `cache_write_tokens`) are extracted from all providers generically and flowed through `TokenUsage`, `StreamResult`, `UsageReport` events, and conversation logs. Cost calculation is cache-aware: uses provider-specific rates from LiteLLM cost map when available, defaults to Anthropic rates (0.1x read, 1.25x write). Non-Anthropic models are unaffected. Expected 80-90% cost reduction on the ~8K system prompt portion for multi-turn Anthropic sessions.
- **Phase 6A: Event Decoupling** — Foundation for multi-agent and Web UI scenarios.
  - Typed event dataclasses (`TextChunk`, `ToolCallStarted`, `ToolResult`, `UsageReport`, `AgentStarted`, `AgentFinished`, `DelegationRequested`) in `packages/core/events.py`.
  - `StreamHandler` emits events via `on_event` callback (backward compatible — existing `on_chunk`/`on_tool_call` unchanged).
  - Shared bootstrap extracted to `packages/core/app.py` (`load_config`, `init_llm_client`, `init_stream_handler`, `discover_all_agents_and_skills`, `instantiate_agent`).
  - Comprehensive architecture doc: `docs/engineering/multi-agent-architecture.md` covering Phase 6A status and Scenarios A/B/C design.

### Changed
- **Hybrid Context: Project Knowledge via Obsidian**: Removed static project file loading from `context_builder.py`. Project knowledge now lives exclusively in Obsidian (`02 – Projects/`) and is retrieved on demand via `search_vault_semantic` and `read_note` tools. Reduces system prompt size and eliminates dual-maintenance of project docs. `current_focus.md` slimmed to a lightweight pointer with project names only.
- **CortexClient `refresh_index()`**: New method to trigger incremental re-indexing via `POST /index/refresh`, enabling JARVIS to request a reindex after bulk vault writes.
- **Cortex Roadmap Transfer**: Phases 2–5 (Readwise, Zotero, MCP, Inbox Processor) moved to the `cherubeam/cortex` repository's own roadmap. JARVIS roadmap 5H now references the external roadmap.
- **Web Tools Refactor**: Extracted `WEB_SEARCH_TOOL` and `FETCH_URL_TOOL` from hardcoded JARVIS init into a `web_tools` tool group. Researcher agent now has independent web search capability via `tools: [web_tools]` in meta.yaml.
- **Simplifier Agent Redesign**: Rewrote the simplifier from a 5-rule placeholder into a technique-aware clarity specialist. New system prompt includes 12 simplification techniques with selection criteria, 4 adaptive output modes (Quick Explain, Deep Dive, Compare/Contrast, Misconception Correction), audience assessment protocol, domain-specific heuristics, quality self-check, and multi-turn refinement guidance. Added `max_iterations: 5` for follow-up conversations.
- **Streaming Always Markdown**: All streaming responses now render as Markdown in the CLI, removing the conditional `_has_markdown()` detection. Simpler and more consistent rendering.
- **Delegation Message Framing**: When JARVIS delegates to a specialist agent, the task is now framed as a goal with explicit instructions to confirm, ask scoping questions, and propose a plan before acting.

### Fixed
- **DuckDuckGo Package Rename**: Migrated from deprecated `duckduckgo-search` to `ddgs` package (v9.x). Updated import, removed context manager pattern (no longer needed in v9), and simplified API call.
- **Tool Retry Loop Prevention**: Enhanced tool error messages with fallback guidance ("do not retry — try a different approach") so the LLM stops retrying a failing tool and uses alternative tools or existing knowledge instead. Applied to both web_search-specific and generic executor-level error handling.
- **Obsidian Note Creator Vault Writing**: Added missing `slip_box` config section and filesystem access rule for `05 – Slip-Box`. Updated system prompt to use `write_note` tool when available instead of outputting code blocks.
- **Delegate Session Token Bloat**: Added tool result trimming for delegate agent sessions (`packages/core/history.py`). Old tool results are truncated to 200 chars while recent messages stay intact, preventing history from ballooning to 30K+ tokens in multi-turn sessions. First implementation step of the token economics history management priority.
- **Prompt Caching Investigation**: Diagnosed why prompt caching shows zero cache hits despite correct implementation. Root cause: LiteLLM formats messages differently for streaming vs non-streaming via OpenRouter (different prompt token counts = different cache keys). Non-streaming caching works; streaming (used by JARVIS) does not. Added diagnostic script (`scripts/test_prompt_caching.py`) and updated research docs. Blocked on upstream LiteLLM fix.
- **Raw Markdown in Pattern Expert Output**: Pattern language expert now outputs regular markdown in conversation instead of wrapping drafts in fenced code blocks, so Rich renders styled headings, tables, and bold text in the terminal.
- **Cost Tracking in Terminal Tool Path**: When `pricing` was `None`, the delegation (terminal tool) path silently reported `cost_usd = 0.0` instead of falling back to LiteLLM cost calculation. Also added missing `UsageReport` event emission so delegation costs appear in session summaries. Extracted `_calculate_cost()` helper to centralize pricing→fallback logic across all three streaming paths.
- **JARVIS Iteration Limit**: JARVIS exhausted the default 5-iteration limit calling vault tools before it could delegate to specialist agents. `BaseAgent.run()` now passes `max_iterations` from config (removing duplicated logic in `DataDrivenAgent`), JARVIS is set to 15, and the delegation directive more strongly instructs first-turn delegation.
- **Credit Error Crash**: 402 errors from OpenRouter now handled gracefully — max_tokens is automatically reduced to what the user can afford, with a warning message. If credits are too low for a useful response (< 256 tokens), a clear error with a link to add credits is shown.
- **Prompt Token Limit Error**: 402 errors from OpenRouter when the prompt itself exceeds the API key's monthly token limit are now caught and shown as a clear error with a link to create a key with a higher limit, instead of crashing with an unhandled `APIError`.
- **Agent Credit Error**: All agents crashed with a 402 error when OpenRouter credits were below the model's default max_tokens (65536). Added configurable `default_max_tokens` (16384) applied globally unless an agent specifies its own.
- **Pattern Agent**: Vault write tools (create_note, edit_note, list_notes_in_dir) now enabled via missing `obsidian.writing.patterns` config; system prompt deduplicated using `{skills}` placeholder; concrete output format added for vault notes; agentic loop enabled with `max_iterations: 10`.
- **Pattern Agent Delegation**: Pattern agent no longer skips discussion when delegated from JARVIS — added session start protocol requiring scoping questions before generating patterns.
- **Apply Prompt Blocked by Spinner**: Tool execution (e.g. `create_note` confirmation prompt) was unusable because `rich.Live` spinner overwrote the input area. Added `on_before_tool_exec` / `on_after_tool_exec` callbacks to `StreamHandler` that pause/resume the Live display during tool execution.

### Added
- **Token Economics Research**: Analysis document (`docs/research/token-economics.md`) covering system prompt costs, five optimization approaches with tradeoff matrix, and a recommended layered strategy.
- **Token Economics Instrumentation**: Lightweight measurement of context usage patterns — per-section token breakdown in session summaries, history growth tracking per turn, context utilization heuristic (which sections are referenced in responses). All data saved to conversation JSON for cross-session analysis. No behavior changes — observation only.
- **Token Economics Cost Status**: Analysis document (`docs/research/token-economics-cost-status.md`) with actual cost data from 28 sessions ($10.94 total), cost driver analysis, savings opportunities ranked by impact, and cost tracking discrepancy investigation.

---

## [0.11.0] - 2026-03-16

### Changed
- **Year-Based Conversation Storage**: Conversations are now organized into `data/conversations/YYYY/` subdirectories instead of a flat directory. Includes a migration script (`scripts/migrate_conversations_to_years.py`) to move existing files. All importers, the indexer, and `ConversationLogger` updated accordingly.

### Fixed
- **Daily Summary Spinner**: Activity spinner now shows for `/daily-summary`, matching the main chat loop behavior instead of the static "Generating daily summary..." message.
- **Daily Summary Credit Error**: `/daily-summary` crashed with a 402 error when OpenRouter credits were lower than the model's default max_tokens (65536). Now explicitly caps max_tokens at 4096, which is appropriate for short structured summaries.

### Added
- **UI Design Foundations**: Four framework-agnostic design documents in `docs/design/` — [design principles](design/principles.md), [voice & tone guide](design/voice-and-tone.md), [design tokens](design/tokens.md), and [component inventory](design/components.md). Establishes visual language, UI copy standards, and component vocabulary ahead of Phase 6.
- **Activity Spinner**: Animated "Thinking…" spinner displays immediately after pressing Enter, filling the gap before the first LLM token arrives. Spinner is automatically replaced by streaming text — no changes needed to callers.
- **Substack Prepare-to-Publish Skill**: New 7-step interactive pre-publication workflow for the writing agent. Generates Substack tags, SEO descriptions, article summaries, LinkedIn post drafts, and Substack note drafts with promotional timelines. Persists chosen promotional content to Obsidian vault callout blocks.
- **Agent Split — Writer → 4 Specialists**: Split the monolithic `writing` agent into `writer` (drafting/editing), `content_reviewer` (structured evaluation), `substack_publisher` (pre-pub workflow), and `substack_image_creator` (header image prompts). Each agent gets only the tools it needs — `evaluate_content` is no longer available during publishing workflows.
- **Shared Prompt Includes**: New `packages/agents/_shared/prompts/` directory for prompt files shared across agents (voice-profile, anti-patterns). Resolver falls back to shared dir when include not found in agent-local `prompts/`.

### Changed
- **Naming Conventions Normalized**: Agent directories use actor nouns (`writer`, `researcher`, `simplifier`, `tactics_coach`). All `meta.yaml` `name:` fields use `snake_case`. Renamed `vault_tools.py` → `vault_read_tools.py` and `make_vault_tools()` → `make_vault_read_tools()` to match `vault_write_tools.py`.
- **Agent Renames**: `writing` → `writer`, `research` → `researcher`, `clarity` → `simplifier`, `tactics` → `tactics_coach`. Kebab-case `name:` fields normalized to snake_case: `obsidian-note-creator` → `obsidian_note_creator`, `okr-architect` → `okr_architect`, `pattern-language-expert` → `pattern_language_expert`.

### Changed
- **All Delegate Agents Data-Driven**: Migrated WritingAgent, TacticsAgent, and DeveloperAgent from Python classes to `meta.yaml` + `prompts/system.md`. All 9 delegate agents are now data-driven. Removed `agent_class` from `AgentMeta` and the Python-class discovery/instantiation path.
- **Per-Agent Tool Declarations**: Replaced flat `agent_only_tools` list with named `tool_groups` registry. Each agent declares which tool groups it needs via `tools:` in `meta.yaml` (e.g. writing gets `blog_tools`, `content_evaluator`, `suggest_improvements`; developer gets `dev_tools`; tactics gets `card_search`). Agents no longer receive tools they don't need.
- **Prompt Includes**: New `prompt_includes:` field in `meta.yaml` replaces `{placeholder}` tokens in system prompts with content from included files. Used by the writing agent for `voice-profile` and `anti-patterns`.
- **Max Iterations**: New `max_iterations:` field in `meta.yaml` passed through to `StreamHandler.stream()`. Used by developer agent (20 iterations for multi-step workflows).

### Fixed
- **max_tokens Regression**: Changed `AgentConfig.max_tokens` default from `4096` to `None`. The recent max_tokens wiring was sending 4096 to LiteLLM for all agents, capping responses that were previously unlimited. Now only agents with explicit `max_tokens` in `meta.yaml` have it enforced.
- **Stale Documentation**: Updated architecture.md (agent list 9→12, file tree), api.md (example agent name), roadmap.md (Phase 4 agent names), and AGENTS.md (max_tokens comment) to reflect current agent names and conventions.
- **Substack Publisher Improvements**: Reduced redundant tool calls in prepare-to-publish workflow (Step 1 now uses `list_blog_posts` + `read_blog_post` instead of multiple `search_notes`). Added explicit guidance to preserve article body verbatim when using `edit_blog_post`. Improved confirmation prompt UX from ambiguous `[y/N]` to clear `(y/yes to confirm):`. Wired `max_tokens` from `AgentConfig` through to LiteLLM calls (substack_publisher set to 16384) to prevent runaway token usage and 402 errors.
- **Normalize Exit Commands**: Removed plain `exit`/`quit` from the main loop (now slash-only: `/exit`, `/quit`). Added `/quit` to delegate sessions alongside `/exit` and `/back`. Updated hint messages to reflect the consistent commands.
- **Tool Context Loss in Delegate Sessions**: Tool call messages and results were discarded from delegate agent `session_history`, causing agents to lose context of what they read and re-call the same tools. Now persists `result.tool_messages` to both session history and logger, mirroring the JARVIS main loop fix.
- **TTFT Always 0ms**: Removed duplicate `start_request()` calls in `_stream_from_response()` and `_stream_simple()` that reset the metrics timer right before streaming, causing TTFT to measure only microseconds instead of actual user-perceived latency.
- **`/exit` Command Not Recognized**: Added `/exit` and `/quit` as recognized slash commands in the main CLI loop, so they work consistently with the non-slash `exit`/`quit` variants.
- **Dynamic Delegation Directive**: Replaced hardcoded 3-agent delegation directive in JARVIS with `_build_delegation_directive()` that dynamically lists all discovered agents. Developer, clarity, research, navigator, OKR architect, and pattern language expert now appear in JARVIS's delegation guidance.
- **Things 3 Tag Preservation**: Added instruction in `tasks.md` header telling JARVIS to always include all tags in brackets when presenting tasks, preventing tag paraphrasing.

### Added
- **Agent Attribution in Conversations**: Assistant messages now include an optional `"agent"` field identifying the originating agent (e.g. `"JARVIS"`, `"writing"`, `"developer"`). Existing conversations without the field are unaffected.
- **Developer Agent Roadmap**: `docs/product/developer-agent-roadmap.md` documenting Phase 1 (complete), Phase 2 (autonomous operation), and Phase 3 (continuous self-improvement) plans. Cross-references ADR-028.

### Changed
- **Daily Summary Prompt**: Moved `daily_note_entry.md` and `general_writing.md` from `data/prompts/obsidian/` into `packages/agents/jarvis/prompts/`, using `BaseAgent.load_prompt()` like all other agents. Removed legacy `prompts.py` module, `obsidian.prompts_dir` config key, and `data/prompts/obsidian/` directory.
- **Things 3 SQLite Migration**: Replaced AppleScript integration with `things.py` (direct SQLite reads). Added `area` field to `Task` dataclass. Markdown output now grouped by area > project > tasks. Removed `detect_things3_language`, `fetch_tasks_applescript_direct`, `MCPThings3Client`, `parse_task_response`. Removed `asyncio` dependency from task sync. Removed `projects_to_include` config key.
- **Data-Driven Agents**: All 9 delegate agents use `meta.yaml` + `prompts/system.md`. `DataDrivenAgent` supports `prompt_includes`, `max_iterations`, and per-agent `tool_groups`.
- **Agent Registry**: Discovery via `meta.yaml` only. `AgentMeta` dataclass with `tool_groups`, `skills`, `vault_writing` fields.
- **Agent Instantiation**: `_instantiate_agent()` and `_assemble_agent_tools()` in CLI build agents from `shared_tools` + declared tool groups.

### Removed
- **Standalone Skill Invocation**: `--skill` CLI flag, `/skills` listing command, and skill slash-command routing removed. Skills remain as passive knowledge packs for card indexing and tool wrapping.
- **Boilerplate Agent Code**: 12 files deleted (6 × `__init__.py` + `agent.py`) from data-driven agent directories.
- **Per-Agent Test Files**: `test_promoted_agents.py`, `test_navigator.py`, `test_pattern_language_expert.py` replaced by parameterized `test_data_driven_agents.py`.

### Added
- **Agent-Skill Binding**: Agents can declare `skills:` in `meta.yaml` to automatically inject skill knowledge into their system prompt. Simple skills append SKILL.md content; deck-skills add card search tool and prompt hints. `resolve_skills()` in `packages/skills/resolver.py` handles resolution.
- **Agent-to-Agent Handoff**: Full conversation history flows between agents through JARVIS. When JARVIS delegates to Agent B after Agent A's session, Agent B receives Agent A's complete conversation. `DelegationState.context` carries JARVIS's pre-delegation summary; `prior_session` carries the full prior agent conversation.
- **Delegation Context**: `delegate_to_agent` tool now accepts an optional `context` parameter for JARVIS to summarize relevant background before delegating.
- **Parameterized Agent Tests**: `test_data_driven_agents.py` covers all 6 data-driven agents with 24 parametrized tests (meta.yaml validation, instantiation, streaming, registry discovery).
- **CLI Instantiation Tests**: 5 new tests in `test_cli_agents.py` for the `_instantiate_agent()` helper.
- **Per-Agent Vault Write Tool Routing**: Agents declare `vault_writing: <config_key>` in `meta.yaml` to receive scoped vault write tools. `_make_agent_vault_tools()` reads `obsidian.writing.<key>` config and calls `make_vault_write_tools()` per agent. `pattern-language-expert` → `patterns`, `obsidian-note-creator` → `slip_box`. Global patterns vault write tools removed from `agent_only_tools`. New `slip_box` config section in `default.yaml`. 9 new tests.
- **Developer Agent** (`/develop`): Self-improvement agent with codebase awareness, git sandbox, and scoped write access. 14 tools across four modules: codebase read tools (`read_source_file`, `search_code`, `list_directory`, `read_architecture_map`), git operations (`git_status`, `git_diff`, `git_branch`, `git_add`, `git_commit`, `git_log`), guarded file writes (`write_file`, `edit_file`, `create_directory`), and a test runner (`run_tests`). Phase 1 write scope limited to data-driven files (`.md`, `.yaml`, `.yml`).
- **Codebase Map Generator**: `scripts/generate_codebase_map.py` produces `data/codebase_map.md` — a compact project summary used by the developer agent for codebase orientation.
- **Extended Agentic Loop**: `StreamHandler.stream()` now accepts a `max_iterations` parameter (default unchanged at 5). Developer agent uses `max_iterations=20` to support multi-step edit-test-fix cycles.
- Tests: 1025 pass, 11 skip

---

## [0.10.0] - 2026-03-12

### Added
- **Vault Write Tools**: Generic `make_vault_write_tools()` factory creates `create_note`, `edit_note`, and `list_notes_in_dir` tools scoped to any vault directory. Follows the blog_tools closure pattern. Pattern Language Expert agent now receives these tools for persisting patterns directly to the Obsidian vault.
  - Configurable target directory and template path via `obsidian.writing.patterns` in config
  - Diff-based confirmation with reasoning before any write
  - Descriptive file names with spaces (user convention)
  - 17 new tests for vault write tools, 3 for pattern agent; total: 916 pass, 11 skip
- **Pattern Language Expert `extra_tools`**: Agent now accepts `extra_tools` parameter (like WritingAgent). System prompt updated with vault tools section and graceful degradation to conversation-only mode.

### Fixed
- **Delegation Tool Passing**: Delegated agents now receive both vault read (Tier 1) and vault write (Tier 2) tools. Previously `all_delegate_tools = agent_only_tools` missed `extra_tools`.

### Added
- **Obsidian Note Creator Agent** (`/obsidian-note-creator`): Promoted from skill to agent for multi-turn evergreen note extraction sessions
  - Create-review-refine cycle for iterative note development
  - Session awareness: tracks created notes, suggests connections and refinements
  - Full Obsidian-compatible output with YAML frontmatter, wiki-links, and Note Maps
  - 3 new tests; total: 896 pass, 11 skip

### Removed
- Skill symlink for `obsidian-note-creator` from `packages/skills/` (replaced by agent)

### Added
- **Claude Importer Incremental Sync**: Re-importing a Claude export now updates existing conversations with new messages (appended), title changes, and session timestamps. Additive-only — JARVIS never removes messages even if deleted in Claude. New `Updated: N` count in import summary output.
- **Runtime Model Switching** (ADR-023): `--model` CLI flag and `/model` slash command for switching models at startup or mid-session. Named presets (`fast`, `quality`, `balanced`) configurable in `config/default.yaml`. Multi-provider support — API keys collected from env vars, provider inferred from model ID prefix.
- **Vault Read Tools**: Three new read-only tools (`read_note`, `search_notes`, `read_daily_note`) give JARVIS direct access to the Obsidian vault for information retrieval. 50KB content cap, 100-entry search cap. Inherits FilesystemGuard access control.
- **Vault Search Sorting**: `search_notes` tool now supports `sort_by` (`"name"` or `"modified"`) and `limit` (1–100) parameters. `sort_by="modified"` returns most-recent-first with timestamps (`YYYY-MM-DD HH:MM  path`).
- **Capability Ownership Framework** (ADR-022): Four-criteria decision framework for placing capabilities on JARVIS vs subagents. Core principle: JARVIS owns general-purpose reads; subagents own creative transformation.

### Changed
- **LLMClient signature** (breaking): `LLMClient(api_key, default_model, provider)` → `LLMClient(api_keys, default_model)`. Provider inferred from model ID prefix. All callers updated.
- **Config structure** (breaking): `openrouter:` section replaced by `models:` with `default` and `presets` map. Model IDs now use full LiteLLM-routable format with provider prefix.
- **Pricing source**: Replaced OpenRouter HTTP pricing call (`fetch_all_pricing()`) with `litellm.get_model_cost_map()`. Works offline, covers all providers. Removed `requests` dependency from pricing module.
- **search_tactics moved to agent-only**: `card_search_tool` now in `agent_only_tools` (TacticsAgent) instead of `extra_tools` (JARVIS). Per ADR-022, its downstream intent is creative synthesis.
- **Delegation directive updated**: JARVIS system prompt now mentions vault read tools and tactics delegation.

### Added
- **Filesystem Access Control**: `FilesystemGuard` with per-path read/write/deny rules replaces flat `allowed_dirs`. Most-specific-path-wins resolution enables whole-vault read access with selective write permissions. Breaking change: `allowed_dirs` removed from `VaultConfig`.
- **Suggest Improvements Tool**: New `suggest_improvements` tool shows proposed changes as a colored preview diff without writing to disk. Available to any delegated agent. The writing agent's review workflow now runs evaluate → suggest → discuss → apply.

### Fixed
- **Pricing Unavailable for claude-sonnet-4.6**: Upgraded LiteLLM from 1.80.16 to 1.82+ which includes claude-sonnet-4.6 in its cost map. Also added bare model name as a third lookup candidate in `get_model_pricing()` for extra resilience against missing entries.
- **Recall Tool Delegation Leak**: `extra_tools` (like `recall_conversations`) no longer leak to delegated agents. Introduced `agent_only_tools` list to separate orchestration tools from specialist tools.

### Docs
- **Tool Scoping for Delegation**: Documented the `extra_tools` vs `agent_only_tools` distinction in architecture.md and ADR-020. Fixed startup flow diagram (blog tools → `agent_only_tools`).

### Added
- **Content-Evaluator Tool**: The content-evaluator skill is now available as a callable tool (`evaluate_content`) for agents. When asked to review content, the writing agent uses the structured 5-lens framework directly instead of improvising.
- **Agent Delegation**: JARVIS can now delegate tasks to specialized agents via a `delegate_to_agent` tool. When a user asks JARVIS to review content, it hands off to the writing agent, which enters a multi-turn session with the initial task pre-loaded.
- **LLMClient Temperature Support**: `LLMClient.complete()` now accepts an optional `temperature` parameter, enabling tools like the content evaluator to use skill-specific temperature settings.

### Fixed
- **Streaming Output Duplication**: Long responses no longer duplicate in the terminal. Changed `Rich.Live` overflow from `visible` to `crop` — only the last screenful shows during streaming, then `finish_live_stream` renders the full markdown.
- **Tool Call History Loss**: Tool call context (assistant `tool_calls` + tool results) is now persisted in conversation history via `StreamResult.tool_messages` and `ConversationLogger.add_tool_messages()`. Follow-up questions no longer cause redundant tool re-invocation.

### Added
- **Writing Agent File Access**: `/write` agent can now read, create, and edit Obsidian blog posts
  - Four new tools: `list_blog_posts`, `read_blog_post`, `create_blog_post`, `edit_blog_post`
  - Diff-based confirmation with reasoning before any write
  - Template support for new blog posts
  - Write-guarded template directory (read-only)
  - `write_note()` added to `writer.py` for full-file replacement with diff confirmation
  - 27 new tests

### Changed
- **Writing Agent Voice Profile**: Enhanced `/write` agent with Marco's authentic voice DNA and AI anti-pattern detection
  - `voice-profile.md`: Core persona, tone, sentence rhythm (burstiness mandate), vocabulary, opening/closing patterns, vulnerability markers, structural preferences
  - `anti-patterns.md`: Banned vocabulary, banned structural/style patterns, Humanizer's Checklist for self-verification
  - System prompt rewritten as composable template loading voice profile and anti-patterns at init
  - Agent description updated: "Refined prose, editing, and rewriting" -> "Write and edit in Marco's authentic voice"

### Added
- **Navigator Agent** (`/navigator`): Personal alignment and structured review agent for weekly reviews and life-direction coaching
  - Structured review cycles: reflection, alignment check, priority setting
  - Session awareness: tracks topics reviewed and commitments made
  - Multi-turn coaching for values-based decision making
- **Pattern Language Expert Agent** (`/pattern-language-expert`): Promoted from skill to agent for multi-turn pattern coaching sessions
  - Draft-review-refine cycle for iterative pattern development
  - Session awareness: tracks patterns discussed and maps relationships across the session
  - Full pattern anatomy reference (essential/valuable/optional elements)
- **OKR Architect Agent** (`/okr-architect`): Promoted from skill to agent for multi-turn OKR facilitation
  - Structured facilitation cycle: objectives, key results, alignment check, refinement
  - Session awareness: tracks drafted/pending/rejected OKRs
  - Challenges weak formulations and checks cross-OKR alignment
- 13 new tests; total: 749 pass, 11 skip

### Removed
- Skill symlinks for `pattern-language-expert` and `okr-architect` from `packages/skills/` (replaced by agents)

### Added
- **SOUL.md** (`data/context/soul.md`): Consolidated Jarvis identity file — single source of truth for personality, communication style, values, guardrails, and persistent directives
  - `context_builder.py` loads `soul.md` from `context_dir` as the prompt prefix (replaces `system_prompt_prefix` config key)
  - New sections: Values & Principles, Guardrails, Persistent Directives
  - Behavioral rules moved from `preferences.md` to `soul.md` (preferences.md retains user-facing preferences only)

### Removed
- `system_prompt_prefix` from `config/default.yaml` and all callers — soul.md is now the identity source
- `prefix` parameter from `build_system_prompt()` and `JarvisAgent.__init__()`

---

## [0.9.0] - 2026-03-05

### Added
- **Skills vs Agents Guide** (`docs/engineering/skills-vs-agents.md`): Standalone document explaining the skill/agent distinction, promotion criteria, migration path, and assessment of expert personas
- **Pip Decks Integration (Phase 5E)**: Deck-skills + RAG + TacticsAgent
  - `packages/core/rag/card_indexer.py`: `CardIndexer` and `CardSearcher` for indexing deck-skill card content into ChromaDB (`"pip_deck_cards"` collection)
  - `packages/core/tools/card_search.py`: `make_card_search_tool()` factory — `search_tactics` tool for cross-deck semantic card search
  - `packages/agents/tactics/`: TacticsAgent (`/tactics`, `--agent tactics`) — cross-deck Pip Decks coaching orchestrator with multi-turn session support
  - Deck-skill pattern: `SKILL.md` + `skill.py` + `deck.yaml` + `resources/cards/*.md` per deck
  - Auto-discovery of deck-skills via `deck.yaml` presence in skill directories
  - `config/default.yaml`: new `rag.index_cards` option (default: true)
  - `apps/cli/main.py`: card indexing startup wiring, `extra_tools` passthrough for agents
  - ADR-018: Pip Decks Integration architecture decision
  - 25 new tests (19 card indexer/searcher/tool + 6 TacticsAgent); total: 725 pass, 11 skip
- **Agent Sessions**: Multi-turn agent sessions with `/exit` command
  - `_run_agent_session()` in `apps/cli/main.py` for multi-turn agent loop
  - `/tactics` (no args) enters coaching session instead of showing usage
  - 8 new tests (extra_tools forwarding, session lifecycle, multi-turn)

### Fixed
- **/tactics extra_tools not forwarded**: `_handle_agent_command` now inspects agent's `run()` signature and forwards `extra_tools` when supported — fixes `/tactics` single-turn mode missing `search_tactics` tool

---

## [0.8.0] - 2026-03-02

### Added
- **Skills Framework (Phase 5A)**: Vendor-portable, SKILL.md-driven task specifications
  - `packages/skills/base.py`: `BaseSkill` class with two modes — SKILL.md only (zero Python) and SKILL.md + `skill.py` (custom execution config)
  - `packages/skills/registry.py`: Filesystem-based discovery scanning for `SKILL.md` files (not Python imports)
  - SKILL.md format matches Claude's native spec: `name` + `description` frontmatter, markdown body as prompt
  - Two example skills: Nano Banana Pro (Mode 1, SKILL.md only) and Content Evaluator (Mode 2, with `skill.py` + rubric resource)
  - Slash-command routing: `/nano-banana-pro`, `/content-evaluator`, `/skills` listing
  - `--skill <name>` standalone mode (mirrors `--agent <name>`)
  - ADR-017 documenting the vendor-portable design decision
  - 30 new unit tests; total: 698 pass, 11 skip

---

## [0.7.0] - 2026-02-28

### Added
- **Enhanced CLI Terminal UX**: Colored output, markdown rendering, and robust input handling
  - `apps/cli/display.py`: New display module centralizing all terminal formatting with `rich`
  - Colored startup banner, assistant/agent prefixes, dim stats, styled errors and system messages
  - Post-stream markdown rendering: fenced code blocks, headings, bold, lists render properly after streaming completes; plain-text responses left as-is
  - `prompt_toolkit` replaces `input()` for paste support (no more ~4096 byte truncation) and input history (up-arrow recall)
  - `StreamHandler.on_tool_call` callback decouples `packages/core/` from CLI display concerns
  - `config/default.yaml`: new `cli:` section (`colors`, `history_file`)
  - Blank line separator between token stats and next prompt (fixes cramped output)
  - 26 new unit tests in `test_display.py`; 2 new `on_tool_call` tests in `test_stream_handler.py`
- **Conversation Recall (RAG)**: Semantic search over past conversations via ChromaDB + LiteLLM embeddings
  - `packages/core/rag/indexer.py`: `ConversationIndexer` — startup scan of `data/conversations/*.json`, incremental embedding + upsert to ChromaDB
  - `packages/core/rag/searcher.py`: `ConversationSearcher` + `SearchResult` dataclass — cosine similarity search with optional date filters
  - `packages/core/tools/conversation_recall.py`: `make_conversation_recall_tool()` factory — produces a `recall_conversations` ToolDefinition backed by the searcher
  - `JarvisAgent.__init__()`: new `extra_tools` parameter for injecting additional tools at construction
  - `apps/cli/main.py`: RAG initialization block — indexes new conversations at startup, wires `recall_tool` into `JarvisAgent`
  - `config/default.yaml`: new `rag:` section (`enabled`, `db_path`, `embedding_model`)
  - `pyproject.toml`: new optional `[rag]` dependency group with `chromadb>=0.6.0`
  - 27 new unit tests across `test_rag_indexer.py`, `test_rag_searcher.py`, `test_conversation_recall.py`
  - Opt-in: set `rag.enabled: true` in `config/local.yaml` and `uv add chromadb`; disabled by default
- **Tool Calling Infrastructure + Web Fetch**: LLM can now invoke tools via function calling
  - `packages/core/tools/base.py`: `ToolDefinition` dataclass and `ToolRegistry` class
  - `packages/core/tools/executor.py`: `execute_tool_calls()` — runs tool calls, returns formatted result messages
  - `packages/core/tools/web_fetch.py`: `fetch_url` tool using `httpx` + `trafilatura` for clean article extraction
    - 10s timeout, `follow_redirects=True`, 50KB content cap with truncation notice
    - All errors (timeout, HTTP, network) returned as strings so LLM can reason about them
  - `LLMClient.complete()`: non-streaming completion for agentic loop intermediate calls
  - `StreamHandler.stream(tool_registry=...)`: agentic loop (max 5 iterations) — non-streaming tool calls then streaming final answer
  - `JarvisAgent` now wires `FETCH_URL_TOOL` into its `AgentConfig.tools` list
  - Backward compatible: no tool registry → existing code path unchanged
  - 26 new unit tests across `test_tools_base.py`, `test_tools_executor.py`, `test_web_fetch.py`, plus additions to `test_stream_handler.py`
  - Dependencies added: `httpx`, `trafilatura`

### Fixed
- **RAG recall poor for broad queries**: Per-conversation deduplication prevents one verbose conversation from monopolizing all result slots. Searcher over-fetches 3x when deduplicating. New `n_results` tool parameter (default 10, max 20) lets the LLM request more results for broad queries like weekly summaries.
- **RAG date filtering broken**: ChromaDB's `$gte`/`$lte` operators only support numeric types, so string-based `session_date` filters silently threw `ValueError`. Added integer `session_date_int` (YYYYMMDD) metadata field with automatic migration of existing records. Tool description now includes today's date and instructs the LLM to set `date_from`/`date_to` for temporal queries. Results with similar relevance scores now prefer newer conversations (recency tiebreaker).
- **RAG startup failure with OpenRouter**: Explicitly pass `encoding_format="float"` in `_embed_batch()` (`indexer.py`) and `search()` (`searcher.py`) to satisfy OpenRouter's strict Zod schema validation, which rejects requests missing or sending an unexpected `encoding_format` value.
- **Agentic loop double-counting bug** (`StreamHandler._run_agentic_loop()`):
  - Usage accumulation now only happens for `"tool_calls"` responses; `"stop"` responses are covered by `chat_stream()` and were previously double-counted
  - Eliminated a redundant `complete()` call (the "stop check") that was immediately discarded when `chat_stream()` regenerated the same answer — saves one billable API call per tool-use turn
  - Corrected flow: `complete() → tool_calls → execute → break → chat_stream()` (2 calls instead of 3)

### Changed
- **`AgentConfig.tools`**: Type changed from `list[str]` → `list[ToolDefinition]`; `BaseAgent.__init__` builds `ToolRegistry` from config tools; `to_dict()` serializes as tool names
- **`StreamHandler.stream()`**: Accepts optional `tool_registry` parameter (default `None` — fully backward compatible)
- **`BaseAgent.run()`**: Passes `tool_registry` to `stream_handler.stream()` when tools are registered

---

## [0.6.0] - 2026-02-13

### Added
- **Agent Framework**: Wired agent layer into CLI with slash-command routing and standalone mode
  - `StreamHandler` class extracted from `main.py` into `packages/core/stream_handler.py`
  - `BaseAgent.run()` method — primary entry point for agent execution with streaming
  - `BaseAgent.load_prompt()` classmethod — loads prompts from agent's `prompts/` directory
  - Agent registry (`packages/agents/registry.py`) with filesystem-based auto-discovery
  - Three specialized agents: Writing (`/write`), Research (`/research`), Clarity (`/clarity`)
  - `--agent <name>` CLI flag for standalone agent mode (e.g. `uv run jarvis --agent writing`)
  - Slash-command routing in CLI via agent registry lookup
  - 44 new tests for StreamHandler, registry, BaseAgent, agents, and CLI routing
  - Convention: drop a folder in `packages/agents/` with `agent.py` + `prompts/system.md` and it works
- **Nested Daily Note Paths**: `daily_note_path_format` replaces `daily_notes_dir` + `daily_note_format`
  - Single `strftime`-based path format supports date-derived subdirectories (e.g., `Journals/%Y/%Y-%m/%Y-%m-%d`)
  - Config key: `obsidian.daily_notes.path_format` (default: `"Daily Notes/%Y-%m-%d"`)
- **Obsidian Vault Integration**: Read from and write to Obsidian vaults, starting with daily notes
  - Five-module architecture: `vault.py`, `callout.py`, `diff.py`, `writer.py`, `prompts.py`
  - `VaultConfig` with path validation and symlink/traversal protection
  - `> [!JARVIS]` callout block parser and content builder (pure string ops, no I/O)
  - UI-agnostic diff computation with CLI (colored) and API (JSON) formatters
  - `ConfirmationHandler` ABC for GUI-ready write confirmation (CLI implementation included)
  - `/daily-summary` CLI command: generates end-of-day summary via LLM, appends to daily note callout
  - Prompt files in `data/prompts/obsidian/` loaded on demand (not in system prompt)
  - 83 new tests (73 unit + 10 integration) covering all modules and security boundaries
  - Configuration in `config/default.yaml` (disabled by default, user enables in `local.yaml`)

### Changed
- **JARVIS Persona Prompt**: Replaced generic `system_prompt_prefix` with movie-inspired JARVIS voice
  - Traits: loyal, sharp, composed — dry wit and understated precision
  - Guardrails against sycophantic responses ("never obsequious")
  - Context presented as innate knowledge, not file reads
  - Encourages honest pushback ("When you disagree, say that too")
  - No explicit "sir" or "British butler" stereotypes — modern and tech-literate tone
  - ~85-90 tokens (up from ~60), negligible cost impact

### Fixed
- **`/daily-summary` session tracking**: Command now logs the exchange via `logger.add_message()` so `save()` writes the conversation file and prints the session summary on exit
- **`/daily-summary` content duplication**: Existing JARVIS callout entries are stripped from the note content sent to the LLM and passed separately with a "DO NOT repeat" instruction, preventing duplicated bullets on re-runs

---

## [0.5.0] - 2026-02-08

### Added
- **Selective Context Loading via Frontmatter**: Project files support YAML frontmatter for tiered loading
  - `active: true/false` controls whether full content is loaded into system prompt
  - `topics` list for future topic-based auto-activation
  - `summary` one-liner used in the project index
  - Files without frontmatter default to `active: true` (backwards compatible)
  - New `parse_frontmatter()` utility in `context_builder.py`
  - Project index section lists all projects (active + inactive) so LLM knows they exist
  - Inactive projects appear only as summary lines (~100 tokens vs ~1-4K tokens each)
  - CLI context snapshot now tracks `active` status and `frontmatter` per project file
  - 19 new unit tests for frontmatter parsing, filtering, and project index
- **Context Utilization Analyzer**: `scripts/analyze_context.py` measures how context files are referenced in assistant responses
  - Keyword-based matching against loaded context content
  - Per-file utilization stats, context overhead estimates
  - Markdown report output (stdout or `--output FILE`)
  - 31 unit tests for context analyzer functions
- **Cost-by-Type Analysis**: `scripts/analyze_costs.py` classifies and aggregates conversation costs
  - Groups by source (native/imported), model, or message length
  - Supports `--by source`, `--by model`, `--by length`, `--by all`
  - Markdown table output with cost, token, and latency breakdowns
  - 32 unit tests for cost analysis functions
- **Default Model Recommendation**: Formal decision matrix in `docs/research/models.md`
  - Based on golden test benchmarks across 7 models
  - Claude Sonnet 4.5 selected as default (highest score 0.919, 100% pass rate)
  - Config comments in `config/default.yaml` explaining rationale
- **Claude Context Import**: Import Claude memories + projects into Jarvis context system
  - Import module at `packages/core/importers/claude_context.py`
  - CLI script at `scripts/import_claude_context.py` with `--memories`, `--projects`, `--dry-run` flags
  - Splits `profile.md` into `personal_context.md` and `professional_context.md`
  - Parses Claude `conversations_memory` bold-header sections (Work, Personal, Top of mind, Brief history)
  - Imports project memories and prompt templates to `data/context/projects/<slug>.md`
  - Saves project docs to `data/context/projects/docs/<slug>/` (not loaded into prompt)
  - Updates `current_focus.md` top-of-mind section from Claude memories
  - Skips starter/template projects automatically
  - Context builder updated to load split profile files + project context
  - CLI context snapshot includes project files
- **Claude Conversation Import**: Bulk import of Claude conversation exports into Jarvis schema v1.0.0
  - Conversion module at `packages/core/importers/claude.py`
  - CLI script at `scripts/import_claude.py` with `--dry-run`, `--date-from/to` filters
  - Handles all Claude content block types: text, thinking, tool_use, tool_result, token_budget
  - Converts attachments (human messages) and generated files (assistant messages)
  - Deterministic conversation IDs from Claude UUIDs (enables idempotent re-imports)
  - Tags: `["imported", "claude"]`
- **Shared Importer Utilities**: Extracted common code to `packages/core/importers/common.py`
  - `ImportSummary` dataclass shared across all importers
  - `make_conv_id()` and `make_filename()` utility functions
  - ChatGPT importer refactored to use shared utilities (no behavior changes)
- **ChatGPT Conversation Import**: Bulk import of ChatGPT conversation exports into Jarvis schema v1.0.0
  - Reusable conversion module at `packages/core/importers/chatgpt.py`
  - CLI script at `scripts/import_chatgpt.py` with `--dry-run`, `--date-from/to`, `--model`, `--include-archived` filters
  - Handles all ChatGPT content types: text, multimodal, code, thoughts, browsing, quotes, execution output, system errors
  - Linearizes ChatGPT's tree-structured message mapping into sequential messages
  - Deterministic conversation IDs from ChatGPT UUIDs (enables idempotent re-imports)
  - Tags: `["imported", "chatgpt"]` (+ `"archived"` if applicable)
  - Filename collision handling for same-second timestamps
  - 54 unit tests with fixture and integration round-trip test
- **Future-Proof Conversation Schema (v1.0.0)**: Complete redesign of conversation JSON format
  - Schema versioning (`schema_version: "1.0.0"`) for safe evolution
  - Conversation identity (`id`, `title`, `topic`, `tags`) for classification and referencing
  - Model configuration tracking (`model.id`, `model.provider`, `model.parameters`)
  - Agent/persona tracking (`agent.name`, `agent.system_prompt_hash`)
  - Context snapshot (`context.files_loaded` with hashes, `context.system_prompt_prefix`)
  - Environment info (`client`, `platform`, `python_version`)
  - Typed content blocks (`content` as array of `{type, ...}` objects) — supports text, tool_use, tool_result, thinking, images, audio, code without schema changes
  - Message identity (`id`, `parent_id`, `status`, `error`, `stop_reason`)
  - Extended usage tracking (`cache_read_tokens`, `cache_write_tokens`, `thinking_tokens`)
  - `metadata: {}` escape hatches at every level (conversation, metrics, messages, usage)
  - Session-level `feedback` (nullable, with `overall_rating`, `helpful`, `notes`)
  - Read-time migration (`migrate_conversation()`) for backward compatibility with all old formats
  - `ConversationLogger.load()` static method for migration-aware file reading
  - New methods: `set_title()`, `set_topic()`, `add_tag()`, `set_feedback()`
  - New utility functions: `generate_conversation_id()`, `hash_content()`
  - 52 unit tests for memory module (expanded from 15)
  - 2 new integration tests for schema verification

### Fixed
- **8 Stale Unit Tests**: Aligned test mocks with current MCP SDK and AppleScript direct architecture across `test_benchmark_costs.py`, `test_cli.py`, `test_task_sync.py`

### Changed
- **Test Suite**: Expanded from 246 to 512 tests (482 unit + 32 integration + 10 golden)
- **Context Builder**: Now loads `personal_context.md` + `professional_context.md` instead of `profile.md`
  - Section order: Personal -> Professional -> Preferences -> Current Focus -> Tasks -> Project Index -> Active Projects
  - Loads `projects/*.md` files alphabetically with frontmatter-based filtering
  - Project index lists all projects; only `active: true` projects get full context
- **CLI Context Snapshot**: Now includes `projects/*.md` in context file tracking with `active` and `frontmatter` metadata

### Documentation
- Added branching guideline to AGENTS.md (`git switch -c <type>/<description>`)
- Updated test counts in `docs/engineering/testing.md` (246 → 428)

---

## [0.4.0] - 2026-01-23

### Added
- **Benchmark Report Generator**: `scripts/benchmark_report.py` creates comparison tables in `docs/research/models.md`
- **Model Benchmark Results**: Golden test benchmarks for Sonnet 4.5, Opus 4.5, GPT-5.2, GPT-5.2-Codex, GPT-OSS-120B, Gemini 3 Flash/Pro (preview)
- **Benchmark Runner Resilience**: Continue model runs even when individual evaluations fail
- **TTFT (Time to First Token) Tracking**: Integrated latency metrics into CLI and conversation logs
  - CLI now displays TTFT and total latency after each response
  - Session summary includes average TTFT and latency across all requests
  - Conversation JSON logs include latency metrics per message
  - Extended `SessionMetrics` with `average_ttft_ms` and `average_latency_ms` properties
  - New unit test for latency tracking
- **Scalable Monorepo Structure**: Major folder restructure for multi-agent and web interface support
  - New `apps/` directory for deployable applications (CLI, web)
  - New `packages/` directory for shared libraries (core, agents, integrations, telemetry)
  - New `data/` directory for user data (context, conversations)
  - New `config/` directory for configuration files
- **BaseAgent Foundation**: `packages/agents/base.py` with abstract base class for agents
- **JarvisAgent**: Initial orchestrator agent in `packages/agents/jarvis/agent.py`
- **MetricsTracker**: `packages/telemetry/metrics.py` for TTFT and response metrics tracking
- **Web Interface Structure**: `apps/web/` prepared for FastAPI backend + React frontend
- **Web Dependencies**: Added FastAPI, uvicorn, sse-starlette to pyproject.toml
- **Benchmark Cost Estimator**: Estimate golden test run costs per model using OpenRouter pricing
- **LLM-as-Judge Evaluation System** - Complete automated quality assessment
  - Core evaluation engine with `JudgeEvaluator` class (~400 lines)
  - Category-specific judge prompts for 4 test types (~200 lines)
  - Result storage with JSON + markdown report generation (~500 lines)
  - 33 additional unit tests (16 evaluator + 17 storage)
  - Pytest plugin with `--evaluate` flag for on-demand evaluation
  - Historical tracking with trend analysis in `tests/golden/results/`
  - Cost management with configurable budget limits ($1.00 max, $0.50 warn)
  - Expected cost: ~$0.41 per full run (8 tests)
  - Uses Claude Opus 4.5 as judge for highest quality evaluations
  - Structured JSON output + markdown reports with recommendations
  - See [tests/golden/README.md](../tests/golden/README.md) for complete usage guide
- **Things 3 Integration (Phase A)**: Context awareness from Things 3 task manager
- **Automatic Language Detection**: Supports German, French, Spanish, Italian, English Things 3 installations
- **Task Sync Module**: `task_sync.py` (~520 lines) with AppleScript integration
- **Context File**: Auto-generated `tasks.md` included in system prompt
- **Task Caching**: 5-minute TTL cache to optimize performance
- **43 Additional Tests**: 33 unit tests + 8 integration tests + 2 golden tests for task sync
- **MCP Architecture**: Preserved MCPThings3Client class for Phase B (interactive features)

### Changed
- **Project Structure**: Migrated from `personal-context/` to monorepo structure
  - `personal-context/src/*.py` → `packages/core/`
  - `personal-context/src/cli.py` → `apps/cli/main.py`
  - `personal-context/src/task_sync.py` → `packages/integrations/things3/`
  - `personal-context/context/` → `data/context/`
  - `personal-context/memory/` → `data/conversations/`
  - `config.yaml` → `config/default.yaml`
- **Import Paths**: All imports now use package paths (e.g., `packages.core.llm_client`)
- **pyproject.toml**: Updated with new package structure and entry points
- **Tests**: Updated with backward-compatible imports (try/except pattern)
- **Test Suite**: Expanded from 73 to 149 tests total (103 unit + 20 integration + 26 golden/evaluation)
- **Context Builder**: Now loads `tasks.md` as 4th context file
- **CLI Startup**: Added task sync before building system prompt
- **Golden Tests Imports**: Updated golden test runner to use package import paths
- Updated `config.yaml` with evaluation settings (judge model, thresholds, cost limits)
- Modified `conftest.py` to add evaluation fixtures and `--evaluate` flag support
- Modified `test_golden_conversations.py` to implement evaluation execution

### Fixed
- **Token Usage Tracking**: Fixed streaming responses not reporting token counts
  - Added `stream_options={"include_usage": True}` to LiteLLM completion calls
  - Modified usage extraction to read from streaming chunks instead of response iterator
  - Suppressed harmless Pydantic serialization warnings in fallback cost calculation
  - Token counts and costs now display correctly after each response

### Technical Details
- Direct AppleScript communication for Phase A (read-only)
- Auto-detects localized Things 3 list names (e.g., "Eingang" vs "Inbox")
- Graceful degradation if Things 3 not running
- File-based cache at `~/.cache/jarvis/tasks_cache.json`
- Custom delimiter (|||) for task titles containing commas

### Documentation
- Added ADR-008 to `docs/product/decisions.md`
- Added ADR-009: Scalable Monorepo Structure to `docs/product/decisions.md`
- Updated `docs/engineering/architecture.md` with new architecture diagram and task_sync module
- Updated `docs/engineering/deployment.md` with new paths and commands
- Updated `docs/product/roadmap.md` with Phase 3 web interface scope and Phase A completion
- Updated `AGENTS.md` with new folder structure, import patterns, and test counts

---

## [0.3.0] - 2026-01-15

### Added
- **Comprehensive Testing Framework**: Complete test infrastructure with pytest
- **73 Automated Tests**: 53 unit tests + 12 integration tests + 8 golden test scenarios
- **97.5% Code Coverage**: High coverage on all core modules
- **Test Documentation**: Complete testing guides and plans
- **CI/CD Ready**: Infrastructure prepared for GitHub Actions integration

### Testing Infrastructure
- **Unit Tests**:
  - `context_builder.py`: 10 tests, 100% coverage
  - `memory.py`: 15 tests, 97% coverage
  - `pricing.py`: 12 tests, 98% coverage
  - `llm_client.py`: 11 tests, 95% coverage
  - `cli.py`: 5 tests (complex I/O, intentionally skipped)

- **Integration Tests**: 12 tests covering full conversation flows, context integration, and pricing

- **Golden Test Conversations**: 8 YAML test cases covering:
  - Basic Q&A without context
  - Profile information recall
  - Multi-turn technical reasoning
  - Tone matching from preferences
  - Technical deep-dives
  - Current focus awareness
  - Ambiguous query handling
  - Multiple preference adherence

### Test Tools
- pytest 8.0+ with Python 3.13 support
- pytest-cov for coverage reporting
- pytest-mock for mocking
- pytest-xdist for parallel execution
- respx for HTTP mocking
- freezegun for time mocking

### Documentation
- `tests/TESTING_PLAN.md`: Comprehensive 30-file testing plan
- `tests/TEST_RESULTS.md`: Detailed test results and coverage report
- `tests/README.md`: Quick reference guide for running tests
- Updated `docs/engineering/testing.md` with current state
- Updated `docs/product/roadmap.md` (Phase 1: 100% complete)

### Performance
- All unit tests execute in < 1 second
- Full test suite runs in < 2 seconds
- 62/73 tests passing (85% pass rate)
- 11 tests intentionally skipped (manual golden tests + complex CLI)

### Technical Details
- Test fixtures for context files, configurations, and mock responses
- Shared pytest fixtures in `conftest.py`
- HTML coverage reports generated
- Parallel test execution support
- Ready for continuous integration

---

## [0.2.0] - 2026-01-14 (Documentation Release)

### Documentation
- Restructured documentation into organized `/docs` directory
- Created product docs: vision, roadmap, metrics, decisions (ADRs)
- Created engineering docs: architecture, API reference, testing strategy, deployment guide
- Created research docs: AI engineering framework, model comparison, prompt engineering
- Archived original DEVELOPMENT.md for reference

---

## [0.2.1] - 2026-01-14 (LiteLLM Integration)

### Added
- **LiteLLM Integration**: Migrated from raw HTTP to LiteLLM for better provider flexibility
- **Fallback Cost Calculation**: Added LiteLLM-based cost calculation as fallback when OpenRouter pricing unavailable
- **Raw Response Access**: `StreamingResponse` now exposes raw LiteLLM response for advanced use cases
- **Provider Flexibility**: Easy switching between OpenRouter, Anthropic, and OpenAI

### Changed
- **llm_client.py**: Refactored to use LiteLLM instead of manual HTTP requests (112 → 117 lines)
- **pricing.py**: Added `calculate_cost_from_litellm()` function for fallback pricing
- **cli.py**: Updated to use fallback cost calculation when primary pricing fails
- **StreamingResponse**: Now returns tuple of `(TokenUsage, raw_response)` instead of just `TokenUsage`

### Technical Details
- LiteLLM handles SSE parsing, retries, and provider-specific formatting
- Function calling support now available (ready for Phase 5)
- Provider switching requires only config change
- Maintained backward compatibility with existing conversation logs

### Dependencies
- Added: `litellm` (~10MB, includes OpenAI SDK)
- Added transitive dependencies: `aiohttp`, `httpx`, `pydantic`, etc.

---

## [0.1.0] - 2026-01-07

### Added
- **Token Usage Tracking**: Per-request and session-level token counting
- **Cost Calculation**: Real-time cost tracking using OpenRouter pricing API
- **Session Metrics**: Total tokens, cost, and request count saved to conversation JSON
- **Model Comparison Documentation**: Detailed pricing and recommendations for different models

### Changed
- **memory.py**: Enhanced `ConversationLogger` to track token usage and costs
- **pricing.py**: New module for fetching and calculating LLM costs
- **cli.py**: Display token usage and cost after each response
- **Conversation logs**: Now include per-message token counts and session totals

### Documentation
- Added model comparison table with pricing
- Added cost examples for typical usage patterns
- Documented cost optimization strategies

---

## [0.0.1] - 2026-01-05

### Added
- **Initial Release**: Basic personal AI assistant functionality
- **CLI Interface**: Command-line chat interface with streaming responses
- **Context System**: Load user context from markdown files (profile, preferences, current_focus)
- **Conversation Logging**: Save conversations to timestamped JSON files
- **Provider Integration**: OpenRouter API integration for multi-model access
- **Configuration**: YAML-based config with environment variables for API keys

### Core Modules
- `cli.py`: Main entry point and chat loop
- `context_builder.py`: Assemble system prompts from context files
- `llm_client.py`: HTTP client for OpenRouter API with streaming
- `memory.py`: Conversation logging and history management

### Architecture Decisions
- Local-first: All data on user's machine
- Markdown for context: Human-readable, version-controllable
- JSON for conversations: Structured but readable
- No database: Filesystem sufficient at personal scale

### Documentation
- Initial README with project overview
- DEVELOPMENT.md with AI engineering framework
- Basic setup and usage instructions

---

## Release Notes Format

### Version Numbering

Following [Semantic Versioning](https://semver.org/):
- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible

### Categories

Changes are grouped by type:
- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be-removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security fixes
- **Documentation**: Documentation changes

---

## Upcoming Changes (Roadmap)

See [roadmap.md](product/roadmap.md) for detailed plans.

### Completed Phases
- ✅ Phase 1: Foundation & Metrics
- ✅ Phase 2: Evaluation & Quality Metrics
- ✅ Phase 3: Context & Integrations
- ✅ Phase 4: Agent Framework

### Phase 5: Agent Capabilities (In Progress)
- ✅ Function calling & tool support, web fetch tool, RAG
- ✅ Skills / Capabilities (5A) — mini-agents with prompt + tool config
- ✅ Pip Decks Integration (5E) — deck-skills + RAG + TacticsAgent + agent sessions
- ✅ Things 3 SQLite migration — replaced AppleScript with `things.py` direct reads
- ✅ Developer Agent (5G) — codebase tools, git, guarded writes, test runner
- Agent orchestration (5B), extended tools (5C), model routing (5D)

### Phase 6: Web Interface
- Event decoupling (6A), API layer (6B), frontend (6C)

### Future Phases
- Phase 7: Context Window Management & Search
- Phase 8: System Monitoring & Optimization
- Phase 9: UX Enhancements
- Phase 10: Fine-tuning (optional)

---

## Migration Guides

### 0.3.0 → 0.4.0 (Monorepo Restructure)

**Breaking Changes**: Import paths changed

**Migration Steps**:
1. Update imports from old paths to new package paths:
   ```python
   # Old
   from llm_client import LLMClient
   from context_builder import build_system_prompt

   # New
   from packages.core.llm_client import LLMClient
   from packages.core.context_builder import build_system_prompt
   ```

2. Update configuration paths:
   - Context files: `personal-context/context/` → `data/context/`
   - Conversations: `personal-context/memory/conversations/` → `data/conversations/`
   - Config: `config.yaml` → `config/default.yaml`

3. Run CLI with new path:
   ```bash
   uv run python -m apps.cli.main
   # Or
   uv run jarvis
   ```

**Data Compatibility**: Copy your data files to new locations:
```bash
cp -r personal-context/context/* data/context/
cp -r personal-context/memory/conversations/* data/conversations/
```

---

### 0.2.1 → 0.3.0 (Testing Framework)

**Breaking Changes**: None

**New Dependencies**:
```bash
uv sync --extra test
```

**Running Tests**:
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=packages --cov=apps --cov-report=html

# View coverage report
open htmlcov/index.html
```

**Documentation**: See `tests/README.md` for complete testing guide

---

### 0.1.0 → 0.2.1 (LiteLLM Migration)

**Breaking Changes**: None

**New Dependencies**:
```bash
uv add litellm
```

**Configuration Changes**: None required, but you can now switch providers easily:
```python
# In apps/cli/main.py
client = LLMClient(
    api_key=your_key,
    default_model="model-id",
    provider="openrouter"  # or "anthropic", "openai"
)
```

**Data Compatibility**: All existing conversation logs remain compatible.

---

### 0.0.1 → 0.1.0 (Token Tracking)

**Breaking Changes**: None

**New Features**: Automatic token and cost tracking

**Configuration Changes**: None required

**Data Format**: Conversation JSON now includes token metadata (backward compatible)

---

## Contributors

- **Marco Braun** (@Cherubeam) - Creator and maintainer

---

*Last updated: 2026-03-19*
