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

Available via OpenRouter (as of January 2026):

| Model | Prompt (per 1M) | Completion (per 1M) | Notes |
|-------|-----------------|---------------------|-------|
| Claude Opus 4.5 | $5.00 | $25.00 | Best quality, highest cost. Complex reasoning, long context. |
| Claude Sonnet 4.5 | $3.00 | $15.00 | Extended thinking model, **best quality/cost balance**. |
| Claude Sonnet 4 | $3.00 | $15.00 | Strong balance of quality and cost. |
| Claude Haiku 3.5 | $0.80 | $4.00 | Fast and cheap, good for simple tasks. |
| GPT-4o | $2.50 | $10.00 | OpenAI's flagship, competitive with Sonnet. |
| GPT-4o-mini | $0.15 | $0.60 | Very cheap, good for simple tasks. |
| Gemini 2.0 Flash | $0.10 | $0.40 | Google's fast model, extremely cheap. |

---

## Cost Examples

### Assumptions

For a typical Jarvis conversation:
- **Prompt tokens**: ~1,200 (system prompt + history)
- **Completion tokens**: ~200

### Cost per Request

| Model | Cost per Request | 10-Request Session | 100-Request Month |
|-------|------------------|-------------------|-------------------|
| Claude Opus 4.5 | ~$0.011 | ~$0.11 | ~$1.10 |
| Claude Sonnet 4.5 | ~$0.007 | ~$0.07 | ~$0.70 |
| Claude Sonnet 4 | ~$0.007 | ~$0.07 | ~$0.70 |
| Claude Haiku 3.5 | ~$0.002 | ~$0.02 | ~$0.20 |
| GPT-4o | ~$0.006 | ~$0.06 | ~$0.60 |
| GPT-4o-mini | ~$0.0003 | ~$0.003 | ~$0.03 |
| Gemini 2.0 Flash | ~$0.0002 | ~$0.002 | ~$0.02 |

### Cost Comparison vs. Subscriptions

**Commercial AI subscriptions:**
- ChatGPT Plus: $20/month
- Claude Pro: $20/month
- Copilot: $10-20/month

**Jarvis with Sonnet 4.5:**
- Light use (30 requests/month): ~$0.20
- Moderate use (100 requests/month): ~$0.70
- Heavy use (300 requests/month): ~$2.10

**Savings**: 90-95% cost reduction vs. subscriptions!

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

## Benchmarking Plan (Phase 3)

### Golden Test Suite

Create 5-10 test conversations covering:
1. Context recall (uses profile.md)
2. Technical explanation
3. Multi-step reasoning
4. Personalization (tone matching)
5. Edge cases (ambiguity handling)

### Benchmark Each Model

Run golden tests on:
- Claude Sonnet 4.5 (baseline)
- Claude Haiku 3.5 (fast/cheap)
- Claude Opus 4.5 (quality)
- GPT-4o (alternative)
- GPT-4o-mini (ultra-cheap)

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

## Model Selection TODOs

**Phase 2-3:**
- [ ] Create golden test suite
- [ ] Benchmark 3-5 models
- [ ] Document quality vs. cost tradeoffs

**Phase 5:**
- [ ] Implement task complexity classifier
- [ ] Model routing based on complexity
- [ ] Track cost savings from routing

**Phase 7:**
- [ ] CLI option to choose model at session start
- [ ] Model presets (fast/quality/balanced)
- [ ] Easy model switching UI

---

## Switching Models

### Via Config (Current)

Edit `config.yaml`:
```yaml
openrouter:
  default_model: "anthropic/claude-haiku-3.5"  # Change this line
```

### Via CLI (Future)

```bash
# Not yet implemented
jarvis --model claude-opus-4.5
jarvis --preset quality  # Uses Opus
jarvis --preset fast     # Uses Haiku
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

*Last updated: 2026-01-14*
