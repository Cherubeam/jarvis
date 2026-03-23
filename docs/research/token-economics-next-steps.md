# Token Economics: Next Steps After Instrumentation

## Context

Instrumentation is complete (merged to `feat/token-economics-instrumentation`). We now have:
- Per-section token breakdown in session summaries
- History growth tracking per turn
- Context utilization heuristic (which sections are referenced in responses)
- All data persisted to conversation JSON (`section_breakdown`, `utilization`, `history_tokens_per_turn`)

Research document at `docs/research/token-economics.md` outlines 5 approaches with tradeoffs.

## What Comes Next

### Step A: Collect Data (no code — just use Jarvis)

Use Jarvis normally for 20-30 sessions. The instrumentation is already running. After enough sessions accumulate in `data/conversations/2026/`, we'll have the data to answer:

1. Which context sections are utilized most/least?
2. What's the typical session length distribution?
3. At what turn does history exceed system prompt size?
4. Are projects (49% of prompt) actually referenced proportionally?

### Step B: Analysis Script

Write a small script (`scripts/analyze_token_economics.py`) that reads conversation JSONs and produces a summary report:
- Session length distribution (histogram of `request_count`)
- Section utilization frequency (% of sessions each section was referenced)
- History growth curve (avg history tokens by turn number)
- Cost breakdown (system prompt cost vs history cost over time)

This is a one-off analysis tool, not a production feature.

### Step C: First Optimization — Prompt Caching

The research doc identifies prompt caching as the highest-ROI next step:
- **80-90% cost reduction** on cached system prompt
- **No information loss** — everything stays in the prompt
- **No architecture changes** — just API-level configuration
- Works for all session lengths

Implementation depends on provider:
- **Anthropic**: `cache_control` breakpoints in system prompt (LiteLLM supports this)
- **OpenRouter**: May auto-cache with compatible models
- Need to verify LiteLLM's caching support for the configured provider

This maps to **Phase 7** on the roadmap (Context Window Management) and could be done independently.

**Status: Done** — prompt caching implemented (provider-aware, Anthropic `cache_control` breakpoints).

### Step C.5: Tool Result Trimming for Delegate Sessions ✅

Lightweight first step for history management. Delegate agent sessions accumulate tool results (vault reads, searches, web fetches) that are rarely needed verbatim after the LLM processes them. `trim_tool_results()` in `packages/core/history.py` truncates old tool result content to 200 chars while keeping recent messages intact.

- **Zero API cost**: No summarization call needed
- **Targeted**: Only truncates tool results, not user/assistant messages
- **Preserves flow**: Messages are never dropped, only tool content is shortened
- **Reusable**: Module can be applied to JARVIS main loop too

This addresses the most common bloat pattern. Full summarization (Step D below) remains an option for sessions where even trimmed history grows too large.

**Status: Done** — applied to `_run_agent_session()` in `apps/cli/main.py`.

### Step D: Context Tiering (only if data warrants it)

If Step B reveals that certain sections are rarely utilized (e.g., projects referenced in <20% of sessions):
- Move rarely-used sections to "on-demand" loading
- Keep always-relevant sections (soul, preferences) in system prompt
- Use project index as a lightweight pointer, load full context only when referenced

## What NOT to do yet

- **RAG for context**: Only needed if context grows beyond ~20K tokens (currently ~8K)
- **Two-pass architecture**: Over-engineered for current scale
- **Summarization**: Only pays off for sessions >5 turns; need data on typical length first

## Relationship to Roadmap

This work feeds into multiple roadmap items:
- **Phase 5D (Model Routing)**: Token data informs which queries need expensive models
- **Phase 7 (Context Window Management)**: Prompt caching + context tiering are the first items
- **Phase 8 (System Monitoring)**: Instrumentation is the foundation for cost optimization
