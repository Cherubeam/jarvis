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

### Naming Conventions (Agents & Skills)

| Entity | Pattern | Examples |
|--------|---------|---------|
| Agent directory | `snake_case` | `writer/`, `content_reviewer/` |
| Agent name (meta.yaml `name:`) | `snake_case` | `writer`, `content_reviewer` |
| Agent command (meta.yaml `command:`) | `/kebab-case` | `/write`, `/content-review` |
| Skill directory | `kebab-case` | `substack-prepare-to-publish/` |
| Skill name (in meta.yaml `skills:`) | `kebab-case` | `substack-prepare-to-publish` |
| Tool group key (in main.py) | `snake_case` | `blog_tools`, `content_evaluator` |
| Tool name (ToolDefinition `name=`) | `snake_case` | `evaluate_content`, `read_note` |
| Tool file | `snake_case.py` | `vault_read_tools.py` |
| Prompt include files | `kebab-case.md` | `voice-profile.md` |

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

See [docs/engineering/architecture.md](docs/engineering/architecture.md) for the full project structure.

---

## Creating a New Agent

### Data-Driven Agent (all delegate agents use this)

1. Create a directory under `packages/agents/<name>/`
2. Add `meta.yaml`:
   ```yaml
   name: my_agent
   description: What this agent does
   command: /my-agent
   temperature: 0.7          # optional (default 0.7)
   max_tokens: 4096           # optional (default: provider decides)
   max_iterations: 20         # optional: for multi-step agentic loops
   vault_writing: slip_box    # optional: scoped vault write tools from obsidian.writing.<key>
   skills:                    # optional: bind skill knowledge into the agent
     - my-skill-name
   tools:                     # optional: named tool groups from CLI registry
     - blog_tools
     - content_evaluator
   prompt_includes:           # optional: replace {placeholder} in system.md
     voice_profile: voice-profile   # loads prompts/voice-profile.md
   ```
3. Add `prompts/system.md` with the system prompt
4. Done — the registry discovers it automatically

**Tool groups**: The `tools:` field lists named tool groups registered in `apps/cli/main.py`. Available groups: `blog_tools`, `content_evaluator`, `suggest_improvements`, `dev_tools`, `card_search`. Shared tools (vault read, recall) go to all agents automatically.

**Shared prompt includes**: If a prompt include file isn't found in the agent's `prompts/` dir, the resolver falls back to `packages/agents/_shared/prompts/`. Voice profile and anti-patterns live there.

**Skill binding**: The `skills:` field lists skill names from `packages/skills/`. Simple skills have their SKILL.md body appended to the system prompt. Deck-skills get a card search tool (if RAG is enabled). See `packages/agents/pattern_language_expert/meta.yaml` for an example.

**Prompt includes**: The `prompt_includes:` field maps placeholder names to filenames in `prompts/` (agent-local first, then `_shared/prompts/` fallback). Each `{placeholder}` in `system.md` is replaced with the file content. See `packages/agents/writer/meta.yaml`.

### Python-Class Agent (escape hatch)

Only used for JarvisAgent (the orchestrator) which needs custom delegation logic. All delegate agents should be data-driven.

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

- `data/conversations/YYYY/*.json` - Conversation logs (organized by year)
- `docs/product/decisions.md` - Architecture Decision Records

---

## Documentation Updates

After any implementation, review and update **all** relevant documentation — not just changelog. Check each of these:

- **[README.md](README.md)** — features list, usage examples, slash commands, project structure, roadmap summary
- **[docs/changelog.md](docs/changelog.md)** — always update (new entry under `[Unreleased]`)
- **[docs/engineering/architecture.md](docs/engineering/architecture.md)** — if project structure or components changed
- **[docs/engineering/api.md](docs/engineering/api.md)** — if public interfaces changed
- **[docs/product/roadmap.md](docs/product/roadmap.md)** — if a roadmap item was completed or added
- **[docs/product/decisions.md](docs/product/decisions.md)** — if an architectural decision was made (new ADR)
- **[AGENTS.md](AGENTS.md)** — if agents, commands, or development workflow changed

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

### Merging

Merges to `main` must be fast-forward where possible:

```bash
git switch main
git merge --ff-only <feature-branch>
```

If fast-forward isn't possible, rebase the feature branch first:

```bash
git switch <feature-branch>
git rebase main
git switch main
git merge --ff-only <feature-branch>
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

*Last updated: 2026-03-13*
