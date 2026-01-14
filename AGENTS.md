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

### ⚠️ ALWAYS use `uv add`, NEVER use `pip install` or `uv pip install`

**❌ WRONG:**
```bash
pip install package
uv pip install package
```

**✅ CORRECT:**
```bash
uv add package
```

**Why this matters:**
- `uv add` updates both `pyproject.toml` AND `uv.lock`
- `uv pip install` only installs to `.venv` (not tracked)
- Missing from `pyproject.toml` = project breaks on fresh setup

### Other Dependency Commands

```bash
uv remove package           # Remove dependency
uv add package --upgrade    # Update specific package
uv sync                     # Install from lock file
uv sync --upgrade          # Update all dependencies
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

### Tests (Planned, not yet implemented)

```bash
pytest tests/
```

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
│   ├── memory/conversations/       # Session logs (gitignored)
│   └── src/                        # Source code
│       ├── cli.py                  # Entry point
│       ├── llm_client.py           # LLM abstraction (LiteLLM)
│       ├── context_builder.py      # System prompt assembly
│       ├── memory.py               # Conversation logging
│       └── pricing.py              # Cost tracking
└── docs/                           # Documentation
    ├── product/                    # Product docs (vision, roadmap, metrics, ADRs)
    ├── engineering/                # Technical docs (architecture, API, testing)
    └── research/                   # AI engineering (framework, models, prompts)
```

---

## Testing Guidelines

### Manual Testing (Current)

1. Start CLI: `uv run python personal-context/src/cli.py`
2. Verify context loading (check system prompt includes profile.md)
3. Test streaming responses
4. Verify token/cost tracking
5. Check conversation logs saved

### Automated Testing (Planned Phase 2)

- **Golden test suite**: 5-10 representative conversations
- **Unit tests**: Each module tested in isolation
- **Integration tests**: Full request flow

---

## Important Files to Preserve

### Never Modify Without Explicit Request

- `config.yaml` - User configuration
- `personal-context/context/*.md` - User's personal context
- `.env` - API keys (never commit)

### Read-Only Unless Fixing Bugs

- `personal-context/memory/conversations/*.json` - Conversation logs
- `docs/product/decisions.md` - Architecture Decision Records

---

## Documentation Updates

### When Making Changes

1. **Code changes** → Update [docs/engineering/architecture.md](docs/engineering/architecture.md) or [api.md](docs/engineering/api.md)
2. **New features** → Update [docs/product/roadmap.md](docs/product/roadmap.md)
3. **Architecture decisions** → Add new ADR to [docs/product/decisions.md](docs/product/decisions.md)
4. **Version releases** → Update [docs/changelog.md](docs/changelog.md)

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

1. ✅ Dependencies added via `uv add`
2. ✅ Code works after clean setup (`rm -rf .venv && uv sync`)
3. ✅ Type checking passes (if applicable)
4. ✅ Documentation updated
5. ✅ No API keys or secrets in code

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

*Last updated: 2026-01-14*
