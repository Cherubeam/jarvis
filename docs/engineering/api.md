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

#### `__init__(api_key: str, default_model: str, provider: str = "openrouter")`

**Parameters:**
- `api_key` - API key for the provider
- `default_model` - Model ID (provider format)
- `provider` - Provider name ("openrouter", "anthropic", "openai")

**Methods:**

#### `chat_stream(messages: list[dict], model: str | None = None) -> StreamingResponse`

Stream a chat completion.

**Parameters:**
- `messages` - List of message dicts with "role" and "content"
- `model` - Optional model override

**Returns:**
- `StreamingResponse` - Iterator yielding content chunks

**Usage Example:**
```python
client = LLMClient(api_key="sk-...", default_model="anthropic/claude-sonnet-4.5")
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
1. `profile.md` - User identity
2. `preferences.md` - Behavior guidelines
3. `current_focus.md` - Current priorities

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
- `**metadata` - Optional: `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`

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

Dataclass with import results: `total`, `imported`, `skipped_existing`, `skipped_archived`, `skipped_filter`, `errors`, `error_details`.

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

## Configuration

### `config/default.yaml`

**Structure:**
```yaml
openrouter:
  default_model: "anthropic/claude-sonnet-4.5"

system_prompt_prefix: |
  You are a helpful personal assistant.

paths:
  context_dir: "data/context"
  conversations_dir: "data/conversations"
```

**Loading:**
```python
import yaml
with open("config.yaml") as f:
    config = yaml.safe_load(f)
```

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

Estimate costs for a benchmark run using OpenRouter pricing and the latest golden test token baseline.

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

**Required:**
- `OPENROUTER_API_KEY` - OpenRouter API key

**Optional (future):**
- `ANTHROPIC_API_KEY` - Direct Anthropic access
- `OPENAI_API_KEY` - Direct OpenAI access

**Loading:**
```python
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")
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

*Last updated: 2026-01-22*
