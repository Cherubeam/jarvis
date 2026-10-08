# System Architecture

> Technical overview of Jarvis's design and implementation.

---

## Architecture Overview

Jarvis follows a modular, scalable architecture designed for multi-agent support and multiple interfaces:

```
┌─────────────────────────────────────────────────────────────────┐
│                       User Interfaces                            │
├──────────────────────────┬──────────────────────────────────────┤
│   CLI (apps/cli)         │   GUI (apps/gui) — Phases 1–8        │
│   • main loop            │   • FastAPI + WebSocket              │
│   • session_factory      │   • React 18 + Vite + TypeScript     │
│   • review (/outcomes)   │   • bridge / state / streaming /     │
│                          │     confirmation                      │
└──────────────────────────┴──────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────┐
│                       Shared Packages                            │
├─────────────────────┬──────────────────┬────────────────────────┤
│   packages/core     │ packages/agents  │ packages/integrations  │
│                     │                  │                        │
│  • LLM Client       │ • Base Agent     │ • Things 3             │
│  • Context Builder  │ • JARVIS Agent   │ • Obsidian             │
│  • Memory           │ • Writer Agent   │ • Cortex (via MCP)     │
│  • Pricing          │ • Tactics Coach  │ • Readwise             │
│  • Stream Handler   │ • Data-driven    │ • MCP (client)         │
│  • Settings (typed) │   agents         │                        │
│  • Frontmatter      │ • Registry       │                        │
│  • Date utils       │                  │                        │
│  • Daily summary    │ • _shared/       │                        │
│  • Tools / RAG      │   prompt incl.   │                        │
│  • Events           │                  │                        │
├─────────────────────┴──────────────────┴────────────────────────┤
│                     packages/telemetry                           │
│  • Metrics tracking (TTFT, latency)                              │
│  • Evaluation framework                                          │
└──────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────┐
│                       Data Layer (data/)                         │
│                                                                  │
│  • data/context/*.md         User's personal context             │
│  • data/conversations/YYYY/   Session logs (JSON, by year)       │
│  • data/outcomes/             Tracked recommendations + reviews  │
│  • data/prompt-history/       Per-agent prompt snapshots (gitignored) │
│  • .cache/jarvis/             Task sync cache                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### 1. CLI Layer (`apps/cli/main.py`)

**Purpose**: User interaction and session orchestration.

**Location**: `apps/cli/main.py`

**Responsibilities:**
- Parse user input from stdin
- Display streamed responses
- Show token usage, costs, and latency metrics (TTFT, total latency)
- Handle session lifecycle (start, interrupt, end)
- Route delegation results to agent sessions
- Track response latency using MetricsTracker

**Key Functions:**
- `parse_args()`: Parse CLI arguments (`--agent`, `--model`)
- `main()`: Main chat loop with agent routing and metrics tracking
- `_handle_agent_command()`: Route slash commands to registered agents
- `load_config()`: Re-export of `packages.core.settings.load_config()` (returns typed `Settings` model — see ADR-032)

**Helpers split out:**
- `apps/cli/session_factory.py` — `build_session(confirmation_handler)` lifts the pre-loop wiring (config, agents, tool groups, logger, stream handler) into a reusable factory parameterized on `ConfirmationHandler`. CLI calls it with `CLIConfirmationHandler()`; GUI calls it with `WebConfirmationHandler` per turn. Same `SessionComponents` dataclass returned to both.
- `apps/cli/review.py` — pending-outcome review for `/outcomes`. Public symbols `PendingItem`, `load_pending_due()`, `apply_review()`, `pending_item_to_wire()` are reused by the GUI's `routes/outcomes.py`.

**Dependencies:**
- `packages.agents.jarvis`: Default JARVIS orchestrator agent
- `packages.agents.registry`: Agent discovery and slash-command routing
- `packages.core.settings`: Typed configuration loader (`load_config() -> Settings`)
- `packages.core.stream_handler`: Shared streaming + metrics + cost tracking
- `packages.integrations.things3.task_sync`: Sync Things 3 tasks on startup
- `packages.integrations.obsidian`: Obsidian vault integration (`/daily-summary` command)
- `packages.core.context_builder`: Get system prompt
- `packages.core.daily_summary`: Build `/daily-summary` requests (CLI + GUI shared)
- `packages.core.llm_client`: Stream LLM responses
- `packages.core.memory`: Log conversations
- `packages.core.pricing`: Calculate costs
- `packages.telemetry.metrics`: Track TTFT and response latency

---

### 1b. GUI Layer (`apps/gui/`)

**Purpose**: A graphical peer to the CLI, sharing the same agents, tools, vault, conversation files, and approval flow. Browser-served at `http://127.0.0.1:8123`, gated by a token + origin allowlist since `AON-01` ([ADR-035](../product/decisions.md#adr-035-gui-authentication--derived-value-cookie--origin-allowlist)).

**Location**: `apps/gui/` (entry: `apps/gui/main.py`)

**Responsibilities:**
- FastAPI + WebSocket server (`apps/gui/server/`)
- React 18 + Vite + TypeScript frontend (`apps/gui/web/`)
- Chat surface with streaming, vault-write approval diffs, command palette
- Conversations browser, Dashboard / Home, Sidebar Timeline, Agents grid
- Agent Prompt Editor + Includes editor, Outcomes scoring, Settings editor

