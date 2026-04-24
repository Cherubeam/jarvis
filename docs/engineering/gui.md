# JARVIS GUI — engineering notes

Phases 1–5 ship Chat, Conversations (History), Dashboard (Home), Sidebar
Timeline mode, and Agents overview + detail. The remaining surfaces
(Settings, Agent Prompt editor) are stubbed and will land in later phases.

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

## Agents view (Phase 5)

The left-rail **Agents** slot — previously stubbed — now renders the Agents overview grid and an Agent Detail page. Matches the v6 prototype's Agents Overview and the Overview tab of Agent Detail.

### Overview grid

`apps/gui/web/src/views/AgentsView.tsx`. A single 1040px column with:

- `Agents` title + "N registered · packages/agents/" subtitle.
- `ORCHESTRATOR` section with JARVIS as a featured full-width card.
- Six category sections (`WRITING`, `KNOWLEDGE`, `PLANNING`, `ANALYSIS`, `GENERATION`, `ENGINEERING`), each a 3-column grid of compact cards. Agents whose id isn't in any category fall into an `OTHER` section so new agents aren't silently hidden — see `groupByCategory()` in `lib/agentCategories.ts`.

Each card shows speaker-labeled title, mono command, description, tool count, and relative last-used (`today` / `yesterday` / `Nd ago` / `Nw ago` / `Nmo ago` / `unused`). `last_used` is derived client-side from `/api/conversations?limit=500` in a single fetch — avoids changing the wire shape of the list endpoint.

### Detail page

