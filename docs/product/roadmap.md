# Product Roadmap

## Current Phase: Phase 1 - Foundation & Metrics

**Status**: 95% complete
**Timeline**: Completed January 2026

### Completed ✅

- [x] Basic CLI interface with streaming responses
- [x] Context system (profile.md, preferences.md, current_focus.md)
- [x] Conversation logging to timestamped JSON files
- [x] Token usage tracking per request and session
- [x] Cost calculation using OpenRouter pricing API
- [x] Session metrics saved to conversation JSON
- [x] LiteLLM integration for provider flexibility
- [x] Automatic cost fallback via LiteLLM pricing

### In Progress 🚧

- [ ] Testing framework setup
- [ ] Define 5-10 "golden" test conversations
- [ ] Manual evaluation of context utilization

### Blocked ⛔

None currently.

---

## Phase 2: Evaluation & Quality Metrics

**Timeline**: 2-3 weeks (Late January - Early February 2026)
**Goal**: Systematic quality measurement and baseline establishment

### Features

#### Testing Infrastructure
- [ ] Create golden test conversation suite (5-10 cases)
- [ ] Implement automated test runner
- [ ] Add assertion framework for response quality
- [ ] Baseline quality metrics across different models

#### Metrics Implementation
- [ ] Latency tracking (Time to First Token - TTFT)
- [ ] Response quality scoring (manual → automated)
- [ ] Context utilization analysis (does it reference personal context?)
- [ ] Cost per conversation type benchmarks

#### Model Comparison
- [ ] Benchmark 3-5 models on test suite
- [ ] Compare quality vs. cost tradeoffs
- [ ] Document model-specific behaviors
- [ ] Establish default model recommendation

**Success Criteria:**
- 10 golden test cases covering common scenarios
- Latency < 1 second TTFT for 90% of requests
- Cost per conversation documented for all tested models
- Clear quality vs. cost recommendation chart

---

## Phase 3: Advanced Context Management

**Timeline**: 1-2 months (February-March 2026)
**Goal**: Handle long conversations and enable conversation retrieval

### Features

#### Context Window Management
- [ ] Implement intelligent truncation strategies
- [ ] Summarization for old conversation context
- [ ] Token budget management (stay within context limits)
- [ ] Smart context prioritization (recent + relevant)

#### Conversation Search
- [ ] Full-text search over conversation history
- [ ] Filter by date, model, topic
- [ ] Export conversations to readable formats
- [ ] Conversation statistics and insights

#### Fact Extraction
- [ ] Implement learned_facts.md population
- [ ] Extract key information from conversations
- [ ] Periodic fact review and updates
- [ ] Fact-based context enrichment

**Success Criteria:**
- Handle conversations > 50 turns without quality degradation
- Search returns relevant conversations in < 1 second
- 80% of learned facts are accurate and useful
- Context window utilization optimized (< 80% of limit)

---

## Phase 4: Semantic Search & RAG

**Timeline**: 2-3 months (April-June 2026)
**Goal**: Enable semantic search over conversation history

### Features

#### Vector Store Integration
- [ ] Embed past conversations locally
- [ ] Implement semantic similarity search
- [ ] Retrieve relevant past context for current query
- [ ] Hybrid search (semantic + keyword)

#### Retrieval Quality
- [ ] Measure retrieval relevance
- [ ] Track retrieval confidence scores
- [ ] Optimize chunk size and overlap
- [ ] A/B test retrieval strategies

#### Performance
- [ ] Sub-second retrieval latency
- [ ] Efficient embedding generation
- [ ] Incremental index updates
- [ ] Local model for embeddings (no API calls)

**Success Criteria:**
- Relevant past conversations retrieved 85% of the time
- Retrieval adds value without adding noise
- No significant latency impact (< 200ms overhead)
- Works fully offline (local embeddings)

---

## Phase 5: Agent Capabilities

**Timeline**: 3-6 months (July-December 2026)
**Goal**: Tool use and multi-agent orchestration

### Features

#### Function Calling & Tools
- [ ] Implement function calling support (via LiteLLM)
- [ ] Web search integration
- [ ] Code execution sandbox
- [ ] File system operations
- [ ] Calendar and task management integration

#### Agent Orchestration
- [ ] Multi-agent architecture design
- [ ] Agent communication protocols
- [ ] Task delegation and routing
- [ ] Error recovery and fallbacks

