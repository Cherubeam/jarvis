# Jarvis

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-94A3B8?logo=openrouter&logoColor=fff)](#)
![Version 0.15.0](https://img.shields.io/badge/version-0.15.0-green.svg)
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

- **Agent Framework**: Slash-command routing to specialist agents (Writer, Researcher, Simplifier, Navigator, Tactics Coach, Content Reviewer, Substack Publisher, Substack Image Creator, OKR Architect, Obsidian Note Creator, Pattern Language Expert, Pattern Card Generator, Strategyzer, Developer)
- **Data-Driven Agents**: Most agents defined via `meta.yaml` + `prompts/system.md` -- no Python class needed
- **Standalone Agent Mode**: Run any agent directly with `--agent <name>`
- **Tool Calling**: Agentic loop with tool execution (max 5 iterations per request)
- **Web Fetch Tool**: URL fetching with content extraction (httpx + trafilatura)
- **Conversation Recall (RAG)**: Semantic search over conversation history via ChromaDB (opt-in)
- **Vault Semantic Search**: Meaning-based search over the Obsidian vault via Cortex (opt-in)
- **Enhanced CLI UX**: Rich terminal formatting, markdown rendering, prompt_toolkit with paste support and input history
- **Persistent Personal Context**: Define who you are, your preferences, and current focus areas in simple markdown files
- **Conversation Memory**: All interactions are logged with timestamps, creating a searchable history
- **Streaming Responses**: Real-time token-by-token output for a responsive chat experience
- **Non-Streaming Mode** (opt-in): Toggle with `/stream` or configure via `models.streaming`. Enables prompt caching via OpenRouter (blocked in streaming mode due to upstream LiteLLM format inconsistency)
- **History Summarization** (opt-in): Compresses old conversation turns when history exceeds ~40K tokens, using Gemini Flash to reduce costs in long sessions. Enable via `summarization.enabled` in config.
- **Provider Agnostic**: Unified interface to multiple LLM providers through OpenRouter/LiteLLM
- **Token & Cost Tracking**: Automatic tracking of usage and costs per request and session
- **Latency Metrics**: TTFT and total latency captured per response
- **Simple Configuration**: YAML-based config with sensible defaults
- **Obsidian Integration**: Generate daily note summaries from conversation history
- **Things 3 Integration**: Auto-sync tasks from Things 3 (macOS) via SQLite for task-aware responses. Write tools (`create_task`, `complete_task`, `update_task`) available via `things3_tools` group.
- **MCP Client Integration**: Connect to external MCP (Model Context Protocol) servers. MCP server tools are bridged into the ToolDefinition system and appear as regular tool groups. Supports stdio, SSE, and streamable HTTP transports. Config-only setup via `mcp.servers` in `config/local.yaml`.
- **Comprehensive Testing**: Automated test suite with high code coverage + mutation testing via mutmut
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
uv run jarvis --agent writer
uv run jarvis --agent researcher
uv run jarvis --agent simplifier
uv run jarvis --agent navigator
uv run jarvis --agent tactics_coach
uv run jarvis --agent developer
```

### GUI (Phases 1–6)

A graphical peer to the CLI, sharing the same agents, tools, conversation
files, and approval flow:

```bash
uv sync --extra web
uv run jarvis-gui              # opens http://127.0.0.1:8123 in your browser
uv run jarvis-gui --no-browser # just serve
```

Shipped surfaces: **Chat** (streaming, tool cards, vault-write approval
diffs, command palette, Tweaks panel, light/dark + accent swap), **Home**
(greeting, Things 3 tasks, cost-this-week, resume, recent, quick-start),
**History** (two-pane filterable conversation browser), **Sidebar Timeline
mode** (togglable day-axis variant), **Agents** (categorized grid +
per-agent detail with tools, recent sessions, 14-day cost sparkline, and
"start session →" launcher), and the **Agent Prompt Editor** (Prompt /
Versions / Stats / Context tabs on each agent — edit `system.md`,
snapshot-on-save history with restore, resolved-prompt preview). Settings
is stubbed and lands in a later phase. See
[docs/engineering/gui.md](docs/engineering/gui.md) for architecture +
rebuild instructions.

During a chat session, you can use slash commands:

```
/write <text>           Delegates to Writer agent (prose, editing, rewriting)
/research <text>        Delegates to Researcher agent (analysis, synthesis)
/simplify <text>        Delegates to Simplifier agent (explains complex ideas simply)
/review                 Enters Content Reviewer session (structured evaluation)
/publish                Enters Substack Publisher session (pre-pub workflow)
/substack-image         Enters Substack Image Creator session (header image prompts)
/navigator              Enters Navigator agent session (alignment, weekly reviews)
/tactics                Enters Tactics Coach agent session (Pip Decks coaching)
/okr-architect          Enters OKR Architect agent session
/obsidian-note-creator  Enters Obsidian Note Creator session (evergreen note extraction)
/pattern-language-expert  Enters Pattern Language Expert session
/pattern-cards          Enters Pattern Card Generator session (visual cards from patterns)
/strategize             Enters Strategyzer session (competitive analysis, growth, pricing)
/develop                Enters Developer agent session (codebase, git, tests)
/daily-summary [date]   Generates an Obsidian daily note summary (default: today)
/outcomes               Reviews pending tracked recommendations (score + retrospective)
/stream                 Toggles between streaming and non-streaming response modes
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

### Connecting MCP Servers

JARVIS can connect to external [MCP](https://modelcontextprotocol.io/) servers and use their tools alongside native ones. Adding or removing a server is a config-only change — no code edits required.

**Step 1: Enable MCP and declare servers** in `config/local.yaml`:

```yaml
mcp:
  enabled: true
  servers:
    # Example: filesystem access via stdio
    filesystem:
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/Documents"]
      tool_group: fs_tools           # name used in agent meta.yaml
      timeout_seconds: 30            # per-call timeout (default: 30)

    # Example: remote server via SSE
    github:
      transport: sse
      url: "http://localhost:3001/sse"
      headers:
        Authorization: "Bearer your-token-here"
      tool_group: github_tools

    # Example: remote server via streamable HTTP
    my_api:
      transport: streamable_http
      url: "http://localhost:8080/mcp"
      tool_group: my_api_tools
```

Each server key (e.g. `filesystem`) is used for tool namespacing — MCP tool `read_file` from server `filesystem` becomes `mcp_filesystem__read_file` in JARVIS. The `tool_group` field (defaults to the server key if omitted) is the name you reference from agents.

**Step 2: Assign tool groups to agents.** Add the `tool_group` name to the agent's `meta.yaml`:

```yaml
# packages/agents/researcher/meta.yaml
tools:
  - web_tools
  - fs_tools        # MCP server tool group
  - github_tools    # another MCP server tool group
```

**Step 3: Restart JARVIS.** You should see the tools load at startup:

```
[MCP] 5 tool(s) from 2 server(s).
```

**Giving MCP tools to the JARVIS orchestrator:** By default, only delegate agents receive MCP tools (via `meta.yaml`). To make MCP tools available to the JARVIS orchestrator itself, add the tool group to `jarvis_tools` in `apps/cli/main.py`:

```python
jarvis_tools = (
    list(shared_tools)
    + tool_groups.get("web_tools", [])
    + tool_groups.get("things3_tools", [])
    + tool_groups.get("fs_tools", [])       # add your MCP tool group here
)
```

**Transport reference:**

| Transport | Required fields | Use case |
|---|---|---|
| `stdio` | `command`, `args` (optional) | Local servers launched as child processes |
| `sse` | `url` | Remote servers with Server-Sent Events |
| `streamable_http` | `url` | Remote servers with HTTP streaming |

Optional fields for all transports: `tool_group`, `timeout_seconds`, `headers` (SSE/HTTP only), `env`, `cwd` (stdio only).

**Troubleshooting:**
- If a server fails to connect at startup, JARVIS logs a warning and continues — other servers and native tools are unaffected.
- If a tool call fails at runtime, the error is returned to the LLM as tool output so it can adapt.
- stdio servers require the command to be available on your `PATH` (e.g. `npx` requires Node.js).
- To verify which tools loaded, check the `[MCP]` line in startup output.

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
│   │   ├── settings.py                 # Typed pydantic-settings model + load_config()
│   │   ├── events.py                   # Typed event dataclasses for streaming decoupling
│   │   ├── filesystem_access.py        # Filesystem access control (FilesystemGuard)
│   │   ├── card_renderer.py             # Pattern card rendering (HTML/PNG via WeasyPrint)
│   │   ├── benchmark_costs.py          # Benchmark cost estimation
│   │   ├── importers/                  # Conversation importers (ChatGPT, Claude)
│   │   ├── rag/                        # Conversation recall (optional, ChromaDB)
│   │   │   ├── indexer.py              # Startup scan, message-pair chunking
│   │   │   └── searcher.py             # Cosine similarity search with date filters
│   │   └── tools/                      # Tool calling infrastructure
│   │       ├── base.py                 # ToolDefinition + ToolRegistry
│   │       ├── executor.py             # Tool call execution
│   │       ├── web_fetch.py            # URL fetch (httpx + trafilatura)
│   │       ├── conversation_recall.py  # RAG search tool
│   │       ├── delegate.py             # Agent delegation tool
│   │       ├── vault_read_tools.py     # Obsidian vault read tools
│   │       ├── vault_write_tools.py    # Obsidian vault write tools (scoped per agent)
│   │       ├── web_search.py            # DuckDuckGo web search tool
│   │       ├── blog_tools.py           # Blog management tools
│   │       ├── card_generator_tools.py # Pattern card generator tools
│   │       ├── cortex_search.py        # Cortex semantic vault search tool
│   │       ├── things3_tools.py        # Things 3 task management tools
│   │       ├── codebase_tools.py       # Codebase analysis tools
│   │       ├── git_tools.py            # Git operations tools
│   │       ├── project_write_tools.py  # Project file write tools
│   │       ├── test_tools.py           # Test runner tool
│   │       ├── mutation_tools.py       # Mutation testing tools (mutmut)
│   │       ├── suggest_improvements.py # Content improvement suggestions
│   │       └── content_evaluator.py    # LLM-as-judge evaluation tool
│   ├── agents/                         # Agent implementations
│   │   ├── base.py                     # Base agent class + DataDrivenAgent
│   │   ├── registry.py                 # Filesystem-based agent auto-discovery
│   │   ├── jarvis/                     # Main JARVIS orchestrator agent (Python class)
│   │   ├── _shared/                    # Shared prompt includes (voice-profile, anti-patterns)
│   │   ├── writer/                     # Writer — drafting & editing
│   │   ├── content_reviewer/           # Content Reviewer — structured evaluation
│   │   ├── substack_publisher/         # Substack Publisher — pre-pub workflow
│   │   ├── substack_image_creator/     # Substack Image Creator — header image prompts
│   │   ├── researcher/                 # Researcher — analysis, synthesis
│   │   ├── simplifier/                 # Simplifier — explains complex ideas simply
│   │   ├── tactics_coach/              # Tactics Coach — Pip Decks coaching
│   │   ├── navigator/                  # Navigator — alignment, weekly reviews
│   │   ├── okr_architect/              # OKR Architect
│   │   ├── obsidian_note_creator/      # Obsidian Note Creator
│   │   ├── pattern_language_expert/    # Pattern Language Expert
│   │   ├── pattern_card_generator/    # Pattern Card Generator (visual cards)
│   │   ├── strategyzer/              # Strategyzer (competitive analysis, growth)
│   │   └── developer/                 # Developer agent (git sandbox, code tools)
│   ├── skills/                         # Skills (passive knowledge packs for card indexing)
│   │   ├── base.py                     # BaseSkill (parses SKILL.md, optional skill.py)
│   │   ├── registry.py                 # Filesystem-based skill discovery
│   │   ├── resolver.py                 # Skill resolution and binding for agents
│   │   ├── content-evaluator/          # Content evaluation (SKILL.md + skill.py)
│   │   └── .../                        # Additional skills (each has SKILL.md)
│   ├── integrations/                   # External service integrations
│   │   ├── things3/                    # Things 3 task sync + write tools
│   │   ├── cortex/                     # Cortex semantic search client
│   │   ├── mcp/                        # MCP client integration
│   │   │   ├── config.py               # Config parsing + validation
│   │   │   ├── client.py               # Connection lifecycle + async/sync bridge
│   │   │   └── bridge.py               # MCP Tool → ToolDefinition conversion
│   │   └── obsidian/                   # Obsidian vault integration
│   │       ├── vault.py                # Vault reader with symlink protection
│   │       ├── callout.py              # Callout block parser
│   │       ├── diff.py                 # Diff computation and formatting
│   │       └── writer.py               # Note writer with confirmation
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
│   ├── conversations/                  # Timestamped conversation logs (by year)
│   │   ├── 2024/                      # e.g. 2024-02-10_17-50-05.json
│   │   ├── 2025/
│   │   └── 2026/
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
- [x] Extended tools — web search (DuckDuckGo + URL fetch via `web_tools` group)
- [ ] Extended tools — Playwright browser automation
- [ ] Intelligent model routing (task complexity → model selection)

**Phase 6A: Event Decoupling (Partially Complete)**
- [x] Event decoupling (typed events, StreamHandler emission)
- [x] Typed configuration (`packages/core/settings.py`)
- [ ] Move print statements from StreamHandler into CLI adapter

**Future Phases:**
- [ ] Web interface (Phase 6B/C — FastAPI + frontend)
- [x] Context window management — history summarization (opt-in, ~40K threshold) and tool result trimming
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
- **Testing**: pytest + mutmut ([details](docs/engineering/testing.md))
- **Package Management**: uv (fast Python package installer)

## Contributing

This is primarily a personal learning project, but if you find it useful or have suggestions, feel free to open an issue!

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Built by [Marco Braun](https://github.com/Cherubeam)** | Learning AI Engineering one commit at a time
