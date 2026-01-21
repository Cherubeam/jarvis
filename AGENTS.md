# AGENTS.md

> Guidance for AI coding agents working on Jarvis

---

## Project Overview

Jarvis is a personal AI assistant built to solve the vendor lock-in problem in conversational AI. It's a Python 3.13+ project using `uv` for dependency management.

**Key principles:**
- Local-first architecture
- Provider independence
- Simple, maintainable code
- No premature optimization

---

## Critical: Dependency Management

### ⚠️ ALWAYS use `uv`, NEVER use `pip`

**This project uses `uv` exclusively. AI agents often default to `pip` - DO NOT DO THIS.**

**❌ WRONG:**
```bash
pip install package          # NEVER use pip
uv pip install package       # NEVER use uv pip install
pip install -e ".[test]"     # NEVER use pip for test dependencies
```

**✅ CORRECT:**
```bash
uv add package               # Add runtime dependency
uv add --dev package         # Add dev dependency
uv sync --extra test         # Install with test dependencies
uv run pytest                # Run commands in uv environment
```

**Why this matters:**
- `uv add` updates both `pyproject.toml` AND `uv.lock`
- `pip` or `uv pip install` only installs to `.venv` (not tracked in lock file)
- Missing from `pyproject.toml` = project breaks on fresh setup
- **All documentation and examples in this project use `uv` syntax**

### Common uv Commands

```bash
# Dependencies
uv add package              # Add runtime dependency
uv add --dev package        # Add development dependency
uv remove package           # Remove dependency
uv sync                     # Install from lock file
uv sync --extra test        # Install with optional test dependencies
uv sync --upgrade           # Update all dependencies

# Running code
uv run python script.py     # Run Python script
uv run pytest               # Run tests

# Environment
uv venv                     # Create virtual environment (auto-created by uv sync)
```

---

## Build and Test Commands

### Running the CLI

```bash
uv run python personal-context/src/cli.py
```

### Type Checking

```bash
mypy personal-context/src/
```

### Testing (Implemented ✅)

```bash
# Run all tests (free, no LLM calls)
uv run pytest

# Run with coverage
uv run pytest --cov=personal-context/src --cov-report=html

# Run specific test categories
uv run pytest tests/unit/ -v              # Unit tests only (33 tests)
uv run pytest tests/integration/ -v       # Integration tests only
uv run pytest tests/golden/ -v            # Golden test structure validation (free)

# Run golden tests WITH evaluation (costs ~$0.41, requires API key)
export OPENROUTER_API_KEY="your-key"
uv run pytest tests/golden/ --evaluate -v

# Run tests in parallel (faster)
uv run pytest -n auto

# View coverage report
open htmlcov/index.html
```

**Test Statistics:**
- 149 total tests (103 unit + 20 integration + 26 golden/evaluation)
- 97.5% code coverage on core modules
- Unit/integration suite runs in < 2 seconds
- LLM-as-judge evaluation: 8 golden tests (~$0.41/run, optional)

**LLM-as-Judge Evaluation:**
- Automated quality assessment using Claude Opus 4.5 as judge
- Generates detailed markdown reports with scores and recommendations
- Tracks quality trends over time in `tests/golden/results/`
- Only runs with `--evaluate` flag (no cost by default)

See [tests/README.md](tests/README.md) and [tests/golden/README.md](tests/golden/README.md) for complete testing guides.

### Clean Setup Verification

Always verify changes work from clean environment:

```bash
rm -rf .venv
uv sync
uv run python personal-context/src/cli.py
```

---

## Code Style and Conventions

### Language Version

- **Python 3.13+** required
- Use modern type hints: `list[dict]`, `str | None`
- Avoid legacy typing: `List[Dict]`, `Optional[str]`

### Code Style

- **Simplicity over cleverness**: Code should be readable by intermediate developers
- **No premature optimization**: Build it simple first
- **Single responsibility**: Each module does one thing well
- **Explicit over implicit**: Clear data flow, no magic

### File Naming

- Snake case: `llm_client.py`, not `LLMClient.py`
- Descriptive names: `context_builder.py` over `builder.py`

### Imports

```python
# Standard library
import os
from pathlib import Path

# Third-party
import yaml
from dotenv import load_dotenv

# Local
from context_builder import build_system_prompt
from llm_client import LLMClient
```

---

## Project Structure

