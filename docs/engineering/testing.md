# Testing Strategy

> How we ensure Jarvis works correctly and maintains quality.

---

## Current State

**Phase**: 1 - Manual Testing Only
**Status**: 🔴 Automated testing not yet implemented

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

## Phase 1: Manual Testing (Current)

### What We Test Manually

**Basic Functionality:**
- ✅ CLI starts and accepts input
- ✅ Streaming responses work
- ✅ Token tracking accurate
- ✅ Cost calculation correct
- ✅ Conversation logging saves properly

**Context Usage:**
- 🟡 Spot-check: Does assistant reference profile.md?
- 🟡 Spot-check: Does it follow preferences.md?
- 🟡 Spot-check: Does it acknowledge current_focus.md?

**Provider Switching:**
- 🟡 Can switch models in config.yaml
- 🔴 Haven't tested non-OpenRouter providers yet

---

## Phase 2: Golden Test Suite (Next)

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

## Testing Roadmap

### Phase 1 (Current)
- ✅ Manual testing
- ✅ Type checking with mypy
- 🔴 No automated tests

### Phase 2 (Next 2-3 weeks)
- [ ] Create 5-10 golden test cases
- [ ] Manual evaluation baseline
- [ ] Document expected behaviors

### Phase 3 (1-2 months)
- [ ] Unit tests for all modules
- [ ] Integration tests
- [ ] Golden test automation

### Phase 4 (3-6 months)
- [ ] LLM-as-judge evaluation
- [ ] Performance benchmarks
- [ ] CI/CD integration
- [ ] Regression suite

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

*Last updated: 2026-01-14*
