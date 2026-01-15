# Comprehensive Testing Implementation Plan for Jarvis

## Overview

This plan covers the complete testing setup for Phase 1 completion and Phase 2 preparation, including:
- Testing framework and infrastructure setup
- Unit tests for 100% coverage where feasible
- Integration tests for critical flows
- 8 golden test conversations covering real-world scenarios

---

## 1. Testing Stack & Dependencies

### Dependencies to Add

```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0.0",              # Core test framework
    "pytest-asyncio>=0.23.0",     # Async test support
    "pytest-cov>=4.1.0",          # Coverage reporting
    "pytest-mock>=3.12.0",        # Enhanced mocking
    "pytest-xdist>=3.5.0",        # Parallel execution
    "respx>=0.21.0",              # HTTP mocking for requests
    "freezegun>=1.4.0",           # Time mocking for timestamps
    "pyyaml>=6.0.3",              # Already in deps, for test fixtures
]
```

### Configuration Files to Create

1. **`pytest.ini`** - pytest configuration
2. **`tests/conftest.py`** - Shared fixtures
3. **`.coveragerc`** - Coverage configuration

---

## 2. Project Structure

```
jarvis/
├── personal-context/
│   └── src/
│       ├── cli.py
│       ├── llm_client.py
│       ├── context_builder.py
│       ├── memory.py
│       └── pricing.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py                          # Shared fixtures
│   │
│   ├── unit/                                # Unit tests (isolated, fast)
│   │   ├── __init__.py
│   │   ├── test_context_builder.py          # ~10 tests
│   │   ├── test_memory.py                   # ~15 tests
│   │   ├── test_pricing.py                  # ~12 tests
│   │   ├── test_llm_client.py               # ~8 tests
│   │   └── test_cli.py                      # ~8 tests
│   │
│   ├── integration/                         # Integration tests (with mocks)
│   │   ├── __init__.py
│   │   ├── test_full_conversation_flow.py   # ~5 tests
│   │   ├── test_context_integration.py      # ~4 tests
│   │   └── test_pricing_integration.py      # ~3 tests
│   │
│   ├── golden/                              # Golden test conversations
│   │   ├── __init__.py
│   │   ├── test_golden_conversations.py     # Test runner
│   │   └── conversations/                   # Test case definitions
│   │       ├── 01_basic_qa.yaml
│   │       ├── 02_context_recall.yaml
│   │       ├── 03_multi_turn_reasoning.yaml
│   │       ├── 04_personalization_tone.yaml
│   │       ├── 05_technical_deep_dive.yaml
│   │       ├── 06_current_focus_aware.yaml
│   │       ├── 07_ambiguous_query.yaml
│   │       └── 08_preferences_adherence.yaml
│   │
│   └── fixtures/                            # Test data
│       ├── context/
│       │   ├── profile_test.md
│       │   ├── preferences_test.md
│       │   └── current_focus_test.md
│       ├── config_test.yaml
│       └── mock_responses/
│           └── sample_litellm_response.json
│
├── pytest.ini
├── .coveragerc
└── pyproject.toml
```

---

## 3. Unit Tests - Detailed Breakdown

### 3.1 `test_context_builder.py` (~10 tests, ~100% coverage)

**Module under test**: `personal-context/src/context_builder.py`

| Test Name | Purpose | Coverage Target |
|-----------|---------|----------------|
| `test_load_context_file_exists` | Load existing markdown file successfully | `load_context_file()` happy path |
| `test_load_context_file_missing` | Return empty string for missing file | `load_context_file()` error handling |
| `test_load_context_file_empty` | Handle empty file gracefully | Edge case |
| `test_load_context_file_unicode` | Handle unicode characters properly | Encoding handling |
| `test_build_system_prompt_all_files` | Assemble prompt with all context files present | `build_system_prompt()` happy path |
| `test_build_system_prompt_partial_files` | Assemble with only some files present | Missing file handling |
| `test_build_system_prompt_no_files` | Handle no context files gracefully | Edge case |
| `test_build_system_prompt_section_order` | Verify profile → preferences → focus order | Ordering logic |
| `test_build_system_prompt_prefix_formatting` | Verify prefix is included correctly | Prefix handling |
| `test_build_system_prompt_separator` | Verify sections separated correctly | Formatting |

