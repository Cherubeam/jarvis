# Design Principles

> Seven principles that translate JARVIS's existing values into UI-specific guidance.
> Framework-agnostic. These apply whether the interface is web, desktop, or both.

See also: [voice-and-tone.md](voice-and-tone.md) for how the UI communicates,
[tokens.md](tokens.md) for visual primitives, [components.md](components.md) for the component inventory.

---

## 1. Your data, your screen

**Derived from**: Local-first architecture

The user's filesystem is the source of truth. The UI reflects what's on disk, not what's in a cloud database. File paths are first-class UI elements — shown in full, clickable, copyable. Conversation logs are JSON files the user can open in any editor. Context files are markdown the user already maintains.

**This, not that**:
- Show `~/jarvis/data/conversations/2026/2026-03-14_10-30-00.json` — not "Conversation #47"
- Show `config/local.yaml` as the settings source — not a proprietary settings panel that writes to an opaque store
- Show "Saved to disk" — not "Synced to cloud"

No cloud sync indicators. No "your data is safe with us" messaging. The user's data never left their machine.

---

## 2. Provider is plumbing

**Derived from**: Provider independence (LiteLLM abstraction)

The LLM provider is a configuration detail, not a brand identity. Model names appear in status areas and settings — never in hero sections, splash screens, or prominently branded UI elements. Switching providers is changing a dropdown value, not migrating to a different product.

**This, not that**:
- Status bar: `claude-sonnet-4-5 via openrouter` — not a large Claude logo with "Powered by Anthropic"
- Model selector: a flat list of model IDs — not provider-branded cards with marketing copy
- Error message: `Model returned 429 (rate limited)` — not "Anthropic is experiencing issues"

The user chose JARVIS. The model is a setting.

---

## 3. Show the work, hide the chrome

**Derived from**: Simplicity + tool calling architecture

Agent delegations, tool calls, and reasoning steps are shown transparently — the user sees what JARVIS is doing and why. But the UI scaffolding around that content should be minimal. Content IS the interface. Toolbars, sidebars, and navigation exist to serve the conversation, not to look busy.

**This, not that**:
- `[Tool: fetch_url]` inline in the conversation flow — not a separate "Activity" panel the user has to open
- A single conversation stream where the responding agent changes — not a tabbed interface where each agent has its own window
- Markdown rendered natively — not wrapped in a custom rich-text editor with formatting toolbars

If a UI element doesn't help the user understand what happened or decide what to do next, remove it.

---

## 4. One user, zero onboarding

**Derived from**: Single-user design + no premature optimization

No login screen. No account creation. No "Welcome to JARVIS" wizard. The app starts and the user talks. Configuration lives in YAML files the user already maintains (`config/local.yaml`, `config/default.yaml`). Context lives in markdown files the user already edits (`data/context/*.md`).

**This, not that**:
- First launch: an empty conversation ready for input — not a 5-step setup wizard
- Configuration: "Edit `config/local.yaml`" with a link to open the file — not a sprawling settings UI that duplicates what YAML already does
- No user avatars, no profiles, no "personal workspace" language

The user is the only user. The app knows this.

---

## 5. Costs are always visible

**Derived from**: Deep investment in cost tracking (pricing.py, per-request costs, session metrics)

Token counts and costs appear on every response, always. This is not a toggle, not a "developer mode" feature, not hidden behind a menu. The existing CLI format — `[1,234 tokens | $0.0045 | TTFT: 250ms | Total: 1500ms]` — is the reference design. The UI should make this information easier to scan, not harder to find.

**This, not that**:
- Every message: token count + cost inline — not "View usage" buried in settings
- Session total: running cost in the status bar — not a monthly summary email
- Model comparison: cost per response visible when choosing models — not hidden in docs

Transparency is a core value. If it costs money, the user sees the number.

---

## 6. Agents are peers, not tabs

**Derived from**: Agent delegation architecture (JARVIS orchestrator + 12 specialist agents)

When JARVIS delegates to a specialist agent, the conversation continues in the same stream. The agent name changes (shown via a badge or label), but the user doesn't navigate anywhere. Handoffs are in-flow events, not navigation actions. The conversation is one continuous thread; the responding agent changes.

**This, not that**:
- `[writer]:` label on a message in the same conversation — not a separate "Writer" tab the user switches to
- Delegation notice inline: "Handing off to writer for this draft" — not a modal dialog asking permission to switch
- Agent history: scroll up to see the handoff — not a separate "agent activity" log

The metaphor is a team in one room, not departments in separate offices.

---

## 7. Text-first, always

**Derived from**: Human-readable storage (JSON, markdown) + Obsidian integration

Markdown is the native content format. Copy-pasting from the UI gives the user markdown source, not rich text that loses formatting. Code blocks are real code blocks. Links are real links. The UI renders markdown — it never invents a proprietary formatting layer on top.

**This, not that**:
- Copy a response: get markdown with `##` headers and `` ```python `` blocks — not styled HTML
- Daily notes: rendered markdown from Obsidian vault files — not a custom note format
- Export: the JSON file that already exists on disk — not a "Download as PDF" button

The user's content is already in a format that works everywhere. The UI respects that.

---

*These principles are intentionally opinionated. They reflect JARVIS as it exists today — a local-first, provider-independent, cost-transparent personal assistant. As the project evolves, principles may be revisited, but the bias should always be toward simplicity and user ownership.*

---

*Last updated: 2026-03-16*
