# Changelog

All notable changes to Jarvis will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added (2026-01-23)
- **Benchmark Report Generator**: `scripts/benchmark_report.py` creates comparison tables in `docs/research/models.md`
- **Model Benchmark Results**: Golden test benchmarks for Sonnet 4.5, Opus 4.5, GPT-5.2, GPT-5.2-Codex, GPT-OSS-120B, Gemini 3 Flash/Pro (preview)
- **Benchmark Runner Resilience**: Continue model runs even when individual evaluations fail

### Changed (2026-01-23)
- **Golden Tests Imports**: Updated golden test runner to use package import paths

### Added (2026-01-22)
- **TTFT (Time to First Token) Tracking**: Integrated latency metrics into CLI and conversation logs
  - CLI now displays TTFT and total latency after each response
  - Session summary includes average TTFT and latency across all requests
  - Conversation JSON logs include latency metrics per message
  - Extended `SessionMetrics` with `average_ttft_ms` and `average_latency_ms` properties
  - New unit test for latency tracking
- **Scalable Monorepo Structure**: Major folder restructure for multi-agent and web interface support
  - New `apps/` directory for deployable applications (CLI, web)
  - New `packages/` directory for shared libraries (core, agents, integrations, telemetry)
  - New `data/` directory for user data (context, conversations)
  - New `config/` directory for configuration files
- **BaseAgent Foundation**: `packages/agents/base.py` with abstract base class for agents
- **JarvisAgent**: Initial orchestrator agent in `packages/agents/jarvis/agent.py`
- **MetricsTracker**: `packages/telemetry/metrics.py` for TTFT and response metrics tracking
- **Web Interface Structure**: `apps/web/` prepared for FastAPI backend + React frontend
- **Web Dependencies**: Added FastAPI, uvicorn, sse-starlette to pyproject.toml
- **Benchmark Cost Estimator**: Estimate golden test run costs per model using OpenRouter pricing

### Changed (2026-01-22)
- **Project Structure**: Migrated from `personal-context/` to monorepo structure
  - `personal-context/src/*.py` → `packages/core/`
  - `personal-context/src/cli.py` → `apps/cli/main.py`
  - `personal-context/src/task_sync.py` → `packages/integrations/things3/`
  - `personal-context/context/` → `data/context/`
  - `personal-context/memory/` → `data/conversations/`
  - `config.yaml` → `config/default.yaml`
- **Import Paths**: All imports now use package paths (e.g., `packages.core.llm_client`)
- **pyproject.toml**: Updated with new package structure and entry points
- **Tests**: Updated with backward-compatible imports (try/except pattern)
- **Documentation**: Updated all docs (AGENTS.md, architecture.md, roadmap.md, deployment.md, decisions.md)

### Documentation (2026-01-22)
- Added ADR-009: Scalable Monorepo Structure to `docs/product/decisions.md`
- Updated `docs/engineering/architecture.md` with new architecture diagram
- Updated `docs/engineering/deployment.md` with new paths and commands
- Updated `docs/product/roadmap.md` with Phase 3 web interface scope
- Updated `AGENTS.md` with new folder structure and import patterns

### Added (2026-01-20 Evening)
- **LLM-as-Judge Evaluation System** - Complete automated quality assessment
  - Core evaluation engine with `JudgeEvaluator` class (~400 lines)
  - Category-specific judge prompts for 4 test types (~200 lines)
  - Result storage with JSON + markdown report generation (~500 lines)
  - 33 additional unit tests (16 evaluator + 17 storage)
  - Pytest plugin with `--evaluate` flag for on-demand evaluation
  - Historical tracking with trend analysis in `tests/golden/results/`
  - Cost management with configurable budget limits ($1.00 max, $0.50 warn)
  - Expected cost: ~$0.41 per full run (8 tests)
  - Uses Claude Opus 4.5 as judge for highest quality evaluations
  - Structured JSON output + markdown reports with recommendations
  - See [tests/golden/README.md](../tests/golden/README.md) for complete usage guide

### Added (2026-01-20 Morning)
- **Things 3 Integration (Phase A)**: Context awareness from Things 3 task manager
- **Automatic Language Detection**: Supports German, French, Spanish, Italian, English Things 3 installations
- **Task Sync Module**: `task_sync.py` (~520 lines) with AppleScript integration
- **Context File**: Auto-generated `tasks.md` included in system prompt
- **Task Caching**: 5-minute TTL cache to optimize performance
- **43 Additional Tests**: 33 unit tests + 8 integration tests + 2 golden tests for task sync
- **MCP Architecture**: Preserved MCPThings3Client class for Phase B (interactive features)

### Changed (2026-01-20 Evening)
- **Test Suite**: Expanded from 116 to 149 tests total (103 unit + 20 integration + 26 golden/evaluation)
- Updated `config.yaml` with evaluation settings (judge model, thresholds, cost limits)
- Modified `conftest.py` to add evaluation fixtures and `--evaluate` flag support
- Modified `test_golden_conversations.py` to implement evaluation execution
- Updated all documentation (AGENTS.md, README.md, testing.md, roadmap.md)

