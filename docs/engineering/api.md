# Internal API Reference

> Documentation for Jarvis's internal Python APIs.

---

## Overview

This document provides reference documentation for Jarvis's internal modules. Core code lives in `packages/` with CLI entry points in `apps/`.

---

## Module: `llm_client`

### `class TokenUsage`

Dataclass storing token usage statistics.

**Attributes:**
- `prompt_tokens: int` - Input tokens used
- `completion_tokens: int` - Output tokens generated
- `total_tokens: int` - Sum of prompt + completion
- `cache_read_tokens: int` - Tokens served from cache (default 0)
- `cache_write_tokens: int` - Tokens written to cache (default 0)

---

### `class StreamingResponse`

Iterator wrapper for streaming LLM responses with usage tracking.

**Methods:**

#### `__init__(generator: Generator[str, None, tuple[TokenUsage, object]])`
Initialize with generator that yields content chunks.

#### `__iter__() -> StreamingResponse`
Return self as iterator.

#### `__next__() -> str`
Get next content chunk. Raises `StopIteration` when done.

**Properties:**

#### `usage: TokenUsage`
Get token usage. Only available after iteration completes.

#### `raw_response: object | None`
Get raw LiteLLM response object for fallback cost calculation.

**Usage Example:**
```python
stream = client.chat_stream(messages)
for chunk in stream:
    print(chunk, end="")
print(f"Used {stream.usage.total_tokens} tokens")
```

---

### `class LLMClient`

Main client for LLM provider interactions.

**Constructor:**

#### `__init__(api_keys: dict[str, str], default_model: str)`

**Parameters:**
- `api_keys` - Mapping of provider name → API key (e.g. `{"openrouter": "sk-...", "anthropic": "sk-ant-..."}`)
- `default_model` - LiteLLM-routable model ID (e.g. `"openrouter/anthropic/claude-sonnet-4.6"`)

**Methods:**

#### `set_model(model_id: str) -> None`

Switch the default model mid-session.

#### `chat_stream(messages: list[dict], model: str | None = None) -> StreamingResponse`

Stream a chat completion.

**Parameters:**
- `messages` - List of message dicts with "role" and "content"
- `model` - Optional model override

**Returns:**
- `StreamingResponse` - Iterator yielding content chunks

#### `complete(messages, model=None, tools=None, temperature=None) -> object`

Non-streaming completion for agentic tool-calling loops.

**Usage Example:**
```python
from packages.core.model_resolver import collect_api_keys

client = LLMClient(api_keys=collect_api_keys(), default_model="openrouter/anthropic/claude-sonnet-4.6")
messages = [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Hello!"}
]
stream = client.chat_stream(messages)
for chunk in stream:
    print(chunk, end="")
```

---

## Module: `context_builder`

### `load_context_file(filepath: Path) -> str`

Load a single markdown file, return empty string if missing.

**Parameters:**
- `filepath` - Path to markdown file

**Returns:**
- `str` - File contents or empty string

---

### `build_system_prompt(context_dir: Path) -> str`

Assemble full system prompt from context files. Identity is sourced from `soul.md` (if present) and placed first. Project knowledge is no longer loaded statically from `projects/*.md` — it now lives in the Obsidian vault and is reached via `search_vault_semantic` / vault read tools.

