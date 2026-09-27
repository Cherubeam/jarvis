# Testing Strategy

> How we ensure Jarvis works correctly and maintains quality.

This doc covers strategy, test layers and mutation testing. Commands (by category, coverage,
markers, debugging) are in [tests/README.md](../../tests/README.md); the golden suite is in
[tests/golden/README.md](../../tests/golden/README.md). Run `uv run pytest` for current counts.

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

## Test Layers

**Test Framework Stack:** pytest with pytest-asyncio, pytest-cov, pytest-mock, pytest-xdist,
respx (HTTP mocking), freezegun (time mocking) and mutmut (mutation testing). Versions are in
`pyproject.toml` (`[project.optional-dependencies] test`).

- **Unit tests** (`tests/unit/`, GUI tests under `tests/unit/gui/`) — fast and isolated, LLM calls
  mocked. Every module in `packages/` and `apps/` should have one.
- **Integration tests** (`tests/integration/`) — full flows (conversation, context, pricing, task
  sync, configuration) with mocked external dependencies.
- **Golden tests** (`tests/golden/`) — real conversations judged by an LLM (LLM-as-judge). Without
  `--evaluate` only the free structure checks run, so `uv run pytest` and CI never spend money.
  Cases, judge, cost and how to run or add them: [tests/golden/README.md](../../tests/golden/README.md).

CI (`.github/workflows/test.yml`) runs ruff, mypy and `uv run pytest` on pushes to `main` and on every PR.
Coverage: `uv run pytest --cov=packages --cov=apps` ([tests/README.md](../../tests/README.md#coverage-options)).

---

## Mutation Testing

Mutation testing (mutmut) measures test quality by injecting small code changes and checking
whether the tests catch them. How to write tests that kill mutants is in
[Writing Mutation-Resistant Tests](#writing-mutation-resistant-tests); the audit history is in
[mutation-testing-report.md](mutation-testing-report.md).

### Running Mutation Tests in CI (required)

As of 2026-04-11, **mutmut on macOS is unusable** — every mutant segfaults at fork time due to macOS fork-safety restrictions that upstream mutmut 3.5.0 cannot work around. The only working environment is the Linux CI workflow at [`.github/workflows/mutation.yml`](../../.github/workflows/mutation.yml).

Triggering a run:

```bash
# One-off manual run from any branch
gh workflow run mutation.yml --ref <branch-name>

# Watch the latest run
gh run watch

# Download the results artifact after the run finishes
gh run download --name mutmut-results-<run-id>
```

The workflow also runs automatically every Monday 06:00 UTC against `main`. Each run produces a `mutmut-results.txt` artifact (plus an HTML report when mutmut's `html` subcommand is available), retained for 90 days. No secrets are required — mutmut runs the local test suite only.

Local `uv run mutmut run` commands stay in [tests/README.md](../../tests/README.md#mutation-testing) because they will start working again once mutmut upstream switches to `spawn` or Apple relaxes fork-safety — but for now, CI is the authoritative source for mutation results. Any per-module numbers in [mutation-testing-report.md](mutation-testing-report.md) older than 2026-04-11 should be treated as historical until the first Linux CI run replaces them.

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

### When to Update Tests

**Update test expectations when:**
- Intentional behavior change
- Better response quality
- New features added

**Never update to pass failing tests!**
- Investigate why it failed first
- Fix the code, not the test
- If an expectation was wrong, change it visibly and say why

---

## Writing Mutation-Resistant Tests

Mutation testing (mutmut) measures test quality by injecting small code changes ("mutants") and checking whether tests catch them. A surviving mutant means a test is too shallow. See [mutation-testing-report.md](mutation-testing-report.md) for the full audit.

### The Core Rule

**Assert on values, not just existence.** This is the #1 lesson from our mutation testing audit. Tests that check "something was returned" survive mutations; tests that check "the right thing was returned" kill them.

```python
# BAD — survives mutations (checks existence only)
result = my_function()
assert result is not None
assert "key" in result
assert len(result) > 0

# GOOD — kills mutations (checks values)
result = my_function()
assert result == {"role": "tool", "content": "Expected output"}
assert result["status"] == "success"
assert set(result.keys()) == {"role", "content", "status"}
```

### Checklist for Every New Test

When writing tests, verify your assertions catch these common mutation types:

| Mutation Type | Example | What to Assert |
|---------------|---------|----------------|
| **String content** | `"Error: {x}"` → `"XXError: {x}XX"` | `assert result.startswith("Error:")` |
| **Dictionary keys** | `{"role": "tool"}` → `{"XXroleXX": "tool"}` | `assert result["role"] == "tool"` |
| **Dictionary values** | `{"role": "tool"}` → `{"role": "XXtoolXX"}` | `assert result["role"] == "tool"` |
| **Operators** | `a * 1000` → `a / 1000` | Assert on computed values, not just existence |
| **Boolean defaults** | `flag: bool = True` → `False` | Test behavior with and without the argument |
| **Control flow** | `and` → `or`, `continue` → `break` | Test both branches of conditionals |
| **Return values** | `return x` → `return None` | `assert result == expected` (exact match) |

### Tool Factory Tests

Tool factories (`make_*_tools()` functions) are the most mutation-prone pattern. Every tool factory test should include:

1. **Schema validation** — verify parameter names, types, and required fields:
   ```python
   def test_tool_schema(self, tools):
       tool = get_tool(tools, "my_tool")
       params = tool.parameters
       assert params["type"] == "object"
       assert set(params["properties"].keys()) == {"arg1", "arg2"}
       assert params["properties"]["arg1"]["type"] == "string"
       assert params["required"] == ["arg1"]
   ```

2. **Output content assertions** — check what the tool returns, not just that it runs:
   ```python
   def test_tool_output(self, tools):
       result = tool.execute(arg1="test")
       assert "Expected substring" in result
       # OR for structured output:
       assert result == "exact expected string"
   ```

3. **Error path assertions** — verify error messages, not just that errors occur:
   ```python
   def test_tool_error(self, tools):
       result = tool.execute(arg1="nonexistent")
       assert result.startswith("Error:")
       assert "nonexistent" in result
   ```

4. **Default argument tests** — call without optional args to test defaults:
   ```python
   def test_default_behavior(self, tools):
       # Omit optional arg — exercises the default value
       result = tool.execute(required_arg="value")
       assert "expected default behavior" in result
   ```

### Suppressing Equivalent Mutants

Some mutations don't change behavior (equivalent mutants). Use `# pragma: no mutate` to exclude them:

```python
# Description strings are LLM-facing metadata — text changes don't affect code behavior
tool = ToolDefinition(
    name="my_tool",
    description=(  # pragma: no mutate
        "Describe what the tool does. "  # pragma: no mutate
        "This text is read by the LLM, not by code."  # pragma: no mutate
    ),
    parameters={
        "type": "object",
        "properties": {
            "arg": {
                "type": "string",
                "description": "Parameter docs for the LLM.",  # pragma: no mutate
            },
        },
    },
)
```

**When to use `# pragma: no mutate`:**
- ToolDefinition `description=` strings (LLM reads them, code doesn't)
- Parameter `"description":` strings in JSON schemas
- Log format strings (`logger.info("Processing %s", name)`)

**When NOT to use it:**
- Error messages returned to users (these should be tested)
- Dictionary keys in data structures (these affect behavior)
- Any value that code logic depends on

---

*Last updated: 2026-09-27*