**Coverage Goal**: 100% - This module is pure functions with no external dependencies.

---

### 3.2 `test_memory.py` (~15 tests, ~95% coverage)

**Module under test**: `personal-context/src/memory.py`

#### SessionMetrics Tests (5 tests)

| Test Name | Purpose |
|-----------|---------|
| `test_session_metrics_init` | Default values initialized correctly |
| `test_session_metrics_add_usage` | Accumulates tokens and cost correctly |
| `test_session_metrics_add_usage_multiple` | Multiple calls accumulate properly |
| `test_session_metrics_to_dict` | Serialization to dict correct |
| `test_session_metrics_zero_cost` | Handles zero cost correctly |

#### ConversationLogger Tests (10 tests)

| Test Name | Purpose |
|-----------|---------|
| `test_conversation_logger_init` | Initializes with correct defaults |
| `test_conversation_logger_creates_dir` | Creates conversations directory if missing |
| `test_add_message_user` | Adds user message correctly |
| `test_add_message_assistant_with_usage` | Adds assistant message with usage data |
| `test_add_message_assistant_without_usage` | Adds assistant message without usage |
| `test_add_message_timestamp_format` | Timestamp in ISO format |
| `test_get_messages_for_api` | Returns messages without timestamps/usage |
| `test_save_conversation_json_structure` | Saves with correct JSON structure |
| `test_save_conversation_filename` | Filename format correct (YYYY-MM-DD_HH-MM-SS.json) |
| `test_save_empty_conversation` | Doesn't save if no messages |

**Coverage Goal**: 95% - Will skip testing `_print_session_summary()` print statements.

---

### 3.3 `test_pricing.py` (~12 tests, ~90% coverage)

**Module under test**: `personal-context/src/pricing.py`

#### ModelPricing Tests (3 tests)

| Test Name | Purpose |
|-----------|---------|
| `test_model_pricing_calculate_cost` | Calculates cost correctly |
| `test_model_pricing_zero_tokens` | Handles zero tokens |
| `test_model_pricing_large_numbers` | Handles large token counts |

#### Pricing API Tests (5 tests)

| Test Name | Purpose |
|-----------|---------|
| `test_fetch_all_pricing_success` | Fetches and parses OpenRouter API response |
| `test_fetch_all_pricing_cached` | Returns cached results on subsequent calls |
| `test_fetch_all_pricing_api_error` | Handles network errors gracefully |
| `test_get_model_pricing_found` | Returns pricing for existing model |
| `test_get_model_pricing_not_found` | Returns None for unknown model |

#### Cost Calculation Tests (4 tests)

| Test Name | Purpose |
|-----------|---------|
| `test_calculate_cost_from_litellm_success` | Uses LiteLLM cost calculation |
| `test_calculate_cost_from_litellm_error` | Handles errors gracefully |
| `test_format_cost_small` | Formats tiny costs (< $0.0001) |
| `test_format_cost_medium` | Formats medium costs (< $0.01) |
| `test_format_cost_large` | Formats large costs (≥ $0.01) |

**Coverage Goal**: 90% - Will skip some error handling print statements.

---

### 3.4 `test_llm_client.py` (~8 tests, ~85% coverage)

**Module under test**: `personal-context/src/llm_client.py`

#### TokenUsage Tests (2 tests)

| Test Name | Purpose |
|-----------|---------|
| `test_token_usage_init` | Default values correct |
| `test_token_usage_with_values` | Stores values correctly |

#### LLMClient Tests (6 tests)

| Test Name | Purpose |
|-----------|---------|
| `test_llm_client_init_openrouter` | Formats OpenRouter model name with prefix |
| `test_llm_client_init_other_provider` | Doesn't add prefix for other providers |
| `test_chat_stream_returns_streaming_response` | Returns StreamingResponse object |
| `test_chat_stream_yields_chunks` | Yields text chunks correctly |
| `test_chat_stream_usage_after_completion` | Usage available after iteration |
| `test_chat_stream_custom_model` | Overrides default model |

