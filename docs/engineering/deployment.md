# Setup & Deployment

> How to configure and run Jarvis once it is installed.

Installation (clone, `uv sync`, `.env`, personal context files) is in the
[README's Getting Started section](../../README.md#getting-started). Dev tooling
(uv, ruff, mypy, pre-commit) is in [AGENTS.md](../../AGENTS.md#build-and-test-commands).

---

## Configuration

Configuration lives in two YAML files that are deep-merged at startup:

- **[`config/default.yaml`](../../config/default.yaml)** — committed defaults, with a comment on
  every section. This is the reference for current default values; the docs link to it instead of
  copying it.
- **`config/local.yaml`** — your overrides (gitignored). Write only the keys you want to change:

  ```yaml
  # config/local.yaml
  models:
    default: "openrouter/anthropic/claude-opus-5.5"
  ```

The merged result is validated by the typed `Settings` model in
[`packages/core/settings.py`](../../packages/core/settings.py); every field carries a description,
and the GUI's Settings view edits the same model. Lists replace wholesale when overridden; dicts
merge key by key.

API keys come from `.env`, never from the YAML files. The system prompt is assembled from the
context files (default `data/context/*.md`, identity from `soul.md`), not from config — see
[architecture.md](architecture.md#2-context-builder-packagescorecontext_builderpy). To keep them
elsewhere, see [Context files](#context-files).

---

## Running Jarvis

### CLI

```bash
uv run jarvis                      # or: uv run python -m apps.cli.main
uv run jarvis --agent writer       # run one specialist agent directly
uv run jarvis --model quality      # start on a preset or model id (see below)
```

In a session, type a message and press Enter; `quit` or `exit` ends it, `Ctrl+C` interrupts.
Slash commands are listed in the [README](../../README.md#usage) and per agent in
[agents.md](agents.md#agents).

### GUI

Run commands, authentication and the surfaces it offers are in [gui.md](gui.md#run).

### Docker (not implemented)

There is no container image yet.

---

## Switching Models and Providers

Current defaults and presets are in the `models:` section of
[`config/default.yaml`](../../config/default.yaml); why those models were chosen is in
[models.md](../research/models.md#default-model-recommendation).

Model IDs use the full LiteLLM-routable format with a provider prefix (e.g.
`openrouter/anthropic/claude-sonnet-4.6`). The provider is inferred from the prefix — no code
changes needed. A preset name (`fast`, `balanced`, `quality`) resolves through `models.presets`.

### At Startup (CLI Flag)

```bash
uv run jarvis --model quality                          # a preset
uv run jarvis --model openrouter/openai/gpt-6-luna     # a model id via OpenRouter
uv run jarvis --model anthropic/claude-sonnet-4.6      # direct to Anthropic (needs ANTHROPIC_API_KEY)
uv run jarvis --model auto                             # OpenRouter Auto Router (see below)
```

### Mid-Session (`/model` Command)

```
/model                    # show current model + available presets
/model fast               # switch to a preset
/model openai/gpt-4o      # switch to a model id
/model auto               # switch to the OpenRouter Auto Router
```

### Presets and the Default

Change `models.default` or a preset in `config/local.yaml`. Opt-in heuristic routing
(`routing.enabled`) sends short queries to the `fast` preset, complex ones to `quality` and the
rest to `balanced` (`packages/core/model_router.py`).

### Per-Agent Models

An agent can name its own model with `model:` in its `meta.yaml` (a preset or a model id). It then
always runs on it, whatever the session model is. The `meta.yaml` schema is in
[api.md](api.md#metayaml-schema); which agents are pinned is in [agents.md](agents.md#agents).

### Per-Model Request Fields

`models.extra_body` sends extra fields in the request body for one model, on every call made with
it (chat, tool loop, summarization, nested tool calls). Keys are full model IDs; values go to the
provider unchanged. The default config uses it to switch off Qwen 3.5 Flash's thinking, which
OpenRouter otherwise returns as the answer text (see `models.extra_body` in
[`config/default.yaml`](../../config/default.yaml)). See OpenRouter's reasoning-tokens guide for
the `reasoning` fields.

### OpenRouter Auto Router (opt-in)

Let OpenRouter pick the model per turn instead of `models.default` and JARVIS's own routing: set
`models.auto_router.enabled: true` (plus `cost_tier` and `excluded_models`, documented in
[`config/default.yaml`](../../config/default.yaml)), or per session `--model auto` / `/model auto`.

Each turn shows which model answered (`[Model: auto → deepseek/…]`) and its exact billed cost; the
conversation log records it under `metadata.served_models`. Auto turns don't stream. Agents with
`model:` in `meta.yaml` keep their model. Settings saved on OpenRouter's routing page apply too;
per-request settings win unless "prevent overrides" is on there. Restart after changing the config.
Benchmark results and trade-offs: [models.md](../research/models.md#auto-router-mode-opt-in);
decision: ADR-036.

### Model Selection Order

An agent's own `model:` in `meta.yaml` always wins for that agent. Everything else runs on the
session model, chosen in this order:

1. `--model` at startup, or `/model` mid-session
2. `models.auto_router.enabled` → the Auto Router
3. `models.default`, adjusted per turn by heuristic routing if `routing.enabled`

How this is wired (`StreamHandler.using_model()`, `model_pinned`) is in
[architecture.md](architecture.md#model-selection).

### Using Different Providers

1. Add the provider's API key to `.env`:
   ```
   OPENROUTER_API_KEY=your_key_here    # OpenRouter (default)
   ANTHROPIC_API_KEY=your_key_here     # Direct Anthropic
   OPENAI_API_KEY=your_key_here        # Direct OpenAI
   GOOGLE_API_KEY=your_key_here        # Direct Google
   ```
2. Use the corresponding model prefix, e.g. `--model anthropic/claude-sonnet-4.6`.

Only the API key for the resolved provider is required.

---

## Connecting MCP Servers

JARVIS connects to external [MCP](https://modelcontextprotocol.io/) servers and uses their tools
alongside native ones. Adding or removing a server is a config-only change. How the client works
internally is in [architecture.md](architecture.md#6c-mcp-client-integration-packagesintegrationsmcp).

**Step 1: Enable MCP and declare servers** in `config/local.yaml`:

```yaml
mcp:
  enabled: true
  servers:
    # Local server via stdio
    filesystem:
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/Documents"]
      tool_group: fs_tools           # name used in agent meta.yaml
      timeout_seconds: 30            # per-call timeout (default: 30)

    # Remote server via SSE
    github:
      transport: sse
      url: "http://localhost:3001/sse"
      headers:
        Authorization: "Bearer your-token-here"
      tool_group: github_tools

    # Remote server via streamable HTTP
    my_api:
      transport: streamable_http
      url: "http://localhost:8080/mcp"
      tool_group: my_api_tools
```

Each server key (e.g. `filesystem`) is used for tool namespacing — MCP tool `read_file` from server
`filesystem` becomes `mcp_filesystem__read_file` in JARVIS, so server names must not contain `__`.
The `tool_group` field (defaults to the server key if omitted) is the name you reference from agents.

**Step 2: Assign tool groups to agents.** Add the `tool_group` name to the agent's `meta.yaml`:

```yaml
# packages/agents/researcher/meta.yaml
tools:
  - web_tools
  - fs_tools        # MCP server tool group
```

Or mark the server `shared: true`: its tools then skip the tool group and go to every agent,
including the JARVIS orchestrator, automatically.

**Step 3: Restart JARVIS.** The startup output reports what loaded:

```
[MCP] 5 tool(s) from 2 server(s).
```

**Giving an opt-in MCP tool group to the JARVIS orchestrator:** the orchestrator gets the shared
tools plus a fixed list of groups (`jarvis_tools` in `build_session()`,
[`apps/cli/session_factory.py`](../../apps/cli/session_factory.py)). Either mark the server
`shared: true`, or add the group to that list.

**Transport reference:**

| Transport | Required fields | Use case |
|---|---|---|
| `stdio` | `command`, `args` (optional) | Local servers launched as child processes |
| `sse` | `url` | Remote servers with Server-Sent Events |
| `streamable_http` | `url` | Remote servers with HTTP streaming |

Optional fields for all transports: `tool_group`, `shared`, `timeout_seconds`; `headers` (SSE/HTTP
only); `env`, `cwd` (stdio only). The schema with descriptions is `MCPServerSettings` in
[`packages/core/settings.py`](../../packages/core/settings.py).

### Example: Cortex vault search

Semantic search over the Obsidian vault comes from the Cortex MCP server (`cherubeam/cortex`,
`HUB-01`, ADR-034). Run the Cortex service (`uv run cortex` in the Cortex repo) and declare it as a
shared server:

```yaml
mcp:
  enabled: true
  servers:
    cortex:
      transport: stdio
      tool_group: cortex
      shared: true          # every agent gets the tools automatically
      command: uv
      args: ["--directory", "/path/to/cortex", "run", "cortex-mcp"]
```

Tools arrive as `mcp_cortex__search_knowledge` and `mcp_cortex__index_status`. When the service is
down, the tools return an actionable error and agents fall back to `search_notes`.

### Troubleshooting MCP

- If a server fails to connect at startup, JARVIS logs a warning and continues — other servers and
  native tools are unaffected.
- If a tool call fails at runtime, the error is returned to the LLM as tool output so it can adapt.
- stdio servers need the command on your `PATH` (e.g. `npx` requires Node.js).
- To verify which tools loaded, check the `[MCP]` line in the startup output.

---

## Things 3

JARVIS reads your Inbox, Today and Upcoming tasks from Things 3 (macOS) through a Shortcut you build once. It never opens Things' database, so no Full Disk Access is needed (why: ADR-037; how it works: [architecture.md](architecture.md#5-task-sync-packagesintegrationsthings3)). It's read-only.

### Build the `JARVIS Things Export` Shortcut

In the Shortcuts app, create a shortcut named exactly **`JARVIS Things Export`**. German labels in brackets.

1. **Inbox loop**
   - **Find Items** ("Objekte suchen", from Things). Filters: **Is Inbox** is true, **Status** is Open ("Offen").
   - **Repeat with Each** ("Mit jedem wiederholen") over those items. Inside the loop, a **Dictionary** ("Wörterbuch") with Text entries; the value is **Repeat Item** ("Wiederholungsobjekt"), then click the token to pick the field:
     `id` → ID, `title` → Title, `notes` → Notes, `startDate` → Start Date, `deadline` → Deadline, `tags` → Tags, `parent` → Parent ("Übergeordnet").
2. **Scheduled loop**: duplicate the first loop ("Duplizieren"), and in the copy's Find Items replace the Inbox filter with **Start Date** is after ("ist nach") **01.01.2000**, keeping Status is Open.
3. **Output**: after both loops, an outer **Dictionary** with two List ("Liste") entries: `inbox` → the first loop's **Repeat Results** ("Wiederholungsergebnisse"), `scheduled` → the second loop's. Then **Stop and Output** ("Stoppen und ausgeben") with that Dictionary.
4. Run it once by hand and allow any permission prompt; the command line can't show it later.

To check it:

```bash
shortcuts run "JARVIS Things Export" --output-type public.json -o /tmp/things.json && head -c 300 /tmp/things.json
```

If Things can't be read, startup logs `Things tasks not refreshed: <reason>` and keeps the previous `tasks.md`. Shortcuts needs a logged-in macOS session.

## File Structure

See [architecture.md](architecture.md#file-structure) for the project structure.

---

## Data Management

### Conversation Logs

Saved to `data/conversations/YYYY/YYYY-MM-DD_HH-MM-SS.json` (by year). **Gitignored** — they
contain sensitive data. The folder is the `paths.conversations_dir` setting (an absolute path in
`config/local.yaml` moves it out of the repo); the import, backfill and analysis scripts in
`scripts/` default to the same `paths.*` settings.

### Context files

The context files live in `paths.context_dir` under the names in `paths.context_files`; the
Things tasks file is written to `paths.tasks_file` (defaults in
[`config/default.yaml`](../../config/default.yaml)). Relative paths are joined onto the project
root; absolute paths work. To keep the context files in an Obsidian vault folder, with the
memory notes in a subfolder, and the generated tasks file out of the vault:

```yaml
# config/local.yaml
paths:
  context_dir: "/path/to/vault/JARVIS"
  context_files:
    soul: "JARVIS Soul.md"
    personal: "Memory/Personal Context.md"
    professional: "Memory/Professional Context.md"
    preferences: "Memory/Preferences.md"
    focus: "Memory/Current Focus.md"
    reading: "Memory/Reading Profile.md"
  tasks_file: "/Users/<you>/Library/Caches/JARVIS/tasks.md"
```

Frontmatter on these notes is stripped before it reaches the prompt, and a missing file is
skipped. Invalid frontmatter stays in the prompt and logs a warning naming the file; quote
values that contain `: `. Changes need a restart.

**Memory frontmatter** ([ADR-041](../product/decisions.md#adr-041-where-each-kind-of-data-lives)):
every note records when it was last true and where it came from, so later imports can tell
newer facts from older ones. Fields follow the vault's own conventions:

```yaml
---
created: 2026-04-09
updated: 2026-04-09          # when the content was last true; imports compare against this
aliases:
tags:
  - type/jarvis-memory        # type/jarvis-soul for the soul note
  - project/jarvis
type: jarvis-memory
memory-section: professional  # key in paths.context_files
summary: "One line; quote it if it contains ': '"
source:                       # marco | jarvis | claude-export | readwise | …
  - marco
  - claude-export
review-by: 2026-10-09         # past this date the note is due for a review
assist:                       # P7: present when the note holds AI-written prose
  - prose
---
```

### Importing Claude memory

`scripts/import_claude_memory.py <export folder>` reads a Claude data export (the unzipped
folder with `memories/`, 2026-09 format) and proposes changes to the memory notes; it never
overwrites them ([ADR-041](../product/decisions.md#adr-041-where-each-kind-of-data-lives)).

```bash
uv run python scripts/import_claude_memory.py ~/Downloads/claude-export --dry-run   # show proposals only
uv run python scripts/import_claude_memory.py ~/Downloads/claude-export             # review and apply
```

- Facts about you are routed to one note each (profile, people and areas → professional;
  communication → preferences; recent work → focus; other topics → personal; table in
  `packages/core/importers/claude_memory.py`). Project memories wait for the project mapping;
  the soul and the reading profile are never touched.
- A model (`models.presets.quality`, override with `--model`) drafts add/update proposals per
  note and drops facts the note already covers. A fact older than the note's `updated` date is
  shown as a conflict and never applied.
- Each proposal asks `[y]es / [e]dit / [n]o / [q]uit`; `e` opens the proposed text for editing
  (paste works; line breaks are collapsed). Applying re-reads the note, changes only the lines
  involved, sets `updated`, adds `claude-export` to `source` and `prose` to `assist`.
- The raw export is copied once to `<paths.imports_dir>/claude/<export date>/export/` (without
  login history and account data), and every decision is appended to `memory-decisions.jsonl`
  next to it. Point `paths.imports_dir` at the data home in `config/local.yaml`.

### Backup Strategy

**What to back up:**
- your context files (`paths.context_dir`; default `data/context/*.md`)
- `config/local.yaml` (your configuration)
- `data/conversations/` and `data/outcomes/` (optional, if you want history)

**How to back up:**
```bash
# Simple: copy the data directory
cp -r data/ ~/backups/jarvis-data-$(date +%Y%m%d)/

# Better: encrypted backup of data and config
tar -czf - data/ config/ | gpg -c > jarvis-backup-$(date +%Y%m%d).tar.gz.gpg
```

---

## Troubleshooting

#### "OPENROUTER_API_KEY not found"

Create `.env` with your API key:
```bash
echo "OPENROUTER_API_KEY=sk-or-v1-..." > .env
```

#### "Import litellm could not be resolved" / `ModuleNotFoundError`

Install dependencies with `uv sync`. For `No module named 'apps'` on macOS, see the
[README troubleshooting note](../../README.md#troubleshooting).

#### Missing context files

`data/context/` is not tracked in git. Create the files listed in the
[README](../../README.md#installation):
```bash
mkdir -p data/context
echo "# About Me" > data/context/personal_context.md
echo "# Professional Background" > data/context/professional_context.md
echo "# Preferences" > data/context/preferences.md
echo "# Current Focus" > data/context/current_focus.md
```

#### Slow responses or high costs

Switch model or preset (see [Switching Models and Providers](#switching-models-and-providers));
latency and cost per model are in [models.md](../research/models.md#benchmark-results). Long
sessions can turn on history summarization (`summarization.enabled`, see
[architecture.md](architecture.md#history-summarization)).

---

## Security Best Practices

- **API keys**: store in `.env` (gitignored); never hardcode or commit them.
- **Conversation logs**: contain personal data; gitignored by default; prefer encrypted backups and
  review before sharing.
- **Context files**: may contain personal information; think before committing them anywhere.
- **GUI**: token + origin allowlist; see [gui.md](gui.md#authentication) before binding past
  loopback with `--host`.

---

## Updates & Maintenance

```bash
git pull origin main
uv sync                  # install the locked dependencies
uv sync --upgrade        # or: update all dependencies
```

Read [changelog.md](../changelog.md) for breaking changes and back up `data/` before updating.

---

## Reporting Bugs

Open an issue at [github.com/Cherubeam/jarvis/issues](https://github.com/Cherubeam/jarvis/issues)
with the Python version, OS, steps to reproduce, error messages and relevant config (redact API
keys).

---

*Last updated: 2026-09-27*
