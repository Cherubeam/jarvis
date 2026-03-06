# Testing Strategy

> How we ensure Jarvis works correctly and maintains quality.

---

## Current State

**Phase**: 1 Complete ✅ + Phase 2 Complete ✅
**Status**: 🟢 Comprehensive automated testing + LLM-as-judge evaluation
**Coverage**: 97.5% on core modules
**Tests**: Run `uv run pytest` for current counts
**Documentation**: [tests/README.md](../../tests/README.md), [tests/golden/README.md](../../tests/golden/README.md), [tests/TESTING_PLAN.md](../../tests/TESTING_PLAN.md)

---

## Testing Philosophy

### Priorities

1. **Correctness**: Does it give accurate, helpful responses?
2. **Reliability**: Does it work consistently?
3. **Regressions**: Do changes break existing functionality?
4. **Cost**: Are we within budget expectations?

### Approach

- **Quality > Coverage**: Better to have 10 meaningful tests than 100 trivial ones
- **Golden tests first**: Real user scenarios, not synthetic edge cases
- **Manual baselines**: Establish quality expectations before automation
- **Gradual automation**: Start manual, automate as patterns emerge

---

## Phase 1: Automated Testing Framework (Complete ✅)

### Testing Infrastructure

**Test Framework Stack:**
- ✅ pytest 8.0+ with Python 3.13 support
- ✅ pytest-asyncio for async test support
- ✅ pytest-cov for coverage reporting
- ✅ pytest-mock for enhanced mocking
- ✅ pytest-xdist for parallel execution
- ✅ respx for HTTP mocking
- ✅ freezegun for time mocking

**Test Structure:**
```
tests/
├── unit/              # Fast, isolated (includes evaluator tests)
├── integration/       # 22 tests - With mocked dependencies
├── golden/            # LLM-as-judge evaluation system
│   ├── conversations/ # 8 YAML test cases
│   ├── results/       # Evaluation results (JSON + markdown)
│   ├── evaluator.py   # Core evaluation engine
│   ├── judge_prompts.py  # Judge prompt templates
│   ├── result_storage.py # Storage & reporting
│   └── test_golden_conversations.py  # Test runner
├── fixtures/          # Test data and shared fixtures
└── conftest.py        # Shared pytest fixtures + --evaluate flag
```

### Automated Test Coverage

**Unit Tests (97.5% coverage on core):**
- ✅ `context_builder.py` - 40 tests, 100% coverage (incl. frontmatter parsing, filtering, project index)
- ✅ `memory.py` - 52 tests, 97% coverage (schema v1.0.0 expansion)
- ✅ `pricing.py` - 16 tests, 98% coverage
- ✅ `llm_client.py` - 11 tests, 95% coverage
- ✅ `task_sync.py` - 26 tests, 98% coverage
- ✅ `evaluator.py` - 16 tests, 100% coverage (LLM-as-judge)
- ✅ `result_storage.py` - 17 tests, 100% coverage (evaluation results)
- ✅ `chatgpt importer` - 54 tests, 100% coverage
- ✅ `claude importer` - 59 tests, 100% coverage
- ✅ `claude context importer` - 41 tests, 100% coverage
- ✅ `benchmark_costs.py` - 4 tests
- ✅ `cli.py` - 8 tests
- ✅ `analyze_context.py` - 31 tests (context utilization analysis)
- ✅ `analyze_costs.py` - 32 tests (cost-by-type analysis)

**Integration Tests:**
- ✅ Full conversation flow (5 tests)
- ✅ Context system integration (4 tests)
- ✅ Pricing system integration (3 tests)
- ✅ Task sync integration (8 tests)
- ✅ Configuration integration (2 tests)

**Golden Test Cases:**
- ✅ 8 conversation scenarios (YAML format):
  - Basic Q&A without context
  - Profile information recall
  - Multi-turn technical reasoning
  - Tone matching from preferences
  - Complex technical deep-dives
  - Current focus awareness
  - Ambiguous query handling
  - Multiple preference adherence
- ✅ 2 structure validation tests (free, always run)
- ✅ 8 LLM-as-judge evaluation tests (requires `--evaluate` flag)
- ✅ 8 helper function tests

### Test Execution Performance

- ⚡ All unit tests run in < 1 second
- ⚡ Full test suite runs in < 2 seconds
- 📊 HTML coverage reports generated

### Running Tests

```bash
# Run all tests (free, no LLM calls)
uv run pytest

# Run with coverage
uv run pytest --cov=packages --cov=apps --cov-report=html

# Run specific category
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
uv run pytest tests/golden/ -v  # Structure validation only (free)

# Run golden tests WITH evaluation (costs ~$0.41, requires API key)
export OPENROUTER_API_KEY="your-key"
uv run pytest tests/golden/ --evaluate -v

# View coverage
open htmlcov/index.html
```

