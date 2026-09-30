# Developer Agent Roadmap — `DEV`

> **Retired 2026-09-30 per [ADR-039](decisions.md#adr-039-retire-the-developer-agent)**: the developer agent and
> its tools were deleted (no recorded use, escapable write scope). Coding on
> JARVIS happens in Claude Code. DEV-01 below is history; DEV-02/DEV-03 are
> kept as **trigger-gated ideas**, not planned work. Build a thin dispatcher
> from scratch (not by restoring DEV-01, restore point tag `v0.27.0`) only if
> the reversal trigger in ADR-039 fires.

Milestone plan for JARVIS's self-improvement capabilities via the developer agent (`/develop`).

Uses the initiative/milestone naming scheme from [ADR-033](decisions.md#adr-033-initiative--milestone-naming-scheme): this is initiative **`DEV`**; milestone IDs (`DEV-01`…) are stable and never renumbered. See [ADR-028](decisions.md) for the architectural decision record. *(Legacy: this doc previously used "Phase 1–3"; historical changelog entries keep that label.)*

> **Rescoped 2026-08-19 per [ADR-034](decisions.md#adr-034-context-hub-positioning--rent-coding-harnesses-own-the-context)**: coding harnesses (Claude Code, Codex, OpenCode) are commodities; JARVIS does not compete with them. `DEV-02`/`DEV-03` were unshipped and are rewritten below from "build our own autonomous coding harness" to "**JARVIS decides *what* to improve and delegates execution** to an external harness." The original specs (AutoConfirmationHandler, planning phase, expanded Python file scope with AST validation, in-house heartbeat execution) are superseded. `DEV-01` stays as shipped — its small tool set remains the right size for tiny scoped edits.

---

## DEV-01 — Foundation

*Legacy: Phase 1*

**Status**: 🗑️ Retired 2026-09-30 ([ADR-039](decisions.md#adr-039-retire-the-developer-agent)) — shipped 2026-03-13

The developer agent can read its own codebase, make scoped changes, and commit safely.

- **14 tools**: codebase (4), git (6), project write (3), test runner (1)
- **Git sandbox**: branch prefix enforcement (`jarvis-auto/`), `[JARVIS-auto]` commit tags, no push/merge to protected branches
- **Scoped writes**: `.md`, `.yaml`, `.yml` files only, limited to `packages/agents/`, `packages/skills/`, `data/`, `config/`
- **Codebase map**: auto-generated structural overview at `data/codebase_map.md`
- **61 tests** covering all tool modules
- **Max 20 iterations** per invocation

## DEV-02 — Delegated Execution

*Legacy: Phase 2 "Autonomous Operation" — rescoped 2026-08-19 per ADR-034*

**Status**: 💤 Trigger-gated idea (ADR-039) — not planned

`/develop` becomes a thin dispatcher: JARVIS frames the task and supplies context; an external coding harness executes it.

- **Harness dispatch**: invoke Claude Code headless (`claude -p`) / Agent SDK with a JARVIS-composed prompt (task framing, relevant context, acceptance criteria); capture the result and surface it in the conversation
- **Task composition**: reuse the `AGENTS.md` conventions (the codebase map was deleted with DEV-01) so the delegated harness lands changes that follow house rules (branch naming, commit format, `uv`-only)
- ~~**Tiny-edit fast path**: keep the DEV-01 tool set for small scoped edits~~ — dropped by ADR-039; the DEV-01 tools no longer exist
- **End-to-end integration test**: dispatch a mocked harness run and assert the composed prompt, sandbox flags, and result capture

> **Dropped from the original spec**: AutoConfirmationHandler (it had in fact
> shipped with DEV-01 behind `--auto-confirm`; deleted by ADR-039) (headless-safe
> confirmation for JARVIS's own jobs is `AON-02`'s `PolicyConfirmationHandler`;
> confirmation *inside* delegated coding runs is the harness's permission
> system, not ours), planning phase, and expanded Python file scope with AST
> validation (the harness already does both better).

## DEV-03 — Continuous Self-Improvement

*Legacy: Phase 3 — rescoped 2026-08-19 per ADR-034*

**Status**: 💤 Trigger-gated idea (ADR-039) — not planned

Periodic, proactive improvement — JARVIS discovers, the harness executes, a human reviews the PR.

- **Improvement discovery**: a scheduled read-only job (an `AON-02` `jarvis run-job` consumer) identifies stale docs, missing tests, outdated configs
- **Delegated fixes**: each finding becomes a DEV-02 dispatch; the harness opens a PR for human review — JARVIS never merges
- **Review routing**: findings and PR links land in the `AON-02` approval inbox / Telegram digest
- **Multi-agent coordination**: developer agent can request reviews from other JARVIS agents (e.g., docs review by the writer)

> **Cross-initiative note**: depends on `AON` foundations — the shared
> `TurnRunner` + headless session factory (`AON-02`) and the budget/safety
> rails (`AON-01`). Sequence `DEV-03` after those land. The in-house
> daemon/heartbeat *execution* engine from the original spec is superseded:
> scheduling stays in launchd, execution in the external harness.

---

*Last updated: 2026-09-30*
