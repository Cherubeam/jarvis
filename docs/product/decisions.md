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
- `profile.md` - Who the user is
- `preferences.md` - How the assistant should behave
- `current_focus.md` - Current projects and priorities

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

*Last updated: 2026-01-14*
