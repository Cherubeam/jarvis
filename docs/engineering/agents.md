# Agent Capability Matrix

Overview of all agents, their capabilities, and configuration.

---

## Agents

| Agent | Command | Type | Temperature | Max Iterations | Vault Writing |
|-------|---------|------|:-----------:|:--------------:|:-------------:|
| **JARVIS** | *(orchestrator)* | Python class | 0.7 | 5 | — |
| **Writing** | `/write` | Data-driven | 0.7 | 5 | — |
| **Research** | `/research` | Data-driven | 0.7 | 5 | — |
| **Clarity** | `/clarity` | Data-driven | 0.7 | 5 | — |
| **Navigator** | `/navigator` | Data-driven | 0.7 | 5 | — |
| **Tactics** | `/tactics` | Data-driven | 0.7 | 5 | — |
| **Developer** | `/develop` | Data-driven | 0.3 | 20 | — |
| **OKR Architect** | `/okr-architect` | Data-driven | 0.7 | 5 | — |
| **Obsidian Note Creator** | `/obsidian-note-creator` | Data-driven | 0.7 | 5 | `slip_box` |
| **Pattern Language Expert** | `/pattern-language-expert` | Data-driven | 0.7 | 5 | `patterns` |

---

## Tool Distribution

Tools are assigned in two tiers, configured in `apps/cli/main.py`:

### Tier 1 — Available to JARVIS and all agents

| Tool | Source | Description |
|------|--------|-------------|
| `fetch_url` | `packages/core/tools/web_fetch.py` | Fetch and extract web page content |
| `delegate_to_agent` | `packages/core/tools/delegate.py` | JARVIS-only: route to specialist agents |
| `recall_conversations` | `packages/core/tools/conversation_recall.py` | RAG search over past conversations (opt-in) |
| Vault read tools | `packages/core/tools/vault_read_tools.py` | `read_note`, `search_notes`, `read_daily_note` |

### Tier 2 — Specialist agent tools (passed via delegation)

| Tool | Agent(s) | Source |
|------|----------|--------|
| `search_tactics` | Tactics | `packages/core/tools/card_search.py` (RAG card search) |
| Git tools | Developer | `packages/core/tools/git_tools.py` |
| Codebase tools | Developer | `packages/core/tools/codebase_tools.py` |
| Project write tools | Developer | `packages/core/tools/project_write_tools.py` |
| Test runner | Developer | `packages/core/tools/test_tools.py` |
| Vault write tools | Obsidian Note Creator, Pattern Language Expert, Writing | `packages/core/tools/vault_write_tools.py` (scoped by `vault_writing`) |
| `evaluate_content` | *(via skill)* | `packages/core/tools/content_evaluator.py` |
| `suggest_improvements` | *(via skill)* | `packages/core/tools/suggest_improvements.py` |

---

## Skill Bindings

| Agent | Skills |
|-------|--------|
| Tactics | brand-tactics, idea-tactics, innovation-tactics, strategy-tactics, team-tactics, storyteller-tactics, productivity-tactics, workshop-tactics |
| OKR Architect | okr-architect |
| Pattern Language Expert | pattern-language-expert (deck-based card search) |

---

## Agent Architecture Notes

Only JarvisAgent uses a Python class (custom delegation routing, conversation context management). All 9 delegate agents are data-driven via `meta.yaml`.

Features that previously required Python classes are now handled declaratively:

| Feature | `meta.yaml` field | Used by |
|---------|-------------------|---------|
| Prompt composition | `prompt_includes:` | Writing (`voice-profile`, `anti-patterns`) |
| Extended iterations | `max_iterations:` | Developer (20) |
| Tool wiring | `tools:` (tool groups) | Writing, Developer, Tactics |
| Custom temperature | `temperature:` | Developer (0.3) |

---

*See [architecture.md](architecture.md) for system-level design. See [skills-vs-agents.md](skills-vs-agents.md) for the distinction between skills and agents.*
