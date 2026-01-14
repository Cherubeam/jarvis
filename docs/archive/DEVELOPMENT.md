# Development Guide

This document tracks the AI Engineering framework I'm following to build Jarvis, along with design decisions and learnings.

## AI Engineering Framework

Building AI applications systematically, phase by phase.

### Phase 1: Problem Framing & Success Metrics (Current)

Before writing code, define what success looks like.

#### User-Facing Metrics
*Is this actually useful?*

| Metric | Description | How to Measure | Status |
|--------|-------------|----------------|--------|
| Context retention | Does the assistant use personal context without being explicitly told? | Manual spot-checks | Not tracked |
| Migration success | Can I switch providers and retain full context? | Test with different models | Not tested |
| Conversation retrievability | Can I find and search past conversations? | Feature completeness | Not implemented |

#### Technical Metrics
*Is the AI performing well?*

| Metric | Description | How to Measure | Status |
|--------|-------------|----------------|--------|
| Context utilization | Does the model actually reference personal context? | Review responses for personalization | Manual |
| Response relevance | Are responses personalized vs. generic? | LLM-as-judge evaluation | Future |
| Accuracy on test cases | Does it handle "golden" test conversations correctly? | Build test suite (start with 5-10) | Not started |

#### System Metrics
*Is this sustainable?*

| Metric | Description | How to Measure | Status |
|--------|-------------|----------------|--------|
| Latency (TTFT) | Time to first token | Timestamp logging | Not tracked |
| Cost per conversation | Token usage × pricing | OpenRouter pricing API | **Implemented** |
| Error rate | Failed API calls / total calls | Error logging | Not tracked |
| Token efficiency | Personal context tokens vs. conversation tokens | Token counting | **Implemented** |

#### Jarvis-Specific Metrics
*Unique to the vendor lock-in problem*

| Metric | Description | Target |
|--------|-------------|--------|
| Data portability | Everything exportable in human-readable format | 100% (achieved) |
| Context file coverage | All context files loaded and used | 100% |
| Provider independence | Single config change to switch models | Achieved |

---

### Phase 2: Prompt Engineering & Systematic Tracking

- [ ] Treat prompts as versioned components
- [ ] Build structured evaluation framework
- [ ] Create test inputs with expected outputs (start with 5-10, grow to 100+)
- [ ] Consider metrics: BLEU, ROUGE, LLM-as-judge
- [ ] Tools to explore: PromptLayer, Langfuse, Weights & Biases

---

### Phase 3: Model Selection & Evaluation

- [ ] Benchmark different models on test cases
- [ ] Compare quality vs. cost vs. latency tradeoffs
- [ ] Document model-specific prompt adjustments needed

---

### Phase 4: RAG (Retrieval-Augmented Generation)

*When conversation history grows too large for context window*

- [ ] Implement semantic search over past conversations
- [ ] Evaluate retrieval quality (relevance, diversity)
- [ ] Track: retrieval confidence, chunks retrieved, latency

---

### Phase 5: Agent Systems

*The long-term vision: agent orchestration*

- [ ] Define agent capabilities and tools
- [ ] Track: task completion rate, steps to completion, tool success rates
- [ ] Implement error recovery and fallback strategies
- [ ] Implement model routing (cheap models for simple tasks, expensive for complex reasoning)

---

### Phase 6: System Monitoring & Error Analysis

#### What to Track by Component

| Component | Metrics |
|-----------|---------|
| Prompts | Response quality scores, format compliance, refusal rates, response length |
| RAG | Retrieval confidence, chunks retrieved, source diversity, retrieval latency |
| Agents | Task completion, steps to completion, tool success rates, error types, cost per task |
| Overall | End-to-end success, user satisfaction, latency, cost per request, error rate |

#### Minimum Logging Requirements

Every request should log:
- Timestamp
- User query
- Components/models/prompt versions used
- Response
- Latency
- Any errors

---

### Phase 7: Deployment & User Interface

- [ ] Consider: CLI improvements, TUI, web interface, or API
- [ ] User experience optimizations