### Changed (2026-01-20 Morning)
- **Test Suite**: Expanded from 73 to 116 tests total
- **Context Builder**: Now loads `tasks.md` as 4th context file
- **CLI Startup**: Added task sync before building system prompt
- **Documentation**: Updated all docs with Things 3 integration details

### Fixed
- **Token Usage Tracking**: Fixed streaming responses not reporting token counts
  - Added `stream_options={"include_usage": True}` to LiteLLM completion calls
  - Modified usage extraction to read from streaming chunks instead of response iterator
  - Suppressed harmless Pydantic serialization warnings in fallback cost calculation
  - Token counts and costs now display correctly after each response

### Technical Details
- Direct AppleScript communication for Phase A (read-only)
- Auto-detects localized Things 3 list names (e.g., "Eingang" vs "Inbox")
- Graceful degradation if Things 3 not running
- File-based cache at `~/.cache/jarvis/tasks_cache.json`
- Custom delimiter (|||) for task titles containing commas

### Documentation
- Added ADR-008 to `docs/product/decisions.md`
- Updated `docs/engineering/architecture.md` with task_sync module
- Updated `docs/product/roadmap.md` with Phase A completion
- Updated `AGENTS.md` with new test counts and structure

---

## [0.3.0] - 2026-01-15

### Added
- **Comprehensive Testing Framework**: Complete test infrastructure with pytest
- **73 Automated Tests**: 53 unit tests + 12 integration tests + 8 golden test scenarios
- **97.5% Code Coverage**: High coverage on all core modules
- **Test Documentation**: Complete testing guides and plans
- **CI/CD Ready**: Infrastructure prepared for GitHub Actions integration

### Testing Infrastructure
- **Unit Tests**:
  - `context_builder.py`: 10 tests, 100% coverage
  - `memory.py`: 15 tests, 97% coverage
  - `pricing.py`: 12 tests, 98% coverage
  - `llm_client.py`: 11 tests, 95% coverage
  - `cli.py`: 5 tests (complex I/O, intentionally skipped)

- **Integration Tests**: 12 tests covering full conversation flows, context integration, and pricing

- **Golden Test Conversations**: 8 YAML test cases covering:
  - Basic Q&A without context
  - Profile information recall
  - Multi-turn technical reasoning
  - Tone matching from preferences
  - Technical deep-dives
  - Current focus awareness
  - Ambiguous query handling
  - Multiple preference adherence

### Test Tools
- pytest 8.0+ with Python 3.13 support
- pytest-cov for coverage reporting
- pytest-mock for mocking
- pytest-xdist for parallel execution
- respx for HTTP mocking
- freezegun for time mocking

### Documentation
- `tests/TESTING_PLAN.md`: Comprehensive 30-file testing plan
- `tests/TEST_RESULTS.md`: Detailed test results and coverage report
- `tests/README.md`: Quick reference guide for running tests
- Updated `docs/engineering/testing.md` with current state
- Updated `docs/product/roadmap.md` (Phase 1: 100% complete)

### Performance
- All unit tests execute in < 1 second
- Full test suite runs in < 2 seconds
- 62/73 tests passing (85% pass rate)
- 11 tests intentionally skipped (manual golden tests + complex CLI)

### Technical Details
- Test fixtures for context files, configurations, and mock responses
- Shared pytest fixtures in `conftest.py`
- HTML coverage reports generated
- Parallel test execution support
- Ready for continuous integration

---

## [0.2.0] - 2026-01-14 (Documentation Release)

### Documentation
- Restructured documentation into organized `/docs` directory
- Created product docs: vision, roadmap, metrics, decisions (ADRs)
- Created engineering docs: architecture, API reference, testing strategy, deployment guide
- Created research docs: AI engineering framework, model comparison, prompt engineering
- Archived original DEVELOPMENT.md for reference

---

## [0.2.1] - 2026-01-14 (LiteLLM Integration)

### Added
- **LiteLLM Integration**: Migrated from raw HTTP to LiteLLM for better provider flexibility
- **Fallback Cost Calculation**: Added LiteLLM-based cost calculation as fallback when OpenRouter pricing unavailable
- **Raw Response Access**: `StreamingResponse` now exposes raw LiteLLM response for advanced use cases
- **Provider Flexibility**: Easy switching between OpenRouter, Anthropic, and OpenAI

### Changed
- **llm_client.py**: Refactored to use LiteLLM instead of manual HTTP requests (112 → 117 lines)
- **pricing.py**: Added `calculate_cost_from_litellm()` function for fallback pricing
- **cli.py**: Updated to use fallback cost calculation when primary pricing fails
- **StreamingResponse**: Now returns tuple of `(TokenUsage, raw_response)` instead of just `TokenUsage`

### Technical Details
- LiteLLM handles SSE parsing, retries, and provider-specific formatting
- Function calling support now available (ready for Phase 5)
- Provider switching requires only config change
- Maintained backward compatibility with existing conversation logs

### Dependencies
- Added: `litellm` (~10MB, includes OpenAI SDK)
- Added transitive dependencies: `aiohttp`, `httpx`, `pydantic`, etc.