**Key modules:**
- `server/app.py` — FastAPI factory + lifespan (MCP start/stop, conversation save on shutdown)
- `server/state.py` — `GuiSession` holds `SessionComponents` + per-turn handlers
- `server/bridge.py` — per-turn orchestration (`agent.run()` in `asyncio.to_thread`)
- `server/streaming.py` — `WebStreamHandler` subscribes to the `Event` bus, maps each event to a WS protocol dict over a bounded `janus.Queue`
- `server/confirmation.py` — `WebConfirmationHandler` mirrors the `ConfirmationHandler` ABC; `present_diff` buffers, `get_confirmation` blocks the worker thread on a `threading.Event` resolved by the client's `approval_decision`
- `server/protocol.py` — WebSocket TypedDicts (server ↔ client); mirrored in `apps/gui/web/src/lib/types.ts`
- `server/routes/` — REST routes: `api · chat_ws · agents · agent_includes · conversations · home · outcomes · settings`
- `server/agents/`, `server/home/`, `server/history/` — domain helpers (cost rollups, conversation index, prompt history)
- `server/resume.py` — `load_and_replay()` for chat-view conversation resume: reads a historic JSON, mutates the active `ConversationLogger` in place via `rehydrate()` so the next save appends to the original file, and emits synthetic StreamEvents for the chat UI to repaint the prior turns

**Dependencies:**
- `apps.cli.session_factory.build_session` — shared session bootstrap
- `apps.cli.review` — outcome scoring helpers
- `packages.core.settings` — typed config (live-rebound on hot-applicable saves; see `HOT_APPLY_PATHS`)
- `packages.core.daily_summary` — `/daily-summary` request builder
- `packages.core.events`, `packages.core.frontmatter` — typed events + atomic writes

See [docs/engineering/gui.md](gui.md) for the full per-phase architecture and the WebSocket protocol reference.

---

### 2. Context Builder (`packages/core/context_builder.py`)

**Purpose**: Assemble system prompt from user context files.

**Location**: `packages/core/context_builder.py`

**Responsibilities:**
- Load markdown context files
- Concatenate in correct order (profile → preferences → focus)
- Add section headers
- Combine with system prompt prefix

**Key Functions:**
- `load_context_file(filepath)`: Load single markdown file
- `parse_frontmatter(text)`: Extract YAML frontmatter from markdown, returns `(metadata, content)`
- `build_system_prompt(context_dir, context_files, tasks_file)`: Assemble full prompt, frontmatter stripped

