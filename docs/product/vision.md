# Product Vision

## Problem Statement

Most professionals rely on ChatGPT, Claude, Gemini, or similar tools to interact with AI. These tools are powerful, but they create a critical dependency: **all your context, conversation history, and learned preferences are locked within each provider's ecosystem.**

Switching providers means:
- Losing all conversation history
- Rebuilding context from scratch
- No way to compare models on your specific use cases
- Vendor lock-in through data captivity

## Solution

Jarvis is a provider-agnostic personal AI assistant that puts users in control of their data, context, and conversation history.

**Core Capabilities:**
- Maintains persistent context in human-readable markdown files
- Works with any LLM provider through unified interface
- Stores all conversations locally with full ownership
- Enables true multi-provider comparison and switching

## Why Jarvis Exists

Jarvis is Marco's owned, local-first personal assistant and his learning and
portfolio platform ([ADR-040](decisions.md#adr-040-what-jarvis-is-for--an-owned-daily-assistant-and-a-place-to-learn)).
It exists so he can:

- **Try new things and learn** by building them himself
- **Show his skills and experience**: every milestone gets a write-up
- **Own his assistant** and **use it every day**
- Keep **all his AI conversations in one place**, imported from ChatGPT, Claude
  and the other tools he uses, next to his vault, tasks and other sources
  (Obsidian, Things 3, Readwise)

Jarvis does not try to beat commercial assistants. It is measured by what it
teaches, what it lets him show, and how often he uses it.

**North star:** a personal assistant in the spirit of OpenAI's Dots (2026-09):
always on, able to act across his own apps, reachable from the phone. Jarvis
gets there local-first and in small steps that each ship on their own.

## Long-term Vision

### Year 1: Personal Assistant Foundation
- Robust context management system
- Multi-provider support (OpenRouter, Anthropic, OpenAI)
- Conversation search and retrieval
- Quality metrics and evaluation framework

### Year 2: Agent Capabilities
- Function calling and tool use
- Multi-agent orchestration
- Complex workflow automation
- Intelligent model routing based on task complexity

### Year 3: Autonomous Systems
- Proactive assistance based on learned patterns
- External integrations (calendar, email, code repositories)
- Fine-tuned personal models
- Community-driven agent marketplace

## Target Users

### Primary: AI Engineers & Technical Learners
- Building AI applications professionally
- Want to understand AI systems from first principles
- Value transparency and control over abstractions
- Need flexibility to experiment with different providers

### Secondary: Privacy-Conscious Power Users
- Frustrated with vendor lock-in
- Want full control over their data
- Need provider independence for cost optimization
- Value local-first, open-source solutions

### Tertiary: Research & Education
- Students learning AI engineering
- Researchers comparing model behaviors
- Educators demonstrating AI concepts
- Practitioners needing reproducible experiments

## Core Values

### 1. Simplicity Over Complexity
No unnecessary abstractions. Code should be readable and understandable by intermediate developers.

### 2. User Data Ownership
All data lives on the user's machine in human-readable formats. No cloud dependencies, no proprietary formats.

### 3. Provider Independence
Switching from Claude to GPT-4 to Gemini should be a configuration change, not a rewrite.

### 4. Transparency
Every decision is documented. Open-source by default. No magic, no hidden behavior.

### 5. Learning-Oriented
This project teaches AI engineering through real implementation. Documentation explains the "why" behind every choice.

## Success Criteria

### Short-term (3 months)
- 100% data portability achieved
- Sub-$0.10 average conversation cost
- Zero vendor lock-in (validated through provider switching)
- Clear, documented codebase understandable by others

### Ongoing (from 2026-09)
- Jarvis is used daily: native sessions per week are counted and reviewed
- The conversation archive is current (imports no more than a month old)
- Each shipped milestone has a public write-up

### Medium-term (1 year)
- Conversation search and retrieval working
- 5+ different models benchmarked on personal use cases
- Agent capabilities (function calling, tool use)
- 10+ users actively using the system

### Long-term (2-3 years)
- Multi-agent orchestration framework
- Community of users sharing agent configurations
- Reference implementation for AI engineering education
- Proven cost savings vs. commercial solutions

## Why This Matters

This project demonstrates:

1. **Problem-first thinking**: Real pain point → concrete solution
2. **Learning by building**: Theory meets practice
3. **Simplicity over cleverness**: Maintainable, understandable code
4. **Open development**: Every decision documented and explained
5. **User empowerment**: Data ownership and provider freedom

## Competitive Landscape

### Commercial Solutions
- **ChatGPT Plus ($20/mo)**: Best UX, total vendor lock-in
- **Claude Pro ($20/mo)**: Excellent quality, locked ecosystem
- **Copilot ($10-20/mo)**: IDE integration, Microsoft lock-in

**Jarvis Advantage**: Pay-per-use, no subscriptions, full data ownership, provider flexibility

### Open-Source Alternatives
- **Open WebUI**: Self-hosted UI, limited context management
- **Anything LLM**: Document focus, heavier setup
- **LangChain apps**: Over-engineered, complex abstractions

**Jarvis Advantage**: Simpler, focused on personal assistant use case, better documentation

### Agent Harnesses (Claude Code, Codex, OpenCode, Cowork, Pi)

These are **complements, not competitors** ([ADR-034](decisions.md#adr-034-context-hub-positioning--rent-coding-harnesses-own-the-context)). They compete on the agentic loop — sandboxing, planning, headless execution — and improve faster than any solo project can. Jarvis does not compete there:

> **Harnesses are commodities; the context is the moat.**

Jarvis is the **personal context, memory, and workflow hub**: the vault, context files, conversation history, typed memory, voice profile, personal integrations, and provider independence. Coding execution is *delegated* to a harness (the developer agent was retired, [ADR-039](decisions.md#adr-039-retire-the-developer-agent)); the commodity argument applies to coding harnesses, not to the assistant itself ([ADR-040](decisions.md#adr-040-what-jarvis-is-for--an-owned-daily-assistant-and-a-place-to-learn)). The context itself is *exported* to every tool via MCP (initiative `HUB`), so nothing has to be copy-pasted between Jarvis, Claude Code, and friends.

## Non-Goals

What Jarvis is **not** trying to be:

- ❌ A hosted service (local-first always)
- ❌ A team collaboration tool (personal use only)
- ❌ A general-purpose coding agent harness (delegate to Claude Code & co. — ADR-034, ADR-039)
- ❌ A competitor to commercial assistants such as ChatGPT, Claude or Dots (ADR-040): features they also ship are built for learning and daily use, not to win on scale
- ❌ A framework for others to build on (learning project first)
- ❌ Production-ready for non-technical users (technical audience)

These may change in the future, but clarity on non-goals prevents scope creep.

---

*Last updated: 2026-09-30*