**Coverage Goal**: 85% - Will mock LiteLLM calls, skip some LiteLLM internal error handling.

---

### 3.5 `test_cli.py` (~8 tests, ~70% coverage)

**Module under test**: `personal-context/src/cli.py`

#### Configuration Tests (5 tests)

| Test Name | Purpose |
|-----------|---------|
| `test_load_config_success` | Loads config and env correctly |
| `test_load_config_missing_api_key` | Exits with error if API key missing |
| `test_load_config_missing_yaml` | Handles missing config.yaml |
| `test_load_config_paths_resolved` | Resolves paths correctly |
| `test_load_config_env_override` | Environment variables override config |

#### Main Loop Tests (3 tests)

| Test Name | Purpose |
|-----------|---------|
| `test_main_startup_info` | Prints startup information |
| `test_main_handles_quit` | Exits on 'quit' command |
| `test_main_handles_ctrl_c` | Handles KeyboardInterrupt gracefully |

**Coverage Goal**: 70% - Main loop is complex and involves user input, so we'll test key paths only.

---

## 4. Integration Tests - Detailed Breakdown

### 4.1 `test_full_conversation_flow.py` (~5 tests)

**Purpose**: Test end-to-end conversation flow with mocked LiteLLM

| Test Name | Purpose |
|-----------|---------|
| `test_single_turn_conversation` | User input → LLM response → logging |
| `test_multi_turn_conversation` | Multiple back-and-forth exchanges |
| `test_context_included_in_request` | System prompt with context sent to LLM |
| `test_token_tracking_across_turns` | Metrics accumulate correctly |
| `test_cost_calculation_integrated` | Pricing fetched and used |

---

### 4.2 `test_context_integration.py` (~4 tests)

**Purpose**: Verify context system works end-to-end

| Test Name | Purpose |
|-----------|---------|
| `test_context_files_loaded_into_prompt` | All context files included |
| `test_missing_context_files_graceful` | Works with partial context |
| `test_context_order_preserved` | Profile → Preferences → Focus |
| `test_system_prompt_format` | Proper formatting with sections |

---

### 4.3 `test_pricing_integration.py` (~3 tests)

**Purpose**: Test pricing system with real API structure (mocked responses)

| Test Name | Purpose |
|-----------|---------|
| `test_pricing_fetch_and_calculate` | Fetch from API and calculate cost |
| `test_pricing_fallback_to_litellm` | Falls back if OpenRouter unavailable |
| `test_pricing_display_format` | Displays cost correctly in CLI |

---

## 5. Golden Test Conversations

### Overview

8 representative test cases covering the main use patterns for Jarvis. These tests can be run manually initially, then automated with LLM-as-judge evaluation in Phase 2.

---

### 5.1 `01_basic_qa.yaml` - Basic Question Answering

**Category**: Reasoning (30%)
**Purpose**: Verify basic conversational ability without personal context

```yaml
name: "basic_qa"
description: "Simple factual question without requiring personal context"
context: {}  # No personal context needed
conversation:
  - role: "user"
    content: "What is the capital of France?"
  - role: "assistant"
    expected_content:
      - "Paris"
    expected_qualities:
      - accurate: true
      - concise: true
      - confident: true
```

---

### 5.2 `02_context_recall.yaml` - Profile Recall

**Category**: Context Recall (20%)
**Purpose**: Verify assistant references user's profile information

```yaml
name: "context_recall_profile"
description: "Assistant should reference user's profession from profile"
context:
  profile: |
    I am a software engineer with 10 years of experience.
    I specialize in Python and machine learning.
    I'm currently learning about LLM applications.
conversation:
  - role: "user"
    content: "What do I do for work?"
  - role: "assistant"
    expected_themes:
      - "software engineer"
      - "Python"
      - "machine learning"
    expected_qualities:
      - references_profile: true
      - natural_tone: true  # Shouldn't say "according to your profile"
```

---

### 5.3 `03_multi_turn_reasoning.yaml` - Multi-turn Technical Discussion

**Category**: Reasoning (30%)
**Purpose**: Verify multi-step reasoning and context retention across turns

