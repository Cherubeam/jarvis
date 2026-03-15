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

### `build_system_prompt(context_dir: Path, prefix: str) -> str`

Assemble full system prompt from context files.

**Parameters:**
- `context_dir` - Directory containing context/*.md files
- `prefix` - System prompt prefix from config

**Returns:**
- `str` - Complete system prompt

**Context File Loading Order:**
1. `personal_context.md` - Personal background
2. `professional_context.md` - Professional background
3. `preferences.md` - Behavior guidelines
4. `current_focus.md` - Current priorities
5. `tasks.md` - Things 3 tasks (auto-generated)
6. `projects/*.md` - Project context (alphabetical)

**Usage Example:**
```python
from pathlib import Path

prompt = build_system_prompt(
    Path("data/context"),
    "You are a helpful assistant."
)
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
- `YYYY-MM-DD_HH-MM-SS_<model>.json`

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

Orchestrate bulk import with filters. Idempotent — skips already-imported conversations by `chatgpt_id`.

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

Orchestrate bulk import with date filters. For existing conversations, calls `update_conversation` instead of skipping. New conversations are converted and written. Idempotent — unchanged conversations are skipped.

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

**Methods:**

#### `calculate_cost(prompt_tokens: int, completion_tokens: int) -> float`

Calculate total cost in USD for a request.

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

Subclass of `BaseAgent` for agents defined entirely via `meta.yaml` + `prompts/system.md`. No per-agent Python code is required.

**Constructor:**

#### `__init__(name, system_prompt, config, tools=None, extra_tools=None)`

**Parameters:**
- `name: str` — Agent name (from `meta.yaml`)
- `system_prompt: str` — System prompt loaded from `prompts/system.md`
- `config: AgentConfig` — Agent configuration (model, temperature, max_tokens, tools)
- `tools: list[ToolDefinition] | None` — Agent-specific tools
- `extra_tools: list[ToolDefinition] | None` — Shared tools (conversation recall, vault read)

**Methods:**

#### `process_message(user_message, conversation_history, stream_handler) -> str`

Process a user message using the standard agent flow: build messages, stream response, return assistant text.

---

### `agent_from_meta(meta_path, llm_client, extra_tools=None) -> BaseAgent`

Factory function that builds an agent instance from a `meta.yaml` file.

**Parameters:**
- `meta_path: Path` — Path to the agent's `meta.yaml` file
- `llm_client: LLMClient` — Shared LLM client instance
- `extra_tools: list[ToolDefinition] | None` — Additional tools to provide

**Returns:**
- `BaseAgent` — A `DataDrivenAgent` instance (or custom class if `agent_class` is specified in the YAML)

**Behavior:**
1. Reads `meta.yaml` for agent configuration
2. Loads `prompts/system.md` from the same directory
3. Builds an `AgentConfig` with specified temperature, max_tokens
4. Returns a configured agent instance ready for `process_message()`

---

### `class AgentMeta`

Dataclass describing a discovered agent for registry purposes.

**Attributes:**
- `name: str` — Agent name (e.g., `"clarity"`)
- `description: str` — Human-readable description
- `command: str` — Slash command (e.g., `"/clarity"`)
- `agent_class: type | None` — Python class to instantiate, or `None` for data-driven agents
- `module_path: str` — Dotted module path (e.g., `"packages.agents.clarity"`)
- `meta_path: Path | None` — Path to `meta.yaml` file, or `None` for legacy agents

---

### `meta.yaml` Schema

Data-driven agents are configured via a `meta.yaml` file in their directory:

```yaml
name: agent-name           # required — agent identifier
description: What it does   # required — shown in help/registry
command: /agent-name        # required — slash command to invoke
temperature: 0.7            # optional, default 0.7
max_tokens: 4096            # optional, default 4096
agent_class: ClassName      # optional — for hybrid agents needing custom Python class
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
    fast: "openrouter/google/gemini-2.0-flash"
    quality: "openrouter/anthropic/claude-opus-4.6"
    balanced: "openrouter/anthropic/claude-sonnet-4.6"

paths:
  context_dir: "data/context"
  conversations_dir: "data/conversations"
```

Model IDs use full LiteLLM-routable format with provider prefix. API keys are read from environment variables (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, etc.).

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
- Static type checking with mypy
- Better IDE autocomplete
- Self-documenting code

---

*Last updated: 2026-03-12*
