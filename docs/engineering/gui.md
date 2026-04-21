# JARVIS GUI — engineering notes

Phase 1 ships the **Chat shell**. Dashboard, Agents, Conversations, Settings,
and the Agent-Prompt-editor surfaces are stubbed and will land in later phases.

## Run

```bash
uv sync --extra web
uv run jarvis-gui              # opens http://127.0.0.1:8123 in your browser
uv run jarvis-gui --no-browser # just serve; visit manually
uv run jarvis-gui --port 9000  # override the port
```

The server binds to `127.0.0.1` only — **no authentication**. Don't expose it.

The CLI (`uv run jarvis`) continues to work unchanged. Both share:
- the same conversation JSON files (`data/conversations/YYYY/*.json`)
- the same agent registry (`packages/agents/*/meta.yaml`)
- the same tool groups, vault config, MCP servers, RAG index, Things 3 sync

## Architecture

```
apps/gui/
  main.py                 # entry — uvicorn.run + webbrowser.open
  server/
    app.py                # FastAPI factory + lifespan (MCP start/stop, logger save)
    state.py              # GuiSession — SessionComponents + per-turn handlers
    protocol.py           # WS TypedDicts (server ↔ client)
    streaming.py          # WebStreamHandler — on_event → queue events
    confirmation.py       # WebConfirmationHandler — diff buffer + threaded wait
    bridge.py             # per-turn orchestration (agent.run in to_thread)
    session_factory_helpers.py
    routes/
      api.py              # GET /api/agents, /api/session
      chat_ws.py          # /ws/chat (submit / approval_decision / cancel)
  web/
    src/                  # React + TypeScript source
    dist/                 # built bundle, committed (see below)
```

Backend wiring reuses `apps/cli/session_factory.build_session()` — the CLI's
own factory, refactored to accept an injected `ConfirmationHandler`.

## WebSocket protocol

Client → server (`/ws/chat`):

```json
{ "type": "submit",            "text": "..." }
{ "type": "approval_decision", "id": "...", "approved": true }
{ "type": "cancel" }
```

Server → client events (each a JSON object with a `type` discriminator):

- `session_start { session }` — fires once on connect.
- `system { text }` — ambient info (startup line, errors, rejections).
- `user { id, text, time }` — echo of the user's submit.
- `thinking_start / thinking_end { agent }` — for the spinner.
- `chunk { id, agent, delta }` — streaming text; client appends to the in-progress row.
- `text { id, agent, markdown, stats }` — finalized assistant turn with stats
  (`[N tokens | $cost | TTFT: Nms | Total: Nms]`).
- `tool_call { id, agent, tool, args, result, elapsed_ms }` — emitted after a
  `ToolResult` event pairs with its `ToolCallStarted`.
- `delegation { id, from, to, reason }` — JARVIS → specialist.
- `approval_pending { id, tool, agent, path, diff, summary }` — vault-write
  diff awaiting user decision. Client must respond with `approval_decision`.
- `approval_resolved { id, approved }` — echoed after resolution.
- `rag_result { id, query, matches }` — recall cards.
- `error { id?, message }` — turn failed.
- `totals { messages, tokens, cost }` — updates the status bar.
- `turn_finished { id }` — releases the composer.

The protocol is mirrored in `apps/gui/server/protocol.py` (Python TypedDicts)
and `apps/gui/web/src/lib/types.ts` (TypeScript). Keep them in sync.

## Rebuilding the frontend

The `dist/` bundle (~175 KB, ~55 KB gzipped) is committed so `uv run
jarvis-gui` works on a fresh clone without Node. When you edit frontend
source, rebuild and re-commit:

```bash
cd apps/gui/web
npm install      # only needed once, or when package.json changes
npm run build    # produces dist/index.html + dist/assets/index-*.js
cd ../../..
git add apps/gui/web/dist/
git commit -m "chore(gui): rebuild frontend bundle"
```

For HMR during UI iteration:

```bash
cd apps/gui/web
npm run dev      # vite on :5173, proxies /api and /ws to :8123
```

In a separate terminal:

```bash
uv run jarvis-gui --no-browser   # backend on :8123
```

Open http://localhost:5173 for hot-reloading UI with a live backend.

## Sidebar Timeline mode (Phase 4)

The Chat-view sidebar has two render variants, toggled from the Tweaks panel:

