# System Architecture

> Technical overview of Jarvis's design and implementation.

---

## Architecture Overview

Jarvis follows a modular, scalable architecture designed for multi-agent support and multiple interfaces:

```
┌────────────────────────────────────────────────────────────────┐
│                     User Interfaces                             │
├──────────────────────┬─────────────────────────────────────────┤
│     CLI (apps/cli)   │         Web UI (apps/web) [Phase 3]     │
└──────────────────────┴─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────┐
│                      Shared Packages                            │
├─────────────────┬──────────────────┬───────────────────────────┤
│  packages/core  │  packages/agents │  packages/integrations    │
│                 │                  │                           │
│  • LLM Client   │  • Base Agent    │  • Things 3               │
│  • Context      │  • JARVIS Agent  │  • (Future: Calendar)     │
│  • Memory       │  • (Future:      │  • (Future: Email)        │
│  • Pricing      │    Research,     │                           │
│  • Benchmarks   │    Coding)       │                           │
│                 │    Coding)       │                           │
├─────────────────┴──────────────────┴───────────────────────────┤
│                    packages/telemetry                           │
│  • Metrics tracking (TTFT, latency)                            │
│  • Evaluation framework                                         │
└────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────┐
│                      Data Layer (data/)                         │
│                                                                 │
│  • data/context/*.md        User's personal context             │
│  • data/conversations/      Session logs (JSON)                 │
│  • .cache/jarvis/           Task sync cache                     │
└─────────────────────────────────────────────────────────────────┘
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
- Track response latency using MetricsTracker

**Key Functions:**
- `load_config()`: Load YAML config and environment variables
- `main()`: Main chat loop with metrics tracking

**Dependencies:**
- `packages.integrations.things3.task_sync`: Sync Things 3 tasks on startup
- `packages.core.context_builder`: Get system prompt
- `packages.core.llm_client`: Stream LLM responses
- `packages.core.memory`: Log conversations
- `packages.core.pricing`: Calculate costs
- `packages.telemetry.metrics`: Track TTFT and response latency

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
- `build_system_prompt(context_dir, prefix)`: Assemble full prompt

**Context Loading Order:**
1. `profile.md` - Who the user is
2. `preferences.md` - How to behave
3. `current_focus.md` - What's currently relevant
4. `tasks.md` - Current tasks from Things 3 (auto-generated)

**Design Principle**: Intentionally simple (no templating, no logic).

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
- `TokenUsage`: Dataclass for token counts
- `StreamingResponse`: Iterator wrapper with usage tracking
- `LLMClient`: Main client class

**Key Methods:**
- `chat_stream(messages, model)`: Stream a completion
- `_stream_response(messages, model)`: Internal generator

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

**File Format:**
```json
{
  "timestamp": "2026-01-14T10:30:00Z",
  "model": "anthropic/claude-sonnet-4.5",
  "messages": [
    {"role": "user", "content": "...", "timestamp": "..."},
    {
      "role": "assistant",
      "content": "...",
      "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cost_usd": 0.0045},
      "latency": {"ttft_ms": 250.0, "total_ms": 1500.0}
    }
  ],
  "metrics": {
    "total_tokens": 15000,
    "total_cost_usd": 0.045,
    "average_ttft_ms": 280.0,
    "average_latency_ms": 1650.0,
    "request_count": 10
  }
}
```

---

### 5. Task Sync (`packages/integrations/things3/task_sync.py`)

**Purpose**: Synchronize tasks from Things 3 to provide task context.

**Location**: `packages/integrations/things3/task_sync.py`

**Responsibilities:**
- Auto-detect Things 3 language (supports German, French, Spanish, Italian, English)
- Fetch tasks from Today, Anytime, and Upcoming lists via AppleScript
- Write tasks to `tasks.md` in markdown format
- Cache results to avoid repeated queries (5-minute TTL)
- Handle errors gracefully (CLI works without task sync)

**Key Classes:**
- `Task`: Dataclass for task representation
- `TaskSyncCache`: File-based cache with TTL
- `MCPThings3Client`: Preserved for Phase B (interactive features)

**Key Functions:**
- `detect_things3_language()`: Auto-detect localized list names
- `fetch_tasks_applescript_direct()`: Execute AppleScript to fetch tasks
- `fetch_tasks_async()`: Orchestrate fetching with caching
- `write_tasks_to_markdown()`: Format and write tasks.md

**Design Decision**:
- **Phase A** (Current): Direct AppleScript for read-only sync
- **Phase B** (Future): MCP server integration for interactive management
- See ADR-008 for rationale

**Supported Languages:**
```python
{
    "en": {"inbox": "Inbox", "today": "Today", ...},
    "de": {"inbox": "Eingang", "today": "Heute", ...},
    "fr": {"inbox": "Boîte de réception", "today": "Aujourd'hui", ...},
    "es": {"inbox": "Bandeja de entrada", "today": "Hoy", ...},
    "it": {"inbox": "Casella in arrivo", "today": "Oggi", ...}
}
```

---

### 6. Pricing (`packages/core/pricing.py`)

**Purpose**: Track LLM costs across providers.

**Location**: `packages/core/pricing.py`

**Responsibilities:**
- Fetch pricing from OpenRouter API
- Calculate per-request costs
- Fallback to LiteLLM pricing if needed
- Format costs for display

**Key Functions:**
- `fetch_all_pricing()`: Get pricing map (cached)
- `get_model_pricing(model_id)`: Get specific model pricing
- `calculate_cost_from_litellm(response)`: Fallback cost calculation
- `format_cost(cost_usd)`: Human-readable formatting

**Related Module:**
- `packages/core/benchmark_costs.py`: Estimate benchmark costs from golden test baselines

**Pricing Strategy:**
1. **Primary**: OpenRouter API (upfront, accurate)
2. **Fallback**: LiteLLM internal pricing database
3. **Degraded**: Show token count only

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

### Startup Flow

```
1. Load config.yaml + .env
   ↓
