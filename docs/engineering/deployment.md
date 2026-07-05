# Setup & Deployment

> How to install, configure, and run Jarvis.

---

## Prerequisites

### System Requirements

- **OS**: macOS, Linux, or WSL2 on Windows
- **Python**: 3.13 or higher
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (recommended)

### API Keys

- **Required**: [OpenRouter API key](https://openrouter.ai/)
- **Optional**: Direct provider keys (Anthropic, OpenAI)

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/jarvis.git
cd jarvis
```

### 2. Install Dependencies

**Using uv (recommended):**
```bash
uv sync
```

**Using pip:**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

Create `.env` file:
```bash
echo "OPENROUTER_API_KEY=your_key_here" > .env
```

**Security Note**: Never commit `.env` to git (already in `.gitignore`).

### 4. Configure Personal Context

Edit files in `data/context/`:

**`personal_context.md`** - Who you are:
```markdown
# About Me

I am a software engineer learning AI engineering.
I work primarily with Python and enjoy building tools.
```

**`preferences.md`** - How the assistant should behave:
```markdown
# Communication Preferences

- Be concise and technical
- Provide code examples when relevant
- Ask clarifying questions when ambiguous
```

**`current_focus.md`** - What you're working on:
```markdown
# Current Focus

Working on:
- Building Jarvis, a personal AI assistant
- Learning about RAG and vector databases
- Exploring agentic AI frameworks
```

---

## Configuration

### Configuration Files

Configuration is stored in `config/`:

**`config/default.yaml`** - Default configuration:
```yaml
openrouter:
  default_model: "anthropic/claude-sonnet-4.5"

system_prompt_prefix: |
  You are a helpful personal assistant.

paths:
  context_dir: "data/context"
  conversations_dir: "data/conversations"  # files stored in YYYY/ subdirs
  learned_facts: "data/learned_facts.md"
```

**`config/local.yaml`** - Local overrides (gitignored):
```yaml
# Override any settings from default.yaml
openrouter:
  default_model: "anthropic/claude-3-5-haiku-20241022"
```

**Key Settings:**

- `default_model`: LLM model to use (see [Model Comparison](../research/models.md))
- `system_prompt_prefix`: Base instruction for the assistant
- `paths`: Where to find context files and save conversations

---

## Running Jarvis

### Start CLI

```bash
# Using uv (recommended)
uv run python -m apps.cli.main

# Or using the installed script
uv run jarvis
```

Or with activated virtual environment:
```bash
source .venv/bin/activate
python -m apps.cli.main
```

### Usage

```
Personal Assistant
Model: anthropic/claude-sonnet-4.5 ($3.00/$15.00 per 1M tokens)
Type 'quit' or 'exit' to end. Ctrl+C also works.

You: Hello!
Assistant: Hi! How can I help you today?

You: quit
[15,234 tokens | $0.0456]
Goodbye!
```

**Commands:**
- Type message and press Enter
- `quit` or `exit` to end session
- `Ctrl+C` to interrupt

---

## Switching Models and Providers

Model IDs use full LiteLLM-routable format with provider prefix (e.g. `openrouter/anthropic/claude-sonnet-4.6`). The provider is inferred from the prefix — no code changes needed.

### At Startup (CLI Flag)

```bash
# Use a preset
uv run python -m apps.cli.main --model quality   # → openrouter/anthropic/claude-opus-4.6
uv run python -m apps.cli.main --model fast       # → openrouter/google/gemini-2.5-flash

# Use a literal model ID
uv run python -m apps.cli.main --model anthropic/claude-sonnet-4.6
```

### Mid-Session (`/model` Command)

```
/model                    # Show current model + available presets
/model fast               # Switch to fast preset
/model openai/gpt-4o      # Switch to a specific model
```

### Configuring Presets

Edit `config/default.yaml` (or `config/local.yaml`):
```yaml
models:
  default: "openrouter/anthropic/claude-sonnet-4.6"
  presets:
    fast: "openrouter/google/gemini-2.5-flash"
    quality: "openrouter/anthropic/claude-opus-4.6"
    balanced: "openrouter/anthropic/claude-sonnet-4.6"
```

### Using Different Providers

1. Add the provider's API key to `.env`:
   ```
   OPENROUTER_API_KEY=your_key_here    # OpenRouter (default)
   ANTHROPIC_API_KEY=your_key_here     # Direct Anthropic
   OPENAI_API_KEY=your_key_here        # Direct OpenAI
   GOOGLE_API_KEY=your_key_here        # Direct Google
   ```
2. Use the corresponding model prefix:
   ```bash
   uv run python -m apps.cli.main --model anthropic/claude-sonnet-4.6
   uv run python -m apps.cli.main --model openai/gpt-4o
   ```

Only the API key for the resolved provider is required.

---

## File Structure

See [docs/engineering/architecture.md](architecture.md#file-structure) for the full project structure.

---

## Data Management

### Conversation Logs

Saved to `data/conversations/YYYY/`:
- Format: `YYYY/YYYY-MM-DD_HH-MM-SS.json` (organized by year)
- **Gitignored by default** (contain sensitive data)

### Backup Strategy

**What to back up:**
- ✅ `data/context/*.md` (your context files)
- ✅ `config/default.yaml` (your configuration)
- ✅ `data/conversations/YYYY/*.json` (optional, if you want history)

**How to back up:**
```bash
# Simple: Copy data directory
cp -r data/ ~/backups/jarvis-data-$(date +%Y%m%d)/

# Better: Use git for context files
cd data/context
git init
git add *.md
git commit -m "Update context"

# Best: Encrypted backup of everything
tar -czf - data/ config/ | gpg -c > jarvis-backup-$(date +%Y%m%d).tar.gz.gpg
```

---

## Troubleshooting

### Common Issues

#### "OPENROUTER_API_KEY not found"

**Solution**: Create `.env` file with your API key:
```bash
echo "OPENROUTER_API_KEY=sk-or-v1-..." > .env
```

#### "Import litellm could not be resolved"

**Solution**: Install dependencies:
```bash
uv sync
```

#### "File does not exist: context/personal_context.md"

**Solution**: Create context files:
```bash
mkdir -p data/context
echo "# About Me" > data/context/personal_context.md
echo "# Professional Background" > data/context/professional_context.md
echo "# Preferences" > data/context/preferences.md
echo "# Current Focus" > data/context/current_focus.md
```

#### Slow responses

**Causes:**
- Model is slow (Opus takes longer than Haiku)
- Network latency to API
- Large context window

**Solutions:**
- Switch to faster model (Haiku, GPT-4o-mini)
- Check internet connection
- Reduce context size

#### High costs

**Solutions:**
- Use cheaper model (see [Model Comparison](../research/models.md))
- Implement context truncation (future)
- Add model routing (`CAP`)

---

## Development Setup

### For Contributors

1. Clone with git hooks:
   ```bash
   git clone https://github.com/yourusername/jarvis.git
   cd jarvis
   ```

2. Install dev dependencies:
   ```bash
   uv sync --extra test
   ```

3. Run type checking:
   ```bash
   mypy packages/ apps/
   ```

4. Run tests:
   ```bash
   uv run pytest
   ```

5. Run tests with coverage:
   ```bash
   uv run pytest --cov=packages --cov=apps --cov-report=html
   ```

---

## Deployment Modes

### Local CLI (Current)

```bash
uv run python -m apps.cli.main
# Or
uv run jarvis
```

### Web Interface (WEB)

```bash
# Backend
cd apps/web/backend
uvicorn main:app --reload

# Frontend (in separate terminal)
cd apps/web/frontend
npm run dev
```

### Docker (Future)

```bash
# Not yet implemented
docker build -t jarvis .
docker run -it -v $(pwd)/data:/app/data jarvis
```

---

## Security Best Practices

### API Keys

- ✅ Store in `.env` file (gitignored)
- ✅ Never commit to version control
- ✅ Use environment-specific keys (dev/prod)
- ❌ Don't hardcode in source files

### Conversation Logs

- ⚠️ Contain sensitive personal data
- ✅ Gitignored by default
- ✅ Consider encrypted backups
- ✅ Review before sharing

### Context Files

- ⚠️ May contain personal information
- ✅ Think before committing to git
- ✅ Use private repository if needed

---

## Updates & Maintenance

### Updating Dependencies

```bash
# Update a specific package
uv add --upgrade litellm

# Or update all
uv sync --upgrade
```

### Checking for Updates

```bash
# Pull latest changes
git pull origin main

# Review changelog
cat docs/changelog.md
```

### Migration Guide

**When updating Jarvis:**
1. Read [changelog.md](../changelog.md) for breaking changes
2. Back up your `data/` directory
3. Pull updates: `git pull`
4. Update dependencies: `uv sync`
5. Test with a simple conversation

---

## Support

### Getting Help

1. Check [Documentation](../README.md)
2. Review [Troubleshooting](#troubleshooting)
3. Open [GitHub Issue](https://github.com/yourusername/jarvis/issues)

### Reporting Bugs

Include:
- Python version (`python --version`)
- OS and version
- Steps to reproduce
- Error messages
- Relevant config (redact API keys!)

---

*Last updated: 2026-02-07*
