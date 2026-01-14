# System Architecture

> Technical overview of Jarvis's design and implementation.

---

## Architecture Overview

Jarvis follows a straightforward, layered architecture that prioritizes clarity and maintainability:

```
┌─────────────────────────────────────────────────────────────┐
│                        User (CLI)                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    CLI Layer (cli.py)                        │
│  • Input/output handling                                     │
│  • Session management                                        │
│  • Cost display                                              │
└─────────┬───────────────────────────┬────────────────────────┘
          │                           │
          ▼                           ▼
┌─────────────────────┐    ┌──────────────────────┐
│  Context Builder    │    │   LLM Client         │
│  (context_builder)  │    │   (llm_client)       │
│                     │    │                      │
│  • Load .md files   │    │  • LiteLLM wrapper   │
│  • Build prompts    │    │  • Streaming         │
│  • Assemble context │    │  • Token tracking    │
└─────────┬───────────┘    └──────────┬───────────┘
          │                           │
          └───────────┬───────────────┘
                      │
          ┌───────────▼───────────────┐
          │  Conversation Logger       │
          │  (memory.py)               │
          │                            │
          │  • Save to JSON            │
          │  • Track metadata          │
          │  • Session stats           │
          └────────────┬───────────────┘
                       │
          ┌────────────▼────────────┐
          │   Filesystem Storage     │
          │                          │
          │  • context/*.md          │
          │  • conversations/*.json  │
          └──────────────────────────┘
```

---

## Component Responsibilities

### 1. CLI Layer (`cli.py`)

**Purpose**: User interaction and session orchestration.

**Responsibilities:**
- Parse user input from stdin
- Display streamed responses
- Show token usage and costs
- Handle session lifecycle (start, interrupt, end)

**Key Functions:**
- `load_config()`: Load YAML config and environment variables
- `main()`: Main chat loop

**Dependencies:**
- `context_builder`: Get system prompt
- `llm_client`: Stream LLM responses
- `memory`: Log conversations
- `pricing`: Calculate costs

---

### 2. Context Builder (`context_builder.py`)

**Purpose**: Assemble system prompt from user context files.

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

**Design Principle**: Intentionally simple (no templating, no logic).

---

### 3. LLM Client (`llm_client.py`)

**Purpose**: Abstract LLM API calls with provider flexibility.

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

### 4. Conversation Logger (`memory.py`)

**Purpose**: Persist conversation history to disk.

**Responsibilities:**
- Accumulate messages during session
- Track session metadata (tokens, cost, model)
- Save to timestamped JSON files
- Return message history for API calls

**Key Class:**
- `ConversationLogger`

**Key Methods:**
- `add_message(role, content, ...)`: Add message to log
- `get_messages_for_api()`: Format messages for LLM API
- `save()`: Write to JSON file

**File Format:**
```json
{
  "timestamp": "2026-01-14T10:30:00Z",
  "model": "anthropic/claude-sonnet-4.5",
  "messages": [
    {"role": "user", "content": "...", "timestamp": "..."},
    {"role": "assistant", "content": "...", "tokens": {...}}
  ],
  "session_stats": {
    "total_requests": 10,
    "total_tokens": 15000,
    "total_cost_usd": 0.045
  }
}
```

---

### 5. Pricing (`pricing.py`)

**Purpose**: Track LLM costs across providers.

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
2. Build system prompt from context/*.md
   ↓
3. Initialize LLM client
   ↓
4. Fetch pricing data (async)
   ↓
5. Display startup info (model, pricing)
   ↓
6. Enter chat loop
```

---

## File Structure

```
jarvis/
├── config.yaml                     # Configuration
├── .env                            # API keys (gitignored)
├── personal-context/
│   ├── context/                    # User context (version controlled)
│   │   ├── profile.md
│   │   ├── preferences.md
│   │   └── current_focus.md
│   ├── memory/
│   │   ├── conversations/          # Session logs (gitignored)
│   │   │   └── YYYY-MM-DD_HH-MM-SS_model.json
│   │   └── learned_facts.md        # (Future) Extracted facts
│   └── src/
│       ├── cli.py                  # Main entry point
│       ├── context_builder.py      # System prompt assembly
│       ├── llm_client.py           # LLM API abstraction
│       ├── memory.py               # Conversation logging
│       └── pricing.py              # Cost tracking
└── docs/                           # Documentation
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

**Future:**
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

### Current State (Phase 1)
- ✅ Manual testing
- ✅ Type hints for static analysis
- 🔴 No automated tests yet

### Planned (Phase 2-3)
- [ ] Golden test suite (5-10 cases)
- [ ] Unit tests for each module
- [ ] Integration tests for full flow
- [ ] Regression testing

### Test Coverage Goals
- Core logic: 80%+
- CLI: Manual + smoke tests
- API clients: Mocked

---

## Monitoring & Observability

### Current Logging

- Token usage per request ✅
- Cost per request ✅
- Session statistics ✅
- Conversation history ✅

### Missing (Planned)

- Latency tracking (TTFT)
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

*Last updated: 2026-01-14*