See [tests/README.md](../../tests/README.md) and [tests/golden/README.md](../../tests/golden/README.md) for complete guides.

---

## Phase 2: LLM-as-Judge Evaluation (Complete ✅)

**Goal**: Automated quality assessment of golden test conversations
**Status**: ✅ Implemented 2026-01-20
**Cost**: ~$0.41 per full run (8 tests)

### System Architecture

The LLM-as-judge system uses Claude Opus 4.5 as an expert evaluator to assess response quality against defined criteria.

**Components:**
- **evaluator.py**: Core evaluation engine with `JudgeEvaluator` class
- **judge_prompts.py**: Category-specific prompt templates
- **result_storage.py**: JSON persistence + markdown report generation
- **test_golden_conversations.py**: Pytest integration with `--evaluate` flag

### Test Categories

1. **Reasoning** (2 tests): Technical accuracy and clarity
2. **Context Recall** (2 tests): Personal context awareness
3. **Personalization** (2 tests): Tone and preference adherence
4. **Edge Cases** (2 tests): Ambiguity handling

### Evaluation Workflow

```
1. Load YAML test case
   ↓
2. Execute conversation with model under test (e.g., Sonnet 4.5)
   ↓
3. Send to judge (Opus 4.5) with evaluation criteria
   ↓
4. Judge returns structured JSON with scores + reasoning
   ↓
5. Basic checks (forbidden patterns, expected content)
   ↓
6. Store results (JSON + markdown report)
   ↓
7. Assert on quality threshold (default: 0.70)
```

### Usage

**Run Without Evaluation (Free):**
```bash
pytest tests/golden/  # Structure validation only, tests skip
```

**Run With Evaluation (~$0.41):**
```bash
export OPENROUTER_API_KEY="your-key"
pytest tests/golden/ --evaluate -v

# With custom settings
pytest tests/golden/ --evaluate \
  --judge-model=anthropic/claude-opus-4.5 \
  --quality-threshold=0.75 \
  -v
```

### Results

**JSON Results** (per test):
```json
{
  "test_name": "basic_qa",
  "model_tested": "anthropic/claude-sonnet-4.5",
  "judge_model": "anthropic/claude-opus-4.5",
  "evaluation": {
    "overall_score": 0.95,
    "dimension_scores": {"accurate": 1.0, "concise": 0.9},
    "reasoning": "Perfect factual answer, slightly verbose",
    "passed_criteria": ["accurate", "concise"],
    "failed_criteria": []
  },
  "passed": true,
  "costs": {
    "response_cost_usd": 0.007,
    "judge_cost_usd": 0.011,
    "total_cost_usd": 0.018
  }
}
```

**Markdown Report** (generated per run):
- Executive summary (pass rate, avg scores, costs)
- Per-test results table
- Failed tests detail with judge reasoning
- Cost analysis
- Performance metrics
- Recommendations

**Historical Tracking** (`tests/golden/results/history.json`):
- Quality trends over time
- Cost trends
- Pass rate evolution
- Comparison across runs

### Cost Management

**Budget Configuration** (in `config.yaml`):
```yaml
evaluation:
  judge_model: "anthropic/claude-opus-4.5"
  quality_threshold: 0.70
  max_cost_per_run: 1.00  # Hard limit (aborts)
  warn_cost_threshold: 0.50  # Soft limit (warns)
```

**Expected Costs per Run:**
- Response generation (Sonnet 4.5): ~$0.05 (8 tests × $0.006)
- Judge evaluation (Opus 4.5): ~$0.36 (8 tests × $0.045)
- **Total**: ~$0.41 per full run

### Quality Scoring

- **1.0**: Excellent - Exceeds expectations
- **0.8-0.9**: Good - Meets all criteria well
- **0.6-0.7**: Acceptable - Meets minimum requirements
- **0.4-0.5**: Poor - Missing key elements
- **0.0-0.3**: Failing - Does not meet criteria

**Default threshold**: 0.70 (acceptable minimum)

### Adding New Golden Tests

1. Create YAML in `tests/golden/conversations/`:
```yaml
name: "my_test"
category: "reasoning"
context:
  profile: "Optional context"
conversation:
  - role: "user"
    content: "User query"
  - role: "assistant"
    expected_qualities:
      accurate: true
    forbidden_patterns: ["bad phrase"]
```

2. Add test method to `test_golden_conversations.py`
3. Run evaluation: `pytest tests/golden/test_golden_conversations.py::TestGoldenConversations::test_my_test --evaluate`

See [tests/golden/README.md](../../tests/golden/README.md) for complete documentation.

---

## Phase 3: Golden Test Suite (Legacy)

**Goal**: Create 5-10 representative test conversations

### Test Categories