```
jarvis/
├── config.yaml                     # Configuration
├── .env                            # API keys (gitignored)
├── personal-context/
│   ├── context/                    # User context (markdown)
│   │   └── tasks.md                # Auto-synced Things 3 tasks
│   ├── memory/conversations/       # Session logs (gitignored)
│   └── src/                        # Source code
│       ├── cli.py                  # Entry point
│       ├── llm_client.py           # LLM abstraction (LiteLLM)
│       ├── context_builder.py      # System prompt assembly
│       ├── memory.py               # Conversation logging
│       ├── pricing.py              # Cost tracking
│       └── task_sync.py            # Things 3 integration (~520 lines)
├── tests/                          # Comprehensive test suite
│   ├── unit/                       # 103 unit tests (includes evaluator tests)
│   ├── integration/                # 20 integration tests
│   ├── golden/                     # Golden test conversations + LLM-as-judge
│   │   ├── conversations/          # 8 YAML test cases
│   │   ├── results/                # Evaluation results (JSON + markdown reports)
│   │   ├── evaluator.py            # Core evaluation engine (~400 lines)
│   │   ├── judge_prompts.py        # Judge prompt templates (~200 lines)
│   │   ├── result_storage.py       # Storage & reporting (~500 lines)
│   │   ├── test_golden_conversations.py  # Test runner
│   │   └── README.md               # Evaluation system guide
│   ├── fixtures/                   # Test data
│   ├── conftest.py                 # Shared pytest fixtures + --evaluate flag
│   ├── TESTING_PLAN.md             # Testing plan
│   ├── TEST_RESULTS.md             # Test results
│   └── README.md                   # Testing guide
└── docs/                           # Documentation
    ├── product/                    # Product docs (vision, roadmap, metrics, ADRs)
    ├── engineering/                # Technical docs (architecture, API, testing)
    └── research/                   # AI engineering (framework, models, prompts)
```

---

## Testing Guidelines

### Automated Testing (Implemented ✅)

**Test Framework:** pytest with 97.5% code coverage

**Test Categories:**
- **Unit Tests** (103 tests): Fast, isolated tests for each module including evaluator
- **Integration Tests** (20 tests): Full flow with mocked dependencies
- **Golden Tests** (8 tests): Real conversation test cases with LLM-as-judge evaluation
  - Structure validation: Free, always runs
  - Quality evaluation: Costs ~$0.41/run, requires `--evaluate` flag

### Before Committing Code

Always run tests to ensure nothing broke:

```bash
# Quick check (unit tests only, < 1 second)
uv run pytest tests/unit/

# Full test suite (< 2 seconds)
uv run pytest

# With coverage report
uv run pytest --cov=personal-context/src --cov-report=term
```

### Writing New Tests

When adding features, add corresponding tests:

```bash
# Unit test template location
tests/unit/test_your_module.py

# Integration test location
tests/integration/test_your_feature.py
```

See [tests/TESTING_PLAN.md](tests/TESTING_PLAN.md) for detailed testing guidelines.

### Manual Testing

For end-to-end verification:

1. Start CLI: `uv run python personal-context/src/cli.py`
2. Verify context loading (check system prompt includes profile.md)
3. Test streaming responses
4. Verify token/cost tracking
5. Check conversation logs saved

---

## Important Files to Preserve

### Never Modify Without Explicit Request

- `config.yaml` - User configuration
- `personal-context/context/*.md` - User's personal context (except tasks.md which is auto-generated)
- `.env` - API keys (never commit)

### Read-Only Unless Fixing Bugs

- `personal-context/memory/conversations/*.json` - Conversation logs
- `docs/product/decisions.md` - Architecture Decision Records

---

## Documentation Updates

### ⚠️ CRITICAL: Always Check ALL Documentation Files

**After ANY implementation, you MUST read and update ALL relevant files in the `docs/` folder.**

This is a mandatory step - do not skip it. Many files reference each other and need to stay consistent.

### When Making Changes

1. **Code changes** → Update [docs/engineering/architecture.md](docs/engineering/architecture.md) or [api.md](docs/engineering/api.md)
2. **New features** → Update [docs/product/roadmap.md](docs/product/roadmap.md) AND [docs/changelog.md](docs/changelog.md)
3. **Architecture decisions** → Add new ADR to [docs/product/decisions.md](docs/product/decisions.md)
4. **Version releases** → Update [docs/changelog.md](docs/changelog.md)
5. **Test changes** → Update [docs/engineering/testing.md](docs/engineering/testing.md)

### Documentation Review Checklist

After implementing a feature, check and update these files if relevant:

**Product Documentation:**
- [ ] [docs/product/vision.md](docs/product/vision.md) - Does this change the vision or principles?
- [ ] [docs/product/roadmap.md](docs/product/roadmap.md) - Mark features as complete, update phases
- [ ] [docs/product/metrics.md](docs/product/metrics.md) - Are there new metrics to track?
- [ ] [docs/product/decisions.md](docs/product/decisions.md) - Add ADR for architectural decisions
- [ ] [docs/changelog.md](docs/changelog.md) - **ALWAYS UPDATE** - Document all changes here

