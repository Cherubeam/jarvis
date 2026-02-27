# Product Roadmap

## Phase 1: Foundation & Metrics

**Status**: 100% complete
**Timeline**: Completed January 2026

### Features

- [x] Basic CLI interface with streaming responses
- [x] Context system (profile.md, preferences.md, current_focus.md)
- [x] Conversation logging to timestamped JSON files
- [x] Token usage tracking per request and session
- [x] Cost calculation using OpenRouter pricing API
- [x] Session metrics saved to conversation JSON
- [x] LiteLLM integration for provider flexibility
- [x] Automatic cost fallback via LiteLLM pricing
- [x] **Testing framework setup (pytest, coverage, fixtures)**
- [x] **Comprehensive unit test suite (388 tests, 97.5% coverage)**
- [x] **Integration tests (22 tests)**
- [x] **8 golden test conversations defined**

---

## Phase 2: Evaluation & Quality Metrics

**Timeline**: 2-3 weeks (Late January - Early February 2026)
**Goal**: Systematic quality measurement and baseline establishment
**Status**: Complete

### Features

#### Testing Infrastructure

- [x] Create golden test conversation suite (8 cases)
- [x] Implement automated test runner (pytest)
- [x] **Add LLM-as-judge for automated quality evaluation**
  - 33 unit tests (evaluator + storage)
  - Structured JSON results + markdown reports
  - Historical trend tracking
  - Cost management (~$0.41/run)
  - On-demand via `--evaluate` flag
- [x] ChatGPT conversation import (bulk import with CLI filters)
- [x] Claude conversation import (bulk import with date filters)
- [x] Baseline quality metrics across different models

#### Things 3 Integration (Phase A - Context Awareness)

- [x] Task sync module with AppleScript integration
- [x] Automatic language detection (German, French, Spanish, Italian, English)
- [x] Auto-sync tasks to tasks.md on startup
- [x] 5-minute task cache to optimize performance
- [x] 43 tests for task sync (33 unit + 8 integration + 2 golden)
- [ ] Phase B (Interactive management) - Moved to Phase 5

#### Metrics Implementation

- [x] Latency tracking (Time to First Token - TTFT)
  - MetricsTracker integrated into CLI
  - TTFT and total latency displayed after each response
  - Session summary with average latency metrics
  - Conversation JSON logs include latency per message
- [x] Response quality scoring (manual → automated)
- [x] Context utilization analysis (does it reference personal context?)
- [x] Cost per conversation type benchmarks

#### Model Comparison

- [x] Benchmark 3-5 models on test suite
- [x] Compare quality vs. cost tradeoffs
- [x] Document model-specific behaviors
- [x] Establish default model recommendation
- [x] Cost estimation tooling for benchmark runs (OpenRouter pricing API)

**Success Criteria:**
- 10 golden test cases covering common scenarios
- Latency < 1 second TTFT for 90% of requests
- Cost per conversation documented for all tested models
- Clear quality vs. cost recommendation chart

---

## Phase 3: Web Interface + Advanced Context Management

**Timeline**: 1-2 months (February-March 2026)
**Goal**: Add web interface and handle long conversations
**Status**: Not Started

### Features

#### Web Interface

- [ ] FastAPI backend with SSE streaming (`apps/web/backend/`)
- [ ] React frontend with chat UI (`apps/web/frontend/`)
- [ ] Conversation history browser
- [ ] Real-time streaming responses
- [ ] Session switching between conversations

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
**Status**: Not Started

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
**Status**: In Progress

### Features

#### Agent Framework (Phase A - Infrastructure)

- [x] Extract `StreamHandler` from CLI into shared module
- [x] Add `BaseAgent.run()` and `BaseAgent.load_prompt()` methods
- [x] Agent registry with filesystem-based auto-discovery
- [x] Wire agents into CLI with slash-command routing
- [x] `--agent <name>` standalone mode
- [x] Writing agent (`/write`), Research agent (`/research`), Clarity agent (`/clarity`)
- [ ] Phase B: JARVIS delegation — sub-conversations with specialist agents
- [ ] Phase C: LLM-based intent detection and auto-routing

#### Function Calling & Tools

- [x] Implement function calling support (via LiteLLM) — `feat/tool-calling-web-fetch`
- [x] Web fetch tool (`fetch_url` via httpx + trafilatura) — `feat/tool-calling-web-fetch`
- [ ] Playwright-based fetch tool for JS-rendered pages (job portals, SPAs)
- [ ] Tool approval/permission UI (user confirms before execution)
- [ ] Things 3 write operations as tools (task creation, completion)
- [ ] Obsidian write operations as tools (create/update notes)
- [ ] Web search integration
- [ ] Code execution sandbox
- [ ] File system operations

#### Things 3 Integration (Phase B - Interactive Management)

- [ ] Add MCP server integration for task creation
- [ ] Implement task completion via MCP
- [ ] Task search and filtering
- [ ] Task updates and modifications
- [ ] Localization support in MCP wrapper (if needed)

#### Agent Orchestration

- [x] Multi-agent architecture design (folder convention + registry)
- [ ] Agent communication protocols (JARVIS delegation)
- [ ] Task delegation and routing (LLM-based intent detection)
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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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

## Roadmap Principles

1. **Ship small, iterate fast**: Each phase delivers usable value
2. **Metrics-driven**: Measure before optimizing
3. **User needs first**: Build features that solve real problems
4. **Technical excellence**: Maintain code quality and documentation
5. **Flexibility**: Adjust based on learnings and user feedback

---

*Last updated: 2026-02-27*