#### 1. Context Recall Tests (20%)
Verify the assistant uses personal context appropriately.

**Example Test Case:**
```yaml
name: "profile_recall"
context_files:
  - profile.md: "I am a software engineer learning AI."
messages:
  - user: "What do I do for work?"
  - expected_themes:
      - software engineering
      - AI learning
      - references_profile: true
```

#### 2. Reasoning Tests (30%)
Multi-step problem solving and technical explanations.

**Example Test Case:**
```yaml
name: "technical_explanation"
messages:
  - user: "Explain how LLM context windows work"
  - expected_qualities:
      - technical_depth: high
      - clear_examples: true
      - appropriate_length: 3-5 paragraphs
```

#### 3. Personalization Tests (25%)
Tone, style, domain knowledge matching preferences.

**Example Test Case:**
```yaml
name: "tone_matching"
context_files:
  - preferences.md: "Be concise and technical."
messages:
  - user: "How does Git work?"
  - expected_qualities:
      - concise: true
      - technical_language: true
      - no_fluff: true
```

#### 4. Edge Cases (25%)
Handling ambiguity, refusals, uncertainty.

**Example Test Case:**
```yaml
name: "ambiguous_query"
messages:
  - user: "What should I do?"
  - expected_behavior:
      - asks_clarification: true
      - acknowledges_ambiguity: true
```

---

## Phase 3: Automated Testing

### Unit Tests

Test individual modules in isolation.

**Example: `test_context_builder.py`**
```python
def test_load_context_file():
    """Test loading a markdown file"""
    path = Path("test_data/profile.md")
    content = load_context_file(path)
    assert "software engineer" in content

def test_build_system_prompt():
    """Test system prompt assembly"""
    prompt = build_system_prompt(
        Path("test_data/context"),
        "You are helpful."
    )
    assert "You are helpful." in prompt
    assert "## About this person" in prompt
```

**Example: `test_pricing.py`**
```python
def test_calculate_cost():
    """Test cost calculation"""
    pricing = ModelPricing(
        prompt_cost=0.000003,
        completion_cost=0.000015,
        model_id="test-model"
    )
    cost = pricing.calculate_cost(1000, 200)
    assert cost == 0.006  # (1000*0.000003) + (200*0.000015)
```

---

### Integration Tests

Test full request flow with mocked LLM.

**Example: `test_cli_integration.py`**
```python
@mock.patch('litellm.completion')
def test_full_conversation_flow(mock_completion):
    """Test complete conversation flow"""
    # Mock LLM response
    mock_completion.return_value = create_mock_stream("Hello!")

    # Run conversation
    config = load_config()
    client = LLMClient(...)
    logger = ConversationLogger(...)

    # Simulate user input
    logger.add_message("user", "Hi")
    stream = client.chat_stream(...)
    response = "".join(stream)
    logger.add_message("assistant", response)

    # Assert
    assert response == "Hello!"
    assert logger.message_count == 2
```

---

### Golden Test Runner

Automated evaluation of golden test suite.

**Test Runner Flow:**
```python
# Pseudocode
for test in golden_tests:
    # 1. Setup context
    load_context_files(test.context_files)

    # 2. Run conversation
    response = run_conversation(test.messages)

    # 3. Evaluate
    scores = evaluate_response(response, test.expected)

    # 4. Report
    report_results(test.name, scores)
```

**Evaluation Methods:**
1. **Keyword matching**: Check for required themes/terms
2. **LLM-as-judge**: Use another LLM to score quality
3. **Manual review**: Flag for human evaluation

---

## Evaluation Metrics

### Response Quality Dimensions

| Dimension | Weight | Measurement |
|-----------|--------|-------------|
| Accuracy | 30% | Factual correctness |
| Relevance | 25% | Addresses query directly |
| Personalization | 20% | Uses context appropriately |
| Helpfulness | 15% | Actionable and useful |
| Tone | 10% | Matches preferences |

### Success Criteria

**Per Test:**
- Overall score ≥ 80%
- No dimension < 60%
- Critical failures = 0

**Test Suite:**
- 95% of tests passing
- No regressions on existing tests
- New features covered by new tests

---

## LLM-as-Judge Framework

Use a separate LLM to evaluate response quality.

**Evaluation Prompt Template:**
```
Evaluate the following assistant response:

USER QUERY: {query}
ASSISTANT RESPONSE: {response}

Score each dimension (0-10):
1. Accuracy: Is the information correct?
2. Relevance: Does it address the query?
3. Personalization: Does it use context appropriately?
4. Helpfulness: Is it actionable?
5. Tone: Does it match the requested style?

Provide scores and brief justification.
```

**Pros:**
- Scales to many test cases
- Catches nuanced quality issues
- Consistent evaluation

