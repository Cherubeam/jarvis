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

### ALWAYS use `uv`, NEVER use `pip`

**This project uses `uv` exclusively. AI agents often default to `pip` - DO NOT DO THIS.**

**WRONG:**
```bash
pip install package          # NEVER use pip
uv pip install package       # NEVER use uv pip install
pip install -e ".[test]"     # NEVER use pip for test dependencies
```

**CORRECT:**
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
# Using module syntax (always works)
uv run python -m apps.cli.main

# Using the installed script (requires editable install)
uv run jarvis
```

### Script Entry Point Setup

If `uv run jarvis` fails with `ModuleNotFoundError: No module named 'apps'`, you need to install the package in editable mode:

```bash
uv pip install -e .
```

**Why this happens:**
- `uv run python -m apps.cli.main` works because Python adds the current directory to `sys.path`
- `uv run jarvis` uses the installed script entry point which needs the packages to be properly installed
- After running `uv pip install -e .`, both methods will work

**When to run editable install:**
- After a fresh clone
- After changing the package structure in `pyproject.toml`
- When switching between branches with different structures

### Type Checking

```bash
mypy packages/ apps/
```

### Testing

```bash
# Run all tests (free, no LLM calls)
uv run pytest

# Run with coverage
uv run pytest --cov=packages --cov=apps --cov-report=html

# Unit tests only
uv run pytest tests/unit/ -v
```

Run `uv run pytest` to see current counts. See [docs/engineering/testing.md](docs/engineering/testing.md) for test statistics, strategy, and the full command reference. See [tests/README.md](tests/README.md) for quick-reference test commands.

### Clean Setup Verification

Always verify changes work from clean environment:

```bash
rm -rf .venv
uv sync
uv pip install -e .        # Required for script entry point
uv run jarvis              # Or: uv run python -m apps.cli.main
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

# Local (use package imports)
from packages.core.context_builder import build_system_prompt
from packages.core.llm_client import LLMClient
from packages.integrations.things3.task_sync import sync_tasks_to_file
```

---

## Project Structure

See [docs/engineering/architecture.md](docs/engineering/architecture.md#project-structure) for the full project structure.

**Note**: The old `personal-context/` structure is deprecated. Use the new `packages/`, `apps/`, and `data/` directories.

---

## Before Committing Code

```bash
# Quick check (unit tests only, < 1 second)
uv run pytest tests/unit/

# Full test suite (< 2 seconds)
uv run pytest

# With coverage report
uv run pytest --cov=packages --cov=apps --cov-report=term
```

---

## Important Files to Preserve

### Never Modify Without Explicit Request

- `config/default.yaml`, `config/local.yaml` - Configuration files
- `data/context/*.md` - User's personal context (except tasks.md which is auto-generated)
- `.env` - API keys (never commit)

### Read-Only Unless Fixing Bugs

- `data/conversations/*.json` - Conversation logs
- `docs/product/decisions.md` - Architecture Decision Records

---

## Documentation Updates

### CRITICAL: Always Check ALL Documentation Files

**After ANY implementation, you MUST read and update ALL relevant files in the `docs/` folder.**

This is a mandatory step - do not skip it. Many files reference each other and need to stay consistent.

### When Making Changes

1. **Code changes** → Update [docs/engineering/architecture.md](docs/engineering/architecture.md) or [api.md](docs/engineering/api.md)
2. **New features** → Update [docs/product/roadmap.md](docs/product/roadmap.md) AND [docs/changelog.md](docs/changelog.md)
3. **Architecture decisions** → Add new ADR to [docs/product/decisions.md](docs/product/decisions.md) (see that file for format)
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

---

## Security Considerations

### API Keys

- Always use `.env` file (gitignored)
- Never hardcode in source files
- Never commit to git

### Conversation Logs

- Contain sensitive personal data
- Gitignored by default
- Warn user before committing context files

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
echo "# New Context Section" > data/context/new_file.md
# Update packages/core/context_builder.py to load it
```

### Importing Conversations

```bash
# Preview what would be imported
uv run python scripts/import_chatgpt.py imports/conversations.json --dry-run

# Import all non-archived conversations
uv run python scripts/import_chatgpt.py imports/conversations.json

# Import with filters
uv run python scripts/import_chatgpt.py imports/conversations.json --date-from 2025-01-01 --model gpt-4o --include-archived
```

```bash
# Claude conversation import
uv run python scripts/import_claude.py imports/conversations.json --dry-run
uv run python scripts/import_claude.py imports/conversations.json
uv run python scripts/import_claude.py imports/conversations.json --date-from 2025-01-01
```

```bash
# Claude context import (memories + projects)
uv run python scripts/import_claude_context.py --dry-run
uv run python scripts/import_claude_context.py
uv run python scripts/import_claude_context.py --memories imports/memories.json --projects imports/projects.json
```

Imported files are written to `data/conversations/` with source-specific tags (`["imported", "chatgpt"]` or `["imported", "claude"]`). The import is idempotent — re-running skips already-imported conversations.

### Switching LLM Providers

Edit `config/default.yaml` or `config/local.yaml`:

```yaml
openrouter:
  default_model: "anthropic/claude-sonnet-4.5"  # Change to desired model
```

See [docs/engineering/deployment.md](docs/engineering/deployment.md) for full provider configuration details.

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

1. Dependencies added via `uv add` (NEVER pip)
2. Tests pass: `uv run pytest`
3. Code works after clean setup: `rm -rf .venv && uv sync`
4. Type checking passes (if applicable)
5. Documentation updated
6. No API keys or secrets in code

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
- **Testing**: [docs/engineering/testing.md](docs/engineering/testing.md)
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
uv run python -m apps.cli.main

# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=packages --cov=apps --cov-report=html
```

---

*Last updated: 2026-02-07*
