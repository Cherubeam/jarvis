# LLM Model Comparison

> Comparing models available via OpenRouter for quality, cost, and latency tradeoffs.

---

## Overview

Choosing the right model is a cost/quality tradeoff. No single model is best for everything:
- Expensive models waste money on simple tasks
- Cheap models produce poor quality on complex tasks
- Latency varies dramatically between models

**Key Insight**: Provider independence (via LiteLLM) means we can switch models anytime to optimize for the task at hand.

> **Current results:** see [Benchmark Results](#benchmark-results) and [Default Model Recommendation](#default-model-recommendation) (2026-09 refresh). The comparison table, cost examples and model notes below describe the April 2026 landscape and are kept for history.

---

## Model Comparison Table

Available via OpenRouter (as of April 2026):

| Model | Prompt (per 1M) | Completion (per 1M) | Context | Tool Use | Notes |
|-------|-----------------|---------------------|---------|----------|-------|
| Claude Opus 4.6 | $5.00 | $25.00 | 200K | Yes | Best quality, highest cost |
| Claude Sonnet 4.6 | $3.00 | $15.00 | 200K | Yes | Current default, strong all-round |
| Claude Haiku 4.5 | $0.80 | $4.00 | 200K | Yes | Cheap Anthropic option |
| Qwen 3.5 397B (MoE 17B) | $0.39 | $2.34 | 262K | Unclear | Flagship Qwen, large MoE |
| Gemini 2.5 Flash | $0.30 | $2.50 | 1M | Yes | Current `fast` preset, reasoning |
| Qwen 3.5 Plus | $0.26 | $1.56 | 1M | Yes | MoE, 1M context, multimodal |
| Qwen 3.5 122B (MoE 10B) | $0.26 | $2.08 | 262K | Yes | "Second only to 397B" |
| Qwen 3.5 27B | $0.195 | $1.56 | 262K | Yes | Dense, confirmed tool use |
| Qwen 3.5 35B (MoE 3B) | $0.16 | $1.30 | 262K | Likely | Small active params |
| Qwen 3 Coder Next | $0.12 | $0.75 | 262K | Yes | Code-focused |
| Nemotron 3 Super (120B/12B) | $0.10 | $0.50 | 262K | Unclear | MoE, very fast inference |
| Gemini 2.5 Flash Lite | $0.10 | $0.40 | 1M | Yes | Cheapest Gemini |
| Qwen 3.5 Flash | $0.065 | $0.26 | 1M | Yes | MoE, 1M context, ultra-cheap |
| Qwen 3.5 9B | $0.05 | $0.15 | 256K | Likely | Tiny, cheapest option |

---

## Cost Examples

### Assumptions

For a typical Jarvis conversation:
- **Prompt tokens**: ~1,200 (system prompt + history)
- **Completion tokens**: ~200

### Cost per Request

| Model | Cost per Request | 10-Request Session | 100-Request Month |
|-------|------------------|-------------------|-------------------|
| Claude Opus 4.6 | ~$0.011 | ~$0.11 | ~$1.10 |
| Claude Sonnet 4.6 | ~$0.007 | ~$0.07 | ~$0.70 |
| Claude Haiku 4.5 | ~$0.002 | ~$0.02 | ~$0.20 |
| Qwen 3.5 Plus | ~$0.0006 | ~$0.006 | ~$0.06 |
| Gemini 2.5 Flash | ~$0.0009 | ~$0.009 | ~$0.09 |
| Qwen 3.5 Flash | ~$0.0001 | ~$0.001 | ~$0.01 |
| Gemini 2.5 Flash Lite | ~$0.0002 | ~$0.002 | ~$0.02 |
| Nemotron 3 Super | ~$0.0002 | ~$0.002 | ~$0.02 |

### Cost Comparison vs. Subscriptions

**Commercial AI subscriptions:**
- ChatGPT Plus: $20/month
- Claude Pro: $20/month
- Copilot: $10-20/month

**Jarvis with Sonnet 4.6:**
- Light use (30 requests/month): ~$0.20
- Moderate use (100 requests/month): ~$0.70
- Heavy use (300 requests/month): ~$2.10

**Jarvis with Qwen 3.5 Flash (potential new default):**
- Light use (30 requests/month): ~$0.003
- Moderate use (100 requests/month): ~$0.01
- Heavy use (300 requests/month): ~$0.03

**Savings**: 90-99% cost reduction vs. subscriptions!

---

## Model Recommendations

### Default Choice: Claude Sonnet 4.5

**Why:**
- ✅ Best quality/cost ratio
- ✅ Extended thinking capabilities
- ✅ Strong at personalization
- ✅ Good context understanding
- ✅ Reasonable latency

**Use for:**
- Default personal assistant interactions
- Technical questions
- Planning and reasoning
- Context-aware responses

---

### Heavy Use: Claude Haiku 3.5 or GPT-4o-mini

**Why:**
- ✅ 5-20x cheaper than Sonnet
- ✅ Fast responses (low latency)
- ✅ Good for simple queries
- ⚠️ Less nuanced personalization

**Use for:**
- Quick factual lookups
- Simple questions
- When cost optimization matters
- High-volume use cases

**Cost savings example:**
- 300 requests/month with Haiku: ~$0.60 (vs. $2.10 with Sonnet)

---

### Complex Reasoning: Claude Opus 4.5

**Why:**
- ✅ Best overall quality
- ✅ Strongest reasoning capabilities
- ✅ Best for complex, multi-step problems
- ⚠️ 2-3x more expensive than Sonnet

**Use for:**
- Complex technical problems
- Multi-step planning
- Critical decisions
- When quality > cost

**Strategy**: Use sparingly, only when Sonnet isn't sufficient.

---

## Model-Specific Considerations

### Claude Models (Anthropic)

**Strengths:**
- Strong instruction following
- Good at personalization
- Excellent context understanding
- Constitutional AI (safer, more aligned)

**Weaknesses:**
- More expensive than Google models
- Sometimes overly cautious

**Prompt Tips:**
- Direct, clear instructions work best
- Can handle long system prompts well
- Responds well to structured context

---

### GPT Models (OpenAI)

**Strengths:**
- Good general capabilities
- Fast inference
- Strong coding abilities
- Widely tested and documented

**Weaknesses:**
- Less personalization-focused
- Can be verbose
- Sometimes repeats patterns

**Prompt Tips:**
- Be explicit about desired tone
- Use "You are..." system prompts
- Shorter is often better

---

### Gemini Models (Google)

**Strengths:**
- **Extremely cheap**
- Fast responses
- Good for high-volume use

**Weaknesses:**
- Lower quality than Claude/GPT-4
- Less consistent
- May miss context nuances

**Prompt Tips:**
- Test thoroughly before production use
- Best for simple, factual queries
- May need more explicit instructions

---

## Model Selection Strategy

### Current (Phase 1)

**Single model**: Claude Sonnet 4.5 for everything

**Pros:**
- Simple
- Consistent quality
- Good cost/quality balance

**Cons:**
- Wastes money on simple queries
- May be overkill for some tasks

---

### Future (Phase 5): Intelligent Model Routing

**Goal**: Route tasks to appropriate models based on complexity.

**Strategy:**
```
User Query
    ↓
Classify Complexity
    ↓
Simple → Haiku/GPT-4o-mini ($$$)
Medium → Sonnet ($$$$$)
Complex → Opus ($$$$$$$$)
```

**Classification Criteria:**
- Length of query
- Keywords (explain, analyze, plan)
- Context requirement
- Historical patterns

**Expected Savings**: 30-50% cost reduction

---

## Benchmarking Plan (Phase 2)

### Golden Test Suite

Golden tests are defined; use them to benchmark models:
1. Context recall (uses personal/professional context)
2. Technical explanation
3. Multi-step reasoning
4. Personalization (tone matching)
5. Edge cases (ambiguity handling)

### Benchmark Each Model

**April 2026 benchmark** — 12 golden tests (8 conversation + 4 agentic tool-use):
- Claude Sonnet 4.6 (baseline)
- Qwen 3.5 Flash (ultra-cheap, 1M context)
- Gemini 2.5 Flash Lite (cheapest Gemini)
- Nemotron 3 Super (MoE, fast inference)
- Qwen 3.5 Plus (flagship Qwen MoE)
- Qwen 3.5 122B (best Qwen quality under $0.30)
- Gemini 2.5 Flash (current fast preset)

### Measure

- **Quality**: LLM-as-judge score (0–1) per test against the YAML criteria, plus rule-based caps (forbidden patterns, `required_verbatim`) at 0.3; pass threshold 0.70
- **Cost**: Per test case, from token usage and litellm prices
- **Latency**: Total response time per test

### Document Findings

- Which models excel at what?
- Cost per quality point
- Failure modes per model
- Recommendations per use case

---

## Benchmark Results

<!-- BENCHMARK_TABLE_START -->
Generated: 2026-09-25 (runs 2026-09-24/25)
Judge model: anthropic/claude-opus-5.5
Test suite: 14 golden tests = 15 results per model (8 conversation, with the multi-turn test scored per turn; 2 writing; 4 agentic tool-use)

| Model | Passed | Avg score | Avg / median latency | Cost per request | $ in/out per 1M |
| --- | --- | --- | --- | --- | --- |
| anthropic/claude-opus-5.5 | 15/15 | 0.923 | 13.6 s / 11.2 s | $0.0139 | 4 / 20 |
| **openai/gpt-6-luna** | **15/15** | 0.907 | **4.3 s / 3.0 s** | **$0.00014** | 0.10 / 0.50 |
| openai/gpt-5.6-luna | 14/15 | 0.889 | 6.2 s / 3.3 s | $0.00049 | 0.20 / 1.20 |
| z-ai/glm-5.3-flash | 14/15 | 0.883 | 25.0 s / 11.3 s | $0.00026 | 0.15 / 0.50 |
| deepseek/deepseek-v4.1-flash | 13/15 | 0.881 | 25.3 s / 9.8 s | $0.00050 | 0.14 / 0.42 |
| z-ai/glm-5.3 | 14/15 | 0.875 | 10.5 s / 6.8 s | $0.00170 | 0.84 / 2.64 |
| google/gemini-3.5-flash-lite | 13/15 ¹ | 0.866 | 2.3 s / 1.9 s | $0.00096 | 0.30 / 2.50 |
| qwen/qwen3.7-flash | 12/15 | 0.855 | 20.9 s / 21.9 s | $0.00008 | 0.03 / 0.13 |
| anthropic/claude-sonnet-5 | 12/15 | 0.807 | 9.0 s / 7.5 s | $0.00573 | 2 / 10 |
| qwen/qwen3.5-flash-02-23 (previous default) | 11/15 ² | 0.796 | 3.1 s / 3.2 s | $0.00013 | 0.065 / 0.26 |
<!-- BENCHMARK_TABLE_END -->

¹ `delegation_to_developer` returned `finish_reason: error` / `MALFORMED_FUNCTION_CALL` in 3 of 3 attempts, which litellm cannot parse; counted as a fail, not scored.
² `multi_step_search_then_read` did not converge within its 3 tool rounds; counted as a fail, not scored. Qwen 3.5 ran with `reasoning: {effort: "none"}` (see `models.extra_body`).

Failures (Opus 5.5 judge):
- **GPT-5.6 Luna:** multi-turn follow-up (turn 2).
- **GLM 5.3 Flash:** multi-step search-then-read.
- **DeepSeek V4.1 Flash:** ambiguous query, multi-turn turn 2.
- **GLM 5.3:** delegation.
- **Gemini 3.5 Flash-Lite:** multi-turn turn 2, delegation (malformed tool call).
- **Qwen 3.7 Flash:** ambiguous query, multi-turn turn 2, technical deep dive.
- **Claude Sonnet 5:** ambiguous query, delegation, tool termination (called a tool for a general-knowledge question).
- **Qwen 3.5 Flash:** ambiguous query, `edit_preserves_links` (0.55: changed text it was only asked to copy), multi-turn turn 2, multi-step did not converge.

### Second judge (google/gemini-3.8-flash)

The stored answers of the 11 conversation results per model were re-scored by a second judge from
neither the Anthropic nor the OpenAI family. The agentic tests weren't re-scored: their tool
transcripts aren't stored.

| Model | Gemini 3.8 Flash avg (pass) | Opus 5.5 avg (pass), same set |
| --- | --- | --- |
| anthropic/claude-opus-5.5 | 0.997 (100%) | 0.921 (100%) |
| z-ai/glm-5.3-flash | 0.994 (100%) | 0.899 (100%) |
| z-ai/glm-5.3 | 0.991 (100%) | 0.915 (100%) |
| qwen/qwen3.7-flash | 0.984 (100%) | 0.841 (73%) |
| openai/gpt-6-luna | 0.971 (100%) | 0.904 (100%) |
| deepseek/deepseek-v4.1-flash | 0.964 (91%) | 0.870 (82%) |
| openai/gpt-5.6-luna | 0.948 (91%) | 0.878 (91%) |
| google/gemini-3.5-flash-lite | 0.944 (100%) | 0.849 (91%) |
| anthropic/claude-sonnet-5 | 0.923 (91%) | 0.848 (91%) |
| qwen/qwen3.5-flash-02-23 | 0.984 (100%) on 8 of 11 ³ | 0.841 on the same 8 |

³ The second judge returned no usable verdict for 3 Qwen 3.5 answers (`ambiguous_query`,
`context_recall_profile`, `edit_preserves_links`), even with a 16k output cap; they are left out.

Reading the two judges together:
- Gemini 3.8 Flash is lenient (0.92–1.00) and separates the models less than Opus does.
- They agree on the top (Opus 5.5) and on GPT-6 Luna passing every conversation test.
- They disagree in the middle. Gemini rates Qwen 3.7 Flash and GLM 5.3 well above Opus's scores,
  so the middle ranks are judge-dependent and shouldn't carry a decision alone.
- The Opus-judged ranking could favour Claude-like answers; Sonnet 5 placing second-to-last
  under an Anthropic judge argues against a strong same-family bias, but doesn't rule it out.

### Method and changes since April

- **Judge:** `evaluation.judge_model` (now read by `tests/conftest.py` and `scripts/model_benchmark.py`), Claude Opus 5.5, output capped at 4,096 tokens.
- **Model under test:** called through `LLMClient` with the configured `models.extra_body` and `models.default_max_tokens`, not through the full agent stack.
- **Multi-turn fixed:** follow-up turns now include the conversation so far (for the model and the judge), and each turn is scored separately. Before, the follow-up was sent without history and overwrote the first turn's result, so April's `multi_turn_reasoning` scores aren't comparable.
- **New writing cases (synthetic):** `13_review_language_errors` (typos, German word order and German placeholder words are errors; commas, semicolons and emoticons are voice) and `14_edit_preserves_links` (a full-file edit must keep frontmatter, wikilinks and URLs byte-identical, enforced by the new `required_verbatim` check, which caps the score at 0.3).
- **Known limit of 13 and 14:** every model except Qwen 3.5 passed both. The short synthetic texts don't reproduce the long full-file rewrite in which the original problems appeared.
- **Stricter judge:** scores aren't comparable with April's Opus 4.5 run; Qwen 3.5 Flash dropped from 0.925 to 0.796 on largely the same tests.
- **Cost:** about $4.50 for the whole refresh, including runs lost to OpenRouter's in-flight credit limit when the ten models first ran in parallel and to uncapped `max_tokens` on a low balance (both fixed: run models sequentially; the harness now caps tokens).

### Live check in the real agent stack

The golden harness doesn't exercise JARVIS's agents, so `/review` of a real vault draft was run with GPT-6 Luna as content_reviewer:
- It found the draft, read it, ran `evaluate_content` and proposed a small, targeted diff (+4/−6 lines; Qwen 3.5 had proposed a +37/−40 rewrite).
- It noticed the draft breaks off mid-sentence, which Qwen 3.5 hadn't.
- It needed 7 tool rounds; content_reviewer's limit of 5 cut the first attempt short. The limit is now 10, and a model that runs out is told the tools still exist (`TOOL_LIMIT_NOTE`) instead of concluding they are missing.

---

## Default Model Recommendation

Based on the 2026-09 refresh (10 models, 15 results each, two judges), **GPT-6 Luna** replaces Qwen 3.5 Flash as the default.

### Decision Matrix

| Criteria | GPT-6 Luna | Opus 5.5 | GPT-5.6 Luna | Qwen 3.5 Flash (previous) |
| --- | --- | --- | --- | --- |
| **Passed (Opus judge)** | 15/15 | 15/15 | 14/15 | 11/15 |
| **Avg score** | 0.907 | 0.923 | 0.889 | 0.796 |
| **Conversation tests, second judge** | 100% | 100% | 91% | 100% on 8 of 11 |
| **Median latency** | 3.0 s | 11.2 s | 3.3 s | 3.2 s |
| **Cost/request** | $0.00014 | $0.0139 | $0.00049 | $0.00013 |

### Presets

| Preset | Model | Why |
| --- | --- | --- |
| `default` | `openrouter/openai/gpt-6-luna` | Only low-cost model with 15/15; about the same price as Qwen 3.5 Flash |
| `balanced` | `openrouter/openai/gpt-6-luna` | The router sends most turns here; no mid-priced model beat it |
| `fast` | `openrouter/openai/gpt-6-luna` | The only faster candidate, Gemini 3.5 Flash-Lite, sends malformed tool calls, and routed short turns still carry tools. Replaces `google/gemini-2.5-flash`, which OpenRouter retires on 2026-10-20 |
| `quality` | `openrouter/anthropic/claude-opus-5.5` | Highest score, 15/15; cheaper than Opus 4.6 ($4/$20 vs $5/$25) |

### When to Override

- **Maximum quality:** `quality` preset (Opus 5.5), about 100× the cost per request.
- **Lowest latency without tools:** Gemini 3.5 Flash-Lite (1.9 s median), but not for turns that call tools.
- **Watch list:** GLM 5.3 Flash and DeepSeek V4.1 Flash score close to GPT-5.6 Luna at similar prices, but reason by default and are slow (25 s average). Re-test with lower reasoning effort if latency matters less than price.

### Configuration

Set in `config/default.yaml`:
```yaml
models:
  default: "openrouter/openai/gpt-6-luna"
  presets:
    fast: "openrouter/openai/gpt-6-luna"
    quality: "openrouter/anthropic/claude-opus-5.5"
    balanced: "openrouter/openai/gpt-6-luna"
```

Override per-session via `--model` flag or `/model` command.

---

## Model Selection TODOs

**Phase 2-3:**
- [x] Create golden test suite ✅
- [x] Add benchmark cost estimation tooling ✅
- [x] Benchmark 3-5 models ✅
- [x] Document quality vs. cost tradeoffs ✅

**Phase 5:**
- [ ] Implement task complexity classifier
- [ ] Model routing based on complexity
- [ ] Track cost savings from routing

**Phase 7:**
- [x] CLI option to choose model at session start (`--model`) ✅
- [x] Model presets (fast/quality/balanced) ✅
- [x] Mid-session model switching (`/model`) ✅

---

## Switching Models

### Via Config

Edit `config/default.yaml` (or override in `config/local.yaml`):
```yaml
models:
  default: "openrouter/openai/gpt-6-luna"
  presets:
    fast: "openrouter/openai/gpt-6-luna"
    quality: "openrouter/anthropic/claude-opus-5.5"
    balanced: "openrouter/openai/gpt-6-luna"
```

### Via CLI Flag

```bash
uv run python -m apps.cli.main --model quality            # Use a preset
uv run python -m apps.cli.main --model anthropic/claude-sonnet-4.6  # Direct provider
```

### Mid-Session

```
/model              # Show current model + presets
/model fast         # Switch to fast preset
/model openai/gpt-4o  # Switch to literal model
```

---

## Provider Comparison

### OpenRouter (Current Default)

**Pros:**
- ✅ Access to all models through one API
- ✅ Easy provider switching
- ✅ Unified pricing API
- ✅ Model fallbacks built-in

**Cons:**
- ⚠️ 10-20% markup over direct APIs
- ⚠️ Adds proxy latency (~100-200ms)
- ⚠️ Dependency on third-party service

---

### Direct Providers

**Anthropic Direct:**
- ✅ No markup, lower cost
- ✅ Slightly lower latency
- ⚠️ Only Claude models

**OpenAI Direct:**
- ✅ No markup
- ✅ Lower latency
- ⚠️ Only GPT models

**Google Direct:**
- ✅ Cheapest option
- ⚠️ API may differ from OpenRouter
- ⚠️ Less mature

---

## Future Considerations

### Model Routing Algorithm

```python
def select_model(query: str, history: list) -> str:
    """Intelligently route to appropriate model."""

    # Simple tasks → cheap model
    if is_simple_query(query):
        return "claude-haiku-3.5"

    # Complex reasoning → expensive model
    if requires_deep_reasoning(query):
        return "claude-opus-4.5"

    # Default: balanced model
    return "claude-sonnet-4.5"
```

### Model Performance Tracking

Track per-model:
- Average quality score
- Cost per request
- Latency (TTFT)
- Success rate

Use data to refine routing algorithm.

---

## Resources

- [OpenRouter Model Pricing](https://openrouter.ai/models)
- [Anthropic Model Comparison](https://www.anthropic.com/pricing)
- [OpenAI Model Pricing](https://openai.com/pricing)
- [LiteLLM Supported Models](https://docs.litellm.ai/docs/providers)

---

*Last updated: 2026-04-07*
