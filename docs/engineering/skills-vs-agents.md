# Skills vs Agents

JARVIS has two abstractions for giving an LLM a specialized persona: **skills** and **agents**. They solve different problems and sit at different points on the complexity spectrum. This document explains when to use each, how to tell them apart, and how to promote a skill to an agent when it outgrows its original design.

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

A skill with a `skill.py` can declare tools, override the model, or adjust temperature, but it remains fundamentally one-shot: the user sends a message, the skill responds, done.

**Examples in JARVIS:** Content Evaluator (`/content-evaluator`), Flow Master (`/flow-master`), PM Strategist (`/pm-strategist`).

## What Is an Agent?

An agent is a stateful, multi-turn Python class that inherits from [`BaseAgent`](../../packages/agents/base.py). It maintains conversation history, supports custom orchestration, and can wire in tools at construction time.

```
tactics/
  __init__.py       # AGENT_META dict for registry discovery
  agent.py          # Python class extending BaseAgent
  prompts/
    system.md       # system prompt loaded via load_prompt()
```

**Key properties:**

- **Stateful** -- maintains `conversation_history` across turns within a session.
- **Multi-turn** -- designed for back-and-forth interaction where context accumulates.
- **Python-native** -- requires a Python class, making it JARVIS-specific.
- **Convention-based discovery** -- the [agent registry](../../packages/agents/registry.py) scans for `AGENT_META` in `__init__.py` files.

Agents can accept `extra_tools` at construction (e.g., the RAG search tool), run agentic loops with tool calls, and implement custom `process_message()` logic.

**Examples in JARVIS:** TacticsAgent (`/tactics`), Writing (`/write`), Research (`/research`), Clarity (`/clarity`), Pattern Language Expert (`/pattern-language-expert`), OKR Architect (`/okr-architect`), Navigator (`/navigator`).

## The Key Difference

> A skill answers a question. An agent has a conversation.

This is not about complexity. A skill can have a sophisticated prompt, tools, and resource files. An agent can have a simple system prompt. The dividing line is **statefulness and memory**:

| | Skill | Agent |
|---|---|---|
| State across turns | None | Conversation history |
| Typical interaction | Single request/response | Multi-turn dialogue |
| Implementation | SKILL.md (+ optional Python) | Python class |
| Portability | Vendor-portable | JARVIS-native |
| Discovery | Filesystem scan for SKILL.md | Python module scan for AGENT_META |

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

OKR Architect and Pattern Language Expert were promoted to agents based on observed interaction patterns: both benefit from iterative refinement cycles and context-dependent responses across turns. The remaining four are correctly implemented as skills -- each can deliver value in a single exchange. If usage patterns show that users consistently need follow-up turns, that's the signal to promote.

## Migration Path

When a skill earns its promotion, here's how to convert it while preserving portability:

### Step 1: Keep the SKILL.md

The original SKILL.md remains the canonical prompt specification. It stays portable and can still be used standalone with other LLM providers.

### Step 2: Create the Agent Directory

```
packages/agents/<name>/
  __init__.py       # AGENT_META = {"name": ..., "description": ..., "command": ...}
  agent.py          # Agent class extending BaseAgent
  prompts/
    system.md       # can reuse or extend the SKILL.md content
```

### Step 3: Implement the Agent Class

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

### Step 4: Wire Up Discovery

Add `AGENT_META` to `__init__.py` so the agent registry finds it:

```python
AGENT_META = {
    "name": "my-agent",
    "description": "...",
    "command": "/my-agent",
}
```

### Step 5: Retire the Skill (Optional)

If the agent fully replaces the skill's use case within JARVIS, remove the skill directory from `packages/skills/` to avoid duplicate slash commands. The SKILL.md can live in the agent's directory or in a shared specifications repo for cross-vendor use.

## Design Principles

1. **Start as a skill.** Skills are simpler, portable, and faster to build. Default to a skill unless you have evidence that multi-turn interaction is needed.

2. **Promote based on evidence, not speculation.** Don't build an agent because a capability *might* need multi-turn support. Build the skill, use it, and let the interaction pattern tell you.

3. **Portability is a feature.** SKILL.md files work everywhere. Once you promote to an agent, you gain power but lose vendor portability. That trade-off should be intentional.

4. **Keep the SKILL.md alive.** Even after promotion, the SKILL.md serves as documentation and as a portable fallback. It's the specification; the agent is the implementation.