```yaml
name: "multi_turn_reasoning"
description: "Technical explanation followed by clarification questions"
context: {}
conversation:
  - role: "user"
    content: "Explain how transformer models work in AI"
  - role: "assistant"
    expected_qualities:
      - technical_depth: "high"
      - includes_examples: true
      - min_length: 200
      - max_length: 600
  - role: "user"
    content: "How does attention differ from previous approaches?"
  - role: "assistant"
    expected_qualities:
      - builds_on_previous: true
      - specific_comparison: true
      - references_earlier_explanation: true
```

---

### 5.4 `04_personalization_tone.yaml` - Tone Matching

**Category**: Personalization (25%)
**Purpose**: Verify assistant follows tone preferences

```yaml
name: "personalization_tone"
description: "Assistant should match concise, technical tone from preferences"
context:
  preferences: |
    - Be concise and technical
    - Avoid unnecessary pleasantries
    - Use technical jargon appropriately
    - No fluff or over-explanation
conversation:
  - role: "user"
    content: "Explain REST APIs"
  - role: "assistant"
    expected_qualities:
      - concise: true
      - technical_language: true
      - no_pleasantries: true
      - direct: true
    forbidden_patterns:
      - "I'd be happy to"
      - "Of course!"
      - "Let me explain in simple terms"
```

---

### 5.5 `05_technical_deep_dive.yaml` - Deep Technical Query

**Category**: Reasoning (30%)
**Purpose**: Verify ability to handle complex technical questions

```yaml
name: "technical_deep_dive"
description: "Complex technical question requiring detailed explanation"
context:
  profile: |
    I am a software engineer specializing in distributed systems.
conversation:
  - role: "user"
    content: "What are the tradeoffs between consistency models in distributed databases?"
  - role: "assistant"
    expected_themes:
      - "CAP theorem"
      - "eventual consistency"
      - "strong consistency"
      - "tradeoffs"
    expected_qualities:
      - technical_depth: "very high"
      - structured_response: true
      - includes_examples: true
      - min_length: 300
```

---

### 5.6 `06_current_focus_aware.yaml` - Current Focus Awareness

**Category**: Context Recall (20%)
**Purpose**: Verify assistant acknowledges current priorities

```yaml
name: "current_focus_aware"
description: "Assistant should be aware of current projects and priorities"
context:
  current_focus: |
    I'm currently building a personal AI assistant called Jarvis.
    My main focus is implementing a testing framework this week.
    I'm using pytest and planning golden test conversations.
conversation:
  - role: "user"
    content: "What am I working on right now?"
  - role: "assistant"
    expected_themes:
      - "Jarvis"
      - "testing"
      - "pytest"
    expected_qualities:
      - references_current_focus: true
      - acknowledges_priorities: true
```

---

### 5.7 `07_ambiguous_query.yaml` - Ambiguity Handling

**Category**: Edge Cases (25%)
**Purpose**: Verify graceful handling of vague questions

```yaml
name: "ambiguous_query"
description: "Assistant should ask for clarification on vague questions"
context:
  profile: |
    I am a software engineer learning AI.
conversation:
  - role: "user"
    content: "What should I do?"
  - role: "assistant"
    expected_qualities:
      - asks_clarification: true
      - acknowledges_ambiguity: true
      - offers_suggestions: true
      - respectful_tone: true
    forbidden_patterns:
      - "I don't know"
      - "I can't help"
```

---

### 5.8 `08_preferences_adherence.yaml` - Multiple Preferences

**Category**: Personalization (25%)
**Purpose**: Verify assistant follows multiple preference rules simultaneously

```yaml
name: "preferences_adherence"
description: "Assistant should follow multiple preference guidelines at once"
context:
  profile: |
    I am a busy startup founder.
  preferences: |
    - Be extremely concise (max 3 sentences per response unless I ask for more)
    - Use bullet points when listing things
    - Skip greetings and sign-offs
    - Be direct and actionable
conversation:
  - role: "user"
    content: "What are the key metrics for SaaS startups?"
  - role: "assistant"
    expected_qualities:
      - max_sentences: 3
      - uses_bullet_points: true
      - no_greeting: true
      - no_sign_off: true
      - actionable: true
```

