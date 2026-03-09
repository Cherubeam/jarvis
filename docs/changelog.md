# Changelog

All notable changes to Jarvis will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Vault Read Tools**: Three new read-only tools (`read_note`, `search_notes`, `read_daily_note`) give JARVIS direct access to the Obsidian vault for information retrieval. 50KB content cap, 100-entry search cap. Inherits FilesystemGuard access control.
- **Vault Search Sorting**: `search_notes` tool now supports `sort_by` (`"name"` or `"modified"`) and `limit` (1–100) parameters. `sort_by="modified"` returns most-recent-first with timestamps (`YYYY-MM-DD HH:MM  path`).
- **Capability Ownership Framework** (ADR-022): Four-criteria decision framework for placing capabilities on JARVIS vs subagents. Core principle: JARVIS owns general-purpose reads; subagents own creative transformation.

### Changed
- **search_tactics moved to agent-only**: `card_search_tool` now in `agent_only_tools` (TacticsAgent) instead of `extra_tools` (JARVIS). Per ADR-022, its downstream intent is creative synthesis.
- **Delegation directive updated**: JARVIS system prompt now mentions vault read tools and tactics delegation.

### Added
- **Filesystem Access Control**: `FilesystemGuard` with per-path read/write/deny rules replaces flat `allowed_dirs`. Most-specific-path-wins resolution enables whole-vault read access with selective write permissions. Breaking change: `allowed_dirs` removed from `VaultConfig`.
- **Suggest Improvements Tool**: New `suggest_improvements` tool shows proposed changes as a colored preview diff without writing to disk. Available to any delegated agent. The writing agent's review workflow now runs evaluate → suggest → discuss → apply.

### Fixed
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

*Last updated: 2026-03-09*
