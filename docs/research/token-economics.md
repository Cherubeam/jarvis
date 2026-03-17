# Token Economics: Analysis & Strategy

> Understanding and optimizing the cost of context in every API call.

---

## Current State

Jarvis sends ~8,000 tokens of system prompt on every API call, regardless of query relevance. This breaks down roughly as:

| Section | Approx. Size | % of System Prompt |
|---------|-------------|-------------------|
| Soul (identity) | ~300 tokens | 4% |
| Personal context | ~500 tokens | 6% |
| Professional context | ~800 tokens | 10% |
| Preferences | ~250 tokens | 3% |
| Current focus | ~300 tokens | 4% |
| Tasks | ~1,700 tokens | 22% |
| Projects (active) | ~3,900 tokens | 49% |
| **Total** | **~7,750 tokens** | **100%** |

**Cost implication**: At Claude Sonnet 4 rates ($3/1M input tokens), the system prompt alone costs ~$0.023 per call. Over a 10-turn session, that's $0.23 just for repeatedly sending context — before any user messages or history.

---

## The "Back of Mind" Problem

The system prompt serves as Jarvis's "working memory" — personal details, active projects, current tasks. Like a human keeping context "in the back of their mind," the LLM needs this information available even when it's not directly relevant to the current query.

The question: **How do we keep context available without paying for it on every call?**

### Approach 1: Always Load (Current)

Load everything into the system prompt every time.

- **Pros**: Simple, reliable, no information loss
- **Cons**: Pays full cost every call, scales poorly as context grows
- **Best for**: Small context sets (<2K tokens), early-stage products

### Approach 2: Compressed Summaries

Replace detailed context with compressed summaries for sections not relevant to the current query.

- **Pros**: Reduces tokens while keeping awareness, no infrastructure
- **Cons**: Information loss in summaries, requires deciding relevance before the call
- **Best for**: Medium context (2K-10K tokens), predictable usage patterns
- **When it pays off**: Only in sessions >5 turns (the summarization call itself costs tokens)

### Approach 3: Two-Pass Architecture

First pass: small/fast model classifies the query and selects relevant context. Second pass: full model with only relevant context.

- **Pros**: Optimal token usage, pays only for what's needed
- **Cons**: Added latency (two API calls), complexity, classification errors
- **Best for**: Large context (>10K tokens), latency-tolerant applications

### Approach 4: RAG (Retrieval-Augmented Generation)

Embed context sections, retrieve only semantically relevant ones per query.

- **Pros**: Scales to very large context, semantically intelligent selection
- **Cons**: Embedding infrastructure, retrieval quality varies, miss "ambient" context
- **Best for**: Very large context (>20K tokens), many distinct knowledge areas

### Approach 5: Prompt Caching

Use provider-level prompt caching (Anthropic's cache_control, OpenAI's auto-caching) to avoid re-processing unchanged prompt prefixes.

- **Pros**: No information loss, no architecture change, 90% cost reduction on cached portion
- **Cons**: Provider-specific, cache has TTL (5 min Anthropic, varies others), minimum size requirements
- **Best for**: Any context size, high-frequency sessions, stable system prompts

### Tradeoff Matrix

| Approach | Complexity | Token Savings | Info Loss | Latency Impact |
|----------|-----------|---------------|-----------|----------------|
| Always Load | None | 0% | None | None |
| Compressed Summaries | Low | 30-60% | Medium | None |
| Two-Pass | High | 50-80% | Low-Medium | +200-500ms |
| RAG | High | 60-90% | Low | +100-300ms |
| Prompt Caching | Low | 80-90% | None | None (faster) |

---

## When Summarization Pays Off

Summarization has a cost: the summarization call itself uses tokens. For it to be net-positive:

```
savings_per_turn × remaining_turns > summarization_cost
```

With ~8K system prompt and 50% compression:
- Savings per turn: ~4K tokens × $3/1M = $0.012
- Summarization cost: ~10K tokens (prompt + completion) = $0.03

**Break-even: 3 turns after summarization**

For a typical session:
- 1-3 turns: Summarization loses money
- 4-7 turns: Modest savings ($0.01-0.05)
- 8+ turns: Clear win ($0.06+)

This means **session length distribution matters enormously** — which is why we need to measure it before deciding.

---

## Recommended Strategy: Layered Approach

### Phase 1: Measure (This PR)

Add lightweight instrumentation to understand real usage patterns:
- Per-component token breakdown in session summaries
- Context utilization tracking (which sections are referenced)
- Session length distribution across real usage
- History growth rate per turn

### Phase 2: Prompt Caching (Next)

Enable provider-level prompt caching. This is the highest-ROI optimization:
- No information loss
- No architecture changes
- 80-90% cost reduction on cached system prompt
- Works for all session lengths

### Phase 3: Context Tiering (If Needed)

Based on Phase 1 data, if certain sections are rarely utilized:
- Move them to "on-demand" loading (mentioned in index, loaded only when referenced)
- Keep always-relevant sections (soul, preferences) in system prompt
- Use summaries for large but rarely-referenced sections (inactive projects)

### Phase 4: Smart Loading (If Needed)

Only if context grows beyond ~20K tokens:
- RAG for project contexts and historical knowledge
- Two-pass for complex multi-domain queries
- Hybrid approach: cache stable prefix + retrieve dynamic context

---

## Open Questions

1. **What's the actual session length distribution?** If most sessions are 1-2 turns, prompt caching alone may be sufficient.
2. **Which context sections drive response quality?** Removing "unused" context might degrade subtle behaviors (tone, awareness).
3. **How fast does history grow?** At what turn does history exceed system prompt size?
4. **Does the current provider support prompt caching?** LiteLLM's caching support varies by provider.
5. **What's the cache hit rate in practice?** Depends on session frequency and TTL.

---

*Created: 2026-03-17*
*Status: Research complete, instrumentation in progress*
