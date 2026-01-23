# Jarvis

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> A personal AI assistant built from first principles to solve the vendor lock-in problem in conversational AI.

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
│   Context Files │  (profile.md, preferences.md, current_focus.md)
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
│   LLM Client    │  Streams responses from any provider (via OpenRouter)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Conversation    │  Logs all interactions to timestamped JSON files
│ Memory          │
└─────────────────┘
```

### Key Design Principles

1. **Human-readable storage**: All context and conversations are stored as markdown or JSON files you can edit directly
2. **Provider independence**: Switching from Claude to GPT-4 is a one-line config change
3. **Simplicity first**: No unnecessary abstractions—just clean functions that do one thing well
4. **Local-first**: Your data lives on your machine, not in someone else's cloud

## Features

- **Persistent Personal Context**: Define who you are, your preferences, and current focus areas in simple markdown files
- **Conversation Memory**: All interactions are logged with timestamps, creating a searchable history
- **Streaming Responses**: Real-time token-by-token output for a responsive chat experience
- **Provider Agnostic**: Unified interface to multiple LLM providers through OpenRouter/LiteLLM
- **Token & Cost Tracking**: Automatic tracking of usage and costs per request and session
- **Latency Metrics**: TTFT and total latency captured per response
- **Simple Configuration**: YAML-based config with sensible defaults
- **Things 3 Integration**: Auto-sync tasks from Things 3 (macOS) for task-aware responses
- **Comprehensive Testing**: 150 automated tests with 97.5% code coverage
- **Benchmark Cost Estimation**: Estimate golden test run costs per model before evaluation

## Getting Started

### Prerequisites

- Python 3.13+
- An [OpenRouter](https://openrouter.ai/) API key

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/jarvis.git
cd jarvis

# Install dependencies using uv (https://github.com/astral-sh/uv)
uv sync

# Install package in editable mode (required for `uv run jarvis` command)
uv pip install -e .

# Set up your environment variables
echo "OPENROUTER_API_KEY=your_key_here" > .env

# Configure your personal context
# Edit the files in data/context/:
# - profile.md (who you are)
# - preferences.md (how the assistant should behave)
# - current_focus.md (what you're working on)
```

### Usage

```bash
# Using the installed script (recommended)
uv run jarvis

# Or using module syntax
uv run python -m apps.cli.main
```

Start chatting! Type `quit` or `exit` to end the session.

## Project Structure

```
jarvis/
├── apps/                               # Deployable applications
│   ├── cli/                            # CLI entry point
│   │   └── main.py                     # Command-line interface
│   └── web/                            # Web application (Phase 3)
│       ├── backend/                    # FastAPI backend
│       └── frontend/                   # React frontend
│
├── packages/                           # Shared libraries
│   ├── core/                           # Core functionality
│   │   ├── llm_client.py               # Unified LLM provider interface
│   │   ├── context_builder.py          # Assembles system prompts from context
│   │   ├── memory.py                   # Conversation logging
│   │   ├── pricing.py                  # Cost calculation and tracking
│   │   └── benchmark_costs.py          # Benchmark cost estimation
│   ├── agents/                         # Agent implementations
│   │   ├── base.py                     # Base agent class
│   │   └── jarvis/                     # Main JARVIS agent
│   ├── integrations/                   # External service integrations
│   │   └── things3/                    # Things 3 task sync
│   └── telemetry/                      # Metrics and evaluation
│
├── data/                               # User data
│   ├── context/                        # Your personal context files
│   │   ├── profile.md                  # Who you are
│   │   ├── preferences.md              # Assistant behavior preferences
│   │   ├── current_focus.md            # Current projects and priorities
│   │   └── tasks.md                    # Auto-synced from Things 3
│   └── conversations/                  # Timestamped conversation logs
│
├── config/                             # Configuration
│   ├── default.yaml                    # Default configuration
│   └── local.yaml                      # Local overrides (gitignored)
│
├── tests/                              # Comprehensive test suite
│   ├── unit/                           # 103 unit tests
│   ├── integration/                    # 20 integration tests
│   ├── golden/                         # 8 golden test conversations + LLM-as-judge
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
- [x] **Comprehensive testing framework (150 tests, 97.5% coverage)**

**Phase 2: Evaluation & Quality Metrics (75% Complete)**
- [x] 8 golden test conversations defined
- [x] **LLM-as-judge automated evaluation (~$0.41/run)**
- [x] **Things 3 integration** (task sync with auto language detection)
- [x] Latency tracking (TTFT)
- [ ] Model comparison benchmarks
- [x] Benchmark cost estimation per model

**Phase 3: Web Interface (Next)**
- [ ] FastAPI backend with SSE streaming
- [ ] React frontend with chat UI
- [ ] Conversation history browser

**Future Phases:**
- [ ] Context window management (truncation strategies)
- [ ] Semantic search over conversation history (RAG)
- [ ] Agent orchestration framework

See [docs/product/roadmap.md](docs/product/roadmap.md) for detailed plans.

## Benchmarking

Estimate benchmark costs anytime (uses latest golden run baseline):

```bash
uv run python scripts/model_benchmark.py
```

To run evaluations after the estimate (paid), add `--evaluate`.

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
- **Storage**: Local filesystem (markdown + JSON)
- **Configuration**: YAML + environment variables
- **Testing**: pytest with 97.5% code coverage
- **Package Management**: uv (fast Python package installer)

## Contributing

This is primarily a personal learning project, but if you find it useful or have suggestions, feel free to open an issue!

## License

MIT License - feel free to fork and adapt for your own use.

---

**Built by [Marco Braun](https://github.com/Cherubeam)** | Learning AI Engineering one commit at a time
