# AI Engineering Framework

> Systematic approach to building AI applications, phase by phase.

*Adapted from Marina's AI Engineering framework*

---

## Overview

Building AI applications systematically requires moving through distinct phases, each with specific goals, metrics, and deliverables. This framework prevents common pitfalls like premature optimization and helps maintain focus on what matters.

**Key Principle**: Measure before optimizing. Establish baselines before improving.

---

## Phase 1: Problem Framing & Success Metrics

**Goal**: Define what success looks like before writing code.

### Why This Matters

Most AI projects fail not because of technical issues, but because:
- Success wasn't clearly defined
- Wrong metrics were tracked
- Quality expectations were unclear

### What to Do

1. **Identify the core problem**
   - What pain point are we solving?
   - Who benefits from this solution?
   - What does success look like?

2. **Define metrics across dimensions**
   - User-facing: Is this useful?
   - Technical: Is the AI performing well?
   - System: Is this sustainable?
   - Business: Does this provide value?

3. **Establish baselines**
   - What's the current state?
   - What's acceptable vs. excellent?
   - Where are the biggest gaps?

### Metrics to Track

See [metrics.md](../product/metrics.md) for Jarvis-specific metrics.

**User-Facing:**
- Context retention
- Migration success
- Conversation retrievability

**Technical:**
- Context utilization
- Response relevance
- Test case accuracy

**System:**
- Latency (TTFT)
- Cost per conversation
- Error rate
- Token efficiency

**Product-Specific:**
- Data portability
- Provider independence
- Local-first architecture

---

## Phase 2: Prompt Engineering & Systematic Tracking

**Goal**: Treat prompts as versioned, evaluated components.

### Why This Matters

Prompts are code. They need:
- Version control
- Testing
- Quality measurement
- Systematic improvement

### What to Do

1. **Version your prompts**
   - Store in files, not hardcoded strings
   - Track changes in git
   - Document why changes were made

2. **Build evaluation framework**
   - Create test inputs with expected outputs
   - Start small (5-10 cases), grow to 100+
   - Automate evaluation where possible

3. **Measure quality systematically**
   - Manual baselines first
   - LLM-as-judge for scale
   - Traditional metrics where applicable (BLEU, ROUGE, etc.)

4. **Iterate based on data**
   - A/B test prompt changes
   - Track quality metrics over time
   - Document what works and why

### Tools to Consider

- **PromptLayer**: Prompt version control and tracking
- **Langfuse**: LLM observability platform
- **Weights & Biases**: Experiment tracking
- **Custom logging**: Simple JSON logs can go far

### Jarvis Status

- ✅ System prompt in version control
- ✅ Context files versioned
- 🔴 No systematic evaluation yet (Phase 2 goal)

---

## Phase 3: Model Selection & Evaluation

**Goal**: Choose the right model for quality, cost, and latency tradeoffs.

### Why This Matters

No single model is best for everything:
- Expensive models waste money on simple tasks
- Cheap models produce poor quality on complex tasks
- Latency varies dramatically between models

### What to Do

1. **Benchmark models on your workload**
   - Use your golden test cases
   - Measure quality, cost, and latency
   - Document model-specific behaviors

2. **Understand tradeoffs**
   - Quality vs. cost
   - Latency vs. accuracy
   - Context window vs. speed

3. **Model-specific tuning**
   - Some models need different prompting
   - Temperature, top_p, frequency_penalty
   - System vs. user messages

4. **Document findings**
   - Which models excel at what?
   - Cost per task type
   - Failure modes per model

### Jarvis Status

- ✅ Multi-provider support via LiteLLM
- ✅ Cost tracking per model
- 🔴 No systematic benchmarking yet (Phase 3 goal)

See [models.md](models.md) for model comparison.

---

## Phase 4: RAG (Retrieval-Augmented Generation)

**Goal**: Scale beyond context window limits with intelligent retrieval.

### When to Implement

**Triggers:**
- Conversation history exceeds 50k tokens
- Context window limits are hit
- Response quality degrades with long history
- Token costs become unsustainable

**Don't implement prematurely!** RAG adds complexity.

### What RAG Solves

1. **Context window limits**: Models have fixed limits (128k-200k tokens)
2. **Cost explosion**: Sending full history every request is expensive
3. **Relevance**: Long context = less focused responses
4. **Performance**: Shorter context = faster, better responses

### What to Do

1. **Embed historical data**
   - Use local embedding model (sentence-transformers)
   - Store in vector database (ChromaDB, FAISS)
   - Keep human-readable files as source of truth

2. **Implement retrieval**
   - Semantic similarity search
   - Hybrid search (semantic + keyword)
   - Reranking for quality

3. **Evaluate retrieval quality**
   - Retrieval relevance
   - Retrieval confidence
   - Impact on response quality

4. **Optimize**
   - Chunk size and overlap
   - Number of chunks retrieved
   - Retrieval latency

### Metrics to Track

- **Retrieval Quality**
  - Relevance: Are retrieved chunks useful?
  - Coverage: Do we find the right information?
  - Diversity: Too similar vs. too different?

- **System Performance**
  - Retrieval latency (target: <200ms)
  - End-to-end latency
  - Cost savings vs. full history

- **Response Quality**
  - Before/after RAG comparison
  - Does retrieval add value or noise?

### Jarvis Status

- 🔴 Not yet implemented (Phase 4 goal)
- ✅ Filesystem architecture supports RAG addition
- ✅ JSON logs ready for embedding

