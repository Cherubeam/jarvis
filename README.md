# Jarvis

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-94A3B8?logo=openrouter&logoColor=fff)](#)

> A personal AI assistant built from first principles to solve the vendor lock-in problem in conversational AI.

![Jarvis Header Image](/jarvis.png)

## Motivation

Most professionals rely on ChatGPT, Claude, Gemini, or Copilot subscriptions to interact with AI. These tools are powerful, but they create a critical dependency: **all your context, conversation history, and learned preferences are locked within each provider's ecosystem.**

As someone learning AI Engineering, I wanted to solve this problem for myself while documenting the journey. Jarvis is the result: a provider-agnostic personal assistant that:

- Maintains persistent context and conversation history **that I control**
- Works with any LLM provider through a unified interface (currently OpenRouter)
- Stores everything locally in human-readable markdown files
- Can be extended and customized as my needs evolve

This project demonstrates my approach to learning: **build solutions to real problems, keep them simple, and document the reasoning behind every decision.**

## How It Works

Jarvis follows a straightforward architecture that prioritizes clarity and maintainability:

```
┌─────────────────┐
│   Context Files │  (personal_context.md, preferences.md, current_focus.md)
│   (Markdown)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Context Builder │  Assembles system prompt from context files
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Agent       │  Data-driven (meta.yaml) or Python class
│  (Orchestrator  │  Specialist agents for focused tasks
│  or Specialist) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Tools       │  Web fetch, conversation recall, etc.
│  (Agentic Loop) │  Max 5 iterations per request
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Stream Handler  │  Streams responses from any provider (via OpenRouter)
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Conversation    │────▶│   RAG Index     │  Semantic search over history
│ Memory          │     │  (ChromaDB,     │  (optional, opt-in)
│                 │     │   optional)     │
└─────────────────┘     └─────────────────┘
```

### Key Design Principles

1. **Human-readable storage**: All context and conversations are stored as markdown or JSON files you can edit directly
2. **Provider independence**: Switching from Claude to GPT-4 is a one-line config change
3. **Simplicity first**: No unnecessary abstractions—just clean functions that do one thing well
4. **Local-first**: Your data lives on your machine, not in someone else's cloud

## Features

- **Agent Framework**: Slash-command routing to specialist agents (Writing, Research, Clarity, Navigator, Tactics, OKR Architect, Pattern Language Expert)
- **Data-Driven Agents**: Most agents defined via `meta.yaml` + `prompts/system.md` -- no Python class needed
- **Standalone Agent Mode**: Run any agent directly with `--agent <name>`
- **Tool Calling**: Agentic loop with tool execution (max 5 iterations per request)
- **Web Fetch Tool**: URL fetching with content extraction (httpx + trafilatura)
- **Conversation Recall (RAG)**: Semantic search over conversation history via ChromaDB (opt-in)
- **Enhanced CLI UX**: Rich terminal formatting, markdown rendering, prompt_toolkit with paste support and input history
- **Persistent Personal Context**: Define who you are, your preferences, and current focus areas in simple markdown files
- **Conversation Memory**: All interactions are logged with timestamps, creating a searchable history
- **Streaming Responses**: Real-time token-by-token output for a responsive chat experience
- **Provider Agnostic**: Unified interface to multiple LLM providers through OpenRouter/LiteLLM
- **Token & Cost Tracking**: Automatic tracking of usage and costs per request and session
- **Latency Metrics**: TTFT and total latency captured per response
- **Simple Configuration**: YAML-based config with sensible defaults
- **Obsidian Integration**: Generate daily note summaries from conversation history
- **Things 3 Integration**: Auto-sync tasks from Things 3 (macOS) via SQLite for task-aware responses
- **Comprehensive Testing**: Automated test suite with high code coverage
- **Benchmark Cost Estimation**: Estimate golden test run costs per model before evaluation
- **Conversation Import**: Import ChatGPT and Claude exports into Jarvis format

## Getting Started

### Prerequisites

- Python 3.13+
- An [OpenRouter](https://openrouter.ai/) API key

### Installation

```bash
# Clone the repository
git clone https://github.com/Cherubeam/jarvis.git
cd jarvis

# Install dependencies using uv (https://github.com/astral-sh/uv)
uv sync

# Set up your environment variables
echo "OPENROUTER_API_KEY=your_key_here" > .env

# Configure your personal context
# Edit the files in data/context/:
# - personal_context.md (who you are)
# - professional_context.md (professional background)
# - preferences.md (how the assistant should behave)
# - current_focus.md (what you're working on)
```

### Usage

```bash
# Start JARVIS (default orchestrator)
uv run jarvis

# Run a specialist agent directly
uv run jarvis --agent writing
uv run jarvis --agent research
uv run jarvis --agent clarity
uv run jarvis --agent navigator
uv run jarvis --agent tactics
```

During a chat session, you can use slash commands:

```
/write <text>           Delegates to Writing agent (prose, editing, rewriting)
/research <text>        Delegates to Research agent (analysis, synthesis)
/clarity <text>         Delegates to Clarity agent (explains complex ideas simply)
/navigator              Enters Navigator agent session (alignment, weekly reviews)
/tactics                Enters Tactics agent session (Pip Decks coaching)
/okr-architect          Enters OKR Architect agent session
/pattern-language-expert  Enters Pattern Language Expert session
/daily-summary          Generates an Obsidian daily note summary
```

Type `quit` or `exit` to end the session.

### Troubleshooting

**`ModuleNotFoundError: No module named 'apps'` when running `uv run jarvis`**

On macOS with Python 3.13+, the editable-install `.pth` file can get a hidden flag (`UF_HIDDEN`) that causes Python to skip it during startup. Fix it with:

```bash
# Remove the hidden flag from the .pth file
chflags nohidden .venv/lib/python3.13/site-packages/_jarvis.pth

# Or recreate the virtual environment from scratch
rm -rf .venv && uv sync
```

### Importing Conversations

```bash
# ChatGPT
uv run python scripts/import_chatgpt.py imports/conversations.json --dry-run
uv run python scripts/import_chatgpt.py imports/conversations.json
uv run python scripts/import_chatgpt.py imports/conversations.json --date-from 2025-01-01 --model gpt-4o --include-archived

# Claude conversations
uv run python scripts/import_claude.py imports/conversations.json --dry-run
uv run python scripts/import_claude.py imports/conversations.json
uv run python scripts/import_claude.py imports/conversations.json --date-from 2025-01-01

# Claude context (memories + projects)
uv run python scripts/import_claude_context.py --dry-run
uv run python scripts/import_claude_context.py
uv run python scripts/import_claude_context.py --memories imports/memories.json --projects imports/projects.json
```

Imports are idempotent — re-running safely updates existing conversations with new messages and title changes (Claude), or skips unchanged conversations (ChatGPT).

### Switching LLM Providers

Edit `config/default.yaml` or `config/local.yaml`:

```yaml
models:
  default: "openrouter/anthropic/claude-sonnet-4.6"  # Change to desired model
```

See [docs/engineering/deployment.md](docs/engineering/deployment.md) for full provider configuration.

## Project Structure

```
jarvis/
├── apps/                               # Deployable applications
│   ├── cli/                            # CLI entry point
│   │   ├── main.py                     # Command-line interface
│   │   └── display.py                  # Rich terminal formatting
│   └── web/                            # Web application (Phase 6, placeholder)
│
├── packages/                           # Shared libraries
│   ├── core/                           # Core functionality
│   │   ├── llm_client.py               # Unified LLM provider interface
│   │   ├── context_builder.py          # Assembles system prompts from context
│   │   ├── stream_handler.py           # Streaming response handler with agentic loop
│   │   ├── memory.py                   # Conversation logging (schema v1.0.0)
│   │   ├── pricing.py                  # Cost calculation and tracking
│   │   ├── benchmark_costs.py          # Benchmark cost estimation
│   │   ├── importers/                  # Conversation importers (ChatGPT, Claude)
│   │   ├── rag/                        # Conversation recall (optional, ChromaDB)
│   │   │   ├── indexer.py              # Startup scan, message-pair chunking
│   │   │   └── searcher.py             # Cosine similarity search with date filters
│   │   └── tools/                      # Tool calling infrastructure
│   │       ├── base.py                 # ToolDefinition + ToolRegistry
│   │       ├── executor.py             # Tool call execution
│   │       ├── web_fetch.py            # URL fetch (httpx + trafilatura)
│   │       └── conversation_recall.py  # RAG search tool
│   ├── agents/                         # Agent implementations
│   │   ├── base.py                     # Base agent class + DataDrivenAgent
│   │   ├── registry.py                 # Filesystem-based agent auto-discovery
│   │   ├── jarvis/                     # Main JARVIS orchestrator agent (Python class)
│   │   ├── writing/                    # Writing specialist (Python class, custom prompt composition)
│   │   ├── tactics/                    # Tactics (Python class, custom temperature)
│   │   ├── research/                   # Research specialist (meta.yaml)
│   │   ├── clarity/                    # Clarity specialist (meta.yaml)
│   │   ├── navigator/                  # Navigator (meta.yaml)
│   │   ├── okr_architect/              # OKR Architect (meta.yaml)
│   │   ├── obsidian_note_creator/      # Obsidian Note Creator (meta.yaml)
│   │   └── pattern_language_expert/    # Pattern Language Expert (meta.yaml)
│   ├── skills/                         # Skills (passive knowledge packs for card indexing)
│   │   ├── base.py                     # BaseSkill (parses SKILL.md, optional skill.py)
│   │   ├── registry.py                 # Filesystem-based skill discovery
│   │   ├── content-evaluator/          # Content evaluation (SKILL.md + skill.py)
│   │   └── .../                        # Additional skills (each has SKILL.md)
│   ├── integrations/                   # External service integrations
│   │   ├── things3/                    # Things 3 task sync
│   │   └── obsidian/                   # Obsidian daily note integration
│   │       ├── vault.py                # Vault reader with symlink protection
│   │       ├── callout.py              # Callout block parser
│   │       ├── diff.py                 # Diff computation and formatting
│   │       ├── writer.py               # Note writer with confirmation
│   │       └── prompts.py              # Prompt loader
│   └── telemetry/                      # Metrics and evaluation
│
├── data/                               # User data
│   ├── context/                        # Your personal context files
│   │   ├── personal_context.md         # Who you are
│   │   ├── professional_context.md     # Professional background
│   │   ├── preferences.md              # Assistant behavior preferences
│   │   ├── current_focus.md            # Current projects and priorities
│   │   ├── tasks.md                    # Auto-synced from Things 3
│   │   └── projects/                   # Project-specific context
│   ├── conversations/                  # Timestamped conversation logs
│   ├── prompts/                        # Prompt templates
│   │   └── obsidian/                   # Obsidian-specific prompts
│   └── rag/                            # ChromaDB vector store (runtime, gitignored)
│
├── scripts/                            # Utility scripts
│   ├── import_chatgpt.py               # ChatGPT conversation importer
│   ├── import_claude.py                # Claude conversation importer
│   ├── import_claude_context.py        # Claude context importer
│   ├── model_benchmark.py              # Model benchmark runner
│   ├── benchmark_report.py             # Benchmark report generator
│   ├── analyze_costs.py                # Cost analysis
│   ├── analyze_context.py              # Context utilization analyzer
│   └── link_skills.sh                  # Symlink private skills repo
│
├── config/                             # Configuration
│   ├── default.yaml                    # Default configuration
│   └── local.yaml                      # Local overrides (gitignored)
│
├── tests/                              # Comprehensive test suite
│   ├── unit/                           # Unit tests
│   ├── integration/                    # Integration tests
│   ├── golden/                         # Golden test conversations + LLM-as-judge
│   └── README.md                       # Testing guide
│
├── docs/                               # Documentation
│   ├── product/                        # Product specs and roadmap
│   ├── engineering/                    # Technical documentation
│   └── research/                       # AI engineering research
│
└── pyproject.toml                      # Project configuration
```

## Roadmap

This is a learning project, and I'm building it iteratively. Current priorities:

**Phase 1: Foundation & Metrics (Complete ✅)**
- [x] Basic chat interface with persistent context
- [x] Conversation logging and history
- [x] Token usage tracking and cost calculation
- [x] LiteLLM integration for provider flexibility
- [x] **Comprehensive testing framework**

**Phase 2: Evaluation & Quality Metrics (Complete ✅)**
- [x] 10 golden test conversations defined
- [x] **LLM-as-judge automated evaluation (~$0.41/run)**
- [x] **Things 3 integration** (SQLite-based task sync via `things.py`)
- [x] Latency tracking (TTFT)
- [x] Model comparison benchmarks
- [x] Benchmark cost estimation per model
- [x] Conversation schema v1.0.0 (structured logging with migration support)
- [x] ChatGPT conversation import (bulk import with filters)
- [x] Claude conversation import (bulk import with date filters)

**Phase 3: Context & Integrations (Complete ✅)**
- [x] Context builder with frontmatter selective loading
- [x] Obsidian daily note integration (`/daily-summary`)

**Phase 4: Agent Framework (Complete ✅)**
- [x] Base agent class with prompt loading
- [x] Agent registry with filesystem-based auto-discovery
- [x] Specialist agents: Writing, Research, Clarity
- [x] Slash-command routing and standalone `--agent` mode
- [x] StreamHandler extraction from CLI

**Phase 5: Agent Capabilities (In Progress)**
- [x] Tool calling infrastructure (`ToolDefinition`, `ToolRegistry`, agentic loop)
- [x] Web fetch tool (httpx + trafilatura)
- [x] Conversation recall via RAG (ChromaDB, opt-in)
- [x] Enhanced CLI UX (rich rendering, prompt_toolkit)
- [x] Skills framework (SKILL.md-driven, vendor-portable, used as passive knowledge packs)
- [x] JARVIS delegation (orchestrator auto-routes to specialists)
- [ ] Extended tools (web search, Playwright)
- [ ] Intelligent model routing (task complexity → model selection)

**Future Phases:**
- [ ] Web interface (Phase 6 — FastAPI + event-driven architecture)
- [ ] Context window management (truncation, summarization)
- [ ] System monitoring and optimization

See [docs/product/roadmap.md](docs/product/roadmap.md) for detailed plans.

## Benchmarking

Estimate benchmark costs anytime (uses latest golden run baseline):

```bash
uv run python scripts/model_benchmark.py
```

To run evaluations after the estimate (paid), add `--evaluate`.

Generate the benchmark comparison table in docs:

```bash
uv run python scripts/benchmark_report.py
```

## What I'm Learning

Building Jarvis is teaching me:

- **System design for AI applications**: How to structure context, manage conversation state, and handle streaming responses
- **API integration patterns**: Working with multiple LLM providers through a unified interface
- **Prompt engineering**: Crafting effective system prompts that incorporate personal context
- **Data persistence strategies**: Balancing human-readability with queryability
- **Token economics**: Understanding context windows, truncation, and cost optimization

## Why This Matters

This project demonstrates several things I value as an engineer:

1. **Problem-first thinking**: I identified a real pain point (vendor lock-in) and built a solution
2. **Learning by building**: Theory is great, but shipping code is how I learn best
3. **Simplicity over cleverness**: The codebase is intentionally straightforward—no premature optimization or over-engineering
4. **Documentation**: Every design decision is explained (see code comments and this README)
5. **Iterative development**: Start simple, ship early, improve based on real usage

## Tech Stack

- **Language**: Python 3.13
- **LLM Provider**: LiteLLM + OpenRouter (unified API for Claude, GPT-4, Gemini, etc.)
- **Terminal UI**: rich + prompt_toolkit
- **Storage**: Local filesystem (markdown + JSON)
- **Vector DB**: ChromaDB (optional, for conversation recall / RAG)
- **HTTP**: httpx + trafilatura (web fetch tool)
- **Configuration**: YAML + environment variables
- **Testing**: pytest ([details](docs/engineering/testing.md))
- **Package Management**: uv (fast Python package installer)

## Contributing

This is primarily a personal learning project, but if you find it useful or have suggestions, feel free to open an issue!

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Built by [Marco Braun](https://github.com/Cherubeam)** | Learning AI Engineering one commit at a time
