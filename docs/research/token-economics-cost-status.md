# Token Economics: Current Cost Status & Savings Analysis

> Analysis of actual cost data from 28 native sessions (Feb–Mar 2026).

---

## Current Cost Status

### Overall Numbers (28 native sessions)

| Metric | Value |
|--------|-------|
| **Total spend** | **$10.94** |
| **Total tokens** | 3,193,451 |
| **Prompt tokens** | 3,080,186 (96.5%) |
| **Completion tokens** | 113,265 (3.5%) |
| **API requests** | 103 |
| **Avg cost/session** | $0.39 |
| **Avg tokens/session** | 114,051 |
| **Avg requests/session** | 3.7 |

### Monthly Trend

| Month | Cost | Tokens |
|-------|------|--------|
| Feb 2026 | $1.42 | 419K |
| Mar 2026 | $9.52 | 2,774K |

March is 6.7x February — driven primarily by one heavy session.

### The Outlier: One Session = 64% of All Costs

The session on **2026-03-17** (pattern language library creation) cost **$6.96** — 63.6% of all-time spend. It ran 19 API calls, with prompt tokens growing from 6,866 to 526,910 (77x growth) as conversation history accumulated.

Without that session, average cost/session drops from $0.39 to **$0.15**.

### Session Length Distribution

| Requests | Sessions | % |
|----------|----------|---|
| 1 | 12 | 43% |
| 2 | 8 | 29% |
| 3-5 | 4 | 14% |
| 6+ | 4 | 14% |

Most sessions (72%) are 1-2 requests. The expensive long-tail sessions drive the majority of cost.

### Cost Drivers

1. **Prompt tokens dominate**: 96.5% of all tokens are prompt (system prompt + history). Completion is tiny.
2. **History accumulation in long sessions**: Each turn re-sends all prior messages. By turn 18 of the expensive session, prompt was 527K tokens.
3. **No prompt caching**: `cache_read_tokens: 0` across all sessions. The static system prompt (~8K tokens) is reprocessed on every request.
4. **System prompt is ~8K tokens**: Projects are 49% (~3,876 tokens), tasks are 22% (~1,832 tokens).

---

## Cost-Saving Opportunities (Ranked by Impact)

### 1. Prompt Caching — HIGH IMPACT, LOW EFFORT ⚠️ BLOCKED

**Estimated savings: 14–40% ($1.50–$4.40)**

Anthropic's prompt caching reduces cost of cached tokens by 90% on reads. The system prompt (~8K tokens) is identical across turns within a session and similar across sessions.

- **Within-session**: $1.52 (13.9%) — guaranteed savings
- **Cross-session** (if within 5-min TTL): up to $4.16 additional
- **Implementation**: `cache_control` breakpoints implemented in `llm_client.py`
- **Info loss**: None

**Current status (2026-03-24):** Implemented but ineffective. LiteLLM reformats messages differently for streaming vs non-streaming via OpenRouter (8026 vs 8823 prompt tokens for identical messages), invalidating cache keys. Non-streaming caching works; streaming (which JARVIS uses exclusively) does not. Blocked on upstream LiteLLM fix. See `scripts/test_prompt_caching.py` for diagnostic and `docs/research/token-economics-next-steps.md` Step C for details.

### 2. History Summarization for Long Sessions — HIGH IMPACT for outliers

**Estimated savings on expensive sessions: 50-70%**

The $6.96 session would have been ~$2-3.50 with mid-session history compression.

- **Trigger**: After N turns or when history exceeds 50K tokens
- **Tradeoff**: Some detail loss in older turns, recent turns stay intact
- **Break-even**: 3 turns after summarization
- **Scope**: Only matters for 14% of sessions (6+ requests), but those drive >70% of cost

### 3. Context Tiering for Projects — LOW IMPACT

**Estimated savings: $1.20 total (10.9%), ~$0.012/request**

Projects consume 49% of the system prompt and load on every API call. However, in long sessions where costs are highest, projects are dwarfed by history (3.2% of the $6.96 session).

Not worth optimizing until prompt caching and history management are in place.

### 4. Model Routing — MEDIUM IMPACT, MEDIUM EFFORT

**Estimated savings: 60-80% on routable queries**

Simple queries don't need Sonnet. Routing to Gemini Flash (~10x cheaper) for trivial queries.

- **Risk**: Quality degradation, routing errors
- **Already planned**: Phase 5D on the roadmap

---

## What NOT to Do

- **RAG**: Context is ~8K tokens — well below the 20K threshold where RAG helps
- **Two-pass architecture**: Over-engineered for current scale
- **Aggressive summarization on all sessions**: 72% of sessions are 1-2 turns — summarization would cost more than it saves

---

## Cost Tracking Discrepancy: Logged vs OpenRouter

**OpenRouter reports $24.40; we logged $10.94 — a $13.46 gap (55%).**

| Cause | Estimated Gap | Evidence |
|-------|--------------|----------|
| **Pre-instrumentation usage** (Jan 2 – Feb 5) | ~$5–6 | 28 imported conversations with no cost data. Tracking added Feb 6. |
| **Pricing bug** (before Mar 11) | ~$0.08 | Two sessions show 25K tokens but $0.00 cost. Fixed by commit `30f1ca2`. |
| **Multi-day session date attribution** | $0 | Accounting mismatch, not a real gap. |
| **Unsaved sessions** (crashes, dev testing) | ~$7–8 | `logger.save()` in `finally` block can be bypassed by SIGKILL/crashes. |

### Bugs Fixed in This Branch

1. **Missing cost fallback in terminal tool path** (`stream_handler.py`): When `self.pricing` is `None`, the terminal tool path (delegation) silently returned `cost_usd = 0.0`. The other two paths fell back to `calculate_cost_from_litellm()`. Fixed by extracting `_calculate_cost()` helper used by all three paths.

2. **Missing UsageReport event in terminal tool path**: The terminal tool path returned without emitting a `UsageReport` event. External consumers listening for usage events missed delegation costs entirely. Fixed by adding emission before the return.

---

## Recommended Priority

| Priority | Action | Savings | Effort | Info Loss |
|----------|--------|---------|--------|-----------|
| **1** | Prompt caching | 14-40% | Low | None | ✅ Workaround: non-streaming mode |
| **1b** | History tool-result trimming | High for delegates + main | Low | None | ✅ Done (main loop + delegates) |
| **2** | History cap/summarization | High for outliers | Medium | Minimal | ✅ Done (opt-in) |
| **3** | Project context tiering | ~11% of prompt cost | Low | None |
| **4** | Model routing | Variable | Medium | Possible | Implemented, opt-in |

---

## Status Update (2026-03-28)

- **Tool result trimming** now applied to the main JARVIS loop (not just delegates). Expected ~88% reduction in tool-related input tokens for long sessions.
- **History summarization** implemented (opt-in via `summarization.enabled`). Compresses old turns using Gemini Flash when history exceeds ~40K tokens.
- **Non-streaming mode** available as prompt caching workaround (`models.streaming: false` or `/stream` toggle). Bypasses the LiteLLM streaming format inconsistency that blocks caching.
- **LiteLLM pinned** to `<1.82.7` due to supply chain attack on versions 1.82.7-1.82.8.
- **Model routing** fully implemented, opt-in via `routing.enabled: true`.

## Verification

- Run `python3 scripts/analyze_costs.py` for cost report
- Raw data: `data/conversations/2026/*.json`
- OpenRouter usage: `curl -s https://openrouter.ai/api/v1/auth/key -H "Authorization: Bearer $OPENROUTER_API_KEY"`