**Context Loading Order:** soul → personal → professional → preferences → current focus → tasks → reading profile. File names come from `paths.context_files` (relative to `paths.context_dir`, so the files can live in a vault folder) and tasks from `paths.tasks_file`; the full list with default names is in [api.md](api.md#module-context_builder).

**Project Knowledge:**
Project details are maintained in Obsidian (`02 – Projects/`) and retrieved on demand via `mcp_cortex__search_knowledge` (Cortex over MCP), `search_notes` and `read_note` tools, rather than being statically loaded into the system prompt. This keeps the prompt lean and ensures project knowledge is always up to date with the single source of truth in the vault.

---

### 3. LLM Client (`packages/core/llm_client.py`)

**Purpose**: Abstract LLM API calls with provider flexibility.

**Location**: `packages/core/llm_client.py`

**Responsibilities:**
- Stream responses from LLM providers
- Handle provider-specific formatting (e.g., `openrouter/` prefix)
- Track token usage
- Return structured responses with usage metadata

**Key Classes:**
- `TokenUsage`: Dataclass for token counts (includes `cache_read_tokens`, `cache_write_tokens`)
- `StreamingResponse`: Iterator wrapper with usage tracking
- `LLMClient`: Main client class

**Key Methods:**
- `chat_stream(messages, model)`: Stream a completion
- `_stream_response(messages, model)`: Internal generator

**Prompt Caching:**
- `_apply_cache_control(messages, model)`: Injects `cache_control` breakpoints into system messages for Anthropic models (the only provider requiring explicit opt-in). Non-Anthropic models are unaffected.
- `_extract_cache_tokens(usage)`: Extracts cache read/write tokens from any provider's usage object (Anthropic, OpenAI, LiteLLM).

**Provider Support:**
- OpenRouter (default)
- Anthropic (direct)
- OpenAI (direct)
- Any LiteLLM-supported provider

**Design Decision**: Uses LiteLLM for provider abstraction (see ADR-003).

---

### 4. Conversation Logger (`packages/core/memory.py`)

**Purpose**: Persist conversation history to disk.

**Location**: `packages/core/memory.py`

**Responsibilities:**
- Accumulate messages during session
- Track session metadata (tokens, cost, latency, model)
- Save to timestamped JSON files
- Replace estimated usage of streamed turns with OpenRouter's billed records (`metadata.usage_source`: `billed` | `estimated`)
- Return message history for API calls

**Key Classes:**
- `SessionMetrics`: Aggregated metrics including latency
- `ConversationLogger`: Main logging class

**Key Methods:**
- `add_message(role, content, ..., ttft_ms, total_latency_ms)`: Add message to log
- `get_messages_for_api()`: Format messages for LLM API
- `reconcile_billed_usage(deadline_s=0.0)`: swap estimated usage for billed records (needs `billing_api_key`; called before `save()` in CLI and GUI)
- `save()`: Write to JSON file

**File Format (Schema v1.0.0):**
```json
{
  "schema_version": "1.0.0",
  "id": "conv_20260206_143022_b8e1",
  "title": null,
  "topic": null,
  "tags": [],
  "session_start": "2026-01-14T10:30:00Z",
  "session_end": "2026-01-14T10:45:00Z",
  "model": { "id": "anthropic/claude-sonnet-4.5", "provider": "openrouter", "parameters": {} },
  "agent": { "name": "JARVIS", "system_prompt_hash": "sha256:...", "tools": [], "metadata": {} },
  "context": { "files_loaded": [...], "system_prompt_prefix": "...", "metadata": {} },
  "environment": { "client": "cli", "client_version": "0.3.0", "platform": "darwin", "python_version": "3.13.1", "metadata": {} },
  "metrics": {
    "total_tokens": 15000, "total_cost_usd": 0.045,
    "total_cache_read_tokens": 0, "total_cache_write_tokens": 0, "total_thinking_tokens": 0,
    "average_ttft_ms": 280.0, "average_latency_ms": 1650.0,
    "request_count": 10, "metadata": {}
  },
  "messages": [
    {
      "id": "msg_001", "parent_id": null, "role": "user",
      "timestamp": "...",
      "content": [{"type": "text", "text": "..."}],
      "usage": null, "latency": null,
      "stop_reason": null, "status": "completed", "error": null, "metadata": {}
    },
    {
      "id": "msg_002", "parent_id": null, "role": "assistant",
      "timestamp": "...",
      "content": [{"type": "text", "text": "..."}],
      "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cache_read_tokens": 0, "cache_write_tokens": 0, "thinking_tokens": 0, "cost_usd": 0.0045, "metadata": {}},
      "latency": {"ttft_ms": 250.0, "total_ms": 1500.0},
      "stop_reason": "end_turn", "status": "completed", "error": null, "metadata": {}
    }
  ],
  "feedback": null,
  "metadata": {}
}
```

---

### 5. Task Sync (`packages/integrations/things3/`)

**Purpose**: Give JARVIS read-only task context from Things 3 (ADR-037).

**How it works:**
- `shortcut_source.run_export()` runs the user-built **`JARVIS Things Export`** Shortcut (`shortcuts run … --output-type public.json`, 10 s timeout) and returns `{"inbox": [...], "scheduled": [...]}`. It raises `ThingsUnavailableError` with an actionable reason when not on macOS, the Shortcut is missing or failing, it times out, or the output isn't the expected JSON.
- `task_sync.fetch_tasks()` maps each item to a `Task` (`_to_task()`: localized dates → ISO, tags one-per-line → comma list, parent title → `project`; there are no areas), splits `scheduled` into Today (start ≤ today, incl. overdue) and Upcoming (later), honours `things3.lists_to_include`, and caches successes only (`TaskSyncCache`, 5-minute TTL).
- `sync_tasks_to_file()` writes `paths.tasks_file` (default `data/context/tasks.md`) at startup (grouped by parent). On any failure it keeps the previous file and logs why.
- The GUI Home view calls `fetch_tasks()` via `asyncio.to_thread`, so a cache miss doesn't block the event loop.

No Full Disk Access, no database access, no write tools. Setting up the Shortcut: [deployment.md#things-3](deployment.md#things-3). History: ADR-008 (AppleScript) → `things.py` SQLite (2026-03) → Shortcut (ADR-037).

---

### 6. Obsidian Integration (`packages/integrations/obsidian/`)

**Purpose**: Read from and write to Obsidian vaults, starting with daily notes.

**Location**: `packages/integrations/obsidian/`

**Responsibilities:**
- Vault access with path validation and symlink/traversal protection
- Parse and manipulate `> [!JARVIS]` callout blocks (pure string operations)
- Compute and format diffs (CLI and API output)
- Orchestrate write operations with diff → confirm → write flow
**Key Modules:**
- `vault.py`: `VaultConfig`, path validation, read/list/get daily note, read ledger (`record_read()`, `changed_since_read()`)
- `callout.py`: `CalloutBlock`, `find_jarvis_callout()`, `build_updated_content()` (no I/O)
- `diff.py`: `VaultDiff`, `compute_diff()`, CLI/API formatters
- `writer.py`: `ConfirmationHandler` ABC, `CLIConfirmationHandler`, `append_to_daily_note()`, `write_note()`

**Key Design Decisions:**
- **Vault safety** (FilesystemGuard access rules, diff approval, changed-link list, stale-write guard): described in [obsidian-integration.md](obsidian-integration.md#data-flow-summary); access rules per ADR-021.
- **ConfirmationHandler ABC**: the CLI (`CLIConfirmationHandler`) and the GUI (`WebConfirmationHandler`) each implement this interface
- **Pure string callout parsing**: No I/O in callout module, testable in isolation
- **Path validation**: All vault I/O goes through `vault.py`, uses `Path.resolve()` to block traversal
- **Prompts on demand**: Not in system prompt, loaded only for `/daily-summary` command via `JarvisAgent.load_prompt()`

**CLI Command**: `/daily-summary`
```
User types: /daily-summary
  → Load vault config
  → Read today's daily note
  → Find > [!JARVIS] callout (abort if not found)
  → Load prompt, send to LLM with conversation history
  → Compute diff, show colored output
  → Write if user confirms
```

---

### 6b. Cortex Vault Search (via MCP, `HUB-01`)

**Purpose**: Semantic search over the Obsidian vault via the external Cortex service (`cherubeam/cortex`).

**How**: Since `HUB-01` (ADR-034), JARVIS consumes Cortex through the generic MCP client (§6c) instead of a bespoke HTTP integration — the same `cortex-mcp` stdio server that Claude Code and other MCP clients use. One integration surface, maintained in the Cortex repo.

**Configuration**: a `cortex` entry under `mcp.servers` in `config/local.yaml`; the example is in [deployment.md](deployment.md#example-cortex-vault-search).

The `shared: true` flag (introduced for this integration, generic to any MCP server) routes the server's tools into every agent's shared toolset instead of an opt-in tool group. Tools arrive namespaced: `mcp_cortex__search_knowledge`, `mcp_cortex__index_status`. When the Cortex service is down, the tools return an actionable error and agents fall back to `search_notes`.

**History**: The retired bespoke path (`packages/integrations/cortex/`, `packages/core/tools/cortex_search.py`, `search_vault_semantic`, `cortex.*` settings) lived from ADR-029 until HUB-01.

**Design Decisions**: ADR-029 (Cortex — Shared Knowledge Layer), ADR-034 (Context Hub Positioning).

---

### 6c. MCP Client Integration (`packages/integrations/mcp/`)

**Purpose**: Connect JARVIS to external MCP (Model Context Protocol) servers, bridging their tools into the existing ToolDefinition system.

**Location**: `packages/integrations/mcp/`

**Responsibilities:**
- Async connection lifecycle with background event loop thread (`client.py`)
- MCP Tool → ToolDefinition conversion with namespacing (`bridge.py`)
- Server schema lives in `packages.core.settings.MCPServerSettings` (PR-8a consolidated the hand-rolled config layer)

**Key Classes:**
- `MCPServerSettings` (in `packages/core/settings.py`): Validated pydantic model for server config
- `MCPConnection`: Manages one server connection; one long-lived task per connection opens the transport and session (`AsyncExitStack`), waits for `disconnect()`, and closes them in that same task (anyio requires it)
- `MCPManager`: Manages all connections, background event loop, and sync/async bridge
- `mcp_tools_to_tool_definitions()`: Converts MCP tools to namespaced `ToolDefinition` instances

**Transports**: stdio, SSE, streamable HTTP. Each server's tools become a named tool group that agents reference in `meta.yaml`; a server marked `shared: true` joins every agent's shared toolset instead.

**Opt-in**: Disabled by default (`mcp.enabled`). Adding/removing servers is a config-only change — setup guide in [deployment.md](deployment.md#connecting-mcp-servers).

---

### 7. Tool Calling (`packages/core/tools/`)

**Purpose**: Provide a composable function-calling layer for LLM tool use.

**Location**: `packages/core/tools/`

**Modules:**
- `base.py`: `ToolDefinition` dataclass + `ToolRegistry` class
- `executor.py`: `execute_tool_calls()` — runs tool calls from LLM, returns formatted result messages
- `web_fetch.py`: `FETCH_URL_TOOL` singleton — fetches URLs with `httpx`, extracts text with `trafilatura`
- `blog_tools.py`: `make_blog_tools()` factory — scoped blog post tools for the Writing Agent (list, read, create, edit). `edit_blog_post` takes `old_text` → `new_text` passage edits, not the full file
- `text_edits.py`: `apply_edits()` — applies passage edits all-or-nothing; each `old_text` must match once (exact first, then ignoring no-break/zero-width characters and typographic quotes); text outside the edits stays byte-for-byte
- `card_generator_tools.py`: `make_card_generator_tools()` factory — pattern card tools (generate_card, generate_deck, generate_image_prompts) for the Pattern Card Generator agent
- `vault_write_tools.py`: `make_vault_write_tools()` factory — generic vault write tools (create_note, edit_note, list_notes_in_dir) for any agent

#### Agentic Loop

Runs in `StreamHandler` (`packages/core/stream_handler.py`):
1. `LLMClient.complete(tools=...)` (non-streaming) — check if LLM wants to call a tool
2. If `finish_reason == "tool_calls"` → execute tool, append result, loop
3. After at most `max_iterations` rounds → stream final answer as usual. When the limit is hit, the model is told the tools still exist (`TOOL_LIMIT_NOTE`) and asked for its next step.

`max_iterations` defaults to `_MAX_AGENTIC_ITERATIONS` in `stream_handler.py`; an agent overrides it with `max_iterations:` in its `meta.yaml`. Per-agent values are in [agents.md](agents.md#agents).

#### Streaming and Prompt Caching

StreamHandler supports both streaming and non-streaming modes (`streaming` flag). Non-streaming mode uses `LLMClient.complete()` for all API calls and gets exact usage and cost from OpenRouter. In streaming mode LiteLLM replaces OpenRouter's usage with a local estimate (BerriAI/litellm#36168; ~36% cost undercount measured 2026-09-29), so streamed calls record their OpenRouter generation ids and `ConversationLogger.reconcile_billed_usage()` swaps the estimate for the billed record (`packages/core/billed_usage.py`) when the log is saved; the record is published ~10-15 s after a turn, and `scripts/backfill_billed_usage.py` fixes turns still estimated at exit. The CLI stats line marks estimates with `~`. The earlier conclusion that streaming blocks prompt caching is being re-checked: a 2026-09-29 probe saw streamed calls write and read the cache, and the March token mismatch matches the estimate-vs-billed gap. Toggle at runtime with `/stream` or via `models.streaming` config. Auto Router turns never stream (see [Model Selection](#model-selection)). Cache breakpoints are described under [LLM Client](#3-llm-client-packagescorellm_clientpy).

**Key Design Choices:**
- Non-streaming intermediate calls (simpler delta parsing, no user-visible cost)
- Errors returned as strings, never raised, so LLM can reason about failures
- `ToolRegistry` built per-agent from `AgentConfig.tools` (no global singleton)
- 50KB cap on extracted web content with truncation notice

**Tool Scoping:**

`build_session()` (`apps/cli/session_factory.py`) sorts tools into three kinds at startup:

- **Shared tools** — go to JARVIS and to every agent (e.g. vault read tools, `recall_conversations`, outcome tools, shared MCP servers). Each is only registered when its feature is enabled.
- **Named tool groups** — an agent gets a group only if its `meta.yaml` lists it under `tools:`. JARVIS gets a fixed subset (`jarvis_tools`) so it delegates specialist work instead of doing it itself.
- **Per-agent vault write tools** — created by `make_agent_vault_tools()` from the agent's `vault_writing:` key (an `obsidian.writing.<key>` section), scoped to that directory. No name collisions because each agent gets its own `ToolRegistry`.

`assemble_agent_tools()` combines them the same way for standalone `--agent` mode and for delegation (CLI and GUI). JARVIS alone gets `delegate_to_agent`. Which tools and groups each agent has is in [agents.md](agents.md#tool-distribution).

---

### 8. Recall: conversations via Cortex, outcomes and cards in `packages/core/rag/`

**Conversation recall lives in Cortex** (HUB-02, one index, decided 2026-10-05).
JARVIS reaches it through the shared `cortex` MCP server as
`mcp_cortex__search_conversations(query, date_from?, date_to?, origins?, n_results?)`.
Cortex indexes the conversation archive (`paths.conversations_dir`) on its own,
one chunk per exchange, and its file watcher re-indexes a conversation seconds
after JARVIS saves it; deleting a conversation file removes its chunks the same
way. JARVIS's own conversation indexer, searcher and `recall_conversations`
tool were removed. Turning conversations on is Cortex config
(`sources.conversations` in Cortex's `config/local.yaml`), see the Cortex README.

**Local RAG store** (`packages/core/rag/`, `rag.db_path`) keeps two collections:
- `outcome_indexer.py`: `OutcomeIndexer` / `OutcomeSearcher` — scored outcomes, searched via `recall_outcomes`
- `card_indexer.py`: `CardIndexer` / `CardSearcher` — deck-skill cards, searched via `card_search`

**Configuration**: the `rag:` section of [`config/default.yaml`](../../config/default.yaml) (store path, embedding model, card indexing).

**On by default**: `rag.enabled` is `true` and `chromadb` is a regular dependency. Embeddings go through the same `OPENROUTER_API_KEY` as chat. Set `rag.enabled: false` in `config/local.yaml` to turn it off; if ChromaDB fails at startup, outcome and card recall are disabled with a warning and the session continues. Scored outcomes are indexed when `outcomes.enabled` is also on.

---

### 9. Pricing (`packages/core/pricing.py`)

**Purpose**: Track LLM costs across providers.

**Location**: `packages/core/pricing.py`

**Responsibilities:**
- Look up pricing from LiteLLM's built-in cost map (offline, all providers)
- Calculate per-request costs
- Fallback cost calculation via LiteLLM response objects
- Format costs for display

**Key Functions:**
- `get_model_pricing(model_id)`: Get specific model pricing (tries full ID, stripped prefix, bare model name)
- `calculate_cost_from_litellm(response)`: Fallback cost calculation from response object
- `format_cost(cost_usd)`: Human-readable formatting

**Related Module:**
- `packages/core/benchmark_costs.py`: Estimate benchmark costs from golden test baselines

**Pricing Strategy:**
1. **Primary**: LiteLLM cost map lookup with progressive prefix stripping
2. **Fallback**: LiteLLM `completion_cost()` on response object
3. **Degraded**: Show token count only

**Cache-Aware Pricing**: `ModelPricing.calculate_cost()` accounts for cached tokens. Cache read/write costs are populated from LiteLLM's cost map (`cache_read_input_token_cost`, `cache_creation_input_token_cost`) when available. When absent, defaults to Anthropic rates (read = 0.1x prompt, write = 1.25x prompt). Regular prompt tokens are computed as `prompt_tokens - cache_read - cache_write`.

**Cost Centralization**: `StreamHandler._calculate_cost()` is the single helper for all three streaming paths (direct streaming, agentic loop intermediate calls, and delegation terminal tool). It passes cache tokens through to `ModelPricing.calculate_cost()` and emits a `UsageReport` event for each cost calculation.

---

### 10. Agent Discovery (`packages/agents/registry.py`)

**Purpose**: Discover and instantiate agents via `meta.yaml` registry.

**Location**: `packages/agents/registry.py`, `packages/agents/base.py`

**Discovery**: Agent directories containing a `meta.yaml` file are loaded as `DataDrivenAgent` instances. The `meta.yaml` declares the agent's name, description, command, and optional parameters (temperature, max_tokens). The system prompt is loaded from `prompts/system.md` in the same directory. No Python code is required.

**Key Components:**

- **`DataDrivenAgent`** (in `base.py`): Subclass of `BaseAgent` that implements `process_message()` and `run()` using only `meta.yaml` + `prompts/system.md`. Supports `max_iterations` for extended agentic loops. No per-agent Python code needed.
- **`agent_from_meta()`** (in `base.py`): Factory function that builds an agent from a `meta.yaml` path. Reads the YAML, loads `prompts/system.md`, resolves `prompt_includes` placeholders, binds skills, and returns a configured `DataDrivenAgent`.
- **`AgentMeta`** dataclass: Contains `meta_path`, `vault_writing`, `tool_groups` (named tool groups from CLI registry), and `skills` (skill names to bind).
- **`assemble_agent_tools()`** (in `apps/cli/session_factory.py`): Builds tool list for an agent from shared tools + its declared `tool_groups`.
- **`instantiate_agent()`** (in `apps/cli/session_factory.py`): Thin wrapper around `agent_from_meta()`.
- **`build_session()`** (in `apps/cli/session_factory.py`): Shared factory that assembles the `SessionComponents` both the CLI and the GUI need (client, agent registry, tool groups, logger, stream handler, vault, MCP). Parameterized on a `ConfirmationHandler` injection — the CLI passes `CLIConfirmationHandler()`; the GUI passes a `WebConfirmationHandler` rebound per turn. See [gui.md](gui.md) for GUI architecture details.

**Agents**: every delegate agent is data-driven (a `meta.yaml` directory under `packages/agents/`); the list with commands, models and tools is in [agents.md](agents.md#agents). The `meta.yaml` fields are documented in [api.md](api.md#metayaml-schema).

**Python-class agent**: jarvis (orchestrator with delegation logic — the only agent with custom Python code).

### Model Selection

Which model a turn runs on (the user-facing order and how to change it: [deployment.md](deployment.md#model-selection-order)):

- **Session model**: resolved at startup by `resolve_model()` (`packages/core/model_resolver.py`) from `--model`, else `auto` if `models.auto_router.enabled`, else `models.default`; `/model` switches it mid-session. Preset names resolve through `models.presets`.
- **Heuristic routing** (opt-in, `routing.enabled`): `packages/core/model_router.py` classifies each query by length and markers and picks the `fast`, `balanced` or `quality` preset. It skips pinned agents and the Auto Router.
- **Auto Router mode** (ADR-036): `models.auto_router.enabled` makes the session model `openrouter/openrouter/auto` (`AUTO_MODEL_ID`); `session_extra_body()` adds the `auto-router` plugin block and a per-session `session_id` to the client's per-model `extra_body` (never mutating settings). `StreamHandler` doesn't stream auto calls (LiteLLM drops the picked model and cost from streams), records the picked models in `StreamResult.served_models`, and prefers the provider-reported `usage.cost` (`TokenUsage.reported_cost`) over the price table.
- **Per-agent model**: `meta.yaml` may name a `model` (preset or model id). `instantiate_agent()` resolves it against the loaded `models` config and marks the agent `model_pinned`; `BaseAgent.run()` then wraps the turn in `StreamHandler.using_model()`, which switches the client default, the reported model and pricing, and restores them afterwards. Tools that call a model themselves (`evaluate_content`) use the client's current model, so they follow the running agent. Unpinned agents run on the session model. Which agents are pinned: [agents.md](agents.md#agents).

### 11. Agent-Skill Binding (`packages/skills/resolver.py`)

**Purpose**: Inject skill knowledge into agents at construction time.

Agents can declare `skills:` in their `meta.yaml` to bind skills:

```yaml
name: pattern_language_expert
command: /pattern-language-expert
skills:
  - pattern-language-expert
```

**Resolution logic** (`resolve_skills()`):
- **Simple skills** (SKILL.md only): Body text (frontmatter stripped) is appended to the agent's system prompt.
- **Deck-skills** (has `deck.yaml`): Name is added to a deck-skill hint section; if `card_search_tool` is available, it's included in the agent's tools.
- Unknown skill names are logged as warnings and skipped.

**Wiring**: `agent_from_meta()` accepts `skill_registry` and `card_search_tool` parameters. `build_session()` threads these from `discover_skills()` and RAG card indexing. The skills-vs-agents distinction is in [skills-vs-agents.md](skills-vs-agents.md).

### 12. Agent-to-Agent Handoff

**Purpose**: Preserve conversation context across delegated agent sessions.

**Two information channels:**
- **`context`** (JARVIS → agent): A summary of JARVIS's conversation with the user before delegating. Prepended as a synthetic context exchange in the agent's session history.
- **`prior_session`** (agent → agent): The full, unmodified conversation history from the previous agent's session. Passed verbatim — no summarization.

**Flow:**
1. JARVIS delegates to Agent A with `context` (summary of JARVIS chat)
2. Agent A runs, user types `/exit` → `_run_agent_session()` returns full `session_history`
3. JARVIS stores `last_agent_session` and adds a summary to its own history
4. When JARVIS delegates to Agent B, `prior_session=last_agent_session` passes Agent A's full conversation

**Hand-back** (agent → JARVIS): a specialist in an interactive CLI session can call `hand_back_to_jarvis(reason)`. The session ends and JARVIS routes the user's message (verbatim, prefixed with the reason) as its next turn, which usually delegates to Agent B via the flow above. A request is routed again at most once. Rationale and alternatives: [ADR-038](../product/decisions.md#adr-038-specialist-hand-back--jarvis-stays-the-only-router).

---

## Data Flow

### Typical Request Flow

```
1. User types message
   ↓
2. CLI appends to logger
   ↓
3. CLI builds message array:
   [system_prompt, ...history, new_message]
   ↓
4. LLM Client streams response
   ├─ Yield chunks → CLI prints
   └─ Track usage
   ↓
5. CLI displays cost
   ↓
6. Logger saves message + metadata
   ↓
7. Repeat until user quits
   ↓
8. Logger saves session to JSON
```

### Import Flow (ChatGPT)

```
1. Load ChatGPT conversations.json
   |
2. Apply filters (date, model, archived)
   |
3. For each conversation:
   ├─ Check if already imported (by chatgpt_id)
   ├─ Linearize message tree (current_node → root)
   ├─ Convert content parts to Jarvis blocks
   ├─ Generate deterministic conv_id
   └─ Write to data/conversations/YYYY/YYYY-MM-DD_HH-MM-SS.json
```

### Import Flow (Claude)

```
1. Load Claude conversations.json
   |
2. Apply filters (date range)
   |
3. For each conversation:
   ├─ Check if already imported (by claude_id → file path)
   │   ├─ Exists: call update_conversation()
   │   │   ├─ Sync title, session_end, append new messages
   │   │   └─ Write updated JSON (or skip if unchanged)
   │   └─ New: convert_conversation() → write new file
   ├─ Convert content blocks (text, thinking, tool_use, etc.)
   ├─ Generate deterministic conv_id
   └─ Write to data/conversations/YYYY/YYYY-MM-DD_HH-MM-SS.json
```

### Startup Flow

```
1. Load config/default.yaml + config/local.yaml + .env
   ↓
2. Collect API keys from env (collect_api_keys())
   ↓
3. Resolve session model (see Model Selection above)
   ↓
4. Sync Things 3 tasks → paths.tasks_file
   ↓
5. Build system prompt from paths.context_files
   (plus the auto-generated tasks file)
   ↓
6. Initialize LLM client (api_keys dict, resolved model)
   ↓
7. RAG initialization (if rag.enabled)
   ├─ OutcomeIndexer.index_new(outcomes_dir) (if outcomes.enabled)
   └─ CardIndexer.index_new(deck_dirs) → tool_groups["card_search"]
   (conversation recall comes from the shared cortex MCP server)
   ↓
7b. Blog tools initialization (if obsidian.enabled and blog_dir set)
   └─ make_blog_tools(vault_config, ...) → tool_groups["blog_tools"]
   ↓
7c. MCP client initialization (if settings.mcp.enabled) — Cortex arrives here
    as a shared MCP server (HUB-01)
   ├─ MCPManager.start(settings.mcp.servers) → connect to servers, discover tools
   └─ MCP tool groups → tool_groups dict (shared: true servers → shared_tools)
   ↓
8. Agent discovery (meta.yaml registry)
   └─ Scan agent directories for meta.yaml (all agents discovered via meta.yaml)
   ↓
9. Load pricing from LiteLLM cost map (offline, no HTTP)
   ↓
10. Display startup info (model, pricing)
   ↓
11. Enter chat loop (handles /model for mid-session switching)
```

---

## File Structure

This is the canonical project tree; other docs show only the top level and link here. The layout
of `tests/` is in [tests/README.md](../../tests/README.md), of `tests/golden/` in
[tests/golden/README.md](../../tests/golden/README.md).

```
jarvis/
├── apps/                           # Deployable applications
│   ├── cli/                        # CLI entry point (`uv run jarvis`)
│   │   ├── main.py                 # Chat loop + slash-command routing
│   │   ├── session_factory.py      # build_session(): shared CLI/GUI bootstrap, tool groups
│   │   ├── review.py               # /outcomes scoring helpers (reused by the GUI)
│   │   └── display.py              # Rich terminal formatting
│   └── gui/                        # Web GUI (`uv run jarvis-gui`, see gui.md)
│       ├── main.py                 # Entry: uvicorn + browser open
│       ├── server/                 # FastAPI backend: app, auth, bridge, state, streaming,
│       │                           #   confirmation, protocol, resume; routes/, agents/, home/, history/
│       └── web/                    # React 18 + Vite + TypeScript (src/ + committed dist/)
│
├── packages/                       # Shared libraries (reusable)
│   ├── core/                       # Core JARVIS functionality
│   │   ├── llm_client.py           # LLM API abstraction
│   │   ├── context_builder.py      # System prompt assembly
│   │   ├── memory.py               # Conversation logging (schema v1.0.0)
│   │   ├── history.py              # History trimming (old tool results + tool-call args) + summarization
│   │   ├── billed_usage.py         # OpenRouter billing records for streamed calls
│   │   ├── pricing.py              # Cost tracking
│   │   ├── stream_handler.py       # Streaming + agentic loop + metrics + cost + event emission
│   │   ├── events.py               # Typed event dataclasses (WEB — event decoupling)
│   │   ├── settings.py             # Typed config (pydantic-settings, ADR-032)
│   │   ├── model_resolver.py       # Presets, `auto` alias, per-session extra_body
│   │   ├── model_router.py         # Heuristic complexity routing (opt-in)
│   │   ├── filesystem_access.py    # Filesystem access control (FilesystemGuard)
│   │   ├── frontmatter.py          # YAML frontmatter parse/dump + atomic write
│   │   ├── date_utils.py           # parse_relative_date ("next week", ISO dates, …)
│   │   ├── daily_summary.py        # /daily-summary request builder (CLI + GUI)
│   │   ├── card_renderer.py        # Pattern card rendering (parse, HTML/CSS, WeasyPrint PNG)
│   │   ├── benchmark_costs.py      # Benchmark cost estimation
│   │   ├── rag/                    # Outcome and card recall (conversations: Cortex)
│   │   │   ├── outcome_indexer.py  # OutcomeIndexer (scored outcomes)
│   │   │   └── card_indexer.py     # CardIndexer (deck-skill cards)
│   │   ├── tools/                  # Function calling tools (groups: agents.md)
│   │   │   ├── base.py             # ToolDefinition + ToolRegistry
│   │   │   ├── executor.py         # execute_tool_calls()
│   │   │   ├── delegate.py         # delegate_to_agent (JARVIS only)
│   │   │   ├── outcome_tools.py, outcome_recall.py
│   │   │   ├── vault_read_tools.py, vault_write_tools.py
│   │   │   ├── web_fetch.py, web_search.py
│   │   │   ├── blog_tools.py, text_edits.py, content_evaluator.py, suggest_improvements.py
│   │   │   ├── card_generator_tools.py, card_search.py
│   │   │   └── readwise_tools.py
│   │   └── importers/              # Conversation importers
│   │       ├── common.py           # Shared importer utilities
│   │       ├── chatgpt.py          # ChatGPT export converter
│   │       ├── claude.py           # Claude export converter
│   │       ├── claude_code.py      # Claude Code session transcript converter
│   │       └── claude_memory.py    # Claude memory export → memory proposals for approval
│   ├── agents/                     # Agent implementations
│   │   ├── base.py                 # BaseAgent + DataDrivenAgent classes
│   │   ├── registry.py             # Agent discovery (meta.yaml) + slash-command lookup
│   │   ├── prompt_includes.py      # prompt_includes resolution chain
│   │   ├── _shared/prompts/        # Shared prompt includes (anti-patterns.md, voice-profile.md.example)
│   │   ├── jarvis/                 # Orchestrator (Python class: agent.py + prompts/)
│   │   └── <name>/                 # One directory per data-driven agent: meta.yaml + prompts/system.md
│   │                               #   (list: docs/engineering/agents.md)
│   ├── skills/                     # Skills (passive knowledge packs)
│   │   ├── registry.py             # Filesystem-based skill discovery + skill.py import
│   │   ├── resolver.py             # Skill resolution and binding for agents
│   │   └── <skill-name>/           # One kebab-case directory per skill (SKILL.md), e.g. content-evaluator/
│   ├── integrations/               # External service integrations
│   │   ├── things3/                # Things 3 task sync via the export Shortcut (ADR-037)
│   │   ├── readwise/client.py      # Readwise / Reader client (/reading)
│   │   ├── mcp/                    # MCP client integration
│   │   │   ├── client.py           # Connection lifecycle + async/sync bridge
│   │   │   └── bridge.py           # MCP Tool → ToolDefinition conversion
│   │   └── obsidian/               # Obsidian vault integration
│   │       ├── vault.py            # Vault access + path validation
│   │       ├── callout.py          # Callout block parser (pure string ops)
│   │       ├── diff.py             # Diff computation + formatters
│   │       └── writer.py           # Write orchestration + ConfirmationHandler
│   └── telemetry/                  # Metrics and monitoring
│       └── metrics.py              # TTFT, response metrics
│
├── data/                           # User data (gitignored)
│   ├── context/                    # Personal context (markdown; load order in §2 above)
│   ├── conversations/YYYY/         # Session logs, YYYY-MM-DD_HH-MM-SS.json
│   ├── outcomes/                   # Tracked recommendations + reviews
│   ├── prompt-history/             # Per-agent prompt snapshots (GUI prompt editor)
│   └── rag/chroma/                 # ChromaDB persistent data
│
├── config/                         # Configuration
│   ├── default.yaml                # Default configuration (reference for all defaults)
│   └── local.yaml                  # Local overrides (gitignored)
│
├── scripts/                        # Importers (import_*.py), model_benchmark.py, benchmark_report.py,
│                                   #   analyze_costs.py, analyze_context.py, backfill_billed_usage.py,
│                                   #   link_skills.sh (symlink private skills), one-off migrations
├── tests/                          # Test suite (layout: tests/README.md)
├── docs/                           # Documentation (product/, engineering/, research/, design/)
├── jarvis_cli.py, jarvis_gui.py    # Script entry points
├── .env                            # API keys (gitignored)
└── pyproject.toml                  # Project configuration
```

---

## Design Principles

### 1. Simplicity Over Cleverness
- No unnecessary abstractions
- Functions do one thing well
- Readable by intermediate developers

### 2. Explicit Over Implicit
- Clear data flow
- No magic behavior
- Documented decisions (ADRs)

### 3. Separation of Concerns
- Each module has single responsibility
- Minimal coupling between components
- Easy to test in isolation

### 4. Local-First
- All data on user's machine
- No cloud dependencies (except LLM APIs)
- Human-readable formats (markdown, JSON)

### 5. Provider Independence
- Abstract LLM providers via LiteLLM
- Switch with config change, not code change
- No vendor-specific code

---

## Technology Choices

### Core Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.13+ | Modern type system, wide AI ecosystem |
| LLM Abstraction | LiteLLM | Provider-agnostic, function calling ready |
| Config | YAML | Human-readable, simple |
| Context Storage | Markdown | Editable, versionable, portable |
| Conversation Logs | JSON | Structured but readable |
| CLI | Standard input/output | Simple, scriptable |

### Dependencies

**Core:**
- `litellm` - LLM provider abstraction
- `requests` - HTTP client (for pricing API)
- `pyyaml` - Config parsing
- `python-dotenv` - Environment variables

**Also core** (listed in `pyproject.toml`):
- `chromadb` - Vector storage for outcome and card recall (`rag.enabled`, on by default)

**Future:**
- `sentence-transformers` - Local embeddings (alternative to API embeddings)
- `textual` - TUI (`UX`)

---

## Scalability Considerations

### Current State

WEB event decoupling (the prerequisite for the web interface) is implemented:

- **Events**: Typed event dataclasses (`TextChunk`, `ToolCallStarted`, `ToolResult`, `UsageReport`, `AgentStarted`, `AgentFinished`, `DelegationRequested`) for decoupled streaming output
- **Typed config**: `packages/core/settings.py` (`load_config() -> Settings`) is the canonical loader for both CLI and GUI; PR-8a deleted the dict-based wrapper.

See `docs/engineering/multi-agent-architecture.md` for the full multi-agent architecture vision (Scenarios A/B/C).

### Limitations

- **Single user**: No multi-user support
- **Single machine**: Distributed execution (Scenario B) is vision-only
- **In-memory history**: Full conversation in context window (mitigated by history summarization — see below)

### History Summarization

Opt-in via `summarization.enabled` (threshold and number of kept messages in the `summarization:` section of [`config/default.yaml`](../../config/default.yaml)). `summarize_history()` in `packages/core/history.py` compresses old conversation turns with the `fast` preset once history exceeds the token threshold, keeping the most recent messages intact. A `[JARVIS_SUMMARY]` marker avoids re-summarizing every turn. The setting is hot-applied in the GUI (`HOT_APPLY_PATHS`).

---

## Security Considerations

### Current State

- ✅ API keys in `.env` (not committed)
- ✅ Local data only (no cloud sync)
- ✅ Single user; the GUI requires a token and checks the request origin ([gui.md](gui.md#authentication), ADR-035)
- ⚠️ Conversation logs contain sensitive data (user responsible for security)

### Best Practices

1. **API Keys**: Never commit to git
2. **Conversation Logs**: Gitignore by default
3. **Context Files**: Careful what you commit (may contain personal info)
4. **Backups**: Encrypted backups recommended

### Future Considerations

- Optional end-to-end encryption for cloud sync
- Sensitive data redaction in logs
- Audit logging for agent actions

---

## Testing Strategy

Unit, integration and golden tests (LLM-as-judge). Strategy and mutation testing: [testing.md](testing.md); commands: [tests/README.md](../../tests/README.md).

---

## Monitoring & Observability

### Current Logging

- Token usage per request ✅
- Cost per request ✅
- Session statistics ✅
- Conversation history ✅

### Missing (Planned)

- Error rates and types
- Model performance metrics
- User interaction patterns

---

## Extension Points

### Easy to Add

1. **New providers**: Just configure LiteLLM
2. **New context files**: Add to `context/` directory
3. **Custom prompts**: Edit an agent's `prompts/system.md` or the context files in `paths.context_dir`
4. **Alternative UIs**: Import and use existing modules

### Future Extensibility

1. **Plugin system**: Load custom tools/functions
2. **Agent marketplace**: Share agent configs
3. **Custom retrieval strategies**: Modular RAG implementation

---

*Last updated: 2026-03-26*
