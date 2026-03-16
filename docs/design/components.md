# Component Inventory

> Catalog of UI components based on actual JARVIS features.
> Names and descriptions only — no implementations, no framework assumptions.
> This is a shared vocabulary for design and development conversations.

See also: [principles.md](principles.md) for design principles,
[voice-and-tone.md](voice-and-tone.md) for UI copy guidelines, [tokens.md](tokens.md) for visual primitives.

---

## Chat / Conversation

| Component | Description |
|-----------|-------------|
| **MessageBubble** | A single message in the conversation stream. Displays role (user/assistant), agent name, timestamp, and rendered markdown content. User messages use `color.user`; assistant messages use `color.assistant`. |
| **StreamingText** | Live text that appends tokens as they arrive from the LLM stream. Replaces the `Thinking...` indicator once the first token arrives. Renders final markdown in place when streaming completes — mirrors `finish_live_stream()` behavior. |
| **ThinkingIndicator** | Animated spinner shown between user input and first token. Equivalent to the CLI's `Spinner("dots", text=" Thinking...")`. Disappears when streaming begins. |
| **UsageStats** | Token count, cost, TTFT, and total latency displayed after each assistant response. Follows the CLI format: `[1,234 tokens | $0.0045 | TTFT: 250ms | Total: 1500ms]`. Uses `color.stats` and `font.mono`. |

## Agent System

| Component | Description |
|-----------|-------------|
| **AgentBadge** | Inline label showing which agent is responding (e.g., "JARVIS", "writer", "researcher"). Uses `color.assistant` styling. Appears before or within message bubbles. |
| **DelegationNotice** | In-flow message indicating a handoff between agents. Shows the source agent, target agent, and a brief reason. Styled as a system message (`color.system`). |
| **CommandPalette** | Keyboard-triggered overlay listing available slash commands (`/write`, `/research`, `/daily-summary`, etc.). Filterable by typing. Maps to the agent registry's command list. |
| **AgentSwitcher** | Compact control for directly selecting an agent, bypassing JARVIS delegation. Equivalent to `--agent <name>` on the CLI. |

## Tool System

| Component | Description |
|-----------|-------------|
| **ToolCallCard** | Inline display of a tool invocation during the agentic loop. Shows tool name, parameters, and result summary. Mirrors `[Tool: fetch_url]` from the CLI but with expandable detail. |
| **ToolApprovalPrompt** | Confirmation dialog for tool calls that require user permission (e.g., vault writes, file modifications). Shows the action, affected path, and diff preview where applicable. Maps to the `ConfirmationHandler` ABC. |
| **ToolProgressIndicator** | Status indicator for long-running tool operations (web fetch, RAG indexing). Shows the tool name and a brief description of what's happening. |

## Cost & Metrics

| Component | Description |
|-----------|-------------|
| **TokenCounter** | Running total of tokens used in the current session. Lives in the status bar. Uses `font.mono` and `color.stats`. |
| **CostDisplay** | Running total cost for the current session, formatted by `format_cost()`. Turns `color.cost.high` above a configurable threshold. Always visible per design principle #5. |
| **SessionSummary** | End-of-session summary showing total messages, tokens, cost, duration, and model used. Displayed when the user ends a session or navigates away. |

## Navigation

| Component | Description |
|-----------|-------------|
| **ConversationBrowser** | List of past conversations from `data/conversations/YYYY/*.json`. Shows date, title (if set), model, cost, and message count. Sorted by date, grouped by year. |
| **ConversationSearch** | Search input for finding past conversations. Supports text search across titles and content. When RAG is enabled, supports semantic search via `ConversationSearcher`. |
| **SessionHeader** | Top bar for the active session showing the current agent name, model ID, and session duration. Equivalent to the CLI startup banner (`print_startup()`). |

## Integrations

| Component | Description |
|-----------|-------------|
| **VaultNoteBrowser** | File browser scoped to the configured Obsidian vault. Lists notes with path validation via `VaultConfig`. Respects `FilesystemGuard` access rules. |
| **DailyNoteSummary** | Rendered view of today's daily note from the Obsidian vault, focused on the `> [!JARVIS]` callout block. Equivalent to `/daily-summary` output. |
| **TaskList** | Display of Things 3 tasks synced via `task_sync.py`. Grouped by area > project > tasks, matching the markdown format written to `tasks.md`. |
| **RAGResultCard** | A single result from conversation recall. Shows the query match, source conversation date, and a snippet of the matched message pair. Maps to `SearchResult` from `searcher.py`. |

## Settings

| Component | Description |
|-----------|-------------|
| **ModelSelector** | Dropdown or list for choosing the active LLM model. Shows model ID and provider. Equivalent to `/model` command and `--model` flag. |
| **ProviderStatus** | Indicator showing which API keys are configured and which providers are available. Derived from `collect_api_keys()` at startup. |
| **ContextFileEditor** | Inline editor for `data/context/*.md` files. Renders as markdown with an edit toggle. Changes write directly to the user's filesystem. |

## Layout

| Component | Description |
|-----------|-------------|
| **AppShell** | Top-level layout container. Defines the sidebar, main content area, and status bar regions. Minimal chrome — content area dominates per design principle #3. |
| **StatusBar** | Persistent bar (bottom or top) showing model ID, session cost, token count, and connection status. Uses `color.stats` and `font.mono`. Always visible. |
| **Sidebar** | Collapsible panel for conversation history and navigation. Hidden by default on narrow viewports. Contains `ConversationBrowser` and `ConversationSearch`. |

## Shared Primitives

| Component | Description |
|-----------|-------------|
| **MarkdownRenderer** | Renders markdown content with syntax highlighting for code blocks, clickable links, and proper heading hierarchy. The primary content display component — used everywhere. |
| **CodeBlock** | Fenced code block with language label and copy button. Uses `font.mono` on `color.surface.secondary` background. Extracted from `MarkdownRenderer` for standalone use. |
| **DiffView** | Side-by-side or inline diff display for vault write confirmations. Maps to `VaultDiff` and `compute_diff()` from `diff.py`. |
| **ConfirmDialog** | Modal confirmation for destructive or significant actions. Shows the action description and affected targets. Two buttons: confirm and cancel. No "Are you sure?" phrasing — states what will happen. |
| **Spinner** | Animated loading indicator. Matches the CLI's `Spinner("dots")` cadence. Used inside `ThinkingIndicator` and `ToolProgressIndicator`. |

---

*This inventory reflects JARVIS features as of Phase 5. Components will be added as new capabilities ship. Implementation details (props, state, styling) belong in a future component specification — this document establishes the vocabulary.*

---

*Last updated: 2026-03-16*