---

### Phase 8: Fine-tuning

*Less common than most think — only when other approaches fall short*

- [ ] Identify specific capability gaps not solvable by prompting
- [ ] Collect training data from successful interactions
- [ ] Evaluate fine-tuned model against baseline

---

## Current Status

**Phase**: 1 - Problem Framing & Success Metrics

**Completed**:
- [x] Problem identified (vendor lock-in)
- [x] Core architecture implemented
- [x] Provider independence achieved (OpenRouter)
- [x] Local data storage (markdown + JSON)
- [x] Basic conversation logging
- [x] Token usage tracking per request and session
- [x] Cost calculation using OpenRouter pricing API
- [x] Session metrics (tokens, cost, request count) saved to conversation JSON

**Next Steps**:
- [ ] Define 5-10 "golden" test conversations
- [ ] Add latency tracking (time to first token)
- [ ] Manual evaluation of context utilization
- [ ] Compare model quality vs. cost (see Model Comparison below)

---

## Model Comparison

Choosing the right model is a cost/quality tradeoff. Here's a comparison of models available via OpenRouter:

| Model | Prompt (per 1M) | Completion (per 1M) | Notes |
|-------|-----------------|---------------------|-------|
| Claude Opus 4.5 | $5.00 | $25.00 | Best quality, highest cost. Good for complex reasoning. |
| Claude Sonnet 4.5 | $3.00 | $15.00 | Extended thinking model, great quality/cost balance. |
| Claude Sonnet 4 | $3.00 | $15.00 | Strong balance of quality and cost. |
| Claude Haiku 3.5 | $0.80 | $4.00 | Fast and cheap, good for simple tasks. |
| GPT-4o | $2.50 | $10.00 | OpenAI's flagship, competitive with Sonnet. |
| GPT-4o-mini | $0.15 | $0.60 | Very cheap, good for simple tasks. |
| Gemini 2.0 Flash | $0.10 | $0.40 | Google's fast model, extremely cheap. |

### Cost Example: 10-message conversation

Assuming ~1,200 prompt tokens per request (system prompt + history) and ~200 completion tokens:

| Model | Cost per request | 10-request session |
|-------|------------------|-------------------|
| Claude Opus 4.5 | ~$0.011 | ~$0.11 |
| Claude Sonnet 4 | ~$0.007 | ~$0.07 |
| Claude Haiku 3.5 | ~$0.002 | ~$0.02 |
| GPT-4o-mini | ~$0.0003 | ~$0.003 |

### Recommendation

For a personal assistant with your context files (~1,100 tokens system prompt):

- **Default choice**: Use **Sonnet 4.5** — best quality/cost ratio, extended thinking capabilities
- **Heavy daily use**: Consider **Haiku 3.5** or **GPT-4o-mini** — 5-20x cheaper
- **Complex reasoning tasks**: Keep **Opus 4.5** available as an option

The provider independence we built means you can switch models in `config.yaml` anytime.

### Model Selection TODOs

- [ ] Allow choosing model at session start (CLI prompt or flag)
- [ ] Implement model routing for agentic mode (use cheap models for simple tasks, expensive for complex reasoning)

---

## Design Decisions

### Why OpenRouter?

Single API for multiple providers. Switching from Claude to GPT-4 is a config change, not a code change.

### Why Markdown for Context?

Human-readable, editable, versionable with git. No database lock-in.

### Why JSON for Conversations?

Structured enough for programmatic access, simple enough to read directly.

### Why No Database?

For a personal tool, filesystem is simpler, more portable, and easier to backup. Database adds complexity without clear benefit at this scale.

---

## Resources

- [Building AI Applications - Marina's Framework](link-to-source)
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)

---

*Last updated: 2025-01-07*

---

## Changelog

### 2025-01-07
- Added token usage tracking per request and session
- Added cost calculation using OpenRouter pricing API
- Session metrics (tokens, cost, request count) now saved to conversation JSON
- Added Model Comparison section with pricing data and recommendations
