# Jarvis Testing Suite

Comprehensive testing framework for the Jarvis personal AI assistant.

## Quick Start

```bash
# Install test dependencies (using uv)
uv sync --extra test

# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=personal-context/src --cov-report=html

# View coverage report in browser
open htmlcov/index.html
```

---

## Test Structure

```
tests/
├── unit/              # Fast, isolated unit tests
├── integration/       # Integration tests with mocked dependencies
├── golden/           # Golden conversation test cases
├── fixtures/         # Test data and fixtures
├── conftest.py       # Shared pytest fixtures
├── TESTING_PLAN.md   # Comprehensive testing plan
└── TEST_RESULTS.md   # Current test results and status
```

---

## Common Commands

### Run Tests by Category

```bash
# Unit tests only (fast)
uv run pytest tests/unit/ -v

# Integration tests only
uv run pytest tests/integration/ -v

# Golden test structure validation
uv run pytest tests/golden/test_golden_conversations.py::TestGoldenConversationStructure -v

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
# Coverage for specific module
uv run pytest --cov=personal-context/src/pricing.py --cov-report=term

# Detailed coverage with missing lines
uv run pytest --cov=personal-context/src --cov-report=term-missing

# Coverage with HTML report
uv run pytest --cov=personal-context/src --cov-report=html

# Coverage with minimum threshold
uv run pytest --cov=personal-context/src --cov-fail-under=85
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

- **Total Tests**: 73
- **Unit Tests**: 53
- **Integration Tests**: 12
- **Golden Tests**: 8 + 2 structure validation
- **Code Coverage**: 97.5% (core modules)
- **Pass Rate**: 85% (62/73 passing)

See [TEST_RESULTS.md](TEST_RESULTS.md) for detailed results.

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

## Golden Tests (Phase 2)

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

Currently, golden tests validate YAML structure. LLM-as-judge automation coming in Phase 2.

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
      - run: uv run pytest --cov=personal-context/src --cov-report=xml
      - uses: codecov/codecov-action@v3
```

---

## Troubleshooting

### Import Errors

If tests can't find modules:
```bash
# Ensure src is in path (conftest.py handles this)
# Or sync the project properly
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
- [TEST_RESULTS.md](TEST_RESULTS.md) - Current test results and coverage
- [../docs/engineering/testing.md](../docs/engineering/testing.md) - Testing strategy and philosophy

---

## Next Steps

### Phase 2: Evaluation & Quality Metrics
1. Implement LLM-as-judge for golden test automation
2. Add TTFT (Time to First Token) tracking
3. Model comparison benchmarks
4. Automated regression detection

See [TESTING_PLAN.md](TESTING_PLAN.md) Section 9 for details.

---

*Last updated: 2026-01-15*
