# Agent Capability Matrix

Overview of all agents, their commands, and configuration.

Agent names and directories use `snake_case`; commands use `/kebab-case` (see [AGENTS.md](../../AGENTS.md#naming-conventions-agents--skills)).

---

## Agents

This matrix is the reference list of agents, their slash commands and their tools; other docs link here. Source of truth: each agent's `packages/agents/<name>/meta.yaml` (fields: [api.md](api.md#metayaml-schema)).

| Agent | Command | Description | Model | Temperature | Max Iterations | Vault Writing | Tool Groups | Skills |
|-------|---------|-------------|-------|:-----------:|:--------------:|:-------------:|-------------|--------|
| **jarvis** *(orchestrator)* | — | Default session; answers directly or delegates to the agents below | session / auto | 0.7 | 5 | — | *(see Tier 1)* | — |
| **content_reviewer** | `/review` | Structured content evaluation and improvement suggestions | session | 0.7 | 10 | — | blog_tools, content_evaluator, suggest_improvements | — |
| **developer** | `/develop` | Self-improvement: reads the codebase, branches, writes data-driven files, runs tests, commits | session | 0.3 | 20 | — | dev_tools | — |
| **navigator** | `/navigator` | Personal alignment, goal clarity and structured reviews | session | 0.7 | default | — | — | — |
| **obsidian_note_creator** | `/obsidian-note-creator` | Extracts atomic evergreen notes into the Slip-Box | session | 0.7 | default | slip_box | — | — |
| **okr_architect** | `/okr-architect` | Designs, implements and tracks OKRs | session | 0.7 | default | — | — | — |
| **pattern_card_generator** | `/pattern-cards` | Visual pattern cards from Obsidian patterns for workshops | session | 0.7 | 15 | — | card_generator | — |
| **pattern_language_expert** | `/pattern-language-expert` | Designs, evolves and applies pattern languages | session | 0.7 | 10 | patterns | — | pattern-language-expert |
| **reading_assistant** | `/reading` | Searches, triages and manages the Readwise reading list | session | 0.7 | default | — | readwise_tools, web_tools | — |
| **researcher** | `/research` | Analysis, synthesis and structured answers | session | 0.7 | default | — | web_tools | — |
| **simplifier** | `/simplify` | Explains complex ideas simply | session | 0.7 | 5 | — | — | — |
| **strategyzer** | `/strategize` | Competitive analysis, growth loops, pricing, positioning | session | 0.7 | default | — | — | strategy-tactics, pm-strategist |
| **substack_image_creator** | `/substack-image` | Header image prompts for Substack posts | session | 0.7 | 5 | — | blog_tools | technical-humanist-image-architect |
| **substack_publisher** | `/publish` | Prepares blog posts for Substack publication | quality | 0.7 | 5 | — | blog_tools | substack-prepare-to-publish |
| **tactics_coach** | `/tactics` | Pip Decks tactics coaching (storytelling, workshops, ideation) | session | 0.7 | default | — | card_search | — |
| **writer** | `/write` | Drafts and edits blog posts in the author's voice | quality | 0.7 | 5 | — | blog_tools | — |

"default" means the agent inherits the framework default for `max_iterations` (`_MAX_AGENTIC_ITERATIONS` in `packages/core/stream_handler.py`, currently 5; not set in `meta.yaml`). **Model**: `quality` = pinned via `meta.yaml` `model:` (runs on that preset whatever the session model is); `session` = the session model (`models.default`, `/model`, heuristic routing, or `openrouter/auto` when `models.auto_router.enabled`). How the session model is chosen: [deployment.md](deployment.md#model-selection-order).

Commands that aren't agents (`/model`, `/stream`, `/daily-summary`, `/outcomes`) are listed in the [README](../../README.md#usage).

---

## Tool Distribution

Tools are registered in `build_session()` ([`apps/cli/session_factory.py`](../../apps/cli/session_factory.py)) and assigned in two tiers. The mechanism is described in [architecture.md](architecture.md#7-tool-calling-packagescoretools).

### Tier 1 — Shared across JARVIS and all agents

Each shared tool is registered only when its feature is enabled.

| Tool | Source | Registered when | Description |
|------|--------|-----------------|-------------|
| Vault read tools | `packages/core/tools/vault_read_tools.py` | `obsidian.enabled` | `read_note`, `search_notes`, `read_daily_note` |
| `recall_conversations` | `packages/core/tools/conversation_recall.py` | `rag.enabled` | RAG search over past conversations |
| `track_recommendation` | `packages/core/tools/outcome_tools.py` | `outcomes.enabled` | Capture a concrete recommendation for later review |
| `recall_outcomes` | `packages/core/tools/outcome_recall.py` | `outcomes.enabled` and `rag.enabled` | Search scored past recommendations |
| Shared MCP tools, e.g. `mcp_cortex__search_knowledge` | MCP servers with `shared: true` ([setup](deployment.md#connecting-mcp-servers)) | `mcp.enabled` | Vault semantic search via Cortex (HUB-01), or any other shared server |

**JARVIS only**: `delegate_to_agent` (`packages/core/tools/delegate.py`) plus the `web_tools` and `readwise_tools` groups (`jarvis_tools` in `build_session()`).

### Tier 2 — Named tool groups (opt-in per agent via `tools:` in `meta.yaml`)

| Tool Group | Used By | Source |
|------------|---------|--------|
| `blog_tools` | content_reviewer, substack_image_creator, substack_publisher, writer | `packages/core/tools/blog_tools.py` |
| `card_generator` | pattern_card_generator | `packages/core/tools/card_generator_tools.py` |
| `card_search` | tactics_coach | `packages/core/tools/card_search.py` |
| `content_evaluator` | content_reviewer | `packages/core/tools/content_evaluator.py` |
| `dev_tools` | developer | `packages/core/tools/git_tools.py`, `codebase_tools.py`, `project_write_tools.py`, `test_tools.py`, `mutation_tools.py` |
| `readwise_tools` | reading_assistant, jarvis | `packages/core/tools/readwise_tools.py` |
| `suggest_improvements` | content_reviewer | `packages/core/tools/suggest_improvements.py` |
| `web_tools` | reading_assistant, researcher, jarvis | `packages/core/tools/web_fetch.py` (`fetch_url`), `web_search.py` (`web_search`) |

A group is only registered when its feature is configured (e.g. `blog_tools` needs `obsidian.writing.blog_dir`, `card_search` needs RAG and a deck-skill). Vault write tools are not a named tool group — they are created on demand per agent based on the agent's `vault_writing` field (see `make_agent_vault_tools` in `apps/cli/session_factory.py`).

MCP server tool groups are registered dynamically from `config/local.yaml` under `mcp.servers`; each server's declared `tool_group` name becomes available alongside the groups above.

---

## Agent Architecture Notes

Only JarvisAgent is implemented as a Python class (custom delegation routing, conversation context management, live-note handling). All delegate agents are data-driven via `meta.yaml` + `prompts/system.md` and are discovered automatically from `packages/agents/`.

Features that would otherwise require a Python class are handled declaratively:

| Feature | `meta.yaml` field | Used by |
|---------|-------------------|---------|
| Prompt composition | `prompt_includes:` | content_reviewer, substack_image_creator, substack_publisher, writer |
| Extended iterations | `max_iterations:` | developer (20), pattern_card_generator (15), content_reviewer (10), pattern_language_expert (10) |
| Own model | `model:` (preset or model id) | writer, substack_publisher (`quality`) |
| Tool wiring | `tools:` (named tool groups) | Most agents |
| Custom temperature | `temperature:` | developer (0.3), strategyzer and tactics_coach (0.7). Sent on every model call of the agent's turn; agents without it send none (provider default) |
| Scoped vault writing | `vault_writing:` | obsidian_note_creator (slip_box), pattern_language_expert (patterns) |
| Skill binding | `skills:` | pattern_language_expert, strategyzer, substack_image_creator, substack_publisher |

---

*See [architecture.md](architecture.md) for system-level design. See [skills-vs-agents.md](skills-vs-agents.md) for the distinction between skills and agents.*
