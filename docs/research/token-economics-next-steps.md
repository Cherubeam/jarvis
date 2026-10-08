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

**Status (2026-09-30): reopened — the March diagnosis below was wrong; see [Step C, reopened](#step-c-reopened-prompt-caching-state-and-plan-2026-09-30).** Kept for the record.

~~**Status: Implemented but NOT effective via OpenRouter streaming.**~~

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

## Step C, reopened: prompt caching state and plan (2026-09-30)

Handoff for the caching work. Marked **verified** (probe or code read, with date) or
**unverified**. Engineering record of how this was found:
[token-economics-edit-tools.md](token-economics-edit-tools.md) §5.

### What changed since March

- **The March diagnosis was a measurement error, not a caching failure (verified 2026-09-29).**
  In streaming mode LiteLLM 1.82.1 drops OpenRouter's usage and substitutes a local estimate
  with no cache fields ([BerriAI/litellm#36168](https://github.com/BerriAI/litellm/issues/36168),
  still open; 1.103.0 doesn't fix it). "8026 vs 8823 prompt tokens" was estimate vs real, not
  two different prompts.
- **Streamed calls do write and read the cache (verified 2026-09-29).** Two LiteLLM streamed
  calls, then a raw OpenRouter call with the same prefix: the raw call reported
  `cached_tokens: 2216`. LiteLLM passes `cache_control` through for `openrouter/` Claude models
  (`litellm/llms/openrouter/chat/transformation.py`).
- **Usage is now measurable (PR #73, merged).** Streamed turns are logged with their OpenRouter
  generation ids and reconciled against the billing record (`packages/core/billed_usage.py`,
  `ConversationLogger.reconcile_billed_usage()`). The record carries `native_tokens_cached`
  (cache reads) and the exact `total_cost`; it has **no cache-write field**, so
  `cache_write_tokens` stays 0 for streamed turns, but the cost includes writes. Each logged
  assistant message says `metadata.usage_source: billed | estimated`; leftovers:
  `uv run python scripts/backfill_billed_usage.py`.

### Current code (verified by code read, 2026-09-29)

- `_apply_cache_control()` in `packages/core/llm_client.py` sets **one** breakpoint,
  `cache_control: {"type": "ephemeral"}` on `messages[0]` (the system prompt), only when the
  model string contains `anthropic`. Applied on every call via `_base_kwargs`.
- Auto Router turns (`openrouter/auto`) get no breakpoints (ADR-036).
- `_extract_cache_tokens()` reads writes only from `cache_creation_input_tokens`; OpenRouter's
  non-streamed responses report them as `prompt_tokens_details.cache_write_tokens`, so
  **non-streamed cache writes are logged as 0 too** (small bug, unfixed).
- `session_id` is sent only for the Auto Router (`packages/core/model_resolver.py`,
  `apps/cli/session_factory.py`).

### Prices (verified via OpenRouter `/api/v1/models`, 2026-09-29)

| `anthropic/claude-opus-5.5` | per M tokens | × input |
|---|---|---|
| Input | $4.00 | 1× |
| Output | $20.00 | — |
| Cache read | $0.20 | 0.05× |
| Cache write, 5-min TTL | $5.00 | 1.25× |
| Cache write, 1-h TTL | $8.00 | 2× |

Same across OpenRouter's Opus providers (Anthropic, Vertex, Azure, Bedrock, Claude on AWS);
regional us/eu endpoints +10%. OpenAI models (the `gpt-6-luna` default) cache automatically at
1,024+ tokens; reads $0.01/M — little to gain there.

### Plan, in order

1. **Baseline first (no code).** Run a real multi-turn Opus session (e.g. `/review` or a
   `substack_publisher` session), then read the billed logs: is `cache_read_tokens` > 0 on turn
   2+? This answers whether today's system-prompt breakpoint hits at all. Without it, no
   savings claim is checkable.

   **Status 2026-10-08: not yet possible.** The archive holds 2 billed messages (both
   2026-09-29). The sessions of 2026-10-03 (2 turns in 24 s) and 2026-10-06 (1 turn, the
   90k-token recall test) are still estimates: the CLI reconciles once at exit without
   waiting, and a record is published 10-15 s after its turn, so the last turn of every
   session and every turn of a short session stay estimated. `backfill_billed_usage.py
   --dry-run` would fix all 3 (billed cost $0.0058 below the estimates). Run the backfill
   before reading the logs. Removing the manual step is trigger-gated in
   [roadmap → TOK](../product/roadmap.md#tok--context-window-management--search).

   **Status 2026-10-08, later: tooling ready, data not.** Backfill run (3 messages swapped
   to billed). `uv run python scripts/analyze_costs.py --by caching` reads the billed turns per
   model: 5 turns, all GPT-6 Luna, 66% of prompt tokens from cache (automatic OpenAI caching).
   There is still no billed Anthropic turn, so the question above stays open. Turns now log
   the model that answered (`metadata.model`), so pinned Opus agents show up as Opus. Next
   step: one real multi-turn Opus session, backfill, then read the table.
2. **Second breakpoint on the last message** of each Anthropic request, next to the system one
   (2 of Anthropic's 4 allowed). Caches the growing history and each tool-loop iteration.
   String content must become `[{"type": "text", "text": ..., "cache_control": ...}]`.
   **Unverified:** whether OpenRouter accepts `cache_control` on `role: "tool"` messages; test it,
   else put the breakpoint on the last user/assistant message. Keep the 5-min TTL (most turn
   gaps in the 2026-09-29 session were 1-3 min).
3. **`session_id` on every OpenRouter call**, not just Auto Router: OpenRouter's sticky routing
   keeps a conversation on the provider that holds its cache. Without it, a request can land on
   another of the 5+ Opus providers with a cold cache (one 2026-09-29 request was tried on five).
   Don't set `provider.order`; it overrides stickiness.
4. **Fix cache-write parsing** in `_extract_cache_tokens()` (read
   `prompt_tokens_details.cache_write_tokens`).
5. **Cache-aware trimming** only if measurement shows prefix churn: roadmap item under AON-04
   ("batched at a token threshold, cache-aware").

### What breaks the cached prefix

- `trim_tool_results(keep_recent=6)` runs every turn: when a message leaves the recent window
  it is truncated (results, and since PR #71 tool-call arguments too), which rewrites history
  from that point. Everything after is re-written to cache at 1.25×; earlier prefix still hits.
- `summarize_history` (enabled in `config/local.yaml`) rewrites history once over threshold.
- Routing (`routing.enabled: true`) can switch models between turns; caches are per model.
  Pinned agents (e.g. `substack_publisher` → `quality`) are unaffected.
- The JARVIS system prompt contains a `Last synced: HH:MM` Things line
  (`packages/integrations/things3/task_sync.py`) and `refresh_context()` output: stable within a
  session, different across sessions.
- Changing thinking/effort settings between requests invalidates the message cache.
- Prompts under the minimum don't cache (512 tokens for Opus/Sonnet 5.5, 4,096 for Haiku 4.5 —
  **unverified** on OpenRouter; a ~2.2k-token Sonnet 5.5 probe did cache).
- Tool-list order: comes from registry insertion order; probably stable, **not audited**.

### Expected effect (a model, not a measurement)

For the 2026-09-29 `substack_publisher` session (~283k Opus input tokens logged, itself an
undercount): if ~85% of input became cache reads (0.05×) and ~15% writes (1.25×), the effective
input rate is ~0.23×, i.e. input cost −77%, whole session roughly −58%. Validate against step 1.

### How to verify a change

- One request: `GET https://openrouter.ai/api/v1/generation?id=<gen-id>` (free) →
  `native_tokens_cached`, `total_cost`, `provider_name`. The id is the stream chunk `id`, and
  logged in `metadata.generation_ids` for streamed turns.
- A session: billed logs in `data/conversations/`; `scripts/analyze_costs.py`.
- Old probe script `scripts/test_prompt_caching.py` targets Sonnet 4.6 and predates this
  diagnosis; update or replace it. The 2026-09-29 probe scripts lived in a session scratchpad
  and are gone.

## Relationship to Roadmap

This work feeds into multiple roadmap items:
- **Phase 5D (Model Routing)**: Token data informs which queries need expensive models
- **Phase 7 (Context Window Management)**: Prompt caching + context tiering are the first items
- **Phase 8 (System Monitoring)**: Instrumentation is the foundation for cost optimization