---

## 6. Test Coverage Goals

| Module | Target Coverage | Rationale |
|--------|----------------|-----------|
| `context_builder.py` | 100% | Pure functions, easy to test |
| `memory.py` | 95% | Skip print statements |
| `pricing.py` | 90% | Skip some error logging |
| `llm_client.py` | 85% | External dependency (LiteLLM) |
| `cli.py` | 70% | Complex I/O, user interaction |
| **Overall** | **85%+** | High confidence without over-testing |

---

## 7. Implementation Phases

### Phase 1: Setup (1-2 hours)
1. Add test dependencies to `pyproject.toml`
2. Create `pytest.ini` configuration
3. Create `tests/conftest.py` with shared fixtures
4. Create directory structure
5. Create test fixture files

### Phase 2: Unit Tests (4-6 hours)
1. `test_context_builder.py` - 10 tests
2. `test_memory.py` - 15 tests
3. `test_pricing.py` - 12 tests
4. `test_llm_client.py` - 8 tests
5. `test_cli.py` - 8 tests

### Phase 3: Integration Tests (2-3 hours)
1. `test_full_conversation_flow.py` - 5 tests
2. `test_context_integration.py` - 4 tests
3. `test_pricing_integration.py` - 3 tests

### Phase 4: Golden Tests (2-3 hours)
1. Create 8 YAML test case files
2. Create test runner (`test_golden_conversations.py`)
3. Manual baseline run and documentation

**Total Estimated Time: 9-14 hours** (can be split across multiple sessions)

---

## 8. Success Criteria

### Phase 1 Completion
- ✅ Testing framework fully set up
- ✅ 53+ unit tests passing
- ✅ 12+ integration tests passing
- ✅ 8 golden test cases defined
- ✅ Overall code coverage ≥ 85%

### Quality Gates
- All unit tests run in < 5 seconds
- All integration tests run in < 30 seconds
- Golden tests can be run manually with clear pass/fail
- No decrease in existing functionality

---

## 9. Future Enhancements (Phase 2+)

1. **LLM-as-Judge Automation**
   - Automate golden test evaluation
   - Use cheap model (GPT-4o-mini or Haiku)
   - Cost budget: $0.10 per test suite run

2. **Performance Benchmarks**
   - TTFT (Time to First Token) tracking
   - Response latency tracking
   - Context loading benchmarks

3. **Continuous Testing**
   - GitHub Actions CI/CD
   - Automated regression detection
   - Nightly golden test runs

---

## 10. Files to Create (Summary)

### Configuration (3 files)
- `pytest.ini`
- `.coveragerc`
- `pyproject.toml` (modify)

### Test Code (13 files)
- `tests/conftest.py`
- `tests/unit/test_context_builder.py`
- `tests/unit/test_memory.py`
- `tests/unit/test_pricing.py`
- `tests/unit/test_llm_client.py`
- `tests/unit/test_cli.py`
- `tests/integration/test_full_conversation_flow.py`
- `tests/integration/test_context_integration.py`
- `tests/integration/test_pricing_integration.py`
- `tests/golden/test_golden_conversations.py`

### Test Fixtures (12+ files)
- `tests/fixtures/context/*.md` (3 files)
- `tests/fixtures/config_test.yaml`
- `tests/golden/conversations/*.yaml` (8 files)

**Total: ~30 files**

---

## 11. Running Tests

### Run All Tests
```bash
pytest
```

### Run Unit Tests Only
```bash
pytest tests/unit/
```

### Run Integration Tests Only
```bash
pytest tests/integration/
```

### Run Golden Tests Only
```bash
pytest tests/golden/
```

### Run with Coverage
```bash
pytest --cov=personal-context/src --cov-report=html
```

### Run in Parallel
```bash
pytest -n auto
```

### Run Specific Test File
```bash
pytest tests/unit/test_context_builder.py
```

### Run Specific Test
```bash
pytest tests/unit/test_context_builder.py::test_load_context_file_exists
```

---

*Last updated: 2026-01-15*
