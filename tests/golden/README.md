# LLM-as-Judge Golden Test Evaluation

This directory contains the LLM-as-judge evaluation system for golden test conversations. This
README is the reference for the golden suite (cases, judge, cost, running, adding tests, scoring,
benchmarking); other docs link here. Testing strategy overall is in
[docs/engineering/testing.md](../../docs/engineering/testing.md).

## Overview

The evaluation system automatically assesses the quality of AI assistant responses using a high-quality LLM (`evaluation.judge_model`, currently Claude Opus 5.5) as a judge. This enables:

- Automated quality evaluation of responses
- Regression detection across code changes
- Model comparison benchmarks
- Quality trend tracking over time

## Quick Start

### Run Golden Tests Without Evaluation (Free)

```bash
# Structure validation runs; the evaluation tests skip without --evaluate
uv run pytest tests/golden/

# Run only structure validation tests
uv run pytest tests/golden/test_golden_conversations.py::TestGoldenConversationStructure -v
```

### Run Golden Tests With Evaluation (Paid — see [Cost Management](#cost-management))

```bash
# Requires OPENROUTER_API_KEY (e.g. in .env). The model under test is models.default
uv run --env-file .env pytest tests/golden/ --evaluate -v

# Test another model: DEFAULT_MODEL overrides models.default
DEFAULT_MODEL=anthropic/claude-opus-5.5 uv run --env-file .env pytest tests/golden/ --evaluate -v

# Run specific test
uv run --env-file .env pytest tests/golden/test_golden_conversations.py::TestGoldenConversations::test_01_basic_qa --evaluate -v

# Use different judge model
uv run --env-file .env pytest tests/golden/ --evaluate --judge-model=google/gemini-3.8-flash -v

# One pass mark for every case (replaces the config thresholds for this run)
uv run --env-file .env pytest tests/golden/ --evaluate --quality-threshold=0.80 -v
```

`DEFAULT_MODEL` (and `models.default`) may be an OpenRouter id (`openai/gpt-6-luna`), an
`openrouter/…` LiteLLM id, or `auto` (OpenRouter Auto Router). Results label the model without the
`openrouter/` prefix, so both forms land in the same row.

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

## Test Categories

Each case YAML has a `category`, which selects the judge prompt (`judge_prompts.py`):

1. **Reasoning**: technical accuracy and clarity (the multi-turn case is scored per turn)
2. **Context Recall**: personal context awareness
3. **Personalization**: tone, preference adherence, and the two writing cases (13–14)
4. **Edge Cases**: ambiguity handling
5. **Tool Use**: agentic cases 09–12 (tool choice, delegation, chaining, stopping)

## How It Works

1. **Load Test Case**: Read YAML file with expected qualities and context
2. **Execute Conversation**: Call model under test with context
3. **Judge Evaluation**: Send response + criteria to the judge (`evaluation.judge_model`, currently Claude Opus 5.5, output capped at 4,096 tokens); it returns structured JSON with scores and reasoning
4. **Basic Checks**: Pattern matching, length validation, content verification
5. **Store Results**: Save individual result + aggregate run summary
6. **Generate Report**: Create markdown report with analysis and recommendations
7. **Assert Quality**: Fail test if score < the case's pass mark (see [Configuration](#configuration))

## Cost Management