2. Sync Things 3 tasks → tasks.md
   ↓
3. Build system prompt from context/*.md
   (includes auto-generated tasks.md)
   ↓
4. Initialize LLM client
   ↓
5. Fetch pricing data (async)
   ↓
6. Display startup info (model, pricing)
   ↓
7. Enter chat loop
```

---

## File Structure

```
jarvis/
├── apps/                           # Deployable applications
│   ├── cli/                        # CLI entry point
│   │   └── main.py                 # CLI application
│   └── web/                        # Web application (Phase 3)
│       ├── backend/                # FastAPI backend
│       └── frontend/               # React frontend
│
├── packages/                       # Shared libraries (reusable)
│   ├── core/                       # Core JARVIS functionality
│   │   ├── llm_client.py           # LLM API abstraction
│   │   ├── context_builder.py      # System prompt assembly
│   │   ├── memory.py               # Conversation logging
│   │   ├── pricing.py              # Cost tracking
│   │   └── benchmark_costs.py      # Benchmark cost estimation
│   ├── agents/                     # Agent implementations
│   │   ├── base.py                 # Base agent class
│   │   └── jarvis/                 # Main JARVIS orchestrator
│   │       └── agent.py
│   ├── integrations/               # External service integrations
│   │   └── things3/                # Things 3 task sync
│   │       └── task_sync.py        # ~520 lines
│   └── telemetry/                  # Metrics and monitoring
│       └── metrics.py              # TTFT, response metrics
│
├── data/                           # User data
│   ├── context/                    # Personal context (markdown)
│   │   ├── profile.md
│   │   ├── preferences.md
│   │   ├── current_focus.md
│   │   └── tasks.md                # Auto-generated from Things 3
│   ├── conversations/              # Session logs (gitignored)
│   │   └── YYYY-MM-DD_HH-MM-SS.json
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

**Phase A (Current):**
- Direct AppleScript - Things 3 task sync (no additional deps)

**Future:**
- `mcp` - Model Context Protocol SDK (Phase B: interactive task management)
- `chromadb` or `faiss` - Vector storage (Phase 4)
- `sentence-transformers` - Local embeddings (Phase 4)
- `textual` - TUI (Phase 7)

---

## Scalability Considerations

### Current Limitations (By Design)

- **Single user**: No multi-user support
- **Single machine**: No distributed architecture
- **Sequential requests**: No concurrency (CLI interface)
- **In-memory history**: Full conversation in context window

### When to Scale

**Not soon**, but if needed:

1. **> 10k conversations**: Add vector index (Phase 4)
2. **Multi-user**: Add authentication, per-user directories
3. **API mode**: FastAPI server wrapping components
4. **Distributed**: Not planned (personal tool)

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

### Current State (Phase 2 - In Progress)
- ✅ Comprehensive automated test suite
- ✅ 150 total tests (104 unit + 20 integration + 26 golden/evaluation)
- ✅ 97.5% code coverage on core modules
- ✅ Type hints for static analysis
- ✅ Fast test execution (< 2 seconds)

### Test Categories
- **Unit Tests**: Each module tested in isolation (mocked dependencies)
- **Integration Tests**: Full flow tests with real interactions
- **Golden Tests**: Conversation scenarios for quality evaluation

### Test Coverage
- `context_builder.py`: 100%
- `llm_client.py`: 98%
- `memory.py`: 100%
- `pricing.py`: 95%
- `task_sync.py`: 97%
- Overall: 97.5%

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

*Last updated: 2026-01-22*
