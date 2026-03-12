# Skills vs Agents

JARVIS has two abstractions for giving an LLM a specialized persona: **skills** and **agents**. They solve different problems and sit at different points on the complexity spectrum. This document explains when to use each, how to tell them apart, and how to promote a skill to an agent when it outgrows its original design.

> **Note (2026-03-12):** Skills are no longer standalone-invokable. The `--skill`, `/skills`, and skill slash commands have been removed. Skills remain as passive knowledge packs for card indexing and can be wrapped as tools for agent use. Most agents now use data-driven `meta.yaml` definitions instead of Python classes.

## What Is a Skill?

A skill is a portable, one-shot persona prompt. The unit of exchange is a single file: `SKILL.md`.

```
okr-architect/
  SKILL.md          # frontmatter (name, description) + markdown prompt
  skill.py          # optional: tools, model override, custom config
  resources/        # optional: rubrics, reference material
```

The SKILL.md format uses YAML frontmatter (`name`, `description`) followed by a markdown body that serves as both the capability specification and the system prompt. This format is compatible with Claude Projects, ChatGPT Custom GPTs, and any LLM that accepts a system prompt -- the same file works across vendors without modification.

**Key properties:**

- **Stateless** -- each invocation is independent. The skill has no memory of previous runs.
- **Portable** -- SKILL.md works with any LLM provider. No JARVIS-specific code required.
- **Zero Python possible** -- a SKILL.md-only skill needs no `skill.py`. Drop a markdown file in a directory and it works.
- **Discovery is filesystem-based** -- the [skill registry](../../packages/skills/registry.py) scans for `SKILL.md` files, not Python imports.
- **Not standalone-invokable** -- skills cannot be run directly by users. They serve as passive knowledge packs for card indexing, and can be wrapped as tools for agent use.

A skill with a `skill.py` can declare tools, override the model, or adjust temperature, but it remains fundamentally one-shot: when invoked as a tool by an agent, the user sends a message, the skill responds, done.

**Examples in JARVIS:** Content Evaluator (wrapped as `evaluate_content` tool), Flow Master, PM Strategist.

## What Is an Agent?

An agent is a stateful, multi-turn entity that maintains conversation history, supports custom orchestration, and can wire in tools at construction time. Agents come in two forms:

### Data-Driven Agents (meta.yaml)

Most agents are now defined declaratively via a `meta.yaml` file and a `prompts/system.md` prompt. No Python class is needed. The `agent_from_meta()` factory creates a `DataDrivenAgent` instance at runtime.

```
clarity/
  meta.yaml         # name, description, command, model (optional)
  prompts/
    system.md       # system prompt
```

This is the preferred approach for agents that follow the standard pattern: load a system prompt, maintain conversation history, stream responses. Six agents use this pattern: Clarity, Research, Navigator, OKR Architect, Obsidian Note Creator, and Pattern Language Expert.

### Python-Class Agents

Agents that need custom logic -- such as custom prompt composition, non-standard temperature, or orchestration -- use a Python class that inherits from [`BaseAgent`](../../packages/agents/base.py).

```
tactics/
  __init__.py       # AGENT_META dict for registry discovery
  agent.py          # Python class extending BaseAgent
  prompts/
    system.md       # system prompt loaded via load_prompt()
```

Only WritingAgent (custom prompt composition), TacticsAgent (custom temperature), and JarvisAgent (orchestrator) use this pattern.

**Key properties (both forms):**

- **Stateful** -- maintains `conversation_history` across turns within a session.
- **Multi-turn** -- designed for back-and-forth interaction where context accumulates.
- **JARVIS-native** -- whether data-driven or Python-class, agents are JARVIS-specific.
- **Dual-path discovery** -- the [agent registry](../../packages/agents/registry.py) scans for both `meta.yaml` files and `AGENT_META` in `__init__.py` files.

Agents can accept `extra_tools` at construction (e.g., the RAG search tool), run agentic loops with tool calls, and (for Python-class agents) implement custom `process_message()` logic.