**Cons:**
- Costs money (use cheap model)
- May miss specific requirements
- Requires careful prompt engineering

---

## Performance Testing

### Latency Benchmarks

**Targets:**
- Time to First Token (TTFT): < 1 second
- Full response: < 10 seconds
- Context loading: < 100ms

**Measurement:**
```python
import time

start = time.time()
stream = client.chat_stream(messages)
first_token = time.time()
for chunk in stream:
    pass
end = time.time()

ttft = first_token - start
total = end - start
```

### Cost Testing

Track costs across test suite runs.

**Budget Constraints:**
- Test suite run: < $0.10
- Daily testing: < $1.00
- Use cheap models for tests

---

## Regression Testing

### Automated Regression Detection

Run golden tests on every significant change:
- New features
- Refactoring
- Dependency updates

**CI/CD Integration (Future):**
```yaml
# .github/workflows/test.yml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run golden tests
        run: python -m pytest tests/golden
```

### When to Update Tests

**Update test expectations when:**
- Intentional behavior change
- Better response quality
- New features added

**Never update to pass failing tests!**
- Investigate why it failed first
- Fix the code, not the test

---

## Testing Tools

### Current Stack (Planned)

- **pytest**: Test runner
- **pytest-mock**: Mocking LLM responses
- **pytest-benchmark**: Performance testing
- **coverage.py**: Code coverage

### Future Tools

- **Langfuse/PromptLayer**: LLM observability
- **DeepEval**: LLM evaluation framework
- **Custom dashboard**: Test results visualization

---

## Test Data Management

### Test Fixtures

Store test data in `tests/fixtures/`:
```
tests/
├── fixtures/
│   ├── context/
│   │   ├── profile_test.md
│   │   ├── preferences_test.md
│   │   └── current_focus_test.md
│   ├── conversations/
│   │   └── sample_conversation.json
│   └── golden_tests.yaml
└── test_*.py
```

### Golden Test Format

```yaml
golden_tests:
  - name: "context_recall_profile"
    description: "Assistant should reference user's profession"
    context:
      profile: "I am a software engineer."
    conversation:
      - role: "user"
        content: "What do I do?"
      - role: "assistant"
        expected_themes:
          - "software engineer"
          - "programming"
        required_context_usage: true

  - name: "technical_explanation"
    description: "Explain technical concept clearly"
    conversation:
      - role: "user"
        content: "Explain how transformers work in AI"
      - role: "assistant"
        expected_qualities:
          min_length: 100
          max_length: 500
          technical_depth: "high"
          includes_examples: true
```

---

## Benchmark Cost Estimation

Estimate model comparison costs before running golden evaluations:

```bash
uv run python scripts/model_benchmark.py
```

Generate the benchmark comparison table in docs:

```bash
uv run python scripts/benchmark_report.py
```

Notes:
- Uses the most recent golden test run in `tests/golden/results/runs/` as the token baseline.
- Pulls current pricing from the OpenRouter model list endpoint.
- Skips models without pricing (emits a warning).
- Add `--evaluate` to run evaluations after the estimate.

---

## Testing Roadmap

### Phase 1 (Complete ✅)
- ✅ Testing framework setup
- ✅ Unit tests for all core modules
- ✅ Integration tests (22 tests)
- ✅ Golden test case definitions (8 scenarios)
- ✅ 97.5% code coverage on core modules
- ✅ Comprehensive test documentation

### Phase 2 (Complete ✅)
- [x] Create golden test conversation suite (8 cases) ✅
- [x] Implement automated test runner (pytest) ✅
- [x] Add LLM-as-judge for automated quality evaluation ✅
- [x] Manual baseline evaluation of golden tests ✅
- [x] Latency tracking (TTFT) ✅
- [x] Model comparison benchmarks ✅
- [x] Benchmark cost estimation for model comparisons ✅

### Phase 3 (1-2 months)
- [ ] Automated LLM-as-judge evaluation
- [ ] Performance benchmarks integration
- [ ] CI/CD integration (GitHub Actions)
- [ ] Regression detection system

### Phase 4 (3-6 months)
- [ ] Continuous quality monitoring
- [ ] Alert system for quality degradation
- [ ] A/B testing framework for prompt changes
- [ ] Cost optimization tracking

---

## Best Practices

### Writing Good Tests

1. **Test behavior, not implementation**
   - ✅ "Assistant references user's profession"
   - ❌ "Profile.md contents appear in response"

2. **Make tests deterministic**
   - Mock LLM responses for unit tests
   - Use temperature=0 for integration tests
   - Document expected variability

3. **Keep tests independent**
   - No shared state between tests
   - Clean up after each test
   - Order shouldn't matter

4. **Test real scenarios**
   - Based on actual usage
   - Cover common patterns
   - Include edge cases users hit

---

*Last updated: 2026-03-06*
