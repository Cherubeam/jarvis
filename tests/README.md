# Jarvis Testing Suite

Comprehensive testing framework for the Jarvis personal AI assistant.

## Quick Start

```bash
# Install test dependencies (using uv)
uv sync --extra test

# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=packages --cov=apps --cov-report=html

# View coverage report in browser
open htmlcov/index.html
```

---

## Test Structure

```
tests/
├── unit/              # Fast, isolated unit tests
├── integration/       # Integration tests with mocked dependencies
├── golden/           # Golden conversation test cases + LLM-as-judge
│   ├── conversations/ # YAML test cases
│   ├── results/       # Evaluation results
│   ├── evaluator.py   # Core evaluation engine
│   ├── judge_prompts.py # Judge prompt templates
│   └── result_storage.py # Storage & reporting
├── fixtures/         # Test data and fixtures
├── conftest.py       # Shared pytest fixtures
└── TESTING_PLAN.md   # Comprehensive testing plan
```

---

## Common Commands

### Run Tests by Category

```bash
# Unit tests only (fast)
uv run pytest tests/unit/ -v

# Integration tests only
uv run pytest tests/integration/ -v

# Golden test structure validation (free)
uv run pytest tests/golden/ -v

# Golden tests WITH evaluation (costs ~$0.41, requires API key)
export OPENROUTER_API_KEY="your-key"
uv run pytest tests/golden/ --evaluate -v

# Exclude slow/manual tests
uv run pytest -m "not slow"
```

### Run Specific Tests

```bash
# Single test file
uv run pytest tests/unit/test_context_builder.py -v

# Single test class
uv run pytest tests/unit/test_memory.py::TestSessionMetrics -v

# Single test function
uv run pytest tests/unit/test_pricing.py::TestModelPricing::test_model_pricing_calculate_cost -v
```

### Coverage Options

```bash
# Coverage for all project code
uv run pytest --cov=packages --cov=apps --cov-report=term

# Detailed coverage with missing lines
uv run pytest --cov=packages --cov=apps --cov-report=term-missing

# Coverage with HTML report
uv run pytest --cov=packages --cov=apps --cov-report=html

# Coverage with minimum threshold
uv run pytest --cov=packages --cov=apps --cov-fail-under=85
```

### Performance Options

```bash
# Run tests in parallel (faster)
uv run pytest -n auto

# Show test durations
uv run pytest --durations=10

# Fail fast (stop on first failure)
uv run pytest -x

# Run only failed tests from last run
uv run pytest --lf
```

### Mutation Testing

```bash
# Run mutation tests (set paths_to_mutate in pyproject.toml first)
uv run mutmut run

# View results summary (survived/killed/timeout counts)
uv run mutmut results

# Inspect a specific surviving mutant diff
uv run mutmut show <mutant_name>

# Re-run only untested/surviving mutants (incremental via .mutmut-cache)
uv run mutmut run

# See the full report: docs/engineering/mutation-testing-report.md
```

### Debugging Options

```bash
# Verbose output with local variables
uv run pytest -vv --showlocals

# Drop into debugger on failure
uv run pytest --pdb

# Print output even for passing tests
uv run pytest -s

# Show full diff for assertions
uv run pytest -vv
```

---

## Test Markers

Tests are categorized with markers for selective execution:

```bash
# Run only unit tests
uv run pytest -m unit

# Run only integration tests
uv run pytest -m integration

# Run only golden tests
uv run pytest -m golden

# Skip slow tests
uv run pytest -m "not slow"
```

---

## Test Statistics

Run `uv run pytest` to see current counts. See [docs/engineering/testing.md](../docs/engineering/testing.md) for test statistics and strategy.

---

## Writing New Tests

### Unit Test Template

```python
import pytest
from your_module import YourClass

@pytest.mark.unit
class TestYourClass:
    """Tests for YourClass."""

    def test_something(self):
        """Test that something works correctly."""
        # Arrange
        obj = YourClass()

        # Act
        result = obj.do_something()

        # Assert
        assert result == expected_value
```

### Using Fixtures

```python
def test_with_fixtures(temp_context_dir, sample_config):
    """Test using shared fixtures from conftest.py."""
    # Fixtures are automatically provided by pytest
    assert temp_context_dir.exists()
    assert "openrouter" in sample_config
```

### Integration Test Template

```python
import pytest
from unittest.mock import patch, Mock

@pytest.mark.integration
class TestIntegration:
    """Integration tests."""

    def test_full_flow(self):
        """Test complete flow with mocked external dependencies."""
        with patch('litellm.completion') as mock_llm:
            # Setup mock
            mock_llm.return_value = Mock()

            # Test integration
            result = run_full_flow()

            # Verify
            assert result is not None
            mock_llm.assert_called_once()
```

---

## Golden Tests

Golden tests are defined in YAML format:

```yaml
name: "test_name"
description: "What this test validates"
category: "reasoning"  # or context_recall, personalization, edge_cases
context:
  profile: |
    User profile information
  preferences: |
    User preferences
conversation:
  - role: "user"
    content: "User question"
  - role: "assistant"
    expected_themes:
      - "theme1"
      - "theme2"
    expected_qualities:
      accurate: true
      concise: true
```

See [tests/golden/README.md](golden/README.md) for the full golden test guide including LLM-as-judge evaluation.

---

## Continuous Integration

Ready for GitHub Actions:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --extra test
      - run: uv run pytest --cov=packages --cov=apps --cov-report=xml
      - uses: codecov/codecov-action@v3
```

---

## Troubleshooting

### Import Errors

If tests can't find modules:
```bash
# Ensure the project is properly synced
uv sync
```

### Fixture Not Found

Check `tests/conftest.py` for available fixtures or define locally:
```python
@pytest.fixture
def my_fixture():
    return "test_data"
```

### Test Discovery Issues

Ensure files follow naming conventions:
- Test files: `test_*.py` or `*_test.py`
- Test functions: `test_*`
- Test classes: `Test*`

---

## Documentation

- [TESTING_PLAN.md](TESTING_PLAN.md) - Comprehensive testing plan and architecture
- [../docs/engineering/testing.md](../docs/engineering/testing.md) - Testing strategy, statistics, and philosophy
- [golden/README.md](golden/README.md) - Golden test guide with LLM-as-judge details