- **Expected Cost**: roughly $0.20–0.50 per model per full run (2026-09 measurements): the Opus 5.5
  judge is ~$0.15–0.25 of it; responses range from well under $0.01 (GPT-6 Luna) to ~$0.20
  (Opus 5.5). Per-model numbers are in
  [docs/research/models.md](../../docs/research/models.md#benchmark-results).

- **No budget limit**: the harness does not stop a run on cost. The per-result `total_cost_usd`
  comes from LiteLLM price tables, not from what OpenRouter billed, and is 0 for a model without a
  price entry (e.g. `auto`), so a limit on it would undercount. Estimate before a run with
  `scripts/model_benchmark.py` and check the OpenRouter balance before and after.

- **Cost Optimization**:
  - Use cheaper judge model: `--judge-model=google/gemini-3.8-flash`
  - Run specific tests instead of all of them
  - Skip evaluation in CI, run manually for important changes
  - Estimate first with `scripts/model_benchmark.py` (see [Benchmarking Models](#benchmarking-models))

## Configuration

The harness reads the `evaluation` section of
[`config/default.yaml`](../../config/default.yaml) (override in `config/local.yaml`) and
`models.default`:

- `judge_model`: the judge; per run `--judge-model`.
- `quality_threshold`: the pass mark for a case; `category_thresholds` overrides it for the
  categories it lists (a case's `category` in its YAML). `--quality-threshold` sets one pass mark
  for every case and ignores both. Each result stores the pass mark it was judged against.
- `results_dir`: where runs are written, relative to the repo root.
  `scripts/model_benchmark.py` and `scripts/benchmark_report.py` read results from the same place.
- `models.default`: the model under test; per run `DEFAULT_MODEL`.

## Benchmarking Models

Run models **one at a time**. Parallel runs share one OpenRouter in-flight credit
budget and fail with 402 `in_flight_budget_exhausted`. On a low balance, every call
must fit the remaining credit, so the harness caps output (`models.default_max_tokens`
for the model under test, 4,096 for the judge).

```bash
# Estimate the cost of a full run per model (free; uses the latest run as token baseline)
uv run python scripts/model_benchmark.py

# Estimate, then run the evaluation for each model sequentially (paid)
uv run python scripts/model_benchmark.py --evaluate --models openai/gpt-6-luna anthropic/claude-opus-5.5

# Regenerate the results table between the BENCHMARK_TABLE markers in docs/research/models.md
uv run python scripts/benchmark_report.py
```

The estimate takes token counts from the most recent run in `results/runs/` (or `--run-id`) and
prices from LiteLLM's cost map; models without pricing are skipped with a warning. The default model
shortlist is `DEFAULT_MODELS` in `scripts/model_benchmark.py`.

## Viewing Results

Each evaluated run writes one JSON file per test (overall and per-dimension scores, judge
reasoning, passed/failed criteria, response and judge cost), a `run_summary.json`, a markdown
report (pass rate, average scores, costs, failed tests with the judge's reasoning), and appends to
`history.json` for trends across runs.

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

2. Add a test method to `TestGoldenConversations` in `test_golden_conversations.py`, and the file
   name to `expected_files` in `TestGoldenConversationStructure.test_all_golden_files_exist`:

```python
def test_15_my_new_test(self, evaluator, evaluation_config, result_storage):
    """Test description."""
    self._run_golden_test("15_my_new_test.yaml", evaluator, evaluation_config, result_storage)
```

3. Run evaluation:

```bash
uv run --env-file .env pytest tests/golden/test_golden_conversations.py::TestGoldenConversations::test_15_my_new_test --evaluate -v
```

## Understanding Scores

- **1.0**: Excellent - Exceeds expectations
- **0.8-0.9**: Good - Meets all criteria well
- **0.6-0.7**: Acceptable - Meets minimum requirements
- **0.4-0.5**: Poor - Missing key elements
- **0.0-0.3**: Failing - Does not meet criteria

**Default threshold**: `evaluation.quality_threshold`, per category `evaluation.category_thresholds`

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

1. **Run structure tests only** (free) — this is what CI does today, since `uv run pytest` skips
   the evaluation tests without `--evaluate`.

2. **Run evaluation on main branch only** (costs money):
   ```bash
   if [ "$BRANCH" = "main" ]; then
     uv run pytest tests/golden/ --evaluate
   fi
   ```

3. **Run evaluation manually** before major releases.

## Further Reading

- [Testing Documentation](../../docs/engineering/testing.md)
- [Product Roadmap](../../docs/product/roadmap.md)
- [Model benchmark results](../../docs/research/models.md)

---

**Questions?** Check the testing documentation or open an issue on GitHub.