Agents can also **bind skills** by declaring `skills:` in their `meta.yaml`. This injects the skill's knowledge (SKILL.md body) into the agent's system prompt automatically, and for deck-skills, adds the card search tool. See [Agent-Skill Binding](#agent-skill-binding) below.

**Examples in JARVIS:** TacticsAgent (`/tactics`), Writing (`/write`), Research (`/research`), Clarity (`/clarity`), Pattern Language Expert (`/pattern-language-expert`), OKR Architect (`/okr-architect`), Navigator (`/navigator`).

## The Key Difference

> A skill answers a question. An agent has a conversation.

This is not about complexity. A skill can have a sophisticated prompt, tools, and resource files. An agent can have a simple system prompt. The dividing line is **statefulness and memory**:

| | Skill | Agent |
|---|---|---|
| State across turns | None | Conversation history |
| Typical interaction | Single request/response | Multi-turn dialogue |
| Implementation | SKILL.md (+ optional Python) | `meta.yaml` (data-driven) or Python class |
| Portability | Vendor-portable | JARVIS-native |
| User invocation | Not standalone-invokable; used as tool by agents | Slash command or `--agent` flag |
| Discovery | Filesystem scan for SKILL.md | Filesystem scan for `meta.yaml` or `AGENT_META` |

If the user's task can be fully addressed in one exchange -- "evaluate this blog post", "draft OKRs for Q3" -- it's a skill. If the task requires follow-up questions, iterative refinement, or accumulated context -- "coach me through building a workshop agenda" -- it's an agent.

## When to Promote a Skill to an Agent

Most capabilities should start as skills. Promote to an agent only when the interaction pattern demands it. Here are four criteria -- meeting **two or more** is a strong signal:

### 1. Multi-Turn Interaction Is Essential

The capability needs to ask clarifying questions, iterate on drafts, or guide the user through a multi-step process. A single prompt/response cycle isn't enough.

*Example:* A workshop facilitator that first asks about audience size, then objectives, then time constraints before designing the agenda.

### 2. Tools Beyond Simple Retrieval

The capability needs to call tools in a loop -- search, evaluate results, search again -- or orchestrate multiple tools in sequence. Skills support tools, but agents handle complex tool orchestration through the agentic loop.

*Example:* TacticsAgent searches for relevant cards, presents options, then searches again based on the user's feedback.

### 3. Context-Dependent Responses

Later responses depend on earlier ones in ways that go beyond what conversation history in the CLI provides. The agent needs to track state that isn't just "what was said before."

*Example:* An agent tracking which OKRs have been drafted, which are pending review, and which the user rejected.

### 4. Session-Level State

The capability needs to maintain structured data across the session -- a running score, a checklist, an evolving document -- not just conversation messages.

*Example:* A code review agent that maintains a list of findings and their resolution status.

## Assessment: Expert Personas

The six expert personas recently ported to JARVIS were evaluated against these criteria:

| Persona | Multi-Turn? | Complex Tools? | Context-Dependent? | Session State? | Verdict |
|---|---|---|---|---|---|
| OKR Architect | Yes (iterative refinement) | No | Yes (tracks OKR state) | No | **Promoted to Agent** |
| Content Evaluator | No (single evaluation) | No | No | No | **Skill** |
| Flow Master | Beneficial but not required | No | No | No | **Skill** |
| Pattern Language Expert | Yes (draft-review-refine) | No | Yes (tracks patterns) | No | **Promoted to Agent** |
| PM Strategist | Beneficial but not required | No | No | No | **Skill** |
| Flight Navigator | No (recommendation is one-shot) | No | No | No | **Skill** |

OKR Architect and Pattern Language Expert were promoted to agents based on observed interaction patterns: both benefit from iterative refinement cycles and context-dependent responses across turns. The remaining four are correctly implemented as skills -- each can deliver value in a single exchange and are available as passive knowledge packs or wrapped as tools for agent use.

## Migration Path

When a skill earns its promotion, here's how to convert it while preserving portability:

### Step 1: Keep the SKILL.md

The original SKILL.md remains the canonical prompt specification. It stays portable and can still be used with other LLM providers.

### Step 2: Create a `meta.yaml` (Preferred)

The preferred path for most agents is a data-driven `meta.yaml` definition. No Python class needed.

```
packages/agents/<name>/
  meta.yaml         # name, description, command, model (optional)
  prompts/
    system.md       # can reuse or extend the SKILL.md content
```

Example `meta.yaml`:

```yaml
name: my-agent
description: "A short description of what this agent does"
command: /my-agent
# model: anthropic/claude-sonnet-4.6  # optional, uses default if omitted
```

The `agent_from_meta()` factory will create a `DataDrivenAgent` instance automatically.

### Step 3: Use a Python Class (Only If Needed)

Only create a Python class if the agent needs custom logic (e.g., custom prompt composition, non-standard temperature, tool orchestration). In that case, use the traditional pattern:

```
packages/agents/<name>/
  __init__.py       # AGENT_META = {"name": ..., "description": ..., "command": ...}
  agent.py          # Agent class extending BaseAgent
  prompts/
    system.md       # system prompt loaded via load_prompt()
```

```python
from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse

class MyAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, model: str = "..."):
        config = AgentConfig(
            name="my-agent",
            description="...",
            model=model,
            system_prompt=self.load_prompt("system"),
        )
        super().__init__(config, llm_client)

    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        self.add_to_history("user", message)
        return self.llm_client.chat_stream(self.get_messages_for_api())
```

### Step 4: Retire the Skill (Optional)

If the agent fully replaces the skill's use case within JARVIS, remove the skill directory from `packages/skills/`. The SKILL.md can live in the agent's directory or in a shared specifications repo for cross-vendor use.

## Skills as Tools

Since skills are no longer standalone-invokable, wrapping them as `ToolDefinition` objects is now the **only** way skills are used at runtime. This makes them callable by agents during the agentic tool-calling loop: an agent can invoke a skill's structured evaluation without the user switching contexts.

**How it works:**

A factory function (e.g., `make_content_evaluator_tool()`) loads the skill's `SKILL.md` as a system prompt and its `skill.py` config (temperature, etc.), then wraps the whole thing in a `ToolDefinition`. The tool calls `LLMClient.complete()` with the skill's prompt -- a nested LLM call within the agent's agentic loop.

**Current examples:** Content Evaluator (`evaluate_content` tool).

**When to use this pattern:**

- The skill's output is useful *within* a larger agent workflow (e.g., reviewing content as part of an editing session)
- The skill's one-shot nature is preserved -- it still runs as a single prompt/response, just invoked by an agent
- The SKILL.md remains vendor-portable even though the tool wrapper is JARVIS-native

| | Skill as Tool | Agent |
|---|---|---|
| Invocation | Tool call by agent | Slash command or delegation |
| State | None (tool is stateless) | Conversation history |
| Portability | JARVIS-native wrapper (SKILL.md is portable) | JARVIS-native |

## Agent-Skill Binding

Agents can declare which skills they consume via the `skills:` field in `meta.yaml`:

```yaml
name: pattern-language-expert
description: Design, evolve, and apply pattern languages
command: /pattern-language-expert
skills:
  - pattern-language-expert
```

When `agent_from_meta()` builds the agent, it calls `resolve_skills()` to:

1. **Simple skills** (no `deck.yaml`): Read the SKILL.md body (frontmatter stripped) and append it to the agent's system prompt.
2. **Deck-skills** (has `deck.yaml`): Add the deck name to a prompt hint section and include the card search tool (if RAG is enabled).
3. **Unknown skills**: Log a warning and skip gracefully.

This keeps the SKILL.md as the canonical knowledge specification while letting agents automatically consume it. The skill stays portable; the binding is JARVIS-native.

| | Skill as Tool | Skill Binding | Agent |
|---|---|---|---|
| Mechanism | Tool call by agent | System prompt injection | Slash command or delegation |
| State | None (stateless) | Agent's conversation history | Agent's conversation history |
| Portability | SKILL.md portable, wrapper native | SKILL.md portable, binding native | JARVIS-native |

## Design Principles

1. **Default to `meta.yaml` agents.** For new capabilities that need multi-turn interaction, create a data-driven agent with `meta.yaml` + `prompts/system.md`. Only use a Python class when custom logic is required.

2. **Use skills for portable knowledge packs.** Skills are simpler and portable. Use them when the capability is one-shot and you want vendor portability (SKILL.md works with any LLM provider). Skills are invoked via tool wrapping, not standalone.

3. **Promote based on evidence, not speculation.** Don't build an agent because a capability *might* need multi-turn support. Build the skill, use it, and let the interaction pattern tell you.

4. **Portability is a feature.** SKILL.md files work everywhere. Once you promote to an agent, you gain power but lose vendor portability. That trade-off should be intentional.

5. **Keep the SKILL.md alive.** Even after promotion, the SKILL.md serves as documentation and as a portable fallback. It's the specification; the agent is the implementation.
