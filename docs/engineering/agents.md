# Agent Capability Matrix

Overview of all agents, their commands, and configuration.

Agent names and directories use `snake_case`; commands use `/kebab-case` (see [AGENTS.md](../../AGENTS.md#naming-conventions-agents--skills)).

---

## Agents

| Agent | Command | Model | Temperature | Max Iterations | Vault Writing | Tool Groups | Skills |
|-------|---------|-------|:-----------:|:--------------:|:-------------:|-------------|--------|
| **jarvis** *(orchestrator)* | — | session / auto | 0.7 | 5 | — | *(shared)* | — |
| **content_reviewer** | `/review` | session | 0.7 | 10 | — | blog_tools, content_evaluator, suggest_improvements | — |
| **developer** | `/develop` | session | 0.3 | 20 | — | dev_tools | — |
| **navigator** | `/navigator` | session | 0.7 | default | — | — | — |
| **obsidian_note_creator** | `/obsidian-note-creator` | session | 0.7 | default | slip_box | — | — |
| **okr_architect** | `/okr-architect` | session | 0.7 | default | — | — | — |
| **pattern_card_generator** | `/pattern-cards` | session | 0.7 | 15 | — | card_generator | — |
| **pattern_language_expert** | `/pattern-language-expert` | session | 0.7 | 10 | patterns | — | pattern-language-expert |
| **reading_assistant** | `/reading` | session | 0.7 | default | — | readwise_tools, web_tools | — |
| **researcher** | `/research` | session | 0.7 | default | — | web_tools | — |
| **simplifier** | `/simplify` | session | 0.7 | 5 | — | — | — |
| **strategyzer** | `/strategize` | session | 0.7 | default | — | — | strategy-tactics, pm-strategist |
| **substack_image_creator** | `/substack-image` | session | 0.7 | 5 | — | blog_tools | technical-humanist-image-architect |
| **substack_publisher** | `/publish` | quality | 0.7 | 5 | — | blog_tools | substack-prepare-to-publish |
| **tactics_coach** | `/tactics` | session | 0.7 | default | — | card_search | — |
| **writer** | `/write` | quality | 0.7 | 5 | — | blog_tools | — |

"default" means the agent inherits the framework default for `max_iterations` (5; not set in `meta.yaml`). **Model**: `quality` = pinned via `meta.yaml` `model:` (runs on that preset whatever the session model is); `session` = the session model (`models.default`, `/model`, heuristic routing, or `openrouter/auto` when `models.auto_router.enabled`).

---

## Tool Distribution

Tools are registered in `apps/cli/session_factory.py` (`build_session`) and assigned in two tiers.

### Tier 1 — Shared across JARVIS and all agents

| Tool | Source | Description |
|------|--------|-------------|
| `fetch_url` | `packages/core/tools/web_fetch.py` | Fetch and extract web page content |
| `recall_conversations` | `packages/core/tools/conversation_recall.py` | RAG search over past conversations (opt-in) |
| `mcp_cortex__search_knowledge` | Cortex MCP server (`mcp.servers.cortex`, `shared: true`) | Vault semantic search (HUB-01) |
| Vault read tools | `packages/core/tools/vault_read_tools.py` | `read_note`, `search_notes`, `read_daily_note` |
| `delegate_to_agent` | `packages/core/tools/delegate.py` | **JARVIS-only** — route to specialist agents |

### Tier 2 — Named tool groups (opt-in per agent via `tools:` in `meta.yaml`)

| Tool Group | Used By | Source |
|------------|---------|--------|
| `blog_tools` | content_reviewer, substack_image_creator, substack_publisher, writer | `packages/core/tools/blog_tools.py` |
| `card_generator` | pattern_card_generator | `packages/core/tools/card_generator_tools.py` |
| `card_search` | tactics_coach | `packages/core/tools/card_search.py` |
| `content_evaluator` | content_reviewer | `packages/core/tools/content_evaluator.py` |
| `dev_tools` | developer | `packages/core/tools/git_tools.py`, `codebase_tools.py`, `project_write_tools.py`, `test_tools.py` |
| `readwise_tools` | reading_assistant | `packages/core/tools/readwise_tools.py` |
| `suggest_improvements` | content_reviewer | `packages/core/tools/suggest_improvements.py` |
| `things3_tools` | *(not currently bound to a delegate)* | `packages/core/tools/things3_tools.py` |
| `web_tools` | reading_assistant, researcher | `packages/core/tools/web_fetch.py`, `web_search.py` |

Vault write tools are not a named tool group — they are created on demand per agent based on the agent's `vault_writing` field (see `make_agent_vault_tools` in `apps/cli/session_factory.py`).

MCP server tool groups are registered dynamically from `config/local.yaml` under `mcp.servers`; each server's declared `tool_group` name becomes available alongside the groups above.

---

## Agent Architecture Notes

Only JarvisAgent is implemented as a Python class (custom delegation routing, conversation context management, live-note handling). All 15 delegate agents are data-driven via `meta.yaml` + `prompts/system.md` and are discovered automatically from `packages/agents/`.

Features that would otherwise require a Python class are handled declaratively:

| Feature | `meta.yaml` field | Used by |
|---------|-------------------|---------|
| Prompt composition | `prompt_includes:` | content_reviewer, substack_image_creator, substack_publisher, writer |
| Extended iterations | `max_iterations:` | developer (20), pattern_card_generator (15), content_reviewer (10), pattern_language_expert (10) |
| Own model | `model:` (preset or model id) | writer, substack_publisher (`quality`) |
| Tool wiring | `tools:` (named tool groups) | Most agents |
| Custom temperature | `temperature:` | developer (0.3). **Stored on `AgentConfig` but not sent to the model yet** — the stream handler never passes it |
| Scoped vault writing | `vault_writing:` | obsidian_note_creator (slip_box), pattern_language_expert (patterns) |
| Skill binding | `skills:` | pattern_language_expert, strategyzer, substack_image_creator, substack_publisher |

---

*See [architecture.md](architecture.md) for system-level design. See [skills-vs-agents.md](skills-vs-agents.md) for the distinction between skills and agents.*
