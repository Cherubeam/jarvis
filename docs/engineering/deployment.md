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

Edit files in `personal-context/context/`:

**`profile.md`** - Who you are:
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

### `config.yaml`

Main configuration file at project root:

```yaml
openrouter:
  default_model: "anthropic/claude-sonnet-4.5"

system_prompt_prefix: |
  You are a helpful personal assistant.

paths:
  context_dir: "personal-context/context"
  conversations_dir: "personal-context/memory/conversations"
```

**Key Settings:**

- `default_model`: LLM model to use (see [Model Comparison](../research/models.md))
- `system_prompt_prefix`: Base instruction for the assistant
- `paths`: Where to find context files and save conversations

---

## Running Jarvis

### Start CLI

```bash
uv run python personal-context/src/cli.py
```

Or with activated virtual environment:
```bash
source .venv/bin/activate
python personal-context/src/cli.py
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

## Switching Providers

### Using OpenRouter (Default)

Already configured. Just ensure `OPENROUTER_API_KEY` is set.

### Using Anthropic Directly

1. Get API key from [Anthropic Console](https://console.anthropic.com/)
2. Add to `.env`:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```
3. Update `cli.py`:
   ```python
   client = LLMClient(
       api_key=config["anthropic"]["api_key"],
       default_model="claude-3-5-sonnet-20241022",
       provider="anthropic"
   )
   ```

### Using OpenAI Directly

1. Get API key from [OpenAI Platform](https://platform.openai.com/)
2. Add to `.env`:
   ```
   OPENAI_API_KEY=your_key_here
   ```
3. Update `cli.py`:
   ```python
   client = LLMClient(
       api_key=config["openai"]["api_key"],
       default_model="gpt-4o",
       provider="openai"
   )
   ```

---

## File Structure

```
jarvis/
├── .env                            # API keys (DO NOT COMMIT)
├── .gitignore                      # Excludes .env, conversations/
├── config.yaml                     # Main configuration
├── README.md                       # Project overview
├── docs/                           # Documentation
│   ├── product/
│   ├── engineering/
│   └── research/
├── personal-context/
│   ├── context/                    # User context (commit these)
│   │   ├── profile.md
│   │   ├── preferences.md
│   │   └── current_focus.md
│   ├── memory/
│   │   └── conversations/          # Session logs (gitignored)
│   └── src/
│       ├── cli.py
│       ├── context_builder.py
│       ├── llm_client.py
│       ├── memory.py
│       └── pricing.py
└── pyproject.toml                  # Python project metadata
```

---

## Data Management

### Conversation Logs

Saved to `personal-context/memory/conversations/`:
- Format: `YYYY-MM-DD_HH-MM-SS_<model>.json`
- **Gitignored by default** (contain sensitive data)

### Backup Strategy

**What to back up:**
- ✅ `personal-context/context/*.md` (your context files)
- ✅ `config.yaml` (your configuration)
- ✅ `personal-context/memory/conversations/*.json` (optional, if you want history)

**How to back up:**
```bash
# Simple: Copy entire directory
cp -r personal-context/ ~/backups/jarvis-$(date +%Y%m%d)/

# Better: Use git for context files
cd personal-context/context
git init
git add *.md
git commit -m "Update context"

# Best: Encrypted backup of everything
tar -czf - personal-context/ | gpg -c > jarvis-backup-$(date +%Y%m%d).tar.gz.gpg
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
uv pip install litellm
```

#### "File does not exist: context/profile.md"

**Solution**: Create context files:
```bash
mkdir -p personal-context/context
echo "# About Me" > personal-context/context/profile.md
echo "# Preferences" > personal-context/context/preferences.md
echo "# Current Focus" > personal-context/context/current_focus.md
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
- Add model routing (Phase 5)

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
   uv sync --all-extras
   ```

3. Run type checking:
   ```bash
   mypy personal-context/src/
   ```

4. Run tests (when available):
   ```bash
   pytest
   ```

---

## Deployment Modes

### Local CLI (Current)

```bash
python personal-context/src/cli.py
```

### API Server (Future)

```bash
# Not yet implemented
uvicorn api:app --reload
```

### Docker (Future)

```bash
# Not yet implemented
docker build -t jarvis .
docker run -it -v $(pwd)/personal-context:/app/personal-context jarvis
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
# Using uv
uv pip install --upgrade litellm

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
2. Back up your `personal-context/` directory
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

*Last updated: 2026-01-14*
