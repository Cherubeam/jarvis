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
│  • Memory           │ • Writer Agent   │ • Cortex (semantic)    │
│  • Pricing          │ • Tactics Coach  │ • Readwise             │
│  • Stream Handler   │ • Developer      │ • MCP (client)         │
│  • Settings (typed) │ • Data-driven    │                        │
│  • Frontmatter      │   agents (×13)   │                        │
│  • Date utils       │ • Registry       │                        │
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
- `build_system_prompt(context_dir, prefix)`: Assemble full prompt with tiered project loading

**Context Loading Order:**
1. `personal_context.md` - Who the user is (personal background)
2. `professional_context.md` - Professional background and skills
3. `preferences.md` - How to behave
4. `current_focus.md` - What's currently relevant (includes project names and Obsidian vault pointer)
5. `tasks.md` - Current tasks from Things 3 (auto-generated)

**Project Knowledge:**
Project details are maintained in Obsidian (`02 – Projects/`) and retrieved on demand via `search_vault_semantic` and `read_note` tools, rather than being statically loaded into the system prompt. This keeps the prompt lean and ensures project knowledge is always up to date with the single source of truth in the vault.

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
- Return message history for API calls

**Key Classes:**
- `SessionMetrics`: Aggregated metrics including latency
- `ConversationLogger`: Main logging class

**Key Methods:**
- `add_message(role, content, ..., ttft_ms, total_latency_ms)`: Add message to log
- `get_messages_for_api()`: Format messages for LLM API
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

### 5. Task Sync (`packages/integrations/things3/task_sync.py`)

**Purpose**: Synchronize tasks from Things 3 to provide task context.

**Location**: `packages/integrations/things3/task_sync.py`

**Responsibilities:**
- Read tasks from Things 3 via SQLite using `things.py` (no app launch required)
- Fetch tasks from Inbox, Today, and Upcoming lists
- Write tasks to `tasks.md` in markdown format grouped by area > project > tasks
- Cache results to avoid repeated reads (5-minute TTL)
- Handle errors gracefully (CLI works without task sync)

**Key Classes:**
- `Task`: Dataclass with fields: `title`, `notes`, `due_date`, `when_date`, `tags`, `project`, `area`
- `TaskSyncCache`: File-based cache with TTL

**Key Functions:**
- `_to_task()`: Convert a `things.py` dict to a `Task` dataclass
- `fetch_tasks()`: Read tasks from SQLite via `things.py` with caching
- `format_tasks_as_markdown()`: Format tasks grouped by area > project > tasks
- `sync_tasks_to_file()`: Orchestrate fetch + format + write to `tasks.md`

**Design Decision**:
- Reads the Things 3 SQLite database directly via `things.py` — language-independent, no app launch needed
- Replaced AppleScript approach (ADR-008) which had 5s timeouts and fragile language detection
- Things 3 write operations (via MCP) remain a future option — tracked under `CAP`
- See ADR-008 for historical context

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
- `vault.py`: `VaultConfig`, path validation, read/list/get daily note
- `callout.py`: `CalloutBlock`, `find_jarvis_callout()`, `build_updated_content()` (no I/O)
- `diff.py`: `VaultDiff`, `compute_diff()`, CLI/API formatters
- `writer.py`: `ConfirmationHandler` ABC, `CLIConfirmationHandler`, `append_to_daily_note()`, `write_note()`

**Key Design Decisions:**
- **FilesystemGuard**: Per-path access control layer replacing flat `allowed_dirs`. Rules use `AccessLevel` (read/write/deny) with most-specific-path-wins resolution. Shared across all vault tools for consistent enforcement. See ADR-021.
- **ConfirmationHandler ABC**: CLI and future GUI each implement this interface
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

**Configuration** (`config/local.yaml`):
```yaml
mcp:
  enabled: true
  servers:
    cortex:
      transport: stdio
      tool_group: cortex
      shared: true          # every agent gets the tools automatically
      command: uv
      args: ["--directory", "/path/to/cortex", "run", "cortex-mcp"]
```

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
- `MCPConnection`: Manages one server connection using `AsyncExitStack`
- `MCPManager`: Manages all connections, background event loop, and sync/async bridge
- `mcp_tools_to_tool_definitions()`: Converts MCP tools to namespaced `ToolDefinition` instances

