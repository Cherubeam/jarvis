# Developer Agent Roadmap — `DEV`

Milestone plan for JARVIS's self-improvement capabilities via the developer agent (`/develop`).

Uses the initiative/milestone naming scheme from [ADR-033](decisions.md#adr-033-initiative--milestone-naming-scheme): this is initiative **`DEV`**; milestone IDs (`DEV-01`…) are stable and never renumbered. See [ADR-028](decisions.md) for the architectural decision record. *(Legacy: this doc previously used "Phase 1–3"; historical changelog entries keep that label.)*

---

## DEV-01 — Foundation

*Legacy: Phase 1*

**Status**: ✅ Complete (2026-03-13)

The developer agent can read its own codebase, make scoped changes, and commit safely.

- **14 tools**: codebase (4), git (6), project write (3), test runner (1)
- **Git sandbox**: branch prefix enforcement (`jarvis-auto/`), `[JARVIS-auto]` commit tags, no push/merge to protected branches
- **Scoped writes**: `.md`, `.yaml`, `.yml` files only, limited to `packages/agents/`, `packages/skills/`, `data/`, `config/`
- **Codebase map**: auto-generated structural overview at `data/codebase_map.md`
- **61 tests** covering all tool modules
- **Max 20 iterations** per invocation

## DEV-02 — Autonomous Operation

*Legacy: Phase 2*

**Status**: 📋 Planned

Enable unattended use and smarter planning.

- **AutoConfirmationHandler**: non-interactive confirmation for CI/scheduled runs
- **Planning phase**: agent generates and validates a plan before executing changes
- **End-to-end integration test**: full agent loop with mocked LLM producing real file changes
- **Expanded file scope**: Python files in agent/skill directories (with AST validation)

> **Cross-initiative note**: the AutoConfirmationHandler overlaps `AON-02`'s
> `PolicyConfirmationHandler` (both solve headless-safe confirmation). Build it
> once in `packages/core` and share it — don't duplicate.

## DEV-03 — Continuous Self-Improvement

*Legacy: Phase 3*

**Status**: 📋 Planned

Heartbeat mode for periodic, proactive improvements.

- **Daemon/heartbeat mode**: scheduled self-improvement cycles (e.g., daily)
- **Improvement discovery**: agent identifies stale docs, missing tests, outdated configs
- **PR creation**: auto-creates pull requests for review instead of direct commits
- **Multi-agent coordination**: developer agent can request reviews from other agents

> **Cross-initiative note**: the daemon/heartbeat and unattended-safety work
> here depends on `AON` foundations — the shared `TurnRunner` + headless
> session factory (`AON-02`) and the `FilesystemGuard`/budget/sandbox rails
> (`AON-01`, `AON-04`). Sequence `DEV-03` after those land.

---

*Last updated: 2026-07-05*
