# UI Voice & Tone

> How JARVIS communicates *through the interface* — labels, status text, errors, empty states.
> This is NOT the writing voice in `voice-profile.md` (that's how JARVIS writes *content* for the user).
> This is the voice of the product itself.

See also: [principles.md](principles.md) for design principles,
[tokens.md](tokens.md) for visual primitives, [components.md](components.md) for the component inventory.

---

## The Character

Competent, understated, occasionally dry. Think Iron Man's JARVIS: reliable, slightly formal, never obsequious. The UI speaks when it has something useful to say and stays quiet otherwise. It states facts. It doesn't celebrate, apologize, or fill silence with filler.

The CLI already embodies this: `Thinking...`, `[Tool: fetch_url]`, `[1,234 tokens | $0.0045 | TTFT: 250ms | Total: 1500ms]`. No emoji, no exclamation marks, no "Great question!" before answering. The UI voice extends this sensibility to every surface.

---

## Four Principles

### 1. Be useful, not chatty

Every piece of UI text should answer a question the user actually has: "What's happening?", "What went wrong?", "What can I do here?" If the text doesn't answer one of these, cut it.

| Before | After |
|--------|-------|
| "Welcome back! Ready to help you with anything you need today." | *(nothing — just show the input field)* |
| "Loading your conversations, this might take a moment..." | "Loading conversations..." |
| "You can type a message below to start chatting with JARVIS!" | *(placeholder text in input):* "Message" |

### 2. State facts, not feelings

The UI reports what happened, not how it feels about it. No anthropomorphizing the interface. The assistant has personality; the chrome does not.

| Before | After |
|--------|-------|
| "Oops! Something went wrong." | "Request failed: connection timeout." |
| "I'm thinking about your question..." | "Thinking..." |
| "Yay! Your daily summary is ready!" | "Daily summary written to vault." |

### 3. Acknowledge, don't congratulate

When an action completes, confirm it happened. Don't praise the user for clicking a button.

| Before | After |
|--------|-------|
| "Great choice! Model updated successfully." | "Model: claude-sonnet-4-5" |
| "Awesome! Conversation exported." | "Exported to 2026-03-14_10-30-00.json" |
| "You've successfully switched to the writer agent!" | "[writer]: Ready." |

### 4. Be specific about what happened

Vague status messages waste the user's time. Include the detail that helps them understand or act.

| Before | After |
|--------|-------|
| "An error occurred." | "OpenRouter returned 402: insufficient credits." |
| "File saved." | "Saved to data/conversations/2026/2026-03-14_10-30-00.json" |
| "Tool completed." | "[Tool: fetch_url] 12,340 chars extracted." |
| "Multiple agents available." | "12 agents registered. Type / for commands." |

---

## Voice by Context

### Loading / Streaming

The existing CLI pattern is the reference: an animated `Thinking...` spinner that appears immediately and is replaced by streaming text. The UI equivalent should feel equally lightweight.

- **Waiting for first token**: "Thinking..." (dim, animated) — mirrors `Spinner("dots", text=" Thinking...")`
- **Streaming in progress**: No status text. The text appearing IS the status.
- **Tool call in progress**: `[Tool: name]` inline — mirrors `print_tool_feedback()`
- **Long operation**: "Indexing conversations..." / "Fetching URL..." — the verb describes the action

Never: "Please wait...", "Hold on...", "Just a moment...", "Working on it..."

### Errors

Lead with what went wrong, then what the user can do about it. Use the same `error` style (bold red in CLI) consistently.

- **API error**: "Model returned 429. Retry in 30s or switch model with /model."
- **Missing config**: "No API key found. Set OPENROUTER_API_KEY in .env."
- **Tool failure**: "[Tool: fetch_url] Failed: connection refused. URL may be unreachable."
- **File not found**: "Daily note not found: 2026-03-14.md. Check vault path in config."

Never: "Oops!", "Uh oh!", "Something went wrong (but don't worry!)", "We're sorry..."

### Empty States

When there's nothing to show, say what's missing and how to get it. One sentence.

- **No conversations**: "No conversations yet. Type a message to start."
- **No search results**: "No matches for 'kubernetes'. Try broader terms."
- **No agents registered**: "No agents found in packages/agents/. See AGENTS.md."
- **RAG disabled**: "Conversation recall is off. Enable in config/local.yaml."

Never: "It's a bit empty in here!", "Nothing to see yet — but that's okay!", placeholder illustrations of empty boxes.

### Confirmations

State what happened. Include the relevant detail (filename, agent name, count).

- **Session saved**: "Session saved. 14 messages, $0.12."
- **Model switched**: "Model: gpt-4o via openai"
- **Agent delegation**: "Delegating to writer."
- **Vault write**: "Updated daily note: 2026-03-14.md"

Never: "Success!", "Done!", "All good!", "That worked!"

### Help Text

Tooltips and help text answer "what does this do?" in one line. Use the imperative mood.

- **Model selector**: "Choose the LLM model for this session."
- **Cost display**: "Cumulative token cost for this session."
- **Agent badge**: "Responding agent. JARVIS delegates to specialists."
- **Conversation browser**: "Browse past sessions by date."

---

## What JARVIS Never Does

These patterns are banned from UI chrome, status text, labels, and system messages.
(The assistant's *conversational responses* have their own voice — this list applies to the interface itself.)

- **Exclamation marks** in status text or labels. Ever.
- **"Please"** in status messages. ("Please wait..." → "Loading...")
- **"Sorry"** in error messages. ("Sorry, that didn't work" → "Request failed: reason.")
- **Emoji** in chrome, labels, or status text. (Emoji in assistant responses is fine if contextually appropriate.)
- **Filler words**: "just", "simply", "actually", "basically" in any UI text.
- **Unsolicited encouragement**: "Great job!", "Keep going!", "You're doing great!"
- **Questions as status**: "Did you know you can...?" in tooltips or banners.
- **Marketing language**: "Powerful", "seamless", "effortless", "supercharge", "unlock".
- **Royal "we"**: "We couldn't find..." → "Not found:" / "No results."
- **Hedging**: "It seems like...", "It looks like...", "We think..." → State the fact.

---

*This guide complements `voice-profile.md` (the writing voice for authored content) without duplicating it. The UI voice is the building, not the person inside it — functional, clear, and out of the way.*

---

*Last updated: 2026-03-16*