- `sidebar mode: list` — the default, unchanged from Phase 2: a flat list of the 20 most recent conversations with date / title / agent / msg count / cost.
- `sidebar mode: timeline` — ported from design prototype v3: a vertical day-axis with token-sized conversation cards. The 40px axis column shows weekday + day-number + day-cost (sum across all convs on that day) only on the first row of each calendar day; subsequent same-day rows keep the axis column blank, and the card-rail's vertical `borderLeft` stays continuous so the rail reads as one line.

Both variants share the same fetch (`/api/conversations?limit=20&sort=recent`), header, search box (still inert, will be wired in a later phase), loading / error / empty states, and session footer. Only the row rendering branches on `mode`.

Card height in timeline mode is log-bucketed in `heightFor(tokens)`:

```
48 + round(log10(max(tokens, 100)) * 8), clamped to [48, 80]
```

Deterministic — doesn't depend on the current fetch's max token count, so heights don't reshuffle when a new conversation lands.

Agent-hue sits on the card's `borderLeft`: 2px baseline, bumped to 3px with the full card border in the hue and `surface2` background when the card represents the active session. The dominant agent's hue comes from `hueFor()` in `lib/agentHues.ts` (shared with Phase 2 History view).

Dates are parsed via `parseLocalDate()` in `lib/dateBucket.ts` to avoid the `new Date("YYYY-MM-DD")` UTC-midnight pitfall that can shift weekday labels in negative-offset timezones.

The tweak is persisted in `localStorage` under `jarvis-gui-tweaks-v1` with the rest of the tweaks object. Pre-existing stores without the new key fall back to `list` via `DEFAULT_TWEAKS` spread in `App.tsx`.

## Dashboard / Home (Phase 3)

The left-rail **Home** slot renders the Dashboard — greeting, Things 3
"On your plate", cost-this-week sparkline, resume card, recent
conversations grid, quick-start commands. Matches design v1 Home.

### Endpoint

`GET /api/home` — composite response:

```json
{
  "greeting": "Good afternoon",
  "today":    { "date": "2026-04-20", "day_label": "Monday, April 20" },
  "tasks":    [ { "title": "...", "project": "...", "when_date": "...",
                  "priority": "high|medium|low", "list": "today|upcoming|inbox",
                  "linked_conversation_ids": [...] } ],
  "cost_week": { "days": [ { "date": "YYYY-MM-DD", "cost": 0.0, "conversations": 0 } ],
                 "total": 0.0, "conversation_count": 0 },
  "resume":   ConversationSummary | null,
  "recent":   [ ConversationSummary, ... ],       // up to 4
  "quick_start": [ { "label": "/write", "cmd": "/write", "agent": "writer" }, ... ]
}
```

### Implementation notes

- **Priority** comes from the Things 3 **list key**, not a field on the
  Task dataclass. `today` → high, `upcoming` → medium, `inbox` → low.
- **Task-conversation linking** is a dumb substring match: longest
  ≥ 4-char word of the task title against the lowercased titles of the
  20 most-recent conversations. Max 2 links per task. Iterate on false
  matches.
- **Cost-week aggregation** walks `ConversationIndex._cache.values()`
  directly — mirrors the pattern `ConversationIndex.facets()` uses
  internally. Days outside the 7-day window are ignored; days inside
  but with no conversations are zero-filled.
- **Active-session exclusion** is **client-side**. The server returns
  `resume` as the absolute most-recent summary; if `resume.id ===
  session.file_id`, the frontend promotes `recent[0]` into the resume
  slot. This keeps the server stateless about `file_id` and handles the
  cold-landing-on-Home case (WS not yet connected, `session === null`)
  without server coordination.
- **Quick Start → Chat** uses a `pendingSeed` lifted into App state.
  ChatView only submits the seed once `wsReady` (set by `session_start`)
  is true — avoids the race where a freshly-mounted ChatView receives a
  seed before the WS is open and silently drops the submit.
- **Refresh cadence**: `HomeView` subscribes to the same
  `historyRefreshToken` that Sidebar + HistoryView use. Chat's
  `turn_finished` bumps it → Home invalidates → `/api/home` returns
  fresh cost-week + resume + recent.

### Known limitations (Phase 3)

- **Resume** button routes to History detail (same as Phase 2); true
  rehydration of a past `ConversationLogger` is deferred.
- **Sparkline drill-down** — bars are static; clicking doesn't filter
  History.
- **Task ↔ conversation link editing** — read-only derivation; users
  can't pin or exclude links manually.
- **Things 3 cache TTL** — `fetch_tasks()` reuses `TaskSyncCache`
  (default 300s); tasks can appear stale if the user added one via
  Things 3 in the last five minutes. Cache invalidates by wall-clock,
  not by a Home refresh button.

