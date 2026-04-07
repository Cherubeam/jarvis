# LLM Model Comparison

> Comparing models available via OpenRouter for quality, cost, and latency tradeoffs.

---

## Overview

Choosing the right model is a cost/quality tradeoff. No single model is best for everything:
- Expensive models waste money on simple tasks
- Cheap models produce poor quality on complex tasks
- Latency varies dramatically between models

**Key Insight**: Provider independence (via LiteLLM) means we can switch models anytime to optimize for the task at hand.

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

- **Quality**: Manual scoring (0-10) on:
  - Accuracy
  - Relevance
  - Personalization
  - Helpfulness
  - Tone

- **Cost**: Per test case

- **Latency**: Time to first token (TTFT)

### Document Findings

- Which models excel at what?
- Cost per quality point
- Failure modes per model
- Recommendations per use case

---

## Benchmark Results

<!-- BENCHMARK_TABLE_START -->
Generated: 2026-04-07 UTC
Judge model: anthropic/claude-opus-4.5
Test suite: 12 golden tests (8 conversation + 4 agentic tool-use)

| Model | Avg score | Pass rate | Avg response latency | Cost per request |
| --- | --- | --- | --- | --- |
| qwen/qwen3.5-plus-02-15 | 0.959 | 100% | 16,225 ms | $0.0006 |
| qwen/qwen3.5-122b-a10b-20260224 | 0.954 | 100% | 9,864 ms | $0.0007 |
| qwen/qwen3.5-flash-02-23 | 0.925 | 100% | 8,118 ms | $0.0001 |
| anthropic/claude-sonnet-4.6 | 0.918 | 92% | 9,686 ms | $0.0066 |
| google/gemini-2.5-flash | 0.874 | 92% | 4,289 ms | $0.0009 |
| nvidia/nemotron-3-super-120b-a12b | 0.863 | 92% | 11,145 ms | $0.0002 |
| google/gemini-2.5-flash-lite | 0.819 | 75% | 3,426 ms | $0.0002 |
<!-- BENCHMARK_TABLE_END -->

Notes:
- All three Qwen 3.5 models achieved 100% pass rate, including the new agentic tool-use tests.
- Claude Sonnet 4.6 failed `preferences_adherence` (too verbose for "max 3 sentences" constraint).
- Gemini 2.5 Flash failed `tool_termination` (called tools unnecessarily on a general knowledge question).
- Nemotron 3 Super failed `delegation` (hallucinated a non-existent tool name instead of using `delegate_to_agent`).
- Gemini 2.5 Flash Lite failed 4 tests (25%) — too weak for agentic tasks.
- Qwen 3.5 Flash is the best cost/quality balance: 100% pass, 0.925 score, 66x cheaper than Sonnet.

---

## Default Model Recommendation

Based on golden test benchmarks across 7 models with 12 tests (8 conversation + 4 agentic tool-use), we recommend **Qwen 3.5 Flash** as the default model.

### Decision Matrix

| Criteria | Qwen 3.5 Flash | Qwen 3.5 Plus | Claude Sonnet 4.6 | Gemini 2.5 Flash |
| --- | --- | --- | --- | --- |
| **Avg Score** | 0.925 | 0.959 | 0.918 | 0.874 |
| **Pass Rate** | 100% | 100% | 92% | 92% |
| **Avg Latency** | 8,118 ms | 16,225 ms | 9,686 ms | 4,289 ms |
| **Cost/Request** | $0.0001 | $0.0006 | $0.0066 | $0.0009 |
| **Tool Use** | 100% pass | 100% pass | 100% pass | 92% pass |

### Rationale

1. **100% pass rate** — all 12 golden tests pass including all 4 agentic tool-use tests
2. **Higher quality than Sonnet** (0.925 vs 0.918) at **66x lower cost**
3. **Confirmed tool use** — correct tool calling, delegation, multi-step chaining, and termination
4. **1M context window** — larger than Sonnet's 200K, useful for long conversations
5. **Good latency** — 8.1s average, comparable to Sonnet (9.7s)

### When to Override

- **Maximum quality**: Use `quality` preset (Claude Opus 4.6) for complex multi-step reasoning
- **Lowest latency**: Use `fast` preset (Gemini 2.5 Flash, ~4.3s avg) when speed matters most
- **Higher quality at low cost**: Use `qwen/qwen3.5-plus-02-15` (0.959 score) at $0.0006/request

### Configuration

Set in `config/default.yaml`:
```yaml
models:
  default: "openrouter/qwen/qwen3.5-flash-02-23"
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
  default: "openrouter/anthropic/claude-sonnet-4.6"
  presets:
    fast: "openrouter/google/gemini-2.5-flash"
    quality: "openrouter/anthropic/claude-opus-4.6"
    balanced: "openrouter/anthropic/claude-sonnet-4.6"
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