**Engineering Documentation:**
- [ ] [docs/engineering/architecture.md](docs/engineering/architecture.md) - New modules or data flows?
- [ ] [docs/engineering/api.md](docs/engineering/api.md) - New APIs or interfaces?
- [ ] [docs/engineering/testing.md](docs/engineering/testing.md) - Test strategy changes?
- [ ] [docs/engineering/deployment.md](docs/engineering/deployment.md) - Setup changes?

**Research Documentation:**
- [ ] [docs/research/framework.md](docs/research/framework.md) - New AI engineering patterns?
- [ ] [docs/research/models.md](docs/research/models.md) - Model comparison updates?
- [ ] [docs/research/prompts.md](docs/research/prompts.md) - Prompt engineering insights?

**Root Documentation:**
- [ ] [AGENTS.md](AGENTS.md) - Changes to development workflow or structure?
- [ ] [README.md](README.md) - User-facing changes?

### ADR Format

When documenting architectural decisions:

```markdown
## ADR-XXX: [Title]
**Date**: YYYY-MM-DD
**Status**: ✅ Accepted

### Context
What's the problem?

### Decision
What are we doing?

### Consequences
- ✅ Benefits
- ⚠️ Tradeoffs
```

---

## Security Considerations

### API Keys

- ✅ Always use `.env` file (gitignored)
- ❌ Never hardcode in source files
- ❌ Never commit to git

### Conversation Logs

- ⚠️ Contain sensitive personal data
- ✅ Gitignored by default
- ⚠️ Warn user before committing context files

---

## Common Tasks

### Adding a New Dependency

```bash
uv add package-name
git add pyproject.toml uv.lock
git commit -m "Add package-name dependency"
```

### Creating New Context File

```bash
echo "# New Context Section" > personal-context/context/new_file.md
# Update context_builder.py to load it
```

### Switching LLM Providers

Edit `personal-context/src/cli.py`:

```python
client = LLMClient(
    api_key=config["provider"]["api_key"],
    default_model="model-id",
    provider="openrouter"  # or "anthropic", "openai"
)
```

---

## Error Handling

### Import Errors on Fresh Setup

**Cause**: Dependency missing from `pyproject.toml`

**Fix**:
```bash
uv add missing-package
```

### API Key Errors

**Cause**: `.env` file missing or incorrect

**Fix**:
```bash
echo "OPENROUTER_API_KEY=sk-or-v1-..." > .env
```

---

## Development Workflow

### Before Making Changes

1. Read relevant documentation in `docs/`
2. Check [docs/product/decisions.md](docs/product/decisions.md) for context
3. Understand current phase (see [docs/product/roadmap.md](docs/product/roadmap.md))

### During Development

1. Keep changes small and focused
2. Use type hints for all new code
3. Test manually before committing
4. Update documentation inline

### Before Committing

1. ✅ Dependencies added via `uv add` (NEVER pip)
2. ✅ Tests pass: `uv run pytest`
3. ✅ Code works after clean setup: `rm -rf .venv && uv sync`
4. ✅ Type checking passes (if applicable)
5. ✅ Documentation updated
6. ✅ No API keys or secrets in code

---

## Git Commit Guidelines

### Commit Message Format

```
<type>: <description>

[optional body]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code restructuring
- `test`: Test additions/changes
- `chore`: Maintenance tasks

**Examples:**
```
feat: add LiteLLM integration for provider flexibility
fix: correct cost calculation fallback logic
docs: restructure documentation into organized /docs directory
```

---

## Resources

- **Full docs**: See `docs/` directory
- **Setup guide**: [docs/engineering/deployment.md](docs/engineering/deployment.md)
- **Architecture**: [docs/engineering/architecture.md](docs/engineering/architecture.md)
- **Roadmap**: [docs/product/roadmap.md](docs/product/roadmap.md)
- **ADRs**: [docs/product/decisions.md](docs/product/decisions.md)

---

## Quick Reference for AI Agents

### Critical Reminders

1. **Use `uv`, not `pip`** - This is the #1 mistake AI agents make
2. **Run tests before committing** - `uv run pytest`
3. **Check documentation** - Read `docs/` before making changes
4. **Keep it simple** - No premature optimization
5. **Test dependencies** - Use `uv sync --extra test` for test setup

### Most Common Commands

```bash
# Add dependency (runtime)
uv add package-name

# Add test dependency
uv add --dev pytest-something

# Install everything including tests
uv sync --extra test

# Run the app
uv run python personal-context/src/cli.py

# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=personal-context/src --cov-report=html
```

---

*Last updated: 2026-01-20*