**Parameters:**
- `context_dir` - Directory containing context/*.md files

**Returns:**
- `str` - Complete system prompt

**Context File Loading Order:**
1. `soul.md` - Identity / values (placed first, ungated by header)
2. `personal_context.md` - Personal background
3. `professional_context.md` - Professional background
4. `preferences.md` - Behavior guidelines
5. `current_focus.md` - Current priorities
6. `tasks.md` - Things 3 tasks (auto-generated via `things-py` SQLite)
7. `reader_persona.md` - Reading profile (optional, loaded by Readwise flow)

See `build_system_prompt_with_metadata()` for the same assembly plus per-section token counts.

**Usage Example:**
```python
from pathlib import Path

prompt = build_system_prompt(Path("data/context"))
```

---

## Module: `memory`

### `class ConversationLogger`

Manages conversation history and persistence.

**Constructor:**

#### `__init__(conversations_dir: Path)`

**Parameters:**
- `conversations_dir` - Directory for saving conversation JSON files

**Methods:**

#### `add_message(role: str, content: str, **metadata) -> None`

Add message to current session.

**Parameters:**
- `role` - "user" or "assistant"
- `content` - Message content
- `**metadata` - Optional: `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `agent_name` (str, tags assistant messages with the originating agent)

#### `get_messages_for_api() -> list[dict]`

Get message history formatted for LLM API.

**Returns:**
- `list[dict]` - Messages with "role" and "content"

#### `save() -> None`

Save conversation to timestamped JSON file.

**File Format:**
- `YYYY/YYYY-MM-DD_HH-MM-SS.json` (organized by year subdirectory)

**Usage Example:**
```python
logger = ConversationLogger(Path("data/conversations"))
logger.add_message("user", "Hello!")
logger.add_message("assistant", "Hi there!", total_tokens=50, cost_usd=0.001)
logger.save()  # Saves to file
```

---

## Module: `importers.chatgpt`

### Functions

#### `linearize_message_tree(mapping: dict, current_node: str) -> list[dict]`

Walk from `current_node` to root via parent pointers, return messages in chronological order. Skips null messages. Detects cycles.

#### `convert_content_parts(content: dict) -> list[dict]`

Convert a ChatGPT message content dict to Jarvis content blocks. Handles `text`, `multimodal_text`, `code`, `thoughts`, `execution_output`, `tether_browsing_display`, `tether_quote`, `reasoning_recap`, `system_error`, `user_editable_context`, `app_pairing_content`, and unknown types.

#### `convert_conversation(chatgpt_conv: dict) -> dict`

Convert a single ChatGPT conversation to Jarvis schema v1.0.0.

#### `import_conversations(source_path, target_dir, *, dry_run, date_from, date_to, model_filter, include_archived) -> ImportSummary`

Orchestrate bulk import with filters. Writes to `data/conversations/YYYY/` subdirectories. Idempotent — skips already-imported conversations by `chatgpt_id`.

### `class ImportSummary`

Dataclass with import results: `total`, `imported`, `updated`, `skipped_existing`, `skipped_archived`, `skipped_filter`, `errors`, `error_details`.

---

## Module: `importers.claude`

### Functions

#### `convert_content_blocks(blocks, attachments, files) -> list[dict]`

Convert Claude content blocks to Jarvis content blocks. Handles: text, thinking, tool_use, tool_result, token_budget. Also converts attachments and assistant-generated files.

#### `convert_conversation(claude_conv: dict) -> dict`

Convert a single Claude conversation to Jarvis schema v1.0.0.

#### `update_conversation(existing_path, claude_conv, *, dry_run=False) -> bool`

Incrementally sync an existing JARVIS conversation with new data from Claude. Syncs title, session_end, and appends new messages. Never removes existing messages (additive-only). Returns `True` if changes were made.

#### `import_conversations(source_path, target_dir, *, dry_run, date_from, date_to) -> ImportSummary`

Orchestrate bulk import with date filters. Writes to `data/conversations/YYYY/` subdirectories. For existing conversations, calls `update_conversation` instead of skipping. New conversations are converted and written. Idempotent — unchanged conversations are skipped.

### `class ImportSummary`

Dataclass with import results: `total`, `imported`, `updated`, `skipped_existing`, `skipped_archived`, `skipped_filter`, `errors`, `error_details`.

---

## Module: `pricing`

### `class ModelPricing`

Dataclass storing model pricing information.

**Attributes:**
- `prompt_cost: float` - Cost per input token (USD)
- `completion_cost: float` - Cost per output token (USD)
- `model_id: str` - Model identifier
- `cache_read_cost: float | None` - Cost per cache-read token (None = derive from prompt_cost)
- `cache_write_cost: float | None` - Cost per cache-write token (None = derive from prompt_cost)

**Methods:**

#### `calculate_cost(prompt_tokens: int, completion_tokens: int, cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float`

Calculate total cost in USD for a request, accounting for cached tokens. When cache costs are not set explicitly, defaults to Anthropic rates (read = 0.1x prompt, write = 1.25x prompt).

---

### Functions

#### `fetch_all_pricing() -> dict[str, ModelPricing]`

Fetch pricing for all models from OpenRouter (cached).

**Returns:**
- `dict` - Map of model_id to ModelPricing

---

#### `get_model_pricing(model_id: str) -> ModelPricing | None`

Get pricing for specific model.

**Parameters:**
- `model_id` - Model identifier (with or without "openrouter/" prefix)

**Returns:**
- `ModelPricing` or `None` if not found

---

#### `calculate_cost_from_litellm(response) -> float`

Calculate cost using LiteLLM's built-in pricing (fallback).

**Parameters:**
- `response` - LiteLLM response object

**Returns:**
- `float` - Cost in USD

---

#### `format_cost(cost_usd: float) -> str`

Format cost for display with appropriate precision.

**Examples:**
- `0.000042` → `"$0.000042"`
- `0.0123` → `"$0.0123"`
- `1.50` → `"$1.50"`

---

## Module: `integrations.obsidian.vault` — Filesystem Access Control

### `class AccessLevel(Enum)`

Access level for a filesystem path.

**Values:**
- `deny` — No access
- `read` — Read-only access
- `write` — Read and write access

---

### `class AccessRule`

Dataclass pairing a path with an access level.

**Attributes:**
- `path: Path` — Absolute resolved path
- `level: AccessLevel` — Access level for this path and its descendants

---

### `class FilesystemGuard`

Per-path access control with most-specific-path-wins resolution.

**Constructor:**

#### `__init__(rules: list[AccessRule])`

**Parameters:**
- `rules` — Access rules ordered by specificity (ordering is handled internally)

**Methods:**

#### `check_read(path: Path) -> bool`

Return `True` if the path has at least `read` access.

#### `check_write(path: Path) -> bool`

Return `True` if the path has `write` access.

---

### `load_filesystem_guard(config: dict) -> FilesystemGuard`

Factory that builds a `FilesystemGuard` from YAML config.

**Parameters:**
- `config` — Dict with `filesystem_rules` list (each entry has `path` and `access` keys)

**Returns:**
- `FilesystemGuard` instance

---

### Updated `VaultConfig`

The `allowed_dirs: list[Path]` field has been replaced by `filesystem_guard: FilesystemGuard`. All vault I/O methods delegate access checks to the guard.

---

## Module: `agents.base` — Agent Framework

### `class DataDrivenAgent`

Subclass of `BaseAgent` for agents defined entirely via `meta.yaml` + `prompts/system.md`. No per-agent Python code is required. Instantiation is handled by `agent_from_meta()`; you normally don't call the constructor directly.

**Constructor (inherited from `BaseAgent`):**

#### `__init__(config: AgentConfig, llm_client: LLMClient)`

**Parameters:**
- `config: AgentConfig` — Agent configuration (name, model, temperature, max_tokens, max_iterations, tools)
- `llm_client: LLMClient` — Shared LLM client for API calls

**Methods:**

#### `process_message(message: str, context: dict | None = None) -> StreamingResponse`

Append the user message to conversation history and return a streamed response from the LLM. Tool execution happens in the agentic loop driven by `StreamHandler` (see `run()`).

---

### `agent_from_meta(meta_path, llm_client, model, extra_tools=None, skill_registry=None, card_search_tool=None, skill_names_override=None, prompt_includes_override=None) -> DataDrivenAgent`

Factory function that builds an agent instance from a `meta.yaml` file.

**Parameters:**
- `meta_path: Path` — Path to the agent's `meta.yaml` file
- `llm_client: LLMClient` — Shared LLM client instance
- `model: str` — Model ID to use for this agent
- `extra_tools: list[ToolDefinition] | None` — Additional tools (e.g. shared vault read tools)
- `skill_registry: dict | None` — Skill registry for resolving bound skills
- `card_search_tool: ToolDefinition | None` — Card search tool for deck-skills
- `skill_names_override: list[str] | None` — If set, replaces the `skills:` list from `meta.yaml`
- `prompt_includes_override: dict[str, str] | None` — Per-placeholder overrides applied before normal expansion

**Returns:**
- `DataDrivenAgent` — A fully configured agent instance

**Behavior:**
1. Reads `meta.yaml` for agent configuration
2. Loads `prompts/system.md` from the same directory
3. Resolves `prompt_includes` placeholders (if declared)
4. Resolves bound skills (if declared)
5. Builds an `AgentConfig` with specified temperature, max_tokens, max_iterations
6. Returns a configured agent instance ready for `process_message()`

---

### `class AgentMeta`

Dataclass describing a discovered agent for registry purposes.

**Attributes:**
- `name: str` — Agent name (e.g., `"simplifier"`)
- `description: str` — Human-readable description
- `command: str` — Slash command (e.g., `"/simplify"`)
- `meta_path: Path | None` — Path to `meta.yaml` file
- `vault_writing: str | None` — Config section key for scoped vault write tools
- `tool_groups: tuple[str, ...]` — Named tool groups from CLI registry
- `skills: tuple[str, ...]` — Skill names to bind into the agent

---

### `meta.yaml` Schema

All delegate agents are configured via a `meta.yaml` file in their directory:

```yaml
name: agent-name           # required — agent identifier
description: What it does   # required — shown in help/registry
command: /agent-name        # required — slash command to invoke
temperature: 0.7            # optional, default 0.7
max_tokens: 4096            # optional (default: provider decides)
max_iterations: 20          # optional — for multi-step agentic loops
vault_writing: slip_box     # optional — scoped vault write config section
skills:                     # optional — skill names to bind
  - my-skill
tools:                      # optional — named tool groups from CLI registry
  - blog_tools
  - dev_tools
prompt_includes:            # optional — placeholder → filename mapping
  voice_profile: voice-profile  # loads prompts/voice-profile.md
```

The system prompt is loaded from `prompts/system.md` in the same directory as `meta.yaml`.

---

## Configuration

### `config/default.yaml`

**Structure:**
```yaml
models:
  default: "openrouter/anthropic/claude-sonnet-4.6"
  presets:
    fast: "openrouter/google/gemini-2.5-flash"
    quality: "openrouter/anthropic/claude-opus-4.6"
    balanced: "openrouter/anthropic/claude-sonnet-4.6"

paths:
  context_dir: "data/context"
  conversations_dir: "data/conversations"
```

Model IDs use full LiteLLM-routable format with provider prefix. API keys are read from environment variables (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, etc.).

---

## Module: `settings` — Typed Configuration

Typed `pydantic-settings` model covering all 16 top-level YAML sections. Replaces the legacy `dict[str, Any]` config (see ADR-032).

### `class Settings(BaseSettings)`

Top-level model holding every section. Each section is a separate `BaseSettings` subclass (`ModelsSettings`, `PathsSettings`, `Things3Settings`, `ObsidianSettings`, `EvaluationSettings`, `RagSettings`, `RoutingSettings`, `SummarizationSettings`, `MCPSettings`, `FilesystemSettings`, `CLISettings`, `OutcomesSettings`, `DeveloperSettings`, `CortexSettings`, `ReadwiseSettings`, `PatternCardsSettings`). Every field carries `Field(description=...)` so the JSON schema doubles as docs for the GUI.

### `load_config(project_root: Path | None = None) -> Settings`

Reads `config/default.yaml`, deep-merges `config/local.yaml`, and validates the result through `Settings`. Raises pydantic `ValidationError` on schema mismatch. Auto-resolves the project root if not passed.

### `diff_from_defaults(settings: Settings) -> dict[str, Any]`

Pure helper that produces the minimal dict which, deep-merged onto `Settings()` defaults, reproduces the given `Settings`. Used by the GUI's `PUT /api/settings` to write a clean overlay to `config/local.yaml`.

- Lists replace wholesale (matches `deep_merge` semantics).
- Dict-keyed sections like `mcp.servers` preserve user entries wholesale.
- Resetting a field to its default drops the key from the diff.

### `dereferenced_schema() -> dict[str, Any]`

Inlines every `$ref` in `Settings.model_json_schema()` by recursive walk. The Settings GUI consumes this so it doesn't need a JSON-Schema resolver.

### `classify_changes(current: dict, new: dict) -> tuple[list[str], list[str]]`

Diffs two `Settings.model_dump()` shapes and splits changed leaf paths into `(hot_applied_fields, restart_required_fields)` based on the `HOT_APPLY_PATHS` whitelist.

### `HOT_APPLY_PATHS: frozenset[str]`

Curated set of dotted prefixes that are truly hot — re-read per turn off `session.components.settings`. Currently `{"summarization", "paths.prompt_history_dir"}`. Additions require a comment trail verifying the field isn't captured into a closure at `build_session()` time.

### `read_yaml_layers(*paths: Path) -> list[dict]` / `deep_merge(base: dict, override: dict) -> dict`

YAML layer loader + recursive dict merge. Lists replace wholesale; dicts merge key-by-key.

---

## Module: `frontmatter` — YAML Frontmatter Utilities

### `parse(text: str) -> tuple[dict, str]`

Parse YAML frontmatter from a markdown string. Returns `(metadata, body)`. Tolerates missing or empty frontmatter (returns `({}, text)`).

### `dump(metadata: dict, body: str) -> str`

Serialise metadata + body into frontmatter markdown. Preserves key order from the input dict.

### `write_atomic(path: Path, content: str) -> None`

Write `content` to `path` atomically: writes to a sibling tmp file, then `os.replace`s. A mid-write disk failure leaves the previous file intact.

---

## Module: `date_utils` — Relative Date Parsing

### `parse_relative_date(s: str, *, now: datetime | None = None) -> date`

Parse a flexible date string into an absolute `date`. Accepts:

- ISO dates: `"2026-04-25"`
- Relative units: `"1 day"`, `"3 weeks"`, `"2 months"` (30-day), `"1 year"` (365-day)
- Keywords: `"tomorrow"`, `"next week"` (+7d), `"next month"` (+30d)

Used by `track_recommendation` to convert user-supplied `revisit_at` strings into stored ISO dates.

---

## Module: `daily_summary` — Daily-Summary Request Builder

Shared by CLI's `handle_daily_summary` and the GUI bridge's `_run_daily_summary_turn`.

### `class DailySummaryRequest`

Dataclass describing a parsed `/daily-summary` invocation: `target_date: date`, `daily_note_path: Path`, `existing_content: str`, optional `prefix_text: str`.

### `class DailySummaryFailure`

Dataclass describing a parse/build failure: `message: str`, optional `category: str` (e.g. `"invalid_date"`, `"vault_unreachable"`).

### `parse_daily_summary_command(text: str) -> tuple[date | None, str | None]`

Parse a `/daily-summary [YYYY-MM-DD]` slash command. Returns `(date, error_message)` — exactly one is non-None.

### `build_daily_summary_request(target_date: date, settings: Settings, *, vault_root: Path) -> DailySummaryRequest | DailySummaryFailure`

Compose the request payload: resolves the daily-note path via `obsidian.daily_notes.path_format`, reads existing content, and packages prefix text. Pure — no display, no LLM call.

---

## Module: `benchmark_costs`

### `class BenchmarkCostEstimate`

Estimated costs for running the golden suite on a model.

**Attributes:**
- `model_id: str` - Model identifier
- `response_cost_usd: float` - Estimated response generation cost
- `judge_cost_usd: float` - Estimated judge evaluation cost
- `total_cost_usd: float` - Combined estimate

---

### `estimate_benchmark_costs(models, judge_model, results_dir, run_id=None)`

Estimate costs for a benchmark run using LiteLLM pricing data and the latest golden test token baseline.

**Parameters:**
- `models` - Model IDs to evaluate
- `judge_model` - Model ID for the judge
- `results_dir` - Golden results directory (default: `tests/golden/results`)
- `run_id` - Optional baseline run ID

**Returns:**
- Tuple of `(estimates_by_model, token_baseline)`

---

## Module: `integrations.cortex.client` — Cortex Semantic Search

### `class CortexClient`

Synchronous HTTP client for the Cortex semantic search API.

**Constructor:**

#### `__init__(base_url: str = "http://127.0.0.1:8100", timeout: float = 10.0)`

**Parameters:**
- `base_url` - Cortex service URL
- `timeout` - Read timeout in seconds (connect timeout is fixed at 3s)

**Methods:**

#### `search(query: str, n_results: int = 5, path_prefix: str | None = None) -> dict | None`

POST `/search`. Returns response dict or `None` on any failure (connection, timeout, HTTP error, malformed JSON).

**Parameters:**
- `query` - Natural language search query
- `n_results` - Number of results to return
- `path_prefix` - Optional path filter (e.g. `"Projects/"`)

#### `is_available() -> bool`

GET `/status`. Returns `True` if Cortex responds with HTTP 200.

#### `close() -> None`

Close the underlying httpx connection pool.

---

### `make_cortex_search_tool(client: CortexClient) -> ToolDefinition`

Factory that wraps a `CortexClient` in a `search_vault_semantic` tool.

**Behavior:**
- Clamps `n_results` to 1–20
- Truncates output to 6,000 characters
- Returns fallback message (suggesting `search_notes`) when Cortex is unreachable

---

## Environment Variables

### `.env` File

At least one provider key is required. All are loaded automatically by `collect_api_keys()`:

- `OPENROUTER_API_KEY` - OpenRouter API key (default provider)
- `ANTHROPIC_API_KEY` - Direct Anthropic access
- `OPENAI_API_KEY` - Direct OpenAI access
- `GOOGLE_API_KEY` - Direct Google access

**Loading:**
```python
from packages.core.model_resolver import collect_api_keys
api_keys = collect_api_keys()  # {"openrouter": "sk-...", "anthropic": "sk-ant-...", ...}
```

---

## Error Handling

### Current State

- HTTP errors: Raised by `requests` and `litellm`
- File errors: Python's built-in exceptions
- No custom exception hierarchy yet

### Future Additions

Will add custom exceptions for:
- `ProviderError` - LLM provider issues
- `ContextLoadError` - Context file problems
- `ConversationSaveError` - Persistence failures

---

## Type Hints

All modules use Python 3.13+ type hints:

```python
def chat_stream(
    self,
    messages: list[dict],
    model: str | None = None
) -> StreamingResponse:
    ...
```

**Benefits:**
- Static type checking with mypy (`strict=true` since 0.18.0)
- Better IDE autocomplete
- Self-documenting code

---

## GUI Server (`apps.gui.server`) — REST + WebSocket

The GUI binds to `127.0.0.1:8123` (no auth — never expose). All routes are mounted under `apps/gui/server/routes/`. The full WebSocket protocol is documented in [docs/engineering/gui.md](gui.md); the table below is a route index.

### REST routes

| Route | File | Description | Released |
|---|---|---|---|
| `GET /api/session` | `routes/api.py` | Session metadata: `file_id`, `conversation_path`, `models`, agent, totals | 0.17.0 |
| `GET /api/agents` | `routes/agents.py` | List all registered agents (JARVIS first, then alphabetical) | 0.17.0 / moved 0.19.0 |
| `GET /api/agents/{id}` | `routes/agents.py` | Agent detail: prompt path, tools, recent sessions, 14-day cost | 0.19.0 |
| `GET /api/agents/{id}/prompt` | `routes/agents.py` | Current `system.md` content + bytes + `editable` | 0.19.0 |
| `PUT /api/agents/{id}/prompt` | `routes/agents.py` | Body `{content, note?}`. Snapshot-on-save; 403 for JARVIS | 0.19.0 |
| `GET /api/agents/{id}/prompt/snapshots` | `routes/agents.py` | Newest-first snapshot list | 0.19.0 |
| `GET /api/agents/{id}/prompt/snapshots/{sid}` | `routes/agents.py` | One snapshot's content + metadata | 0.19.0 |
| `POST /api/agents/{id}/prompt/restore` | `routes/agents.py` | Body `{snapshot_id}`. Snapshots current then restores | 0.19.0 |
| `GET /api/agents/{id}/prompt/stats` | `routes/agents.py` | Char / line / token estimate + includes table | 0.19.0 |
| `GET /api/agents/{id}/prompt/resolved` | `routes/agents.py` | `{placeholder}`-expanded prompt (LLM-eye view) | 0.19.0 |
| `GET /api/agents/{id}/includes` | `routes/agent_includes.py` | One row per declared `prompt_include` with status badge | 0.20.0 |
| `GET /api/agents/{id}/includes/{placeholder}` | `routes/agent_includes.py` | Same shape + `content` | 0.20.0 |
| `PUT /api/agents/{id}/includes/{placeholder}` | `routes/agent_includes.py` | Body `{content, note?}`. 409 for `example` / `missing` | 0.20.0 |
| `POST /api/agents/{id}/includes/{placeholder}/promote` | `routes/agent_includes.py` | Forks an example into a new local include | 0.20.0 |
| `GET /api/agents/{id}/includes/{placeholder}/snapshots` | `routes/agent_includes.py` | Per-`(agent, placeholder)` snapshot list | 0.20.0 |
| `POST /api/agents/{id}/includes/{placeholder}/restore` | `routes/agent_includes.py` | Restores into the *currently-resolved* file | 0.20.0 |
| `GET /api/conversations` | `routes/conversations.py` | Filtered list: `q / agent / tool / date / sort / limit / offset` | 0.17.0 |
| `GET /api/conversations/facets` | `routes/conversations.py` | Unique agents + tools for filter chips | 0.17.0 |
| `GET /api/conversations/{id}` | `routes/conversations.py` | Full detail + preview | 0.17.0 |
| `DELETE /api/conversations/{id}` | `routes/conversations.py` | Hard-delete JSON file + index cache + ChromaDB chunks; 409 when id is the active session | unreleased |
| `GET /api/home` | `routes/home.py` | Composite Dashboard payload (greeting + tasks + cost-week + resume + recent + quick-start) | 0.17.0 |
| `GET /api/outcomes/pending` | `routes/outcomes.py` | Pending outcomes past their `revisit_at` date; `[]` when disabled | 0.19.0 |
| `POST /api/outcomes/{file_id}/review` | `routes/outcomes.py` | Body `{verdict, quality, note}`. 403 when disabled | 0.19.0 |
| `GET /api/settings` | `routes/settings.py` | `settings`, `defaults`, `overrides`, `local_yaml_has_managed_header` | 0.20.0 |
| `GET /api/settings/schema` | `routes/settings.py` | Fully-dereferenced JSON schema (no `$ref`) | 0.20.0 |
| `PUT /api/settings` | `routes/settings.py` | Atomic write to `local.yaml` + managed-header guard + hot-apply rebind | 0.20.0 |

### WebSocket

| Route | File | Description |
|---|---|---|
| `WS /ws/chat` | `routes/chat_ws.py` | Bidirectional chat protocol (`submit` / `approval_decision` / `cancel` from client; `chunk` / `tool_call` / `text` / `approval_pending` / `turn_finished` / etc. from server). Mirrored by `protocol.py` TypedDicts and `web/src/lib/types.ts` |

### Helpers

| Helper | Path | Purpose |
|---|---|---|
| `WebStreamHandler` | `server/streaming.py` | Subscribes to the typed `Event` bus; maps each event to a WS protocol dict over a bounded `janus.Queue` |
| `WebConfirmationHandler` | `server/confirmation.py` | Mirrors the `ConfirmationHandler` ABC; `present_diff` buffers, `get_confirmation` blocks the worker thread on a `threading.Event` resolved by the client's `approval_decision` |
| `Bridge` | `server/bridge.py` | Per-turn orchestration (`agent.run()` in `asyncio.to_thread`) |
| `GuiSession` | `server/state.py` | `SessionComponents` + per-turn handlers; rebound by `PUT /api/settings` for hot-applicable fields |
| `ConversationIndex` | `server/history/index.py` | Mtime-keyed in-memory index of `data/conversations/`; refresh runs in `asyncio.to_thread` |
| `prompt_history` | `server/agents/prompt_history.py` | Microsecond-resolution snapshot store with `index.json` sidecar; per-key `asyncio.Lock` |

---

*Last updated: 2026-04-29*