`apps/gui/web/src/views/AgentDetailView.tsx`. Reached by clicking a card; routed via App-lifted `selectedAgentId` + a new `'agent'` sub-view key (not persisted, excluded from `loadView()`'s allowlist). LeftRail receives `view === 'agent' ? 'agents' : view` so the Agents rail button stays highlighted on detail.

Layout:

- `← agents` back link.
- Agent-hue left bar + large speaker label + command (in hue) + `packages/agents/<id>/` path + `start session →` button (hue background). Clicking the button seeds the agent's command (e.g. `/write `) and switches to Chat — reuses the existing `onStartChat` + `pendingSeed` wiring from Home's Quick Start. JARVIS's empty command seeds `null` and just opens a blank Chat.
- Placeholder tab row (`[Overview]` active · `Prompt · Versions · Stats · Context` greyed) — previews the upcoming Prompt Editor phase without leaving a visual gap.
- Description paragraph.
- `TOOLS` chips (or "no tools · pure reasoning agent" when empty).
- `RECENT SESSIONS` — up to 6 rows from `recent_sessions_for_agent(index, agent_id)` (4-column grid: date / title / msg count / cost).
- `COST · LAST 14 DAYS` — agent-hue sparkline via `Cost14dSparkline`. 14 days, not 30 — reads closer to `CostCard`'s 7-day aesthetic and avoids too many zero bars for infrequently-used agents.
- `CONFIGURATION` — model ("(inherits from session)"), `prompt_path`, `prompt_includes_count`, optional `temperature`, `max_iterations`, `skills`. JARVIS's `prompt_path` is `null`; UI shows `(assembled from ~/.jarvis/context/)` because `build_system_prompt()` composes it from soul.md + personal/professional/preferences/focus/tasks/reading profile files at turn time.

### Endpoints

- `GET /api/agents` — list, moved from `routes/api.py` to `routes/agents.py`. JARVIS first (hard-coded synthetic entry — registry skips it via `_SKIP_DIRS`), then data-driven agents alphabetical.
- `GET /api/agents/{id}` — detail. Re-parses `meta.meta_path` with `yaml.safe_load` to surface `temperature / max_tokens / max_iterations / prompt_includes` (these fields live on `AgentConfig`, not on the registry's `AgentMeta`). Defensive 404 on `/` or `..` in the id. `await idx.refresh()` at the top so the cache reflects any `mark_dirty` calls since boot — same pattern as `home.py`.

### Helpers

`apps/gui/server/agents/detail.py`:

- `cost_14d_rollup(index, agent_id, today=None, *, days=14)` — walks `index._cache.values()`, sums `cost` only where `agent_id in summary["agents"]`. Tolerates missing `cost` / `None` / missing `agents` key.
- `recent_sessions_for_agent(index, agent_id, *, limit=6)` — filters summaries by `agent_id in summary["agents"]`, sorts by `summary["id"]` descending (matching the index's own "recent" sort).

### Known limitations (Phase 5)

- **`last_used` caps at 500 conversations.** Agents whose most recent session is older than the 500th most recent conversation show as `unused`. Acceptable for localhost.
- **No per-agent search on the grid.** 16 agents × 3 columns = ~6 rows; a search bar would be noise. v6 doesn't have one either.

## Agent Prompt Editor (Phase 6)

Activates the tab row that Phase 5 shipped as a placeholder. Five tabs on the Agent Detail page: **Overview · Prompt · Versions · Stats · Context**. Tab state is local to `AgentDetailView` (`useState<TabKey>`) — no URL routing, no persistence across navigation.

### Endpoints

All under `/api/agents/{agent_id}/prompt*`. JARVIS is read-only — writes 403. Path-traversal in `agent_id` returns 404 via `_guard_agent_id`.

- `GET /prompt` — current `system.md` content + bytes + `last_modified_iso` + `editable` + optional `explanation` (for JARVIS).
- `PUT /prompt` — body `{content, note?}`. Snapshot-on-save: writes `pre_first_save` on the very first ever save (idempotent), then a `save` snapshot of the *prior* content, then atomic-writes the new content via `frontmatter.write_atomic()`. Serialised per-agent by `app.state.prompt_write_locks[agent_id]` (an `asyncio.Lock`).
- `GET /prompt/snapshots` — newest-first list. Empty for JARVIS.
- `GET /prompt/snapshots/{id}` — one snapshot's full content + metadata.
- `POST /prompt/restore` — body `{snapshot_id}`. Snapshots the current state as `pre_restore`, then writes the snapshot content over `system.md`.
- `GET /prompt/stats` — char/line counts, byte-based token estimate (`len(text.encode("utf-8")) // 4`, matching `context_builder._approx_tokens`), snapshot count, and a `prompt_includes` table with resolution status per placeholder.
- `GET /prompt/resolved` — `{placeholder}`-expanded system prompt as the LLM sees it. For data-driven agents: calls `resolve_system_prompt(agent_dir, prompt_includes)` (pure helper extracted from `agent_from_meta`). For JARVIS: returns `session.components.active_agent.config.system_prompt` — the prompt *already assembled at session boot* from `data/context/` via `build_system_prompt()`. No re-read.

### Snapshot store

`<jarvis_dir>/<paths.prompt_history_dir>/<agent_id>/` — defaults to `data/prompt-history/` (configurable in `config/default.yaml`, mirrors `context_dir`).

```
data/prompt-history/writer/
  20260423T091530_412880Z.md   # pre_first_save — original content
  20260423T091647_833125Z.md   # save — what was on disk when v2 was saved
  20260423T091701_201998Z.md   # save — what was on disk when v3 was saved
  20260423T091715_007742Z.md   # pre_restore — what was on disk just before restore
  index.json                   # [{id, timestamp, bytes, kind, note?}, ...] newest-first
```

Filenames use `%Y%m%dT%H%M%S_%fZ.md` — microsecond resolution — so rapid consecutive saves never collide.

**`index.json` is a cache, not the source of truth.** `list_snapshots()` reads it first, but falls back to a directory glob when it's missing or corrupt. The rebuilt list loses `kind` and `note` (everything defaults to `kind: save`) but the IDs, timestamps, and byte counts are all recoverable from the `.md` files.

### Frontend

`AgentDetailView` hosts the tab router. Overview body was lifted into `AgentOverviewPanel.tsx` as a pure refactor; the other four panels live alongside it under `components/agents/`:

- `AgentPromptPanel` — `<textarea>` with local `original` + `content` state; `dirty = content !== original`. Save (PUT) disables until dirty; Revert (visible only when dirty) is `setContent(original)` — no network call. Save bumps a parent `promptRefreshToken` that scopes to Versions / Stats / Context only. The outer `/api/agents/{id}` fetch doesn't refire, so the active tab doesn't blur.
- `AgentVersionsPanel` — two-column layout: newest-first snapshot list on the left, preview `<pre>` on the right. Click a row to preview; a "restore" button appears on the active row. Confirm-before-restore via `window.confirm()`. `kind` tags are colour-coded: `save` = agent hue, `pre_first_save` = dim, `pre_restore` = error.
- `AgentStatsPanel` — key/value grid plus a `prompt_includes` table. Example-fallback and missing-include statuses render in the error colour so they read as warnings.
- `AgentContextPanel` — copy-to-clipboard button over the resolved prompt. 1.5 s "copied ✓" confirmation.

### JARVIS read-only

JARVIS's prompt isn't backed by a single file — `context_builder.build_system_prompt()` assembles it at session boot from `data/context/*.md`. So:

- `GET /prompt` for JARVIS returns `editable: false` + an explanation + the assembled prompt.
- `PUT /prompt` and `POST /prompt/restore` return 403.
- `GET /prompt/snapshots` returns `[]`.
- `GET /prompt/stats` runs against the live assembled text (char/line/token counts reflect reality; `snapshot_count` is always 0; `prompt_includes` is empty).
- `GET /prompt/resolved` returns the already-assembled text — cheaper than re-reading and guaranteed in sync with the running session.

The frontend detects `editable: false` and renders a read-only notice + scrollable preview instead of a textarea.

### Known limitations (Phase 6)

- **No diff view between snapshots.** Preview is all-or-nothing; restore overwrites. A visual diff could land in a follow-up.
- **No keyboard shortcut for Save.** Click-only. Trivial to add (`⌘S` listener on the panel) if we miss it.
- **No editing of `prompt_includes` files.** Phase 6 only edits `system.md`. Shared includes (`voice-profile.md`, `anti-patterns.md`, etc.) still require editing on disk.
- **Tab state resets on navigation.** Leaving the agent page and coming back lands on Overview. Acceptable for a localhost tool.

## Settings view (Phase 8b)

The Settings tab is a form-based editor for every field in `packages.core.settings.Settings`. Saves land in `config/local.yaml` as a diff against `Settings()` defaults.

### Endpoints

- `GET /api/settings` — returns `settings` (current state from `components.settings`), `defaults` (`Settings().model_dump()`), `overrides` (the diff drawn by `diff_from_defaults`), `local_yaml_has_managed_header` (sentinel for the overwrite guard), and `paths.local_yaml` / `paths.default_yaml`.
- `GET /api/settings/schema` — returns `Settings.model_json_schema()` with every `$ref` inlined by `dereferenced_schema()`. Lets the frontend read field descriptions, Literal enum choices, and numeric bounds without a client-side resolver.
- `PUT /api/settings` — body `{ settings, accept_overwrite }`. Validates with `Settings.model_validate`, computes `diff_from_defaults`, atomic-writes `config/local.yaml` under a lazy `asyncio.Lock` at `app.state.settings_write_lock`. Responds `{ overrides, bytes, restart_required: true }`.

### Write path guards

1. **Managed-header guard.** If `config/local.yaml` exists and its first non-blank line is not `# Managed by JARVIS Settings — regenerate via Settings view.`, PUT returns `409 Conflict` unless the body carries `accept_overwrite: true`. The GUI surfaces an explicit overwrite dialog before re-submitting with the flag set. Rationale: `local.yaml` can contain user-maintained YAML outside the Settings schema (historical comments, experimental keys, plain-text credentials per ADR-032); first-save would otherwise wipe those silently.
2. **Atomic write.** `packages/core/frontmatter.py:write_atomic` writes to a sibling tmp file then `os.replace`s. A mid-write disk failure leaves the previous file intact.
3. **Validation error normalisation.** `_normalize_validation_errors` walks the dereferenced schema alongside each `loc` tuple from the `ValidationError` and adds `card_loc` + `kind ∈ {"field", "model_validator"}`. Model-validator errors (e.g. `MCPServerSettings` missing `command` on stdio, server name containing `__`) stop at model boundaries — `loc` doesn't point at a field — so the GUI renders them at the enclosing card header instead of inline.

### Frontend architecture

2-pane layout: left nav (`SettingsNav.tsx`) + right panel + sticky footer (`SettingsShell.tsx` → `SettingsFooter` + `OverwriteDialog`). Not a 16-wide tab bar — flat tabs at this scale are a known UX anti-pattern.

- **`SettingsView.tsx`** — fetches both endpoints on mount via `AbortController`, holds `original` (server state) + `working` (user edits) + `errors: SettingsValidationError[]`. `isDirty` is a deep-equality check. Save does `doSave(working, false)`; 409 pops the overwrite dialog; 422 populates errors and auto-scrolls the first erroring section into view.
- **`SettingField.tsx`** — single generic row: label + hover-tooltip (description from schema) + input appropriate for the scalar type. Bool → toggle. Enum → segmented control (from `enumChoices`). Int/float → `<input type="number">`. Lists → one-per-line textarea (trim + drop blanks). String / unknown → `<input type="text">`.
- **`SectionCardError.tsx`** — red banner shown above any panel with `kind: "model_validator"` errors attached at its `card_loc`. Used on `McpServersPanel`'s per-server cards.
- **`ScalarPanel.tsx`** — drives 12 of the 16 sections from a `FieldSpec[]` list declared in `scalarSections.ts`. Paths tab is the only scalar panel with a `PanelWarning` banner (editing paths while JARVIS is running can leave data inconsistent).
- **Custom panels:** `ObsidianPanel` (nested daily_notes + writing with pattern/slip_box sub-sections), `PatternCardsPanel` (nested image_generation), `McpServersPanel` (dict editor with transport-switched field sets, inline rename, DictField for env/headers, "add server" form forcing a transport pick), `FilesystemPanel` (access-rules table + `deny|read|write|read-write` dropdown).
- **`helpers.ts`** — immutable `setAt / getAt / deleteAt` for path-based state updates, `pathsEqual / pathStartsWith / deepEqual`, `fieldErrorAt / cardErrorsAt / sectionHasErrors` for error dispatch, and `schemaAt / fieldType / fieldDescription / enumChoices` for walking the dereferenced JSON schema (including `additionalProperties` for dict-keyed dynamic sections).

### No in-process rebind

Deliberate. `build_session()` captures settings values into `LLMClient`, tool closures, `FilesystemGuard`, `CortexClient`, and MCP subprocesses at startup. Only three code paths re-read `components.settings.*` per request: `outcomes.*`, `summarization.*` (in `bridge.py`), and `paths.prompt_history_dir` (in `agents.py`). Rebinding `components.settings` after PUT would give a false impression of hot-apply for ~95% of fields. Instead PUT always returns `restart_required: true` and the footer banner says so. Per-field hot-apply gating is a follow-up once real usage identifies which toggles users flip most.

### Known limitations (Phase 8b)

- **No file-watching / hot-reload** of external `config/local.yaml` edits. The managed-header guard on PUT helps — a user who hand-edits sees a 409 on their next save — but a GET/PUT cycle in the GUI won't pick up disk-side changes until restart.
- **`evaluation.category_thresholds` (a `dict[str, float]`) is not rendered** — skipped from the scalar-section field list because it's a rare-edit open-keyed map. Edit directly in `config/local.yaml` for now.
- **No diff view before save.** The footer says "unsaved changes" but doesn't list which fields changed. Low priority while the working set is small.
- **No field-level restart-vs-hot-apply classification.** The banner always says "restart required." A follow-up can rebuild specific tool closures for the handful of known hot-applicable fields.

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
