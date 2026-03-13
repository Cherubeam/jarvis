# Developer Agent Roadmap

Phased plan for JARVIS's self-improvement capabilities via the developer agent (`/develop`).

See [ADR-028](decisions.md) for the architectural decision record.

---

## Phase 1 — Foundation (Complete, 2026-03-13)

The developer agent can read its own codebase, make scoped changes, and commit safely.

- **14 tools**: codebase (4), git (6), project write (3), test runner (1)
- **Git sandbox**: branch prefix enforcement (`jarvis-auto/`), `[JARVIS-auto]` commit tags, no push/merge to protected branches
- **Scoped writes**: `.md`, `.yaml`, `.yml` files only, limited to `packages/agents/`, `packages/skills/`, `data/`, `config/`
- **Codebase map**: auto-generated structural overview at `data/codebase_map.md`
- **61 tests** covering all tool modules
- **Max 20 iterations** per invocation

## Phase 2 — Autonomous Operation (Planned)

Enable unattended use and smarter planning.

- **AutoConfirmationHandler**: non-interactive confirmation for CI/scheduled runs
- **Planning phase**: agent generates and validates a plan before executing changes
- **End-to-end integration test**: full agent loop with mocked LLM producing real file changes
- **Expanded file scope**: Python files in agent/skill directories (with AST validation)

## Phase 3 — Continuous Self-Improvement (Planned)

Heartbeat mode for periodic, proactive improvements.

- **Daemon/heartbeat mode**: scheduled self-improvement cycles (e.g., daily)
- **Improvement discovery**: agent identifies stale docs, missing tests, outdated configs
- **PR creation**: auto-creates pull requests for review instead of direct commits
- **Multi-agent coordination**: developer agent can request reviews from other agents

---

*Last updated: 2026-03-13*
