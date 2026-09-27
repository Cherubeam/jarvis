# LLM-as-Judge Golden Test Evaluation

This directory contains the LLM-as-judge evaluation system for golden test conversations.

## Overview

The evaluation system automatically assesses the quality of AI assistant responses using a high-quality LLM (`evaluation.judge_model`, currently Claude Opus 5.5) as a judge. This enables:

- Automated quality evaluation of responses
- Regression detection across code changes
- Model comparison benchmarks
- Quality trend tracking over time

## Quick Start

### Run Golden Tests Without Evaluation (Free)

```bash
# Skip golden tests (they won't run by default)
pytest tests/golden/

# Run only structure validation tests
pytest tests/golden/test_golden_conversations.py::TestGoldenConversationStructure -v
```

### Run Golden Tests With Evaluation (Costs ~$0.20–0.50 per model)

```bash
# Requires OPENROUTER_API_KEY environment variable
export OPENROUTER_API_KEY="your-key-here"

# Run all 14 golden tests with evaluation
pytest tests/golden/ --evaluate -v

# Run specific test
pytest tests/golden/test_golden_conversations.py::TestGoldenConversations::test_01_basic_qa --evaluate -v

# Use different judge model
pytest tests/golden/ --evaluate --judge-model=google/gemini-3.8-flash -v

# Adjust quality threshold
pytest tests/golden/ --evaluate --quality-threshold=0.80 -v
```

### Benchmarking Several Models

Run models **one at a time**. Parallel runs share one OpenRouter in-flight credit
budget and fail with 402 `in_flight_budget_exhausted`. On a low balance, every call
must fit the remaining credit, so the harness caps output (`models.default_max_tokens`
for the model under test, 4,096 for the judge).

```bash
DEFAULT_MODEL=openai/gpt-6-luna uv run --env-file .env pytest tests/golden/ --evaluate
```

### Exact-Match Checks

An assistant turn can list `required_verbatim` strings (URLs, frontmatter lines).
They must appear case-sensitively in the answer; a missing one caps the score at
0.3, like a forbidden pattern. Test 14 uses it for link preservation.

## File Structure

```
tests/golden/
├── conversations/              # 14 YAML test cases (15 scored results; 03 is scored per turn)
│   ├── 01–08_*.yaml            # conversation cases
│   ├── 09–12_*.yaml            # agentic tool-use cases
│   └── 13–14_*.yaml            # writing cases (voice rules, link preservation)
├── results/                    # Evaluation results storage
│   ├── runs/                   # Individual run results (JSON)
│   ├── reports/                # Human-readable markdown reports
│   └── history.json            # Historical metrics tracking
├── evaluator.py                # Core evaluation engine
├── judge_prompts.py            # Judge prompt templates
├── result_storage.py           # Results persistence & reporting
└── test_golden_conversations.py  # Test runner
```

## How It Works

1. **Load Test Case**: Read YAML file with expected qualities and context
2. **Execute Conversation**: Call model under test with context
3. **Judge Evaluation**: Send response + criteria to judge (`evaluation.judge_model`, currently Claude Opus 5.5)
4. **Basic Checks**: Pattern matching, length validation, content verification
5. **Store Results**: Save individual result + aggregate run summary
6. **Generate Report**: Create markdown report with analysis and recommendations
7. **Assert Quality**: Fail test if score < threshold (default 0.70)

## Cost Management

- **Expected Cost**: roughly $0.20–0.50 per model per full run (Opus 5.5 judge ~$0.15–0.25 of it; 2026-09 measurements)

- **Budget Limits** (`evaluation.*` in `config/default.yaml`): `max_cost_per_run` and `warn_cost_threshold` are declared but **not enforced by the harness yet**. Check the OpenRouter balance before and after a run instead.

- **Cost Optimization**:
  - Use cheaper judge model: `--judge-model=google/gemini-3.8-flash`
  - Run specific tests instead of all 14
  - Skip evaluation in CI, run manually for important changes

## Configuration

Edit `config/local.yaml` (overrides `config/default.yaml`) to adjust settings:

```yaml
evaluation:
  judge_model: "anthropic/claude-opus-5.5"
  quality_threshold: 0.70

  category_thresholds:
    reasoning: 0.75        # Higher bar for reasoning
    context_recall: 0.70
    personalization: 0.70
    edge_cases: 0.65       # Lower bar for edge cases

  max_cost_per_run: 1.00
  warn_cost_threshold: 0.50
```

## Viewing Results

### Markdown Reports

```bash
# View latest report
cat tests/golden/results/reports/$(ls -t tests/golden/results/reports/ | head -1)

# View specific run report
cat tests/golden/results/reports/2026-01-20_15-30-45.md
```

### JSON Results

```bash
# View run summary
cat tests/golden/results/runs/2026-01-20_15-30-45/run_summary.json

# View individual test result
cat tests/golden/results/runs/2026-01-20_15-30-45/01_basic_qa.json

# View historical trends
cat tests/golden/results/history.json
```

## Adding New Golden Tests

1. Create YAML file in `conversations/`:

```yaml
name: "my_new_test"
description: "Test description"
category: "reasoning"  # or context_recall, personalization, edge_cases
context:
  profile: "Optional profile info"
  preferences: "Optional preferences"
conversation:
  - role: "user"
    content: "User query"
  - role: "assistant"
    expected_qualities:
      accurate: true
      concise: true
    forbidden_patterns:
      - "bad phrase"
    expected_content:
      - "expected keyword"
```

2. Add test method to `test_golden_conversations.py`:

```python
def test_09_my_new_test(self, evaluator, evaluation_config, result_storage):
    """Test description."""
    self._run_golden_test("09_my_new_test.yaml", evaluator, evaluation_config, result_storage)
```

3. Run evaluation:

```bash
pytest tests/golden/test_golden_conversations.py::TestGoldenConversations::test_09_my_new_test --evaluate -v
```

## Understanding Scores

- **1.0**: Excellent - Exceeds expectations
- **0.8-0.9**: Good - Meets all criteria well
- **0.6-0.7**: Acceptable - Meets minimum requirements
- **0.4-0.5**: Poor - Missing key elements
- **0.0-0.3**: Failing - Does not meet criteria

**Default threshold**: 0.70 (acceptable minimum)

## Troubleshooting

### Tests Skip Automatically

**Solution**: Add `--evaluate` flag to enable evaluation.

### "OPENROUTER_API_KEY environment variable not set"

**Solution**: Export your API key:
```bash
export OPENROUTER_API_KEY="your-key-here"
```

### 402 "in_flight_budget_exhausted" or "can only afford N tokens"

**Solution**: Run one model at a time (parallel runs share OpenRouter's in-flight credit budget), and top up when the balance is low: every call must fit the remaining credit.

### Judge evaluation fails

The system will fall back to basic checks (pattern matching, length validation) and continue with a conservative score. Check the reasoning field in results for details.

## Integration with CI/CD

For continuous integration, consider:

1. **Run structure tests only** (free):
   ```bash
   pytest tests/golden/test_golden_conversations.py::TestGoldenConversationStructure
   ```

2. **Run evaluation on main branch only** (costs money):
   ```bash
   if [ "$BRANCH" = "main" ]; then
     pytest tests/golden/ --evaluate
   fi
   ```

3. **Run evaluation manually** before major releases.

## Further Reading

- [Testing Documentation](../../docs/engineering/testing.md)
- [Product Roadmap](../../docs/product/roadmap.md)
- [Model benchmark results](../../docs/research/models.md)

---

**Questions?** Check the testing documentation or open an issue on GitHub.
