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

## Creating a New Agent

### Data-Driven Agent (recommended for simple agents)

1. Create a directory under `packages/agents/<name>/`
2. Add `meta.yaml`:
   ```yaml
   name: my-agent
   description: What this agent does
   command: /my-agent
   skills:            # optional: bind skill knowledge into the agent
     - my-skill-name
   ```
3. Add `prompts/system.md` with the system prompt
4. Done — the registry discovers it automatically

**Skill binding**: The optional `skills:` field lists skill names from `packages/skills/`. Simple skills have their SKILL.md body appended to the system prompt. Deck-skills get a card search tool (if RAG is enabled). See `packages/agents/pattern_language_expert/meta.yaml` for an example.

### Python-Class Agent (for custom logic)

Use this when you need custom prompt composition, non-default temperature, or custom `process_message()` logic.

1. Create `packages/agents/<name>/`
2. Add `__init__.py` with `AGENT_META` dict
3. Add `agent.py` extending `BaseAgent`
4. Add `prompts/system.md`

See `packages/agents/writing/` (custom prompt composition) or `packages/agents/tactics/` (custom temperature + tools) for examples.

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

After any implementation, check and update all relevant files in `docs/`. Always update [docs/changelog.md](docs/changelog.md). See the docs folder structure for which files may need changes.

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

### Branching

Always create a feature branch before starting work. Never commit directly to `main`.

```bash
git switch -c <type>/<short-description>
```

**Examples:**
```bash
git switch -c feat/task-sync-localization
git switch -c fix/stale-unit-tests
git switch -c refactor/config-loading
```

### Committing During Development

Always commit automatically after completing each development step — do not wait for user confirmation. Use a one-line commit message following the format below. Do not batch multiple steps into a single commit.

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

## Releasing

### When to Release

Cut a new version when a coherent set of features is complete and merged to `main`.
A release doesn't need to be large — even a single meaningful feature warrants a version bump.

### How to Release

1. **Update changelog**: Move items from `[Unreleased]` into a new `[X.Y.Z] - YYYY-MM-DD` section in `docs/changelog.md`
2. **Bump version**: Update `version` in `pyproject.toml`
3. **Commit**: `chore: release vX.Y.Z`
4. **Tag**: `git tag -a vX.Y.Z -m "Release X.Y.Z - <short description>"`
5. **Push**: `git push origin main --tags`
6. **GitHub Release**: `gh release create vX.Y.Z --title "vX.Y.Z - <theme>" --notes-file <changelog_excerpt>`

### Version Numbering (SemVer)

- **PATCH** (0.0.X): Bug fixes only
- **MINOR** (0.X.0): New features (backward compatible)
- **MAJOR** (X.0.0): Breaking changes

While pre-1.0, minor bumps may include breaking changes.

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

---

*Last updated: 2026-03-12*
