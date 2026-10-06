# JARVIS ↔ Obsidian Integration

How JARVIS connects to an Obsidian vault, the tools it exposes to agents, and the safety mechanisms that govern reads and writes.

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph CLI["JARVIS CLI"]
        ORCH["JarvisAgent<br/>(orchestrator)"]
        DAILY["/daily-summary<br/>(CLI command)"]
        DELEG["Delegate Agents<br/>/obsidian-note-creator<br/>/pattern-language-expert"]
    end

    subgraph SHARED["Shared Tools (all agents)"]
        READ["read_note"]
        SEARCH["search_notes (glob)"]
        DAILYR["read_daily_note"]
        SEMSEARCH["mcp_cortex__search_knowledge<br/>(optional, via MCP)"]
        RECALL["recall_conversations"]
    end

    subgraph SCOPED["Scoped Write Tools (per agent)"]
        CREATE["create_note"]
        EDIT["edit_note"]
        LIST["list_notes_in_dir"]
    end

    subgraph SAFETY["Safety Layer"]
        GUARD["FilesystemGuard<br/>per-path ACLs"]
        DIFF["Diff + Confirm<br/>user approves writes"]
        CALLOUT["[!JARVIS] Callout Engine<br/>append entries to notes"]
    end

    VAULT[("Obsidian Vault<br/>local filesystem<br/><br/>06 – Journals/01 Daily/<br/>05 – Slip-Box/<br/>04 – Resources/06 – Patterns/")]

    CORTEX[["Cortex MCP server<br/>(optional, stdio, shared: true)<br/>semantic vector search"]]

    ORCH --> SHARED
    DAILY --> SHARED
    DELEG --> SHARED
    DELEG --> SCOPED

    SHARED --> GUARD
    SCOPED --> DIFF
    DAILY --> CALLOUT

    GUARD --> VAULT
    DIFF --> GUARD
    CALLOUT --> GUARD

    SEMSEARCH -.MCP (stdio).-> CORTEX
    CORTEX -.reads.-> VAULT
```

---

## ASCII Architecture (for terminals)

```
+---------------------------------------------------------------------+
|                            JARVIS CLI                               |
|                                                                     |
|  +----------------+  +-----------------+  +-----------------------+ |
|  | JarvisAgent    |  | /daily-summary  |  | Delegate Agents       | |
|  | (orchestrator) |  | (CLI command)   |  |                       | |
|  |                |  |                 |  | /obsidian-note-creator| |
|  |                |  | Generates daily |  | /pattern-language-... | |
|  |                |  | journal entries |  |                       | |
|  +-------+--------+  +--------+--------+  +-----------+-----------+ |
|          |                    |                       |             |
+----------|--------------------|-----------------------|-------------+
           |                    |                       |
           v                    v                       v
+---------------------------------------------------------------------+
|                          Tool Layer                                 |
|                                                                     |
|  +-- SHARED TOOLS (all agents) ------+  +-- SCOPED TOOLS ---------+ |
|  |                                   |  |    (per agent)          | |
|  |  read_note            read note   |  |                         | |
|  |  search_notes         glob search |  |  create_note   new file | |
|  |  read_daily_note      today's     |  |  edit_note     replace  | |
|  |  mcp_cortex__search_knowledge     |  |  list_notes_in_dir      | |
|  |  recall_conversations             |  |                         | |
|  |                                   |  |  Scoped to:             | |
|  |                                   |  |    slip_box  -> Slip-Box| |
|  |                                   |  |    patterns  -> Patterns| |
|  |                                   |  |    blog_dir  -> (config)| |
|  +-----------------------------------+  +-------------------------+ |
+-----------|----------------|---------------------|------------------+
            |                |                     |
            v                v                     v
+----------------+  +----------------+  +--------------------------+
| FilesystemGuard|  | Diff + Confirm |  | [!JARVIS] Callout Engine |
|                |  |                |  |                          |
| Per-path ACLs: |  | Shows unified  |  | Finds/creates callout    |
|   READ         |  | diff before    |  | blocks in notes; appends |
|   WRITE        |  | any write      |  | entries with timestamps  |
|   READ_WRITE   |  |                |  | and wikilinks            |
|   DENY         |  | User confirms  |  |                          |
|                |  | with y/n       |  | Used by /daily-summary   |
+--------+-------+  +--------+-------+  +-------------+------------+
         |                   |                        |
         v                   v                        v
+---------------------------------------------------------------------+
|                                                                     |
|                Obsidian Vault (local filesystem)                    |
|                                                                     |
|   06 - Journals/01 Daily/         05 - Slip-Box/                    |
|     `-- 2026/2026-04/               `-- Evergreen notes             |
|           `-- 2026-04-14.md                                         |
|               `-- [!JARVIS]       04 - Resources/06 - Patterns/     |
|                    - summary...     `-- Pattern notes               |
|                                                                     |
+---------------------------------------------------------------------+
            ^
            | MCP (stdio)
+-----------+--------------+
| Cortex MCP server        |
| (optional, shared: true) |
|                          |
| Semantic vector search   |
| over vault content       |
| cortex-mcp (stdio)       |
+--------------------------+
```