#### Intelligent Model Routing
- [ ] Classify task complexity
- [ ] Route simple tasks to cheap models (Haiku, GPT-4o-mini)
- [ ] Route complex tasks to expensive models (Opus, o1)
- [ ] Track cost savings from routing

#### Monitoring
- [ ] Task completion rate tracking
- [ ] Tool success rate metrics
- [ ] Steps-to-completion analysis
- [ ] Cost per task type

**Success Criteria:**
- 5+ tools integrated and working reliably
- Model routing saves 30%+ on costs
- Multi-step tasks complete successfully 80% of the time
- Agent errors gracefully handled and logged

---

## Phase 6: System Monitoring & Optimization

**Timeline**: Ongoing (Throughout 2026)
**Goal**: Production-grade reliability and observability

### Features

#### Comprehensive Logging
- [ ] Structured logging for all requests
- [ ] Error categorization and tracking
- [ ] Performance profiling
- [ ] User interaction analytics

#### Evaluation Framework
- [ ] LLM-as-judge for response quality
- [ ] Automated regression testing
- [ ] Continuous quality monitoring
- [ ] Alert system for quality degradation

#### Optimization
- [ ] Prompt optimization based on metrics
- [ ] Context compression techniques
- [ ] Caching frequently used responses
- [ ] Cost optimization recommendations

**Success Criteria:**
- < 2% error rate across all operations
- Automated quality checks catch regressions
- 95% confidence in prompt changes (A/B tested)
- Observable, debuggable system behavior

---

## Phase 7: User Experience Enhancements

**Timeline**: 6-12 months (Mid-2026 onwards)
**Goal**: Improve usability and interaction patterns

### Features

#### CLI Improvements
- [ ] Rich TUI with textual or similar
- [ ] Conversation history browser
- [ ] Interactive context editor
- [ ] Better formatting and syntax highlighting

#### Configuration Management
- [ ] Profile switching (work/personal contexts)
- [ ] Model presets (fast/quality/balanced)
- [ ] Easy provider switching commands
- [ ] Session templates

#### Export & Sharing
- [ ] Export conversations to markdown/PDF
- [ ] Share prompts and configurations
- [ ] Agent configuration sharing
- [ ] Anonymized usage reports

**Success Criteria:**
- TUI provides better UX than CLI alone
- Context switching takes < 5 seconds
- Users report improved satisfaction
- Documentation guides cover all features

---

## Phase 8: Fine-tuning (Optional)

**Timeline**: 12+ months (2027+)
**Goal**: Personalized model behavior (only if needed)

### Prerequisites
- [ ] Collected 1000+ high-quality interactions
- [ ] Identified specific capability gaps
- [ ] Evaluated: prompting alone insufficient
- [ ] Cost-benefit analysis completed

### Features
- [ ] Data preparation for fine-tuning
- [ ] Fine-tuned model training
- [ ] A/B testing vs. base models
- [ ] Cost and quality evaluation

**Note**: Fine-tuning is a last resort. Most problems should be solved through better prompting, RAG, or agent design.

---

## Backlog (Prioritized)

### High Priority
- [ ] Conversation export to multiple formats
- [ ] Conversation statistics dashboard
- [ ] Multi-model comparison UI
- [ ] Cost tracking over time

### Medium Priority
- [ ] Web interface (optional, after TUI)
- [ ] API server mode (for integrations)
- [ ] Mobile companion app
- [ ] Voice input/output

### Low Priority / Future Ideas
- [ ] Multi-user support
- [ ] Cloud sync (optional, end-to-end encrypted)
- [ ] Plugin system for community extensions
- [ ] Integration marketplace

---

## Recently Completed

### January 14, 2026
- ✅ Migrated from raw HTTP to LiteLLM
- ✅ Added provider flexibility (OpenRouter/Anthropic/OpenAI)
- ✅ Implemented fallback cost calculation
- ✅ Prepared system for function calling support

### January 7, 2026
- ✅ Token usage tracking per request
- ✅ Cost calculation via OpenRouter API
- ✅ Session metrics in conversation JSON
- ✅ Model comparison documentation

---

## Roadmap Principles

1. **Ship small, iterate fast**: Each phase delivers usable value
2. **Metrics-driven**: Measure before optimizing
3. **User needs first**: Build features that solve real problems
4. **Technical excellence**: Maintain code quality and documentation
5. **Flexibility**: Adjust based on learnings and user feedback

---

*Last updated: 2026-01-14*