See [ADR-005](../product/decisions.md#adr-005-start-without-database-plan-rag-transition) for planned approach.

---

## Phase 5: Agent Systems

**Goal**: Enable tool use, function calling, and multi-agent orchestration.

### When to Implement

**Prerequisites:**
- Solid prompt engineering (Phase 2 ✅)
- Good model selection (Phase 3)
- RAG if needed (Phase 4)
- Clear use cases for tools

**Don't build agents without clear use cases!**

### What to Do

1. **Define agent capabilities**
   - What tools does the agent need?
   - Web search, code execution, file ops?
   - External integrations (calendar, email)?

2. **Implement function calling**
   - LiteLLM provides unified interface
   - Define tool schemas carefully
   - Handle errors gracefully

3. **Agent orchestration**
   - Single agent vs. multi-agent?
   - Task delegation strategies
   - Communication protocols

4. **Intelligent routing**
   - Simple tasks → cheap models
   - Complex tasks → expensive models
   - Track cost savings from routing

### Metrics to Track

- **Agent Performance**
  - Task completion rate
  - Steps to completion
  - Tool success rates
  - Error recovery

- **Cost Optimization**
  - Cost per task type
  - Savings from model routing
  - ROI of agent system

- **Quality**
  - Accuracy of tool use
  - Appropriate tool selection
  - Error handling

### Jarvis Status

- 🟡 LiteLLM provides function calling support
- 🔴 No tools implemented yet (Phase 5 goal)
- 🔴 No agent orchestration (Phase 5 goal)

---

## Phase 6: System Monitoring & Error Analysis

**Goal**: Production-grade observability and continuous improvement.

### What to Track

#### By Component

| Component | Metrics |
|-----------|---------|
| **Prompts** | Response quality, format compliance, refusal rates, length |
| **RAG** | Retrieval confidence, chunks retrieved, source diversity, latency |
| **Agents** | Task completion, steps to completion, tool success, error types, cost |
| **Overall** | End-to-end success, satisfaction, latency, cost, error rate |

#### Minimum Logging

Every request should log:
- Timestamp
- User query
- Components/models/prompt versions used
- Response
- Latency breakdown
- Token usage and cost
- Any errors

### Error Analysis

1. **Categorize errors**
   - API failures
   - Prompt issues
   - Retrieval failures
   - Tool execution errors

2. **Root cause analysis**
   - Why did it fail?
   - Is it recurring?
   - Can we prevent it?

3. **Automated detection**
   - Quality regression alerts
   - Cost anomaly detection
   - Latency spikes

### Jarvis Status

- ✅ Basic logging (tokens, cost)
- 🔴 No structured error tracking
- 🔴 No automated analysis

---

## Phase 7: Deployment & User Interface

**Goal**: Make it usable and delightful.

### What to Consider

1. **Interface options**
   - CLI (current)
   - TUI (Terminal UI with textual)
   - Web interface
   - API server
   - Mobile app

2. **UX improvements**
   - Faster responses
   - Better formatting
   - Conversation history browser
   - Easy context editing

3. **Production concerns**
   - Reliability (error handling)
   - Performance (caching, optimization)
   - Security (data protection)
   - Monitoring (health checks)

### Jarvis Status

- ✅ Basic CLI working
- 🔴 No TUI yet (Phase 7 goal)
- 🔴 No web interface (future)

---

## Phase 8: Fine-tuning

**Goal**: Personalized model behavior (last resort).

### When to Consider

**Only after:**
- Exhausted prompt engineering (Phase 2)
- Tried multiple models (Phase 3)
- Implemented RAG if needed (Phase 4)
- Built agent systems (Phase 5)
- Still have specific capability gaps

**Fine-tuning is rarely needed!** Most problems solve with better prompts/RAG.

### Prerequisites

1. **Data collection**
   - 1000+ high-quality interactions
   - Diverse scenarios
   - Correct responses labeled

2. **Clear gap identification**
   - What specifically needs improvement?
   - Why can't prompting solve it?
   - Cost-benefit analysis

3. **Evaluation framework**
   - Before/after comparison
   - A/B testing infrastructure
   - Quality metrics

### What to Do

1. Prepare training data
2. Fine-tune model (OpenAI, Anthropic, etc.)
3. Evaluate against baseline
4. Deploy if improvement justifies cost

### Jarvis Status

- 🔴 Not planned (unlikely to need)
- ✅ Logging conversations for potential future use

---

## Summary: Phase Progression

```
Phase 1: Problem Framing ← [You are here]
    ↓ (Define metrics, establish baselines)

Phase 2: Prompt Engineering
    ↓ (Version prompts, build test suite)

Phase 3: Model Selection
    ↓ (Benchmark models, understand tradeoffs)

Phase 4: RAG
    ↓ (Scale beyond context limits)

Phase 5: Agent Systems
    ↓ (Tool use, orchestration)

Phase 6: Monitoring
    ↓ (Observability, error analysis)

Phase 7: Deployment
    ↓ (Production-ready UX)

Phase 8: Fine-tuning
    ↓ (Last resort optimization)
```

**Key Principles:**
1. **Sequential**: Each phase builds on previous
2. **Measured**: Metrics guide decisions
3. **Pragmatic**: Skip phases if not needed
4. **Iterative**: Revisit phases as you learn

---

## Resources

- [Building AI Applications - Marina's Framework](https://example.com)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [RAG Best Practices](https://www.pinecone.io/learn/rag/)
- [LLM Evaluation Methods](https://www.confident-ai.com/)

---

*Last updated: 2026-01-14*