---

## Data Flow Summary

This section is the reference for vault safety behaviour; other docs link here.

- **Reading** — Any agent can read notes, search by filename glob, or query semantically via Cortex (MCP). Read tools record a hash of what the agent saw.
- **Writing** — Only explicitly authorized agents can write, and only to their scoped directory. Every write shows a diff for user confirmation first. The diff lists any URL, `[[wikilink]]` or markdown link that differs between the two versions above the diff. A write (or `suggest_improvements` preview) is refused if the note changed on disk since the agent read it, and re-checked after approval, so edits made in Obsidian meanwhile are never reverted.
- **Provenance** — The writer agent adds `prose` to a note's `assist:` frontmatter list when it writes sentences into it (engineering practice P7); other kinds of help are tagged by hand.
- **Daily notes** — `/daily-summary` appends to the `> [!JARVIS]` callout block inside the daily note, summarizing conversations as first-person bullet points with `[[wikilinks]]`.
- **Security** — `FilesystemGuard` (`packages/core/filesystem_access.py`, ADR-021) enforces per-path permissions for every vault tool; no agent can escape its allowed directories. Rules:
  - Configured as `filesystem.access_rules` (a list of `path` + `access`) in `config/local.yaml`; the framework's own default rule is in [`config/default.yaml`](../../config/default.yaml).
  - `access` is one of `deny`, `read`, `write`, `read-write`. `write` alone does not grant reads; use `read-write` for folders an agent both reads and edits.
  - The most specific (deepest) matching path wins; a path no rule covers is denied.
  - Paths are expanded (`~`) and resolved (`..`, symlinks) before matching, so traversal can't sidestep a rule.
- **Semantic search** — When the Cortex MCP server is configured (`mcp.servers.cortex`, `shared: true`), every agent gets `mcp_cortex__search_knowledge` for meaning-based vault queries; otherwise they fall back to glob-based `search_notes`. Setup: [deployment.md](deployment.md#example-cortex-vault-search).

---

## Components

### Shared Tools (available to all agents)

| Tool | Purpose |
|------|---------|
| `read_note` | Read a markdown note's content (50 KB cap) |
| `search_notes` | List notes matching glob patterns, sorted by name or modification time |
| `read_daily_note` | Read today's or a specified date's daily note |
| `mcp_cortex__search_knowledge` | Meaning-based search via the Cortex MCP server (optional) |
| `mcp_cortex__search_conversations` | Meaning-based search across past AI conversations via Cortex (optional, HUB-02) |

### Scoped Write Tools (per agent, declared in `meta.yaml`)

| Tool | Purpose |
|------|---------|
| `create_note` | Create a new note, optionally prepending a template |
| `edit_note` | Replace full note content (with diff confirmation) |
| `list_notes_in_dir` | List notes within the agent's scoped directory |

Currently authorized writers:

- **`obsidian_note_creator`** (`/obsidian-note-creator`) — writes evergreen atomic notes to the **Slip-Box**.
- **`pattern_language_expert`** (`/pattern-language-expert`) — writes pattern notes to the **Patterns** folder.

### Configuration

Obsidian settings go in `config/local.yaml` (keys and defaults: `obsidian:` in [`config/default.yaml`](../../config/default.yaml)). Example with real vault paths:

```yaml
obsidian:
  enabled: true
  vault_path: "/path/to/vault"
  daily_notes:
    path_format: "06 – Journals/01 Daily/%Y/%Y-%m/%Y-%m-%d"
  writing:
    slip_box:
      target_dir: "05 – Slip-Box"
      template_path: "99 – Meta/00 – Templates/(TEMPLATE) Permanent Note"
    patterns:
      target_dir: "04 – Resources/06 – Patterns"

filesystem:
  access_rules:
    - path: "/path/to/vault"
      access: read
    - path: "/path/to/vault/05 – Slip-Box"
      access: read-write
```

Semantic search needs the Cortex MCP server; its config is in [deployment.md](deployment.md#example-cortex-vault-search).

### Source Layout

| Path | Role |
|------|------|
| `packages/integrations/obsidian/vault.py` | Vault config, path validation, read helpers |
| `packages/integrations/obsidian/writer.py` | Write coordinator with diff confirmation |
| `packages/integrations/obsidian/callout.py` | `> [!JARVIS]` callout block parsing/appending |
| `packages/integrations/obsidian/diff.py` | Unified diff computation and formatting |
| `packages/core/tools/vault_read_tools.py` | Shared read tools factory |
| `packages/core/tools/vault_write_tools.py` | Scoped write tools factory |
| `packages/core/filesystem_access.py` | `FilesystemGuard` per-path ACL enforcement |
