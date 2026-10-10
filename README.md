# Jarvis

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64.svg)](https://github.com/astral-sh/ruff)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-94A3B8?logo=openrouter&logoColor=fff)](#)
![Version 0.35.0](https://img.shields.io/badge/version-0.35.0-green.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

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
│  (Agentic Loop) │  Iteration limit per agent
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
│ Memory          │     │  (ChromaDB)     │  (on by default)
│                 │     │                 │
└─────────────────┘     └─────────────────┘
```

### Key Design Principles

1. **Human-readable storage**: All context and conversations are stored as markdown or JSON files you can edit directly
2. **Provider independence**: Switching from Claude to GPT-4 is a one-line config change
3. **Simplicity first**: No unnecessary abstractions—just clean functions that do one thing well
4. **Local-first**: Your data lives on your machine, not in someone else's cloud

## Features

- **Agent Framework**: Slash-command routing from the JARVIS orchestrator to specialist agents (Writer, Researcher, Content Reviewer, Reading Assistant and more — full list with commands and tools in [docs/engineering/agents.md](docs/engineering/agents.md))
- **Data-Driven Agents**: Delegate agents are defined via `meta.yaml` + `prompts/system.md` -- no Python class needed
- **Standalone Agent Mode**: Run any agent directly with `--agent <name>`
- **Tool Calling**: Agentic loop with tool execution and a per-agent iteration limit ([how it works](docs/engineering/architecture.md#agentic-loop))
- **Model Choice**: Presets in [`config/default.yaml`](config/default.yaml), chosen by benchmark ([docs/research/models.md](docs/research/models.md)); agents can pin their own model in `meta.yaml`; per-model request fields via `models.extra_body` ([how to switch](docs/engineering/deployment.md#switching-models-and-providers))
- **Model Routing** (opt-in): heuristic routing by query complexity (`routing.enabled`), or OpenRouter's Auto Router picking the model per turn (`models.auto_router.enabled`, `/model auto`; ADR-036). The model that answered and its billed cost are shown and logged
- **Safe Vault Edits**: Every write shows a diff for approval, lists changed links above it, and is refused if the note changed on disk since the agent read it ([details](docs/engineering/obsidian-integration.md#data-flow-summary))
- **Web Fetch & Search Tools**: URL fetching with content extraction (httpx + trafilatura) and DuckDuckGo search
- **Conversation Recall**: Meaning-based search over past JARVIS, Claude, Claude Code and ChatGPT conversations via Cortex's `search_conversations` (opt-in in Cortex, HUB-02); new conversations are searchable seconds after they are saved
- **Vault Semantic Search**: Meaning-based search over the Obsidian vault via the Cortex MCP server (opt-in, HUB-01)
- **Enhanced CLI UX**: Rich terminal formatting, markdown rendering, prompt_toolkit with paste support and input history
- **Persistent Personal Context**: Define who you are, your preferences, and current focus areas in simple markdown files
- **Conversation Memory**: All interactions are logged with timestamps, creating a searchable history
- **Streaming Responses**: Real-time token-by-token output; `/stream` toggles non-streaming mode. Streamed usage is logged as an estimate, then replaced with OpenRouter's billed record ([details](docs/engineering/architecture.md#streaming-and-prompt-caching))
- **History Summarization** (opt-in): Compresses old conversation turns in long sessions with the `fast` preset ([details](docs/engineering/architecture.md#history-summarization))
- **Provider Agnostic**: Unified interface to multiple LLM providers through OpenRouter/LiteLLM
- **Token & Cost Tracking**: Automatic tracking of usage and costs per request and session
- **Latency Metrics**: TTFT and total latency captured per response
- **Simple Configuration**: YAML-based config with sensible defaults
- **Obsidian Integration**: Vault read/write tools and daily note summaries from conversation history
- **Things 3 Integration** (read-only): Inbox, Today and Upcoming tasks synced into context through a Shortcut, no Full Disk Access needed ([setup](docs/engineering/deployment.md#things-3))
- **MCP Client Integration**: Connect external MCP (Model Context Protocol) servers over stdio, SSE or streamable HTTP; their tools appear as regular tool groups. Config-only setup ([guide](docs/engineering/deployment.md#connecting-mcp-servers))
- **GUI**: A browser-based peer to the CLI with the same agents, tools and conversation files ([docs/engineering/gui.md](docs/engineering/gui.md))
- **Testing**: Unit, integration and LLM-as-judge golden tests, plus mutation testing via mutmut ([docs/engineering/testing.md](docs/engineering/testing.md))
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
# Create the files in data/context/ (not tracked in git):
# - soul.md (JARVIS's identity, placed first in the prompt)
# - personal_context.md (who you are)
# - professional_context.md (professional background)
# - preferences.md (how the assistant should behave)
# - current_focus.md (what you're working on)
```

Configuration (models, integrations, MCP servers) is covered in
[docs/engineering/deployment.md](docs/engineering/deployment.md).

### Usage

```bash
# Start JARVIS (default orchestrator)
uv run jarvis

# Run a specialist agent directly
uv run jarvis --agent writer
uv run jarvis --agent researcher

# Start on another model (preset or model id)
uv run jarvis --model quality
```

During a chat session, JARVIS delegates to specialist agents on its own, or you enter one with its
slash command, for example `/write` (Writer) or `/research` (Researcher). Every agent's command is
in [docs/engineering/agents.md](docs/engineering/agents.md#agents). Commands that aren't agents:

```
/model [name]           Shows or switches the session model (preset, model id, or `auto`)
/stream                 Toggles between streaming and non-streaming response modes
/daily-summary [date]   Generates an Obsidian daily note summary (default: today)
/outcomes               Reviews pending tracked recommendations (score + retrospective)
```

Type `quit` or `exit` to end the session.

### GUI

```bash
uv sync --extra web
uv run jarvis-gui              # prints a "Sign in:" URL and opens it
```

The GUI is a browser-based peer to the CLI: same agents, tools, conversation files and approval
flow, plus Home, History, Agents (with a prompt editor), Outcomes and Settings views. It requires
the printed sign-in link once per browser. Surfaces, authentication and rebuild instructions are in
[docs/engineering/gui.md](docs/engineering/gui.md).

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
uv run python scripts/import_chatgpt.py ~/Downloads/chatgpt-export/conversations.json --dry-run
uv run python scripts/import_chatgpt.py ~/Downloads/chatgpt-export/conversations.json
uv run python scripts/import_chatgpt.py ~/Downloads/chatgpt-export/conversations.json --date-from 2025-01-01 --model gpt-4o --include-archived

# Claude conversations
uv run python scripts/import_claude.py ~/Downloads/claude-export/conversations.json --dry-run
uv run python scripts/import_claude.py ~/Downloads/claude-export/conversations.json
uv run python scripts/import_claude.py ~/Downloads/claude-export/conversations.json --date-from 2025-01-01

# Claude Code sessions (reads ~/.claude/projects and the desktop app's session titles)
uv run python scripts/import_claude_code.py --dry-run
uv run python scripts/import_claude_code.py --date-from 2026-10-01
```

Raw exports are kept in `paths.imports_dir` (`<source>/<export date>/export/`) as the record
of origin; the memory importer archives a Claude export there on its first run. Claude memory
exports don't overwrite anything: `scripts/import_claude_memory.py <export folder>`
proposes changes to your memory notes and applies only what you approve
([how it works](docs/engineering/deployment.md#importing-claude-memory)).

Imports are idempotent — re-running safely updates existing conversations with new messages and title changes (Claude, Claude Code), or skips unchanged conversations (ChatGPT). Claude Code imports keep prompts, replies, thinking and one-line tool-call summaries; tool output is reduced to its size except the reports subagents return, and subagent transcripts are not imported.

### Connecting MCP Servers

JARVIS can connect to external [MCP](https://modelcontextprotocol.io/) servers and give their tools
to agents; it's a config-only change in `config/local.yaml`. The step-by-step guide (including the
Cortex vault-search server) is in [docs/engineering/deployment.md](docs/engineering/deployment.md#connecting-mcp-servers).

### Switching LLM Providers

Change `models.default` or a preset in `config/local.yaml`, or use `--model` / `/model`. See
[docs/engineering/deployment.md](docs/engineering/deployment.md#switching-models-and-providers).

## Project Structure

```
jarvis/
├── apps/          # Deployable applications: cli/ (terminal) and gui/ (FastAPI + React)
├── packages/      # Shared libraries: core/, agents/, skills/, integrations/, telemetry/
├── config/        # default.yaml (defaults) + local.yaml (your overrides, gitignored)
├── data/          # Your context files, conversations, outcomes, RAG store (gitignored)
├── scripts/       # Importers, benchmarks, analysis tools
├── tests/         # Unit, integration and golden (LLM-as-judge) tests
├── docs/          # Product, engineering, research and design docs
└── pyproject.toml
```

The full tree is in [docs/engineering/architecture.md](docs/engineering/architecture.md#file-structure).

## Roadmap

This is a learning project, and I'm building it iteratively. Workstreams use the
initiative/milestone naming scheme ([ADR-033](docs/product/decisions.md#adr-033-initiative--milestone-naming-scheme)):

- **`FND`** — Foundation & Metrics: complete
- **`EVAL`** — Evaluation & Quality Metrics: complete
- **`CTX`** — Context & Integrations: complete
- **`AGENT`** — Agent Framework: complete
- **`CAP`** — Agent Capabilities: in progress
- **`WEB`** — Web Interface: core shipped
- **`TOK`** — Context-Window Management & Search: in progress
- **`AON`** — Always-On & Loop Engineering: in progress
- **`HUB`** — Context Hub (Cortex via MCP): in progress
- **`OPS`**, **`UX`**, **`TUNE`**: not started

Status, milestones and later initiatives are in [docs/product/roadmap.md](docs/product/roadmap.md).

## Benchmarking

The golden test suite doubles as a model benchmark. Running it, estimating its cost per model
(`scripts/model_benchmark.py`) and regenerating the results table (`scripts/benchmark_report.py`)
are described in [tests/golden/README.md](tests/golden/README.md#benchmarking-models); the results
are in [docs/research/models.md](docs/research/models.md).

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
- **GUI Backend**: FastAPI + WebSockets (uvicorn)
- **GUI Frontend**: React 18 + Vite + TypeScript (built bundle committed)
- **Storage**: Local filesystem (markdown + JSON)
- **Vector DB**: ChromaDB (conversation recall / RAG)
- **HTTP**: httpx + trafilatura (web fetch tool)
- **Configuration**: YAML + `pydantic-settings` (typed) + environment variables
- **Code Quality**: ruff (lint + format) + mypy (`strict=true`); CI + pre-commit hooks
- **Testing**: pytest + mutmut ([details](docs/engineering/testing.md))
- **Package Management**: uv (fast Python package installer)

## Contributing

This is primarily a personal learning project, but if you find it useful or have suggestions, feel free to open an issue!

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Built by [Marco Braun](https://github.com/Cherubeam)** | Learning AI Engineering one commit at a time
