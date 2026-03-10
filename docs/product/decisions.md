# Architecture Decision Records (ADRs)

> Documenting key technical decisions, their context, and tradeoffs.

---

## ADR-001: Use OpenRouter for Multi-Provider Access

**Date**: 2026-01-07
**Status**: ✅ Accepted

### Context

Need access to multiple LLM providers (Claude, GPT-4, Gemini, etc.) without implementing separate integrations for each. Want to avoid vendor lock-in at the API level.

### Decision

Use [OpenRouter](https://openrouter.ai/) as a unified API gateway to multiple LLM providers.

### Alternatives Considered

1. **Direct provider APIs** (Anthropic, OpenAI, Google)
   - ❌ Requires separate code for each provider
   - ❌ Different authentication mechanisms
   - ❌ Harder to switch providers

2. **LangChain**
   - ❌ Too heavy, complex abstractions
   - ❌ Frequent breaking changes
   - ❌ Over-engineered for our needs

3. **LiteLLM** (later adopted, see ADR-003)
   - ⚠️ Initially considered too abstract
   - ✅ Later adopted for better provider support

### Consequences

**Benefits:**
- ✅ Provider switching = single config change
- ✅ Access to 100+ models through one API
- ✅ No vendor lock-in
- ✅ Unified pricing API

**Drawbacks:**
- ⚠️ Additional dependency on OpenRouter service
- ⚠️ Slightly higher cost than direct provider APIs (~10-20% markup)
- ⚠️ Adds latency (proxy layer)

**Mitigation:**
- OpenRouter is reliable and well-maintained
- Can easily switch to direct APIs later if needed (via LiteLLM)

---

## ADR-002: Markdown for Context Files

**Date**: 2026-01-07
**Status**: ✅ Accepted

### Context

Need to store user context (profile, preferences, current focus) in a format that is:
- Human-readable and editable
- Version-controllable with git
- No proprietary lock-in
- Simple to implement

### Decision

Use markdown files for all user context storage:
- `personal_context.md` - Who the user is (personal background)
- `professional_context.md` - Professional background and skills
- `preferences.md` - How the assistant should behave
- `current_focus.md` - Current projects and priorities
- `projects/*.md` - Project-specific context

### Alternatives Considered

1. **JSON/YAML**
   - ✅ Machine-readable
   - ❌ Less pleasant for humans to edit
   - ❌ Harder to write long-form content

2. **Database (SQLite, PostgreSQL)**
   - ✅ Query capabilities
   - ❌ Not human-readable
   - ❌ Adds complexity
   - ❌ Lock-in to database format

3. **Plain text**
   - ✅ Simple
   - ❌ No structure
   - ❌ Harder to parse

### Consequences

**Benefits:**
- ✅ Git-friendly (diffable, versionable)
- ✅ Editable in any text editor
- ✅ No database lock-in
- ✅ Human-readable and writable
- ✅ Easy to backup and migrate

**Drawbacks:**
- ⚠️ No built-in query capabilities
- ⚠️ Manual parsing required
- ⚠️ No schema validation

**Mitigation:**
- At personal-use scale, file system is sufficient
- Can add structured extraction later if needed
- Simple string concatenation works fine

---

## ADR-003: Migrate to LiteLLM

**Date**: 2026-01-14
**Status**: ✅ Accepted

### Context

Initial implementation used raw HTTP requests (`requests` library) to OpenRouter. As we plan for future agentic capabilities, we need:
- Easy provider switching (OpenRouter → Anthropic → OpenAI)
- Function calling support for tool use
- Automatic retries and error handling
- Better cost tracking across providers

### Decision

Migrate from raw HTTP to [LiteLLM](https://github.com/BerriAI/litellm) wrapper.

### Code Impact

**Before** (112 lines, manual SSE parsing):
```python
response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers=headers, json=payload, stream=True
)
for line in response.iter_lines():
    # Manual SSE parsing...
```

**After** (117 lines, LiteLLM handles complexity):
```python
response = litellm.completion(
    model=model_to_use, messages=messages,
    stream=True, api_key=self.api_key
)
for chunk in response:
    # LiteLLM handles SSE parsing
```

### Alternatives Considered

1. **Keep raw HTTP**
   - ✅ Minimal dependencies
   - ✅ Full control
   - ❌ Manual implementation of function calling
   - ❌ Manual retry logic
   - ❌ Provider-specific quirks to handle

2. **OpenAI SDK**
   - ✅ Official SDK quality
   - ⚠️ Primarily designed for OpenAI
   - ❌ Less clean for multi-provider use
   - ❌ Heavier than LiteLLM

3. **LangChain**
   - ❌ Way too heavy for our needs
   - ❌ Complex abstractions
   - ❌ Frequent breaking changes

### Consequences

**Benefits:**
- ✅ Provider-agnostic interface
- ✅ Function calling support ready (for Phase 5)
- ✅ Built-in retries and fallbacks
- ✅ Cost tracking across providers
- ✅ Simpler streaming implementation
- ✅ Maintained by active community

**Drawbacks:**
- ⚠️ Additional dependency (~10MB, includes OpenAI SDK)
- ⚠️ Slight abstraction over raw API
- ⚠️ Need to stay up-to-date with LiteLLM changes

**Mitigation:**
- LiteLLM is well-maintained and widely used
- Can still access raw responses if needed
- Provider switching now takes 1 line of config

### Impact on Existing Code

- `llm_client.py`: Simplified from 112 → 117 lines (cleaner logic)
- `pricing.py`: Added LiteLLM cost calculation as fallback
- `cli.py`: No changes to user-facing behavior
- All functionality preserved, more flexible foundation

---

## ADR-004: JSON for Conversation Logs

**Date**: 2026-01-07
**Status**: ✅ Accepted

### Context

Need to store conversation history with:
- Messages (role, content, timestamp)
- Metadata (tokens, cost, model used)
- Programmatic access for future features (search, analysis)

### Decision

Use JSON format for conversation logs, one file per session:
- Filename: `YYYY-MM-DD_HH-MM-SS_<model>.json`
- Structured format with messages array + session metadata
- Human-readable but also machine-parseable

### Alternatives Considered

1. **Markdown**
   - ✅ Human-readable
   - ❌ Hard to parse programmatically
   - ❌ No structure for metadata

2. **SQLite database**
   - ✅ Query capabilities
   - ❌ Not human-readable
   - ❌ Adds complexity
   - ❌ Single point of failure

3. **CSV**
   - ✅ Simple
   - ❌ Hard to represent nested data
   - ❌ Poor for multi-turn conversations

### Consequences

**Benefits:**
- ✅ Structured enough for programmatic access
- ✅ Human-readable (can inspect in editor)
- ✅ One file per session = easy to manage
- ✅ Git-friendly with proper formatting
- ✅ Easy to export / migrate

**Drawbacks:**
- ⚠️ No built-in indexing for search
- ⚠️ Need to scan all files for global search
- ⚠️ Can grow large for long conversations

**Mitigation:**
- At personal scale, file count is manageable
- Can add indexing/database later if needed
- Compression available if file size becomes issue

---

## ADR-005: Start Without Database, Plan RAG Transition

**Date**: 2026-01-07 (Updated: 2026-01-14)
**Status**: ✅ Accepted (Evolving)

### Context

Personal assistant tool, single user, local machine. Initially simple needs, but recognized early that:
- Conversation history grows unbounded
- Putting all history in context window is expensive (token costs)
- Long context degrades model performance
- Need intelligent retrieval, not "dump everything"

### Decision

**Phase 1 (Current)**: Start with filesystem only
- Simple, gets product working
- No premature optimization
- Learn what retrieval patterns we actually need

**Phase 2 (Planned)**: Add RAG + Vector Store
- Embed conversation history locally
- Semantic search for relevant past context
- Hybrid approach: filesystem + vector index
- Keep human-readable files as source of truth

### Why Not Database From Day 1?

1. **Learn before optimizing**: Need to understand access patterns first
2. **Simplicity wins early**: Ship fast, iterate based on real usage
3. **Different problem**: Not CRUD operations, need semantic similarity
4. **RAG > Database**: Semantic search better than SQL for conversations

### Planned Architecture (Phase 2-4)

```
Filesystem (Source of Truth)
    ├── conversations/*.json         [Human-readable logs]
    ├── context/*.md                 [Human-editable context]
    └── learned_facts.md            [Extracted knowledge]
           ↓
    Vector Store (Index)
    ├── Conversation embeddings      [Semantic search]
    ├── Fast retrieval (<200ms)
    └── Local model (no API calls)
```

### Current Problems This Will Solve

1. **Token cost explosion**: Currently send entire conversation history every request
2. **Context window limits**: Models have 128-200k token limits
3. **Performance degradation**: Long context = slower, less accurate responses
4. **Relevant retrieval**: Need past context, not entire history

### When to Transition

Triggers for adding RAG (likely Phase 3-4):
- [ ] Conversation history > 50k tokens
- [ ] Token costs exceed $20/month
- [ ] Users report slow/irrelevant responses
- [ ] Need to reference conversations > 1 week old

### Alternatives Considered

1. **Traditional Database (PostgreSQL, SQLite)**
   - ✅ Good for structured queries
   - ❌ Poor for semantic similarity
   - ❌ No natural language search
   - ❌ Wrong tool for the problem

2. **Vector DB + pgvector**
   - ✅ Combines SQL + embeddings
   - ⚠️ More complex than needed
   - ⚠️ Still requires database setup

3. **Managed vector services (Pinecone, Weaviate)**
   - ❌ Violates local-first principle
   - ❌ Subscription costs
   - ❌ Data leaves user's machine

4. **Local vector store (ChromaDB, FAISS)**
   - ✅ Fully local, private
   - ✅ Purpose-built for embeddings
   - ✅ Easy Python integration
   - ✅ **Selected for Phase 4**

### Implementation Plan

**Phase 3: Preparation**
- Conversation search with simple text matching
- Understand what users actually search for
- Define retrieval success metrics

**Phase 4: RAG Implementation**
- Choose local embedding model (e.g., sentence-transformers)
- Implement ChromaDB or FAISS locally
- Embed historical conversations
- Semantic retrieval + hybrid search
- A/B test: full history vs. retrieved context

**Phase 5: Optimization**
- Intelligent chunking strategies
- Retrieval confidence scoring
- Dynamic context window management
- Cache embeddings, incremental updates

### Consequences

**Benefits:**
- ✅ Started simple, shipped fast
- ✅ Learned real usage patterns before optimization
- ✅ Filesystem remains human-readable source of truth
- ✅ Can add RAG incrementally without breaking changes
- ✅ No premature database complexity

**Current Limitations:**
- ⚠️ All conversation history in context (expensive)
- ⚠️ No semantic search yet
- ⚠️ Limited to model's context window
- ⚠️ Token costs will increase with usage

**Mitigation Plan:**
- Monitor token usage and costs (✅ implemented)
- Plan RAG transition before hitting limits
- Keep filesystem as authoritative source
- Vector index is just an optimization layer

### Related Decisions
- Complements: ADR-004 (JSON conversation logs)
- Enables: Future ADR on RAG implementation
- Relates to: Phase 4 roadmap (Semantic Search & RAG)

**Current Status**: Phase 1 complete, monitoring for transition triggers.

---

## ADR-006: Python 3.13+ as Minimum Version

**Date**: 2026-01-07
**Status**: ✅ Accepted

### Context

Need modern Python features and type system for clean code.

### Decision

Require Python 3.13+ for:
- Modern type hints (`list[dict]`, `str | None`)
- Pattern matching (future use)
- Performance improvements
- Latest async features

### Consequences

**Benefits:**
- ✅ Clean, modern syntax
- ✅ Better type checking
- ✅ Faster execution
- ✅ Latest standard library

**Drawbacks:**
- ⚠️ Some users may not have 3.13 yet
- ⚠️ Need to document installation

**Mitigation:**
- Python 3.13 is widely available (released Oct 2024)
- Installation instructions in README
- Target audience is technical users

---

## ADR-007: Local-First Architecture

**Date**: 2026-01-07
**Status**: ✅ Accepted

### Context

Core value: user data ownership and privacy.

### Decision

All data lives locally on user's machine:
- No cloud storage dependencies
- No external services except LLM APIs
- Fully functional offline (except LLM calls)
- User owns and controls all data

### Consequences

**Benefits:**
- ✅ Complete data ownership
- ✅ Privacy by default
- ✅ Works without internet (mostly)
- ✅ No subscription costs for storage
- ✅ Easy backup and migration

**Drawbacks:**
- ⚠️ No sync across devices (yet)
- ⚠️ User responsible for backups
- ⚠️ No collaborative features

**Future Considerations:**
- Optional end-to-end encrypted cloud sync
- But always local-first, cloud as backup

---

## ADR-008: Things 3 Integration via Direct AppleScript

**Date**: 2026-01-20
**Status**: ✅ Accepted

### Context

Jarvis needs access to the user's task list from Things 3 to provide context-aware assistance. The integration needs to:
- Automatically sync tasks on startup (Phase A: read-only context)
- Support localized Things 3 installations (German, French, Spanish, Italian, English)
- Lay groundwork for future interactive task management (Phase B: write operations)

Initial plan was to use [mcp-server-things3](https://github.com/jonagill/mcp-server-things3) directly. However, Things 3 localizes internal list names based on system language (e.g., "Inbox" → "Eingang" in German), and the MCP server uses hardcoded English list names, causing it to fail on non-English installations.

### Decision

**Phase A (Current)**: Use direct AppleScript with automatic language detection
- Implement `task_sync.py` module (~520 lines) with AppleScript interface
- Auto-detect Things 3 language by querying list names on first run
- Sync tasks to `data/context/tasks.md` on startup
- Cache results for 5 minutes to avoid repeated queries
- Preserve `MCPThings3Client` class structure for Phase B compatibility

**Phase B (Future - Phase 5)**: Migrate to mcp-server-things3 for interactive features
- Add, complete, update, and search tasks
- Wait for upstream MCP server to add localization support OR
- Implement localization wrapper on our side
- Use existing MCP infrastructure already planned

### Alternatives Considered

1. **Use mcp-server-things3 directly (Phase A)**
   - ✅ Clean MCP integration
   - ✅ Maintained upstream
   - ❌ **Fails on non-English systems** (hardcoded "Inbox", "Today", etc.)
   - ❌ Not suitable for read-only sync

2. **Build full MCP wrapper with localization**
   - ✅ Would work for all languages
   - ❌ Premature for Phase A (read-only)
   - ❌ Complex for simple task sync
   - ⚠️ Better suited for Phase B (interactive features)

3. **Use Things URL scheme**
   - ✅ Official supported interface
   - ❌ Limited to creating/showing tasks
   - ❌ Cannot read task data
   - ❌ Not suitable for context sync

4. **Direct AppleScript (chosen for Phase A)**
   - ✅ Works with all localized Things 3 installations
   - ✅ Can auto-detect language
   - ✅ Full read access to task database
   - ✅ Matches Phase A scope (read-only)
   - ⚠️ macOS-only (acceptable for personal tool)
   - ⚠️ Fragile if Things 3 changes AppleScript API

### Implementation Details

**Language Detection:**
```applescript
tell application "Things3"
    set listNames to name of every list
end tell
```
Maps detected names to canonical keys (inbox, today, anytime, upcoming, etc.)

**Task Fetching:**
```applescript
tell application "Things3"
    set todayTasks to to dos of list "Today"
    -- (or localized equivalent: "Heute", "Aujourd'hui", etc.)
end tell
```

**Supported Languages:**
- English: Inbox, Today, Anytime, Upcoming, Someday, Logbook
- German: Eingang, Heute, Irgendwann, Bevorstehend, Irgendwann, Logbuch
- French: Boîte de réception, Aujourd'hui, À un moment donné, À venir, Un jour, Journal
- Spanish: Bandeja de entrada, Hoy, En cualquier momento, Próximos, Algún día, Registro
- Italian: Casella in arrivo, Oggi, In qualsiasi momento, Prossimi, Un giorno, Registro

### Consequences

**Benefits:**
- ✅ Works on all localized Things 3 installations
- ✅ Automatic language detection (no user configuration)
- ✅ Simple, focused implementation for Phase A
- ✅ MCP architecture preserved for Phase B
- ✅ Clear separation: AppleScript for reads, MCP for writes
- ✅ Fast startup sync with caching

**Drawbacks:**
- ⚠️ macOS-only (by design - Things 3 is macOS/iOS only)
- ⚠️ Two different interfaces for read/write (Phase A/B)
- ⚠️ AppleScript fragility (could break with Things updates)
- ⚠️ Requires Things 3 running in background

**Mitigation:**
- AppleScript is official Things 3 API (stable)
- Error handling with graceful degradation (CLI works without Tasks)
- Can switch to MCP server for all operations in Phase B once localization solved
- Cache prevents performance impact from repeated queries

### Testing

Added comprehensive test coverage:
- 26 unit tests: Language detection, AppleScript generation, task parsing
- 8 integration tests: End-to-end task sync with mocked AppleScript
- Covers all 5 supported languages
- Tests cache behavior and error handling

### Future Migration (Phase B)

When implementing interactive task management:
1. **If MCP server adds localization**: Switch entirely to MCP
2. **If not**: Wrap MCP calls with language translation layer
3. Continue using direct AppleScript as fallback

### Related ADRs
- Complements: ADR-001 (provider flexibility philosophy)
- Relates to: Phase 5 roadmap (Agent Capabilities)

**Current Status**: Phase A implemented and tested. Phase B planned for Phase 5.

---

## ADR-009: Scalable Monorepo Structure

**Date**: 2026-01-22
**Status**: ✅ Accepted

### Context

The original project structure mixed user data with application code in `personal-context/`:

```
jarvis/
├── personal-context/          # Mixed: user data + source code
│   ├── context/               # User's personal data
│   ├── memory/                # User's conversations
│   └── src/                   # Application code (confusing location)
├── tests/
└── docs/
```

Problems with this structure:
1. **Code/data mixing**: Personal data (`context/`, `memory/`) mixed with application code (`src/`)
2. **No multi-agent support**: No clear structure for adding new agents
3. **No web interface support**: No separation for backend/frontend
4. **Deployment complexity**: Hard to share code without sharing personal data
5. **Scaling concerns**: As features grow (RAG, telemetry, integrations), flat structure becomes unmanageable

### Decision

Adopt a scalable monorepo structure with clear separation of concerns:

```
jarvis/
├── apps/                       # Deployable applications
│   ├── cli/                    # CLI entry point
│   └── web/                    # Web application (Phase 3)
│       ├── backend/            # FastAPI backend
│       └── frontend/           # React frontend
│
├── packages/                   # Shared libraries (reusable across apps)
│   ├── core/                   # Core functionality (LLM, context, memory, pricing)
│   ├── agents/                 # Agent implementations
│   │   ├── base.py             # Base agent class
│   │   └── jarvis/             # Main JARVIS agent
│   ├── integrations/           # External services (Things 3, future: calendar, email)
│   │   └── things3/
│   └── telemetry/              # Metrics, evaluation, monitoring
│
├── data/                       # User data (gitignored where appropriate)
│   ├── context/                # Personal context files
│   └── conversations/          # Session logs
│
├── config/                     # Configuration
│   ├── default.yaml            # Default configuration
│   └── local.yaml              # Local overrides (gitignored)
│
├── tests/                      # Test suite
├── docs/                       # Documentation
└── scripts/                    # Utility scripts
```

### Alternatives Considered

1. **Keep `personal-context/` structure**
   - ✅ No migration effort
   - ❌ Continues mixing code/data
   - ❌ Hard to add web interface
   - ❌ No clear agent structure
   - ❌ Doesn't scale

2. **Separate repositories (monorepo split)**
   - ✅ Complete isolation
   - ❌ Over-engineering for single-developer project
   - ❌ Harder to share code between CLI and web
   - ❌ Complex versioning across repos

3. **Flat structure with prefixes**
   - ✅ Simple
   - ❌ No logical grouping
   - ❌ Doesn't support nested modules (agents, integrations)
   - ❌ Import paths become verbose

4. **Monorepo with apps/packages/data (chosen)**
   - ✅ Clear separation of concerns
   - ✅ Multi-agent ready
   - ✅ Web interface ready
   - ✅ Reusable packages across apps
   - ✅ User data isolated and protectable
   - ✅ Follows industry best practices (Turborepo, Nx patterns)

### Implementation

**Migration steps executed:**
1. Created new directory structure
2. Moved `personal-context/src/*.py` → `packages/core/`
3. Moved `personal-context/src/cli.py` → `apps/cli/main.py`
4. Moved `personal-context/src/task_sync.py` → `packages/integrations/things3/`
5. Created `packages/agents/base.py` and `packages/agents/jarvis/agent.py`
6. Created `packages/telemetry/metrics.py` with MetricsTracker
7. Moved `personal-context/context/` → `data/context/`
8. Moved `personal-context/memory/` → `data/conversations/`
9. Updated all imports to use package paths
10. Updated `pyproject.toml` with new package structure
11. Updated tests with backward-compatible imports
12. Created `config/default.yaml` with updated paths

**Import pattern:**
```python
# New package-based imports
from packages.core.llm_client import LLMClient
from packages.core.context_builder import build_system_prompt
from packages.integrations.things3.task_sync import sync_tasks_to_file
from packages.agents.base import BaseAgent
```

**Backward compatibility:**
Tests use try/except pattern to support both old and new import paths during transition:
```python
try:
    from packages.core.llm_client import LLMClient
except ImportError:
    from llm_client import LLMClient
```

### Consequences

**Benefits:**
- ✅ Clear separation: code (`apps/`, `packages/`) vs data (`data/`) vs config (`config/`)
- ✅ Multi-agent ready: `packages/agents/` has clear structure for adding agents
- ✅ Web interface ready: `apps/web/` prepared for FastAPI backend + React frontend
- ✅ Reusable packages: `packages/core/` shared between CLI and web
- ✅ Integration home: `packages/integrations/` for Things 3, calendar, email, etc.
- ✅ Telemetry home: `packages/telemetry/` for metrics, evaluation, RAG
- ✅ Data protection: `data/` can be gitignored and backed up separately
- ✅ Industry standard: Follows monorepo patterns used by large-scale projects
- ✅ All 149 tests passing with updated imports

**Drawbacks:**
- ⚠️ Migration required (one-time effort)
- ⚠️ Longer import paths (`packages.core.llm_client` vs `llm_client`)
- ⚠️ Old `personal-context/` folder deprecated (can be removed after verification)

**Mitigation:**
- Migration completed with backward-compatible imports
- Old structure preserved temporarily for safety
- Clear documentation updated (AGENTS.md, architecture.md)
- Tests verify both old and new paths work

### Related ADRs
- Enables: Future ADR on multi-agent orchestration (Phase 5)
- Enables: Future ADR on web interface architecture (Phase 3)
- Relates to: ADR-007 (Local-first architecture - data still local)
- Relates to: ADR-002 (Markdown context files - preserved in data/context/)

**Current Status**: Migration complete. Old `personal-context/` folder can be removed after user verification.

---

## ADR-010: Future-Proof Conversation Schema (v1.0.0)

**Date**: 2026-02-06
**Status**: ✅ Accepted

### Context

The conversation JSON schema (`data/conversations/*.json`) had drifted through ~3 informal versions (no metrics, metrics without latency, metrics with latency) with no way to distinguish them. The schema lacked conversation identity, topic classification, model info, agent config, context snapshots, extensible metadata, and typed content blocks. Every new feature (topics, tool use, multi-modal, feedback, error tracking) would require a structural change.

### Decision

Redesign the conversation schema once with extensibility primitives so that no future feature ever requires a structural change:

1. **Schema versioning** (`schema_version: "1.0.0"`) — readers branch on major version; minor adds optional fields only
2. **Conversation identity** — unique `id` (`conv_{YYYYMMDD}_{HHMMSS}_{6hex}`), `title`, `topic`, `tags`
3. **Model configuration** — `model.id`, `model.provider`, `model.parameters` (open object)
4. **Agent / persona tracking** — `agent.name`, `agent.system_prompt_hash`, `agent.tools`
5. **Context snapshot** — `context.files_loaded` with hashes, `context.system_prompt_prefix`
6. **Environment info** — `environment.client`, `environment.platform`, `environment.python_version`
7. **Typed content blocks** — `content` as array of `{type, ...}` objects instead of plain strings. Supports `text`, `tool_use`, `tool_result`, `thinking`, `image`, `audio`, `file`, `code` — new types added without schema changes
8. **Message identity** — sequential `id` (`msg_001`), `parent_id` for branching, `status`, `error`, `stop_reason`
9. **Extended usage** — `cache_read_tokens`, `cache_write_tokens`, `thinking_tokens`, `cost_usd`
10. **`metadata: {}` at every level** — escape hatch for unforeseen data at conversation, metrics, message, and usage levels
11. **Session feedback** — nullable `feedback` with `overall_rating`, `helpful`, `notes`
12. **Read-time migration** — `migrate_conversation()` normalizes any old format to v1.0.0 when loaded; existing files never modified on disk

### Alternatives Considered

1. **Incremental patching of existing schema**
   - ✅ Smaller change
   - ❌ Continues drift without versioning
   - ❌ No extensibility story

2. **Database-backed storage (SQLite)**
   - ✅ Query capabilities
   - ❌ Violates local-first / human-readable principle
   - ❌ Much larger scope change

3. **One-time schema redesign with extensibility primitives (chosen)**
   - ✅ Future features require zero structural changes
   - ✅ Backward-compatible read-time migration
   - ✅ Preserves JSON / human-readable format

### Consequences

**Benefits:**
- ✅ Schema versioning prevents silent drift
- ✅ Typed content blocks support tool use, multi-modal, thinking without schema changes
- ✅ `metadata: {}` escape hatches at every level for unforeseen data
- ✅ Read-time migration means zero data loss, no batch conversion needed
- ✅ Conversation identity enables cross-system referencing
- ✅ Environment + model + agent info enables reproducibility

**Drawbacks:**
- ⚠️ Larger JSON files (more fields, even when null)
- ⚠️ Existing tools reading raw JSON need updating

**Mitigation:**
- Null fields compress well; file size increase is minimal
- `ConversationLogger.load()` provides migration-aware reading

### Impact

- `packages/core/memory.py`: Major rewrite — new schema, content blocks, migration
- `apps/cli/main.py`: Constructs model, agent, context, environment configs
- `tests/unit/test_memory.py`: Expanded from 15 to 52 tests
- `tests/integration/test_full_conversation_flow.py`: 2 new schema verification tests

### Related ADRs
- Supersedes: ADR-004 (JSON for Conversation Logs — format updated, decision still valid)
- Relates to: ADR-005 (Start Without Database — filesystem format improved)

**Current Status**: Implemented and tested.

---

## ADR-011: ChatGPT Import Strategy

**Date**: 2026-02-07
**Status**: ✅ Accepted

### Context

147 ChatGPT conversations (March 2023 - February 2026, 13.8 MB) need to be migrated to Jarvis to support vendor independence. Conversations are exported as a single `conversations.json` file using ChatGPT's data export feature. The export uses a tree-structured message mapping (supporting conversation branching in ChatGPT's UI) with various content types (text, multimodal, code, thoughts, browsing results, etc.).

### Decision

Implement a bulk import with CLI filters rather than a per-conversation selection UI:

1. **Reusable conversion module** (`packages/core/importers/chatgpt.py`) — pure conversion logic in an extensible `importers/` subpackage
2. **Thin CLI script** (`scripts/import_chatgpt.py`) — `--dry-run`, `--date-from/to`, `--model`, `--include-archived` filters
3. **Same target directory** (`data/conversations/`) — imported files interleave with native Jarvis conversations, distinguished by tags and metadata
4. **Deterministic IDs** — `conv_id` derived from SHA-256 of ChatGPT UUID, enabling idempotent re-imports
5. **Idempotent skip** — existing imports detected by `chatgpt_id` in metadata, not by filename

### Alternatives Considered

1. **Per-conversation selection UI**
   - ✅ Fine-grained control
   - ❌ Over-engineering for a one-time 147-conversation import
   - ❌ `data/conversations/` is gitignored, so deleting unwanted files is trivial

2. **Separate `data/imported/` directory**
   - ✅ Clear separation
   - ❌ Breaks existing glob/load patterns in `ConversationLogger`
   - ❌ Tags and metadata already distinguish origin

3. **Database-backed import tracking**
   - ✅ Efficient skip-existing checks
   - ❌ Adds database dependency for a one-time operation
   - ❌ Scanning existing JSON files is fast enough for <1000 conversations

### Consequences

**Benefits:**
- ✅ Vendor independence — conversations no longer locked in ChatGPT
- ✅ Extensible `importers/` subpackage for future providers (Claude, Gemini, etc.)
- ✅ Idempotent — safe to re-run without duplicates
- ✅ All content types preserved with metadata markers
- ✅ Imported files work with existing `ConversationLogger.load()`

**Drawbacks:**
- ⚠️ Images stored as `[Image not available]` placeholders (ChatGPT export doesn't include image data)
- ⚠️ No usage/cost data (ChatGPT export doesn't include token counts)
- ⚠️ Tree linearization loses branching information (only follows `current_node` path)

**Mitigation:**
- Image metadata preserved for potential future re-fetch
- Empty metrics clearly indicate imported conversations
- Primary conversation path is the most meaningful one

### Related ADRs
- Builds on: ADR-010 (Conversation Schema v1.0.0 — target format for imports)
- Relates to: ADR-004 (JSON for Conversation Logs — same format, same directory)
- Relates to: ADR-007 (Local-first — imported data stays local)

**Current Status**: Implemented and tested.

---

## ADR-012: Selective Context Loading via Frontmatter

**Date**: 2026-02-08
**Status**: ✅ Accepted

### Context

All context files (~11K tokens: ~6.5K core + ~4.5K projects) are loaded into every system prompt regardless of conversation topic. At 4 project files this is manageable (~5.5% of the 200K context window), but as projects grow to 10-20, blindly loading everything wastes tokens and money.

The question arose: should context files go into future conversation RAG infrastructure? Analysis showed context files and conversations need different strategies:

- **Context files**: Small volume (10-20 files), slow-changing, curated — RAG overhead (embedding, indexing, retrieval) adds complexity without proportional benefit
- **Conversations**: Large volume (hundreds → thousands), fast-changing, unstructured — good RAG candidate

### Decision

Use **annotated selective loading** via YAML frontmatter on project files instead of RAG:

```yaml
---
active: true
topics: [python, ai-engineering]
summary: "One-line project description"
---
```

- **`active`** (bool): Controls full content loading. Files without frontmatter default to `true`.
- **`topics`** (list[str]): Keywords for future topic-based auto-activation. Stored but not used yet.
- **`summary`** (str): One-line description shown in the project index.

Core identity files (personal, professional, preferences, current_focus, tasks) stay always-loaded — they're small and define who the user is.

**Project index**: A new section (~100 tokens) lists all projects so the LLM knows they exist, even when inactive projects are not fully loaded.

### Alternatives Considered

1. **RAG for context files**
   - ✅ Unified infrastructure with conversation RAG
   - ❌ Over-engineering for 10-20 small, curated files
   - ❌ Embedding/retrieval overhead without proportional benefit
   - ❌ Loses deterministic control over what's loaded

2. **Topic-based auto-activation** (keyword matching or embeddings)
   - ✅ Automatic, no manual toggling
   - ⚠️ More complex, potential for false positives/negatives
   - ⚠️ Deferred to future extension — `topics` field stored for this purpose

3. **Manual frontmatter toggle (chosen)**
   - ✅ Simple, predictable, zero-overhead
   - ✅ User controls exactly what's loaded
   - ✅ `topics` field enables future auto-activation without schema change
   - ⚠️ Requires manual toggle when switching between projects

### Consequences

**Benefits:**
- ✅ Token savings: inactive projects contribute ~100 tokens (summary) instead of ~1-4K tokens each
- ✅ Backwards compatible: files without frontmatter default to active
- ✅ No new dependencies (uses PyYAML already in dependency tree)
- ✅ Project index keeps LLM aware of all projects
- ✅ `topics` field provides extensibility for future auto-activation

**Drawbacks:**
- ⚠️ Manual toggle required (user must edit frontmatter)
- ⚠️ No automatic topic detection (deferred)

**Mitigation:**
- Manual toggling is rare (project relevance changes slowly)
- Future topic-based auto-activation can use stored `topics` field

### Impact

- `packages/core/context_builder.py`: Added `parse_frontmatter()`, modified `build_system_prompt()` for tiered loading + project index
- `apps/cli/main.py`: Context snapshot tracks `active` and `frontmatter` per project file
- `data/context/projects/*.md`: All 4 project files annotated with frontmatter
- `tests/unit/test_context_builder.py`: 19 new tests (8 frontmatter, 5 filtering, 6 project index)

### Related ADRs
- Extends: ADR-002 (Markdown for Context Files — adds optional frontmatter)
- Relates to: ADR-005 (Start Without Database — context files stay filesystem-based, RAG reserved for conversations)

**Current Status**: Implemented and tested. Future extension: topic-based auto-activation.

---

## ADR-013: Obsidian Vault Integration Architecture

**Date**: 2026-02-09
**Status**: ✅ Accepted

### Context

JARVIS needs to read from and write to an Obsidian vault for daily note summaries and future note management. Writes must be safe (diff + confirmation), the design must be GUI-ready, and vault access must be restricted to configured directories.

### Decision

Five focused modules under `packages/integrations/obsidian/`:
1. `vault.py` — Single enforcement point for all vault I/O with path validation
2. `callout.py` — Pure string operations for `> [!JARVIS]` callout blocks (no I/O)
3. `diff.py` — UI-agnostic diff computation using stdlib `difflib`
4. `writer.py` — Write orchestration with `ConfirmationHandler` ABC
5. `prompts.py` — On-demand prompt loading from `data/prompts/obsidian/`

GUI-readiness achieved through the `ConfirmationHandler` abstract base class. CLI implements `CLIConfirmationHandler`; future web/GUI would implement their own handler.

### Alternatives Considered

1. **Single monolithic module**
   - ✅ Simpler file structure
   - ❌ Mixes I/O, parsing, and UI concerns
   - ❌ Hard to test callout parsing in isolation

2. **Function-calling / tool-based approach**
   - ✅ Automatic invocation by LLM
   - ❌ JARVIS doesn't have function calling yet
   - ❌ Less explicit user control
   - ⚠️ Easy to convert later when function calling arrives

3. **Five focused modules (chosen)**
   - ✅ Clean separation: I/O, parsing, diffing, confirmation, prompts
   - ✅ Callout module is pure (no I/O), highly testable
   - ✅ GUI-ready via ConfirmationHandler ABC
   - ✅ No new dependencies (stdlib only)

### Consequences

**Benefits:**
- ✅ All vault I/O through single `vault.py` module with path validation
- ✅ Symlink/traversal attacks blocked by `Path.resolve()`
- ✅ Every write shows a diff and requires explicit confirmation
- ✅ GUI can swap in a different `ConfirmationHandler` without touching integration code
- ✅ 83 tests including security boundary tests

**Drawbacks:**
- ⚠️ Five modules for a focused feature (more files than a monolithic approach)
- ⚠️ `/daily-summary` requires manual command (no automatic triggers)

**Mitigation:**
- Module boundaries match responsibility boundaries, keeping each module small and testable
- Manual command is intentional: user controls when summaries are generated

### Impact

- `packages/integrations/obsidian/`: 5 new modules + `__init__.py`
- `data/prompts/obsidian/`: 2 prompt files (daily_note_entry.md, general_writing.md)
- `config/default.yaml`: New `obsidian` section (disabled by default)
- `apps/cli/main.py`: `/daily-summary` command handler (~30 lines)
- `tests/conftest.py`: 3 new fixtures (temp_vault, sample_vault_config, daily_note_with_callout)

### Related ADRs
- Follows pattern of: ADR-008 (Things 3 Integration — similar integration structure)
- Relates to: ADR-009 (Scalable Monorepo — new package under `packages/integrations/`)

---

## Template for Future ADRs

```markdown
## ADR-XXX: [Title]

**Date**: YYYY-MM-DD
**Status**: 🟡 Proposed | ✅ Accepted | ⚠️ Deprecated | 🔴 Superseded

### Context
What's the situation and problem?

### Decision
What are we doing?

### Alternatives Considered
1. Option A
   - ✅ Benefits
   - ❌ Drawbacks

2. Option B
   - ✅ Benefits
   - ❌ Drawbacks

### Consequences

**Benefits:**
- ✅ Positive impact 1
- ✅ Positive impact 2

**Drawbacks:**
- ⚠️ Risk/cost 1
- ❌ Significant drawback

**Mitigation:**
How we address the drawbacks.

### Related ADRs
- Supersedes: ADR-XXX
- Relates to: ADR-YYY
```

---

## ADR-014: Agent Framework — Convention-Based Discovery

**Date**: 2026-02-13
**Status**: Accepted

### Context

JARVIS had a `BaseAgent` ABC and `JarvisAgent` class, but neither was used — the CLI called `LLMClient` directly. To support specialized agents (Writing, Research, Clarity) with minimal friction, we needed to wire the agent layer into the CLI and establish conventions for adding new agents.

### Decision

Convention-based agent framework with filesystem discovery:

1. **Each agent** lives in `packages/agents/<name>/` with `agent.py`, `prompts/system.md`, and an `__init__.py` exporting `AGENT_META`.
2. **Registry** (`registry.py`) scans agent directories at startup, builds a command-to-agent lookup table.
3. **Routing**: Slash commands first (zero LLM overhead), LLM-based auto-routing deferred to Phase C.
4. **StreamHandler** extracted from `main.py` to `packages/core/stream_handler.py` — shared by all agents.
5. **History management**: `ConversationLogger` remains the source of truth; agents receive `messages_override` to avoid duplicate state.
6. **Standalone mode**: `--agent <name>` CLI flag bypasses JARVIS and runs a specialist directly.

### Alternatives Considered

1. **Config-based agent registration** (YAML listing)
   - Requires updating config every time an agent is added
   - More steps = more friction

2. **Decorator-based registration** (`@register_agent`)
   - Requires importing all agent modules at startup
   - Harder to reason about load order

3. **Plugin system** (entry points / setuptools)
   - Over-engineered for a single-repo project
   - Adds packaging complexity

### Consequences

**Benefits:**
- Adding an agent = drop a folder with `agent.py` + `prompts/system.md`, zero config changes
- Prompts live next to agent code (self-contained, portable)
- Slash commands work today with no LLM overhead
- Clean separation: StreamHandler shared, agents pluggable

**Drawbacks:**
- Filesystem scan on startup (negligible for < 20 agents)
- Agent prompts not in the centralized `data/prompts/` location

### Related ADRs
- Extends: ADR-009 (Scalable Monorepo Structure)

---

---

## ADR-015: Tool Calling — Non-Streaming Intermediate Calls + Streaming Final Answer

**Date**: 2026-02-27
**Status**: Accepted

### Context

JARVIS needed the ability to fetch and read web content (articles, docs, links) on demand. LiteLLM already supports function calling; the missing pieces were a tool execution layer and agentic loop wiring. The key design question: where to put the agentic loop and whether to use streaming for tool-calling turns.

### Decision

1. **Non-streaming for tool calls**: Intermediate LLM calls (those that produce `finish_reason == "tool_calls"`) use `LLMClient.complete()` (non-streaming). Only the final answer is streamed. This avoids complex delta-accumulation logic for detecting tool call boundaries in a stream.
2. **Agentic loop in `StreamHandler`**: The loop lives in `stream_handler.py` (`_run_agentic_loop()`) rather than in individual agents or the CLI. All agents get tool calling "for free" without changing their `run()` signature.
3. **`ToolRegistry` passed at call time**: Agents build a `ToolRegistry` in `__init__` from `AgentConfig.tools`; `BaseAgent.run()` passes it to `stream_handler.stream(tool_registry=...)`. No global registry.
4. **Errors returned as strings**: All tool failures (network, HTTP, exception) are returned as error strings inside tool result messages — never raised — so the LLM can reason about and report them gracefully.
5. **`httpx` + `trafilatura`** for web fetch: `trafilatura` extracts clean article text; raw HTML fallback used when extraction yields nothing. 50KB cap with truncation notice.
6. **Max 5 iterations** per agentic loop to prevent runaway tool call chains.

### Alternatives Considered

1. **Streaming tool call detection** (parse `delta.tool_calls` chunks)
   - More complex, error-prone across providers
   - No user-visible benefit (tool call turns are fast, not streamed to user anyway)

2. **CLI-level agentic loop** (in `main.py`)
   - Duplicated across CLI and `--agent` mode
   - Tool calling becomes CLI-specific, breaking agent reuse

3. **Global tool registry** (singleton)
   - Harder to test, implicit coupling
   - Per-agent registries allow different tool sets per agent

4. **Playwright for JS pages** (deferred)
   - Not needed for the immediate use case (articles, docs)
   - Added complexity; deferred to a future phase

### Consequences

**Benefits:**
- Backward compatible: `tool_registry=None` (default) → existing code path unchanged
- Clean separation: tool definition, execution, and looping are independent modules
- Agents declare tools declaratively in `AgentConfig.tools`; no imperative wiring
- All tool errors safe to show to the LLM and user

**Drawbacks:**
- Non-streaming intermediate calls add one round-trip latency per tool use
- `_intermediate_usage` on `StreamHandler` is instance state (not thread-safe for concurrent use)

### Related ADRs
- Extends: ADR-014 (Agent Framework)

---

---

## ADR-016: Agentic Loop — Eliminate Redundant "Stop Check" Call

**Date**: 2026-02-27
**Status**: Accepted

### Context

After shipping ADR-015's agentic loop, a cost investigation revealed that a tool-use turn was making **3 API calls** instead of the expected 2:

1. `complete()` → `finish_reason == "tool_calls"` → execute tool
2. `complete()` → `finish_reason == "stop"` ← **redundant: result immediately discarded**
3. `chat_stream()` → final answer (regenerates the same output as call #2)

Call #2 was also double-counting its usage: the response was appended to `_intermediate_usage`, and then `chat_stream()` counted the same input/output tokens again. For a typical Substack article fetch this produced ~23k reported tokens (~$0.09) instead of ~16k (~$0.05).

### Decision

Two minimal changes to `_run_agentic_loop()`:

1. **Move usage accumulation after the `finish_reason` check**: Only accumulate for `"tool_calls"` responses. When the model returns `"stop"`, its usage is covered by the subsequent `chat_stream()` call — don't add it to `_intermediate_usage` too.

2. **`break` immediately after tool execution**: After executing tool calls and appending results to messages, break out of the loop. This eliminates call #2 entirely; `chat_stream()` in `_stream_simple()` handles the final answer directly.

Corrected flow for a single tool-use turn:
```
complete([system, user], tools)    → "tool_calls" → accumulate ✓ → execute → break
chat_stream([..., tool_result])    → stream final answer → streaming_usage

Total = tool_calls_usage + streaming_usage  ← correct, no double-counting
```

### Alternatives Considered

1. **Skip the agentic loop for non-tool queries** (streaming tool call detection)
   - Would eliminate the `complete()` call entirely for queries that don't use tools
   - Requires parsing `delta.tool_calls` chunks — complex, deferred (noted as known remaining limitation)

2. **Return the "stop" content directly** (skip `chat_stream()` when `finish_reason == "stop"`)
   - Would save the streaming call but lose progressive rendering for users
   - The streaming UX is a core product requirement

### Consequences

**Benefits:**
- Eliminates one billable API call per tool-use turn (~33% reduction in call count)
- Fixes token double-counting — displayed usage now matches actual billing
- Simpler loop logic: no need for a second `complete()` just to detect "stop"

**Drawbacks:**
- Multi-step sequential tool use (tool → inspect result → call another tool) now requires the model to plan ahead and call multiple tools in a single turn. Acceptable for the current single-step `fetch_url` use case.

### Known Remaining Limitation

JARVIS always has a non-empty `ToolRegistry` (contains `FETCH_URL_TOOL`), so `_run_agentic_loop()` is always entered, making one `complete()` call even for queries that don't use URL fetching. After the fix, the "stop" call's usage is no longer double-counted, but the unnecessary call still happens (~$0.002 overhead per query). Fixing this properly requires streaming tool-call detection — deferred to a future phase.

### Related ADRs
- Fixes: ADR-015 (Tool Calling — Non-Streaming Intermediate Calls)

---

## ADR-016: Conversation Recall via ChromaDB + LiteLLM Embeddings (RAG)

**Date**: 2026-02-27
**Status**: ✅ Accepted

### Context

Jarvis stores every session as a JSON file in `data/conversations/` (153+ files). When the user asks "what did we discuss this week?" or "remind me what we decided about X", the assistant has no access to any prior session. All historical context is lost.

### Decision

Add a `recall_conversations` tool backed by **ChromaDB** (local persistent vector store) and **LiteLLM embeddings** (via the existing OpenRouter key) that plugs into the agentic loop introduced in ADR-015.

**Architecture:**

1. At startup, `ConversationIndexer` scans `data/conversations/*.json`, skips already-indexed conv_ids, embeds new message-pair chunks, and upserts them into ChromaDB's `"conversations"` collection.
2. At runtime, the LLM can call `recall_conversations(query, date_from?, date_to?)`. `ConversationSearcher` embeds the query, does a cosine similarity lookup in ChromaDB, and returns formatted snippets back to the LLM.

**Chunking strategy — message pairs:**

Each chunk is a consecutive user + assistant exchange:

```
User: <user turn text>
Assistant: <assistant turn text>
```

This preserves the full conversational context — the question and its answer together — which is more semantically meaningful than indexing individual messages.

**Key implementation details:**
- `chromadb>=0.6.0` in optional `[rag]` dependency group (not installed by default)
- Embedding model: `openrouter/openai/text-embedding-3-small` (cheap, fast, good quality)
- LiteLLM routes to OpenRouter using the existing `OPENROUTER_API_KEY`
- ChromaDB persisted at `data/rag/chroma/` (gitignored)
- `rag.enabled: false` in `default.yaml` — user opts in via `local.yaml`
- Startup indexing is incremental: already-indexed conv_ids are skipped

### Alternatives Considered

1. **Full-text keyword search (grep over JSON)**
   - ✅ Zero dependencies, works offline
   - ❌ No semantic understanding — misses synonyms, paraphrases
   - ❌ 'What did we talk about this week?' requires date-sorted grep, not semantic matching
   - ❌ Doesn't scale gracefully with 1,000+ conversations

2. **In-context window stuffing** (inject recent conversations into system prompt)
   - ✅ Simple, no new dependencies
   - ❌ Context window limits: even at 200K tokens, 153 full conversations don't fit
   - ❌ Noisy: injects irrelevant conversations alongside relevant ones
   - ❌ Quadratic cost growth as conversation count grows

3. **SQLite FTS (full-text search)**
   - ✅ Local, fast, no API calls for indexing
   - ❌ Keyword-only, no semantic search
   - ❌ Adds an FTS schema maintenance burden

4. **Local embeddings (sentence-transformers)**
   - ✅ Fully offline, no embedding API cost
   - ❌ Requires ~100-500MB model download
   - ❌ PyTorch dependency is heavy and platform-specific
   - ⚠️ Can be added later as a config option if offline use becomes a priority

### Consequences

**Benefits:**
- ✅ Semantic recall: 'what did we discuss about the digital twin?' finds relevant sessions even if exact words differ
- ✅ Incremental: startup overhead is proportional to *new* conversations only
- ✅ Optional: disabled by default; no impact on users who don't enable it
- ✅ Reuses existing OpenRouter API key — no new credentials
- ✅ `data/rag/chroma/` is gitignored — no accidental commit of indexed personal data

**Drawbacks:**
- ⚠️ Requires `uv add chromadb` and `rag.enabled: true` — not zero-config
- ⚠️ Embedding API calls cost money (text-embedding-3-small: ~$0.02/1M tokens — minimal for personal use)
- ⚠️ Embedding provider dependency: if OpenRouter changes its embeddings API, the model string needs updating

**Mitigation:**
- Opt-in design keeps the default path clean
- Local embedding support is a future option via config (`embedding_model: 'ollama/...'`)

### Related
- Extends: ADR-015 (Tool Calling — tools are the runtime hook for recall)
- Extends: ADR-003 (LiteLLM — reused for embedding() calls)

---

## ADR-017: Skills — SKILL.md-First, Vendor-Portable Design

**Date**: 2026-03-01
**Status**: Accepted

### Context

Phase 5A calls for task-specific skills (distinct from general-purpose agents). The initial plan mirrored the agent pattern: Python-class-centric modules with `SKILL_META` in `__init__.py`, a required `skill.py`, and a `prompt.md` for the prompt template. This would tightly couple skill definitions to the JARVIS Python runtime — you couldn't take a JARVIS skill and use it with Claude, ChatGPT, or hand it to a colleague.

Meanwhile, Claude's SKILL.md format proves that markdown-first, YAML-frontmatter-driven skill definitions work in production.

### Decision

Make SKILL.md the primary artifact, not Python code:

1. **SKILL.md is the portable capability spec.** YAML frontmatter has exactly two fields — `name` and `description` — matching Claude's specification. The markdown body serves as both documentation and system prompt.
2. **Filesystem-based discovery.** Registry scans `packages/skills/*/SKILL.md` instead of importing Python modules. No `__init__.py` or `SKILL_META` dict needed.
3. **Two modes.** Mode 1: SKILL.md only (zero Python, simple skills). Mode 2: SKILL.md + optional `skill.py` with `SKILL_CONFIG` dict for tools, model, temperature, command overrides.
4. **No JARVIS-specific frontmatter.** Execution config lives in `skill.py`, not frontmatter. This keeps SKILL.md vendor-neutral.
5. **Command derived from name.** `content-evaluator` → `/content-evaluator`. Override via `SKILL_CONFIG["command"]` if needed.

### Alternatives Considered

1. **Mirror agent pattern** (Python-import-based, `SKILL_META` dict)
   - ✅ Consistent with agent conventions
   - ❌ Not portable — useless outside JARVIS runtime
   - ❌ Requires Python code for every skill, even simple ones

2. **Extended frontmatter** (add `command`, `tools`, `version` to YAML)
   - ✅ All metadata in one place
   - ❌ Breaks compatibility with Claude's native SKILL.md format
   - ❌ Mixes capability spec with execution config

3. **JSON/YAML skill definitions** (structured config files)
   - ✅ Machine-parseable
   - ❌ Not human-readable as prompts
   - ❌ Not compatible with any existing LLM skill format

### Consequences

**Benefits:**
- Drop a SKILL.md into Claude's `.claude/skills/` — works without modification
- Paste the markdown body into ChatGPT Custom GPT instructions — works directly
- Adding a simple skill = create a folder with one markdown file, zero Python
- Separates portable spec (what) from JARVIS-specific execution (how)

**Drawbacks:**
- Two places to look for skill config (SKILL.md + skill.py) in Mode 2
- Dynamic import of `skill.py` modules adds a code path to maintain

### Related
- Extends: ADR-014 (Agent Framework — convention-based discovery)
- Extends: ADR-009 (Scalable Monorepo Structure)

---

## ADR-018: Pip Decks Integration — Deck-Skills + RAG + TacticsAgent

**Date**: 2026-03-03
**Status**: Accepted

### Context

Pip Decks (Storyteller Tactics, Workshop Tactics, Idea Tactics — 200+ cards total) are structured reference content ideal for RAG. Primary use cases are multi-turn: iterating on narratives, developing pitches, refining business ideas. Card content is proprietary and lives in a private repository, symlinked via `link_skills.sh`.

### Decision

Three-layer architecture:

1. **Each deck = a skill** (private repo, symlinked). `SKILL.md` for deck-specific coaching personality, `skill.py` with `retrieve_cards` tool, `deck.yaml` for card index metadata, `resources/cards/*.md` for individual card content.
2. **TacticsAgent = cross-deck orchestrator** (main repo). A `BaseAgent` subclass that uses `search_tactics` RAG tool to find cards across all decks and coach users through multi-turn sessions.
3. **CardIndexer + CardSearcher** (main repo). Separate ChromaDB collection (`"pip_deck_cards"`), auto-discovers deck-skills by `deck.yaml` presence, embeds full card markdown.

### Key Tradeoff

Deck-skills include a `skill.py` (JARVIS-specific) rather than being pure markdown (portable). Chose depth over portability: standalone mode with `retrieve_cards` tool provides richer card retrieval than a plain SKILL.md prompt could offer.

### Alternatives Considered

1. **Cards as context files** (data/context/)
   - ❌ No semantic search — all cards in prompt = token bloat
   - ❌ Can't scale to 200+ cards

2. **Cards embedded in SKILL.md body**
   - ❌ Single-deck only, no cross-deck search
   - ❌ Context window limits at ~50 cards

3. **Agent-to-skill delegation** for cross-deck queries
   - ✅ Leverages deck-specific coaching personality
   - ❌ Adds complexity and LLM API cost per delegation
   - ⏳ Deferred to separate branch (`feat/agent-skill-delegation`)

### Consequences

**Benefits:**
- Deck-skills auto-discovered — adding a new deck = copy template + add content + run `link_skills.sh`
- RAG search finds relevant cards across 200+ without token bloat
- Multi-turn coaching with conversation context
- Standalone mode (`/storyteller-tactics`) and orchestrated mode (`--agent tactics`) both work

**Drawbacks:**
- Proprietary content requires private repo + symlink workflow
- ChromaDB dependency for card indexing (already required for conversation recall)
- `skill.py` pattern is JARVIS-specific (SKILL.md body remains portable)

### Related
- Extends: ADR-016 (Conversation Recall via ChromaDB + RAG)
- Extends: ADR-017 (Skills — SKILL.md-First Design)
- Extends: ADR-014 (Agent Framework — Convention-Based Discovery)

---

## ADR-019: Writing Agent File Access via Scoped Vault Tools

**Date**: 2026-03-07
**Status**: ✅ Accepted

### Context

The writing agent (`/write`) can help draft and edit text but has no access to the Obsidian vault where blog posts live. Marco must manually copy-paste content between JARVIS and Obsidian. Adding file access tools lets the agent read, create, and edit blog posts directly, with diff-based confirmation before any write.

### Decision

Reuse existing `vault.py` path validation + add tool-level write guards. Factory pattern (`make_blog_tools()`) with closures captures `VaultConfig` and `ConfirmationHandler` — same pattern as `make_conversation_recall_tool()`.

Four tools scoped to the blog directory:
- `list_blog_posts`: List `.md` files (recursive)
- `read_blog_post`: Read file content
- `create_blog_post`: Create new post (optional template prepend)
- `edit_blog_post`: Full-file replacement with diff + reasoning

Write guards:
1. `validate_path()` enforces `allowed_dirs` from config
2. Template directory is additionally write-guarded at the tool level (`is_relative_to` check)
3. All writes go through `write_note()` which shows a diff and requires y/N confirmation

### Alternatives Considered

1. **General-purpose file tools for all agents**
   - ❌ Too broad — security risk, every agent would need scoping
   - ❌ Deferred to a separate feature

2. **Hardcoded paths in agent**
   - ❌ Not configurable
   - ❌ Breaks for different vault structures

### Consequences

- Writing agent can read/write blog posts without copy-paste
- Scoped, secure pattern reusable for future agent file access
- `extra_tools` injection via existing `_handle_agent_command` mechanism
- Template directory is read-only (protected from accidental edits)

### Related
- Extends: ADR-013 (Obsidian Vault Integration Architecture)
- Extends: ADR-014 (Agent Framework — Convention-Based Discovery)
- Extends: ADR-015 (Tool Calling)

---

## ADR-020: Agent Delegation via Tool Calling

**Date**: 2026-03-07
**Status**: ✅ Accepted

### Context

When a user asks JARVIS to review a blog post, JARVIS improvises a review instead of using the structured 5-lens content-evaluator skill. Two gaps cause this: (1) skills are CLI-only slash commands — agents can't invoke them programmatically, and (2) JARVIS has no mechanism to hand off tasks to specialized agents like the writing agent.

### Decision

**Delegation via tool calling**: JARVIS gets a `delegate_to_agent` tool with an enum constraint listing available agents. When the LLM decides a task is better handled by a specialist, it calls the tool. Post-stream, `main.py` checks `StreamResult.delegate_to` and launches the target agent session with `initial_message` pre-loaded.

**Skills as tools**: Skills can be wrapped as `ToolDefinition` objects via factory functions (e.g., `make_content_evaluator_tool()`). The tool calls `LLMClient.complete()` with the skill's system prompt and temperature — a nested LLM call within the agentic loop.

Key components:
- `DelegationState` dataclass — mutable state set by the delegate tool closure
- `make_delegate_tool()` factory — creates the tool with agent enum constraint
- `JarvisAgent.run()` override — resets state before, reads state after
- `StreamResult.delegate_to` / `delegate_task` — propagates delegation to main.py

### Alternatives Considered

1. **Rule-based routing (keyword matching)**
   - ❌ Brittle — can't handle nuanced or ambiguous requests
   - ❌ Requires maintaining keyword lists

2. **Direct agent invocation in JarvisAgent**
   - ❌ Couples JARVIS to agent instantiation logic
   - ❌ Breaks the clean separation between agents and CLI orchestration

3. **Two-pass classification (separate LLM call to decide routing)**
   - ❌ Extra latency and cost
   - ❌ Tool calling already provides this "classification" for free

### Consequences

- JARVIS delegates content work to the writing agent, which uses `evaluate_content` for structured reviews
- Delegation is LLM-driven (the model decides when to delegate), not rule-based
- Agent sessions from delegation support Ctrl+C to return to JARVIS
- Content-evaluator skill remains usable as a standalone slash command
- Delegated agents receive only `agent_only_tools` (specialist tools), not `extra_tools` (orchestration tools like recall). JARVIS gathers context before delegating; sub-agents don't need orchestration tools.

### Related
- Extends: ADR-014 (Agent Framework — Convention-Based Discovery)
- Extends: ADR-015 (Tool Calling)
- Extends: ADR-017 (Skills — SKILL.md-First Design)

---

## ADR-021: General Filesystem Access Control

**Date**: 2026-03-09
**Status**: ✅ Accepted

### Context

Obsidian vault access used a flat `allowed_dirs` list in `VaultConfig`. This provided coarse-grained path validation but no distinction between read and write access — a directory was either fully allowed or fully blocked. Use cases like "read the entire vault but only write to the blog directory" were impossible to express.

### Decision

Replace `allowed_dirs` with `FilesystemGuard`, a per-path access control layer:

1. **`AccessLevel` enum**: `read`, `write`, `deny` — where `write` implies `read`.
2. **`AccessRule` dataclass**: Pairs a `Path` with an `AccessLevel`.
3. **`FilesystemGuard` class**: Accepts a list of `AccessRule` entries. `check_read(path)` and `check_write(path)` resolve access using **most-specific-path-wins** — the rule whose path is the longest prefix of the target path determines the access level.
4. **`load_filesystem_guard(config)` factory**: Builds a `FilesystemGuard` from YAML config.
5. **`VaultConfig`**: `allowed_dirs` field replaced by `filesystem_guard: FilesystemGuard`.

### Alternatives Considered

1. **Extend `allowed_dirs` with per-entry modes** (e.g., `{"path": "...", "mode": "read"}`)
   - ✅ Backward-compatible shape
   - ❌ No path specificity resolution — ambiguous when paths overlap
   - ❌ Still a flat list with no hierarchy awareness

2. **OS-level ACLs** (delegate to filesystem permissions)
   - ✅ Zero application code
   - ❌ Requires system-level configuration per user
   - ❌ Not portable across macOS/Linux setups
   - ❌ Can't express JARVIS-specific rules (e.g., template dir read-only for agents)

### Consequences

**Benefits:**
- ✅ Whole-vault read access with selective write — enables agents to browse freely while restricting edits to specific directories
- ✅ Most-specific-path-wins is intuitive and predictable
- ✅ Single guard instance shared across all tools — consistent enforcement

**Drawbacks:**
- ⚠️ Breaking change: `allowed_dirs` removed from config and `VaultConfig`
- ⚠️ Existing `local.yaml` configs need migration to the new `filesystem_rules` format

### Related
- Replaces: ADR-019 (Writing Agent File Access — `allowed_dirs` + tool-level guards)
- Extends: ADR-013 (Obsidian Vault Integration Architecture)

---

## ADR-022: Capability Distribution — Orchestrator vs Subagent Tools

**Date**: 2026-03-09
**Status**: ✅ Accepted

### Context

As JARVIS gains integrations (vault, calendar, email), each new capability raises the question: does it belong on JARVIS directly, or on a specialized subagent? Without a clear framework, every integration becomes an ad-hoc decision.

### Decision

Four criteria determine where a capability belongs:

| Criterion | → JARVIS tool | → Subagent tool |
|-----------|--------------|-----------------|
| **Data direction** | Read (information gathering) | Write (content creation) |
| **Judgment required** | Mechanical / deterministic | Creative / voice-aware |
| **Interaction pattern** | One-shot (single tool call) | Multi-turn (refinement loop) |
| **Parallelism benefit** | Safe to parallelize (reads) | Needs sequencing (writes) |

**Core principle:** JARVIS owns general-purpose information retrieval; subagents own domain-specific creative transformation.

A capability meeting ≥3 left-column criteria → JARVIS. One meeting ≥2 right-column criteria → subagent.

**Refinement — downstream intent:** If a read operation only makes sense in the context of a creative task a subagent owns, it belongs with that subagent. Example: `search_tactics` is mechanically a read, but its purpose is always creative synthesis → TacticsAgent, not JARVIS. Contrast: `read_note` has many non-creative uses → general-purpose → JARVIS.

### Applying the Framework

| Capability | Owner | Rationale |
|-----------|-------|-----------|
| `read_note`, `search_notes`, `read_daily_note` | **JARVIS** (Tier 1) | General-purpose reads, mechanical, one-shot |
| `search_tactics` | **TacticsAgent** (agent-only) | Downstream intent is creative synthesis |
| Blog read/write tools | **WritingAgent** (agent-only) | Writing/editing context |
| `/daily-summary` | **CLI command** | LLM-generated write, stays as CLI command |

### Consequences

**Benefits:**
- ✅ JARVIS can answer "what's in my daily note?" without delegation overhead
- ✅ Clear, repeatable framework for future integrations (calendar, email, etc.)
- ✅ Tool count stays manageable: 6 JARVIS tools (well within ~10-tool accuracy threshold)

**Drawbacks:**
- ⚠️ `search_tactics` moved from JARVIS → agent-only; users must delegate or use `/tactics`

### Related
- Extends: ADR-020 (Agent Delegation), ADR-021 (Filesystem Access Control)
- Informs: future calendar/email integration decisions

---

## ADR-023: Runtime Model Switching

**Date**: 2026-03-10
**Status**: ✅ Accepted

### Context

Changing the GenAI model required editing `config/default.yaml` and restarting JARVIS. Users wanted to switch models at startup via a CLI flag and mid-session via a `/model` command. Additionally, supporting direct provider APIs (not just OpenRouter) and named presets (fast/quality/balanced) was desirable.

### Decision

1. **New `model_resolver.py` module** — Resolves preset names or literal model IDs into `ResolvedModel` objects with provider inference.
2. **`LLMClient` refactored** — Accepts `api_keys: dict[str, str]` instead of single `api_key`/`provider`. Provider inferred from model ID prefix. Added `set_model()` for mid-session switching.
3. **Config restructured** — Replaced `openrouter:` section with `models:` section containing `default` and `presets` map. Model IDs use full LiteLLM-routable format with provider prefix.
4. **LiteLLM pricing** — Replaced OpenRouter HTTP pricing call with `litellm.get_model_cost_map()`. Works offline, covers all providers.
5. **`--model` CLI flag** — Overrides config default at startup.
6. **`/model` slash command** — Shows current model + presets; `/model <name>` switches mid-session.

### Alternatives Considered

1. **Keep single provider** — Rejected; provider independence is a core principle.
2. **Separate provider flag** — Rejected; provider is redundant when model ID includes prefix.
3. **Keep OpenRouter HTTP pricing** — Rejected; network dependency, only covers OpenRouter models.

### Consequences

**Benefits:**
- ✅ Switch models without restarting
- ✅ Multi-provider support with zero code changes
- ✅ Offline pricing via LiteLLM cost map
- ✅ Named presets for common workflows (fast/quality/balanced)
- ✅ `requests` no longer needed in pricing module

**Drawbacks:**
- ⚠️ Breaking change: `LLMClient` constructor signature changed (all callers updated)
- ⚠️ Breaking change: `config/default.yaml` `openrouter:` → `models:` (local.yaml may need manual update)

### Related
- Extends: ADR-003 (LiteLLM for provider abstraction)
- Implements: Phase 9 model presets from roadmap

---

*Last updated: 2026-03-10*
