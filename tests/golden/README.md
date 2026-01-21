# LLM-as-Judge Golden Test Evaluation

This directory contains the LLM-as-judge evaluation system for golden test conversations.

## Overview

The evaluation system automatically assesses the quality of AI assistant responses using a high-quality LLM (Claude Opus 4.5) as a judge. This enables:

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

### Run Golden Tests With Evaluation (Costs ~$0.41)

```bash
# Requires OPENROUTER_API_KEY environment variable
export OPENROUTER_API_KEY="your-key-here"

# Run all 8 golden tests with evaluation
pytest tests/golden/ --evaluate -v

# Run specific test
pytest tests/golden/test_golden_conversations.py::TestGoldenConversations::test_01_basic_qa --evaluate -v

# Use different judge model
pytest tests/golden/ --evaluate --judge-model=anthropic/claude-sonnet-4 -v

# Adjust quality threshold
pytest tests/golden/ --evaluate --quality-threshold=0.80 -v
```

## File Structure

```
tests/golden/
├── conversations/              # 8 YAML test cases
│   ├── 01_basic_qa.yaml
│   ├── 02_context_recall.yaml
│   ├── 03_multi_turn_reasoning.yaml
│   ├── 04_personalization_tone.yaml
│   ├── 05_technical_deep_dive.yaml
│   ├── 06_current_focus_aware.yaml
│   ├── 07_ambiguous_query.yaml
│   └── 08_preferences_adherence.yaml
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
3. **Judge Evaluation**: Send response + criteria to judge (Claude Opus 4.5)
4. **Basic Checks**: Pattern matching, length validation, content verification
5. **Store Results**: Save individual result + aggregate run summary
6. **Generate Report**: Create markdown report with analysis and recommendations
7. **Assert Quality**: Fail test if score < threshold (default 0.70)

## Cost Management

- **Expected Cost**: ~$0.41 per full run (8 tests)
  - Response generation: ~$0.05 (Sonnet 4.5)
  - Judge evaluation: ~$0.36 (Opus 4.5)

- **Budget Limits** (in config.yaml):
  - `max_cost_per_run: 1.00` - Hard limit, aborts if exceeded
  - `warn_cost_threshold: 0.50` - Soft limit, warns but continues

- **Cost Optimization**:
  - Use cheaper judge model: `--judge-model=anthropic/claude-sonnet-4`
  - Run specific tests instead of all 8
  - Skip evaluation in CI, run manually for important changes

## Configuration

Edit `config.yaml` to adjust settings:

```yaml
evaluation:
  judge_model: "anthropic/claude-opus-4.5"
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

### "Cost budget exceeded"

**Solution**: Adjust limits in config.yaml or run fewer tests.

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

- [Implementation Plan](/Users/marcobraun/.claude/plans/majestic-soaring-quasar.md)
- [Testing Documentation](../docs/engineering/testing.md)
- [Product Roadmap](../docs/product/roadmap.md)

---

**Questions?** Check the implementation plan or open an issue on GitHub.