## Conversations browser (Phase 2)

The History view is a two-pane browser over `data/conversations/YYYY/*.json`:
400px filters + date-bucketed list + detail pane (5-stat strip, Tools chips,
transcript preview). Matches design v4.

### Endpoints

- `GET /api/conversations?q=&agent=&tool=&date=&sort=&limit=&offset=` — paginated
  summaries. `sort ∈ {recent, cost, messages}`, `date ∈ {all, today, 7d, 30d}`.
- `GET /api/conversations/facets` — unique agents + tools (with counts) +
  `total` file count, for the filter chips.
- `GET /api/conversations/{id}` — full detail including all messages + preview
  (first 4 non-tool messages, 240 chars each).

### Data shape

Summary items: `id` (filename stem, e.g. `2026-04-20_10-20-20`), `date` (from
`session_start[:10]`), derived `title` (first user message, truncated),
`agents[]`, `messages`, `tokens`, `cost`, `duration_ms`, `tool_calls`,
`tools[]`, `handoffs`, `model`, `provider`.

The **Handoffs** stat is counted from assistant messages whose
`tool_calls[].function.name == "delegate_to_agent"` — there is no metadata
flag for delegation, just the tool invocation. If
`packages/core/tools/delegate.py` renames the tool, update
`apps.gui.server.history.derive.HANDOFF_TOOL_NAME`.

### Refresh cadence

- Full refresh on lifespan startup (in `asyncio.to_thread`).
- Lightweight stat-only refresh on every `/api/conversations` request — only
  changed/new files are re-parsed.
- WS `turn_finished` triggers `index.mark_dirty(file_id)` so the current
  session's summary is re-parsed on the next refresh even if mtime is
  unchanged (defends against tight save-then-read races).

### Known limitations (Phase 2)

- **Non-atomic writes** in `ConversationLogger.save()` mean the index may
  occasionally try to read a half-written file. We swallow `JSONDecodeError`
  and skip; the next refresh picks it up clean.
- **Resume** and **Export** buttons are rendered but disabled — actual resume
  requires rehydrating a `ConversationLogger` mid-process and is deferred.
- **Transcript viewer** — "open full transcript →" is a stub (returns to Chat).
- **Pagination UI** — backend supports `limit`/`offset`, but the History view
  loads 200 at once and Sidebar caps at 20. Add an infinite scroll when users
  routinely exceed that.
- **Semantic search** — the Sidebar's "Search or ask recall…" input is not
  wired yet. Title substring-filter only in the History view for now.
- **Filename collisions** — two sessions started in the same second would
  overwrite each other's JSON. Unlikely for single-user local; document and
  revisit only if it bites.

## Known limitations (Phase 1)

- **Cancel is dispatch-only.** The `{ "type": "cancel" }` message stops
  emitting events to the WS but the in-flight LLM call keeps running in the
  worker thread; its tokens/cost still land in the conversation log.
- **Single session, single turn.** Second `submit` while a turn is running is
  rejected. Second WS connection takes over; any pending approval on the
  first is auto-rejected.
- **No interactive delegate sub-loops** — delegation is single-shot
  (JARVIS → delegate → result → back to JARVIS). Matches the design
  prototype's flow.
- **`/daily-summary` and `/outcomes`** are CLI-only in Phase 1 (tightly
  coupled to `prompt_toolkit` and CLI display).
- **`uvicorn --reload` breaks MCP subprocess lifecycle** — don't use it.
  Restart manually when changing Python that owns subprocesses.
- **Running CLI and GUI concurrently** may race on the Things 3 SQLite read
  (both call `sync_tasks_to_file`). Low risk, last-writer-wins on
  `data/context/tasks.md`.

## Visual identity rules (non-negotiable)

- **Speakers Title Case, system affordances lowercase.** `You`, `JARVIS`,
  `Writer`, `OKR Architect` (acronym-aware via `speakerLabel()`); `tool`,
  `approve`, `recall`, `→` stay lowercase.
- **No chat bubbles.** CLI-transcript rows: 96px speaker-label gutter +
  2px colored left border per row.
- **Stats line format exact**: `[1,234 tokens | $0.0045 | TTFT: 250ms |
  Total: 1500ms]`.
- **Costs are never hidden.** Cost color brightens to `costHigh` above
  $0.05 (status bar) / $0.01 (per-turn line).
- **Dark-first.** Cyan accent used sparingly; everything else grayscale.
- **Mono-forward typography.** JetBrains Mono for paths, tool names, stats,
  agent labels. Sans only for prose.