**Configuration** (`config/default.yaml`):
```yaml
mcp:
  enabled: false              # Set to true in local.yaml
  servers: {}                 # Declare servers in local.yaml
```

**Transports**: stdio, SSE, streamable HTTP. Each server's tools become a named tool group that agents reference in `meta.yaml`.

**Opt-in**: Disabled by default. Adding/removing servers is a config-only change.

---

### 7. Tool Calling (`packages/core/tools/`)

**Purpose**: Provide a composable function-calling layer for LLM tool use.

**Location**: `packages/core/tools/`

**Modules:**
- `base.py`: `ToolDefinition` dataclass + `ToolRegistry` class
- `executor.py`: `execute_tool_calls()` — runs tool calls from LLM, returns formatted result messages
- `web_fetch.py`: `FETCH_URL_TOOL` singleton — fetches URLs with `httpx`, extracts text with `trafilatura`
- `blog_tools.py`: `make_blog_tools()` factory — scoped blog post tools for the Writing Agent (list, read, create, edit)
- `card_generator_tools.py`: `make_card_generator_tools()` factory — pattern card tools (generate_card, generate_deck, generate_image_prompts) for the Pattern Card Generator agent
- `vault_write_tools.py`: `make_vault_write_tools()` factory — generic vault write tools (create_note, edit_note, list_notes_in_dir) for any agent
- `codebase_tools.py`: `read_source_file`, `search_code`, `list_directory`, `read_architecture_map` — read-only codebase introspection tools for the Developer Agent
- `git_tools.py`: `git_status`, `git_diff`, `git_branch`, `git_add`, `git_commit`, `git_log` — git operations with branch-prefix enforcement and `[JARVIS-auto]` commit tagging
- `project_write_tools.py`: `write_file`, `edit_file`, `create_directory` — guarded file write tools with confirmation handler and scope restrictions (`DEV-01`: `.md`, `.yaml`, `.yml` only)
- `test_tools.py`: `run_tests` — runs the test suite via subprocess with timeout

**Agentic Loop** (in `StreamHandler`):
1. `LLMClient.complete(tools=...)` (non-streaming) — check if LLM wants to call a tool
2. If `finish_reason == "tool_calls"` → execute tool, append result, loop
3. After at most `max_iterations` iterations → stream final answer as usual
   - Default: 5 (all agents except developer)
   - Developer Agent: 20 (multi-step edit-test-fix cycles)

StreamHandler supports both streaming and non-streaming modes (`streaming` flag). Non-streaming mode uses `LLMClient.complete()` for all API calls, enabling prompt caching via OpenRouter. Toggle at runtime with `/stream` or via `models.streaming` config.

**Key Design Choices:**
- Non-streaming intermediate calls (simpler delta parsing, no user-visible cost)
- Errors returned as strings, never raised, so LLM can reason about failures
- `ToolRegistry` built per-agent from `AgentConfig.tools` (no global singleton)
- 50KB cap on extracted web content with truncation notice

**Tool Scoping for Agent Delegation:**

Tools are split into three categories at startup, each with different forwarding rules:

| List | Examples | Given to JARVIS | Standalone `--agent` | Delegated agent |
|---|---|---|---|---|
| `extra_tools` | `recall_conversations`, vault read tools | Yes | Yes | Yes (via delegation fix) |
| `agent_only_tools` | blog tools, `evaluate_content` | **No** | Yes | Yes |
| Per-agent vault tools | `create_note`, `edit_note` (scoped to agent's dir) | **No** | Yes | Yes |

- **`extra_tools`** — Orchestration tools (conversation recall, card search). Wired at startup, passed to `JarvisAgent`. These are NOT forwarded when JARVIS delegates to a specialist agent, because JARVIS already gathered context before delegating.
- **`agent_only_tools`** — Specialist tools (blog tools, content evaluator). NOT given to JARVIS (so it delegates content work instead of handling it directly). Forwarded to delegated agents via the `extra_tools` parameter.
- **Per-agent vault tools** — Created by `_make_agent_vault_tools()` based on `vault_writing` in the agent's `meta.yaml`. Each agent declares which `obsidian.writing.<key>` config section it uses (e.g. `patterns`, `slip_box`), and gets vault write tools scoped to that directory. No name collisions because each agent gets its own `ToolRegistry`.
- **Standalone `--agent` mode** — Receives `extra_tools + agent_only_tools + agent_vault_tools`.
- **Delegation path** — Receives `extra_tools + agent_only_tools + agent_vault_tools`.

---

### 8. RAG / Conversation Recall (`packages/core/rag/`)

**Purpose**: Semantic search over past conversations via ChromaDB vector storage.

**Location**: `packages/core/rag/`

**Modules:**
- `indexer.py`: `ConversationIndexer` — recursively scans `data/conversations/YYYY/*.json`, skips already-indexed conv_ids, embeds message-pair chunks via LiteLLM, upserts into ChromaDB
- `searcher.py`: `ConversationSearcher` + `SearchResult` dataclass — embeds a query, runs cosine similarity search, returns ranked results with optional date range filter

**Tool Integration:**
- `packages/core/tools/conversation_recall.py`: `make_conversation_recall_tool()` factory — wraps a `ConversationSearcher` in a `ToolDefinition` callable by the LLM
- LLM calls: `recall_conversations(query, date_from?, date_to?)`

**Chunking Strategy:**
Message-pair chunks (user + assistant turns together) preserve conversational context and are more semantically coherent than individual messages.

**ChromaDB Document Schema:**

| Field | Value |
|---|---|
| `id` | `{conv_id}_pair_{n}` |
| `document` | `"User: {text}\n\nAssistant: {text}"` |
| `metadata.conv_id` | e.g. `"conv_20260226_112019_dfa2a9"` |
| `metadata.session_date` | `"YYYY-MM-DD"` (for date range filters) |
| `metadata.pair_index` | 0-based int |
| `metadata.user_snippet` | first 200 chars of user turn |
| `metadata.assistant_snippet` | first 200 chars of assistant turn |
| `metadata.title` | conversation title or `""` |

**Configuration** (`config/default.yaml`):
```yaml
rag:
  enabled: false
  db_path: "data/rag/chroma"
  embedding_model: "openrouter/openai/text-embedding-3-small"
```

**Opt-in**: Disabled by default. Enable with `rag.enabled: true` in `local.yaml` and `uv add chromadb`.

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

**Data-driven delegate agents** (13 total): content_reviewer, developer, navigator, obsidian_note_creator, okr_architect, pattern_language_expert, researcher, simplifier, strategyzer, substack_image_creator, substack_publisher, tactics_coach, writer.

**Python-class agent**: jarvis (orchestrator with delegation logic — the only agent with custom Python code).

### 11. Agent-Skill Binding (`packages/skills/resolver.py`)

**Purpose**: Inject skill knowledge into agents at construction time.

Agents can declare `skills:` in their `meta.yaml` to bind skills:

```yaml
name: pattern-language-expert
command: /pattern-language-expert
skills:
  - pattern-language-expert
```

**Resolution logic** (`resolve_skills()`):
- **Simple skills** (SKILL.md only): Body text is appended to the agent's system prompt.
- **Deck-skills** (has `deck.yaml`): Name is added to a deck-skill hint section; if `card_search_tool` is available, it's included in the agent's tools.
- Unknown skill names are logged as warnings and skipped.

**Wiring**: `agent_from_meta()` accepts `skill_registry` and `card_search_tool` parameters. The CLI threads these from `discover_skills()` and RAG card indexing.

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
1. Load config.yaml + .env
   ↓
2. Collect API keys from env (collect_api_keys())
   ↓
3. Resolve model: --model flag > config models.default
   ↓
4. Sync Things 3 tasks → tasks.md
   ↓
5. Build system prompt from context/*.md
   (includes auto-generated tasks.md)
   ↓
6. Initialize LLM client (api_keys dict, resolved model)
   ↓
7. RAG initialization (if rag.enabled: true)
   ├─ ConversationIndexer.index_new(conversations_dir)
   │   Embed + upsert any new conversation files
   └─ make_conversation_recall_tool() → extra_tools
   ↓
7b. Blog tools initialization (if obsidian.enabled: true)
   └─ make_blog_tools(vault_config, ...) → agent_only_tools
   ↓
7c. Cortex initialization (if cortex.enabled: true)
   ├─ CortexClient(base_url, timeout)
   ├─ make_cortex_search_tool() → shared_tools
   └─ Health check: print connected/unreachable status
   ↓
7d. MCP client initialization (if settings.mcp.enabled)
   ├─ MCPManager.start(settings.mcp.servers) → connect to servers, discover tools
   └─ MCP tool groups → tool_groups dict
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

```
jarvis/
├── apps/                           # Deployable applications
│   ├── cli/                        # CLI entry point
│   │   ├── main.py                 # CLI application
│   │   └── display.py              # Rich terminal formatting
│   └── web/                        # Web application (WEB)
│       ├── backend/                # FastAPI backend
│       └── frontend/               # React frontend
│
├── packages/                       # Shared libraries (reusable)
│   ├── core/                       # Core JARVIS functionality
│   │   ├── llm_client.py           # LLM API abstraction
│   │   ├── context_builder.py      # System prompt assembly
│   │   ├── memory.py               # Conversation logging
│   │   ├── pricing.py              # Cost tracking
│   │   ├── stream_handler.py       # Streaming + metrics + cost + event emission
│   │   ├── events.py               # Typed event dataclasses (WEB — event decoupling)
│   │   ├── app.py                  # Shared bootstrap (config, init)
│   │   ├── filesystem_access.py    # Filesystem access control (FilesystemGuard)
│   │   ├── card_renderer.py         # Pattern card rendering (parse, HTML/CSS, WeasyPrint PNG)
│   │   ├── benchmark_costs.py      # Benchmark cost estimation
│   │   ├── rag/                    # Conversation recall (RAG)
│   │   │   ├── indexer.py          # ConversationIndexer
│   │   │   └── searcher.py         # ConversationSearcher + SearchResult
│   │   ├── tools/                  # Function calling tools
│   │   │   ├── base.py             # ToolDefinition + ToolRegistry
│   │   │   ├── executor.py         # execute_tool_calls()
│   │   │   ├── web_fetch.py        # fetch_url tool
│   │   │   ├── conversation_recall.py  # make_conversation_recall_tool()
│   │   │   ├── delegate.py             # delegate_to_agent tool
│   │   │   ├── vault_read_tools.py     # Obsidian vault read tools (read_note, search_notes, read_daily_note)
│   │   │   ├── blog_tools.py           # make_blog_tools() for Writing Agent
│   │   │   ├── card_generator_tools.py # make_card_generator_tools() for Pattern Card Generator
│   │   │   ├── vault_write_tools.py    # make_vault_write_tools() for any agent
│   │   │   ├── codebase_tools.py       # read_source_file, search_code, list_directory, read_architecture_map
│   │   │   ├── git_tools.py            # git_status, git_diff, git_branch, git_add, git_commit, git_log
│   │   │   ├── cortex_search.py          # make_cortex_search_tool() (vault semantic search)
│   │   │   ├── project_write_tools.py  # write_file, edit_file, create_directory (scoped, guarded)
│   │   │   └── test_tools.py           # run_tests via subprocess
│   │   └── importers/              # Conversation importers
│   │       ├── common.py           # Shared importer utilities
│   │       ├── chatgpt.py          # ChatGPT export converter
│   │       ├── claude.py           # Claude export converter
│   │       └── claude_context.py   # Claude memories/projects importer
│   ├── agents/                     # Agent implementations
│   │   ├── base.py                 # BaseAgent + DataDrivenAgent classes
│   │   ├── registry.py             # Agent discovery (meta.yaml) + slash-command lookup
│   │   ├── _shared/                # Shared prompt includes
│   │   │   └── prompts/
│   │   │       ├── voice-profile.md
│   │   │       └── anti-patterns.md
│   │   ├── jarvis/                 # Main JARVIS orchestrator
│   │   │   ├── agent.py
│   │   │   └── prompts/            # Daily summary + writing prompts
│   │   ├── content_reviewer/       # Data-driven agent (/content-review)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── developer/              # Data-driven agent (/develop)
│   │   │   ├── meta.yaml
│   │   │   ├── confirmation.py
│   │   │   └── prompts/system.md
│   │   ├── navigator/              # Data-driven agent (/navigator)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── obsidian_note_creator/  # Data-driven agent (/obsidian-note-creator)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── okr_architect/          # Data-driven agent (/okr-architect)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── pattern_language_expert/ # Data-driven agent (/pattern-language-expert)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── pattern_card_generator/ # Data-driven agent (/pattern-cards)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── researcher/             # Data-driven agent (/research)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── simplifier/             # Data-driven agent (/simplify)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── strategyzer/            # Data-driven agent (/strategize)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── substack_image_creator/ # Data-driven agent (/substack-image)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── substack_publisher/     # Data-driven agent (/substack-publish)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   ├── tactics_coach/          # Data-driven agent (/tactics)
│   │   │   ├── meta.yaml
│   │   │   └── prompts/system.md
│   │   └── writer/                 # Data-driven agent (/write)
│   │       ├── meta.yaml
│   │       └── prompts/system.md
│   ├── skills/                     # Skills (passive knowledge packs)
│   │   ├── base.py                 # BaseSkill (parses SKILL.md, optional skill.py)
│   │   ├── registry.py             # Filesystem-based skill discovery
│   │   ├── resolver.py             # Skill resolution and binding for agents
│   │   └── .../                    # Individual skills (each has SKILL.md)
│   ├── integrations/               # External service integrations
│   │   ├── things3/                # Things 3 task sync
│   │   │   └── task_sync.py        # ~520 lines
│   │   ├── cortex/                 # Cortex semantic search client
│   │   │   └── client.py           # CortexClient (HTTP)
│   │   ├── mcp/                    # MCP client integration
│   │   │   ├── config.py           # Config parsing + validation
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
├── data/                           # User data
│   ├── context/                    # Personal context (markdown)
│   │   ├── personal_context.md     # Personal background
│   │   ├── professional_context.md # Professional background
│   │   ├── preferences.md
│   │   ├── current_focus.md
│   │   └── tasks.md                # Auto-generated from Things 3
│   ├── conversations/              # Session logs (gitignored)
│   │   └── YYYY/                   # Year-based subdirectories
│   │       └── YYYY-MM-DD_HH-MM-SS.json
│   ├── rag/                        # RAG vector store (gitignored)
│   │   └── chroma/                 # ChromaDB persistent data
│   ├── codebase_map.md             # Auto-generated by scripts/generate_codebase_map.py
│   └── learned_facts.md            # (Future) Extracted facts
│
├── config/                         # Configuration
│   ├── default.yaml                # Default configuration
│   └── local.yaml                  # Local overrides (gitignored)
│
├── tests/                          # Test suite
├── docs/                           # Documentation
├── scripts/                        # Utility scripts
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
- `things.py` - Things 3 task sync via SQLite

**Optional:**
- `chromadb` - Vector storage for conversation recall (via `uv add chromadb`, `rag.enabled: true`)

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

History summarization (`summarize_history()` in `history.py`) compresses old conversation turns using the fast model when history exceeds ~40K tokens. Uses a `[JARVIS_SUMMARY]` marker to avoid re-summarizing every turn.

---

## Security Considerations

### Current State

- ✅ API keys in `.env` (not committed)
- ✅ Local data only (no cloud sync)
- ✅ No user authentication (single-user)
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

See [docs/engineering/testing.md](testing.md) for current test counts, coverage details, and the full testing strategy.

**Quick summary**: Comprehensive automated test suite with 97.5% coverage on core modules. Unit, integration, and golden tests with LLM-as-judge evaluation.

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
3. **Custom prompts**: Edit `config.yaml`
4. **Alternative UIs**: Import and use existing modules

### Future Extensibility

1. **Plugin system**: Load custom tools/functions
2. **Agent marketplace**: Share agent configs
3. **Custom retrieval strategies**: Modular RAG implementation

---

*Last updated: 2026-03-26*
