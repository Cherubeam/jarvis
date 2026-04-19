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
