# Jarvis Testing Suite

Test commands and the layout of `tests/`. Strategy, test layers and mutation testing are in
[docs/engineering/testing.md](../docs/engineering/testing.md); the golden (LLM-as-judge) suite is in
[golden/README.md](golden/README.md).

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
├── unit/              # Fast, isolated unit tests (one file per module)
│   └── gui/           # GUI server tests (routes, bridge, history, home, settings)
├── integration/       # Integration tests with mocked dependencies
├── golden/            # Golden conversations + LLM-as-judge (layout: golden/README.md)
├── fixtures/          # Test data (sample exports, context files, mock responses, config)
├── conftest.py        # Shared pytest fixtures + the --evaluate / --judge-model options
├── TESTING_PLAN.md    # Original Phase 1 testing plan (historical)
└── TEST_RESULTS.md    # Phase 1 results snapshot (historical)
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

# Golden tests WITH evaluation: paid, needs OPENROUTER_API_KEY; tests models.default
# unless DEFAULT_MODEL is set (cost and options: golden/README.md)
uv run --env-file .env pytest tests/golden/ --evaluate -v

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

mutmut currently only works on Linux; use the CI workflow on macOS (see
[testing.md](../docs/engineering/testing.md#running-mutation-tests-in-ci-required)).

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

## Writing New Tests

### Mutation-Resistant Assertions

Assert on values, not existence. The rules and the checklist (including tool-factory tests) are in
[docs/engineering/testing.md](../docs/engineering/testing.md#writing-mutation-resistant-tests).

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
            assert result == expected_result
            mock_llm.assert_called_once()
```

---

## Golden Tests

Case format, running with evaluation, cost, adding cases and benchmarking models are in
[golden/README.md](golden/README.md).

---

## Continuous Integration

`.github/workflows/test.yml` runs ruff, mypy and `uv run pytest` on pushes to `main` and on PRs;
golden tests run without `--evaluate` there, so CI never spends money.
`.github/workflows/mutation.yml` runs mutmut weekly and on demand
([details](../docs/engineering/testing.md#running-mutation-tests-in-ci-required)).

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

- [../docs/engineering/testing.md](../docs/engineering/testing.md) - Testing strategy, layers, mutation testing
- [TESTING_PLAN.md](TESTING_PLAN.md) - Original Phase 1 testing plan (historical)
- [golden/README.md](golden/README.md) - Golden test guide with LLM-as-judge details