---

## [0.1.0] - 2026-01-07

### Added
- **Token Usage Tracking**: Per-request and session-level token counting
- **Cost Calculation**: Real-time cost tracking using OpenRouter pricing API
- **Session Metrics**: Total tokens, cost, and request count saved to conversation JSON
- **Model Comparison Documentation**: Detailed pricing and recommendations for different models

### Changed
- **memory.py**: Enhanced `ConversationLogger` to track token usage and costs
- **pricing.py**: New module for fetching and calculating LLM costs
- **cli.py**: Display token usage and cost after each response
- **Conversation logs**: Now include per-message token counts and session totals

### Documentation
- Added model comparison table with pricing
- Added cost examples for typical usage patterns
- Documented cost optimization strategies

---

## [0.0.1] - 2026-01-05

### Added
- **Initial Release**: Basic personal AI assistant functionality
- **CLI Interface**: Command-line chat interface with streaming responses
- **Context System**: Load user context from markdown files (profile, preferences, current_focus)
- **Conversation Logging**: Save conversations to timestamped JSON files
- **Provider Integration**: OpenRouter API integration for multi-model access
- **Configuration**: YAML-based config with environment variables for API keys

### Core Modules
- `cli.py`: Main entry point and chat loop
- `context_builder.py`: Assemble system prompts from context files
- `llm_client.py`: HTTP client for OpenRouter API with streaming
- `memory.py`: Conversation logging and history management

### Architecture Decisions
- Local-first: All data on user's machine
- Markdown for context: Human-readable, version-controllable
- JSON for conversations: Structured but readable
- No database: Filesystem sufficient at personal scale

### Documentation
- Initial README with project overview
- DEVELOPMENT.md with AI engineering framework
- Basic setup and usage instructions

---

## Release Notes Format

### Version Numbering

Following [Semantic Versioning](https://semver.org/):
- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible

### Categories

Changes are grouped by type:
- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be-removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security fixes
- **Documentation**: Documentation changes

---

## Upcoming Changes (Roadmap)

See [roadmap.md](product/roadmap.md) for detailed plans.

### Phase 2: Evaluation & Metrics (75% Complete)
- ✅ Golden test suite (8 test conversations)
- ✅ LLM-as-judge automated evaluation
- ✅ TTFT tracking (integrated into CLI)
- ⏳ Model benchmarking

### Phase 3: Web Interface + Context Management (Next)
- Web interface (FastAPI + React)
- Conversation search
- Context window management
- Fact extraction (learned_facts.md)

### Phase 4: RAG Implementation
- Vector store integration (ChromaDB/FAISS)
- Semantic search over conversation history
- Hybrid retrieval (semantic + keyword)

### Phase 5: Agent Capabilities
- Function calling support
- Tool integrations (web search, code execution)
- Multi-agent orchestration
- Intelligent model routing
- Things 3 interactive management (Phase B)

---

## Migration Guides

### 0.3.0 → 0.4.0 (Monorepo Restructure)

**Breaking Changes**: Import paths changed

**Migration Steps**:
1. Update imports from old paths to new package paths:
   ```python
   # Old
   from llm_client import LLMClient
   from context_builder import build_system_prompt

   # New
   from packages.core.llm_client import LLMClient
   from packages.core.context_builder import build_system_prompt
   ```

2. Update configuration paths:
   - Context files: `personal-context/context/` → `data/context/`
   - Conversations: `personal-context/memory/conversations/` → `data/conversations/`
   - Config: `config.yaml` → `config/default.yaml`

3. Run CLI with new path:
   ```bash
   uv run python -m apps.cli.main
   # Or
   uv run jarvis
   ```

**Data Compatibility**: Copy your data files to new locations:
```bash
cp -r personal-context/context/* data/context/
cp -r personal-context/memory/conversations/* data/conversations/
```

---

### 0.2.1 → 0.3.0 (Testing Framework)

**Breaking Changes**: None

**New Dependencies**:
```bash
uv sync --extra test
```

**Running Tests**:
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=packages --cov=apps --cov-report=html

# View coverage report
open htmlcov/index.html
```

**Documentation**: See `tests/README.md` for complete testing guide

---

### 0.1.0 → 0.2.1 (LiteLLM Migration)

**Breaking Changes**: None

**New Dependencies**:
```bash
uv add litellm
```

**Configuration Changes**: None required, but you can now switch providers easily:
```python
# In apps/cli/main.py
client = LLMClient(
    api_key=your_key,
    default_model="model-id",
    provider="openrouter"  # or "anthropic", "openai"
)
```

**Data Compatibility**: All existing conversation logs remain compatible.

---

### 0.0.1 → 0.1.0 (Token Tracking)

**Breaking Changes**: None

**New Features**: Automatic token and cost tracking

**Configuration Changes**: None required

**Data Format**: Conversation JSON now includes token metadata (backward compatible)

---

## Contributors

- **Marco Braun** (@Cherubeam) - Creator and maintainer

---

*Last updated: 2026-01-22*
