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

**Status: Implemented but NOT effective via OpenRouter streaming.**

**Investigation (2026-03-24):** Diagnostic confirmed that:
- OpenRouter *does* support prompt caching for Anthropic models
- Non-streaming calls correctly write to and read from cache (verified with `scripts/test_prompt_caching.py`)
- **Streaming calls produce different prompt token counts** (e.g., 8026 vs 8823 for identical messages), indicating LiteLLM reformats messages for streaming — different prompt = different cache key = no cache reuse
- `prompt_tokens_details` (with `cached_tokens`, `cache_write_tokens`) is present in non-streaming responses but `None` in streaming responses
- JARVIS uses streaming exclusively, so caching is currently ineffective

**Blocked by:** LiteLLM streaming format inconsistency via OpenRouter. The `_apply_cache_control()` implementation in `llm_client.py` is correct — the issue is upstream.

**Workaround available (2026-03-27):** Non-streaming mode (`models.streaming: false` or `/stream` toggle) enables prompt caching via OpenRouter by using `LLMClient.complete()` instead of streaming. Verified to produce consistent token counts and cache key stability.

**Next steps:**
- Monitor LiteLLM releases for a fix to streaming format inconsistency (PR #23799 fixes `prompt_tokens_details` mapping but not the underlying cache key divergence)
- Switching to direct Anthropic API is not an option (OpenRouter is required per ADR-001)
- LiteLLM pinned to `<1.82.7` due to supply chain attack on versions 1.82.7-1.82.8 (March 24, 2026)

### Step C.5: Tool Result Trimming for Delegate Sessions ✅

Lightweight first step for history management. Delegate agent sessions accumulate tool results (vault reads, searches, web fetches) that are rarely needed verbatim after the LLM processes them. `trim_tool_results()` in `packages/core/history.py` truncates old tool result content to 200 chars while keeping recent messages intact.

- **Zero API cost**: No summarization call needed
- **Targeted**: Only truncates tool results, not user/assistant messages
- **Preserves flow**: Messages are never dropped, only tool content is shortened
- **Reusable**: Module can be applied to JARVIS main loop too

This addresses the most common bloat pattern. Full summarization (Step D below) remains an option for sessions where even trimmed history grows too large.

**Status: Done** — applied to both `_run_agent_session()` (delegate sessions, line 439) and the main JARVIS loop (line 991) in `apps/cli/main.py`. Analysis of 63 conversations showed tool results account for 40-91% of conversation size during heavy tool-use phases; trimming reduces cumulative tool-related input tokens by ~88% in long sessions.

### Step C.7: History Summarization ✅

Compresses old conversation turns into a concise summary using the fast model (Gemini Flash) when history tokens exceed a configurable threshold (default: 40K). This directly addresses the token accumulation problem in long sessions.

- **Summarize-once pattern**: Detects prior `[JARVIS_SUMMARY]` marker to avoid re-summarizing every turn. Only re-summarizes when new content since the last summary exceeds the threshold.
- **Safe split**: Adjusts the old/recent split point to never break assistant→tool message pairs.
- **Error-tolerant**: On LLM failure, returns history unchanged and falls through to `trim_tool_results()`.
- **Composable**: Runs before `trim_tool_results()` — summarization handles bulk compression, trimming handles remaining recent tool results.
- **Opt-in**: `summarization.enabled: true` in config. Default threshold: 40K tokens, keep recent: 10 messages.

**Status: Done** — implemented in `packages/core/history.py`, integrated into main loop in `apps/cli/main.py`. 7 unit tests in `tests/unit/test_history.py`.

### Step D: Context Tiering (only if data warrants it)

If Step B reveals that certain sections are rarely utilized (e.g., projects referenced in <20% of sessions):
- Move rarely-used sections to "on-demand" loading
- Keep always-relevant sections (soul, preferences) in system prompt
- Use project index as a lightweight pointer, load full context only when referenced

## What NOT to do yet

- **RAG for context**: Only needed if context grows beyond ~20K tokens (currently ~8K)
- **Two-pass architecture**: Over-engineered for current scale
- **Summarization**: ✅ Implemented (Step C.7) — opt-in via config

## Relationship to Roadmap

This work feeds into multiple roadmap items:
- **Phase 5D (Model Routing)**: Token data informs which queries need expensive models
- **Phase 7 (Context Window Management)**: Prompt caching + context tiering are the first items
- **Phase 8 (System Monitoring)**: Instrumentation is the foundation for cost optimization
