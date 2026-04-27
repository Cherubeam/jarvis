# JARVIS GUI Build Wave — Retrospective (2026-04)

_2026-04-19 → 2026-04-27 · 19 PRs · 5 retroactive GitHub releases (v0.16.0 → v0.20.0)_

## What shipped

- **v0.16.0** (`f8d1e0d`, 2026-04-19) — Outcome tracking + prompt-include resolver: `track_recommendation`, `/outcomes` review CLI, `recall_outcomes`, `frontmatter.py`, `date_utils.py`, `.md.example` fallback. Pre-GUI infrastructure.
- **v0.17.0** (`5bc52c5`, 2026-04-21) — GUI Foundation, Phases 1–4 (PRs #1, #2, #4, #5): FastAPI + WS + React Chat shell, Conversations browser, Home/Dashboard, Sidebar Timeline mode. The pivotal extraction here was `apps/cli/session_factory.build_session()` at SHA `619f732`.
- **v0.18.0** (`236e1a2`, 2026-04-22) — Dev-tooling hardening (PRs #6–#10): ruff lint+format gate then mypy ratcheted across four PRs to `strict=true`, with `platform=linux` pinned.
- **v0.19.0** (`309033a`, 2026-04-24) — GUI Productivity, Phases 5–7 (PRs #11–#13): Agents grid + Detail with 14-day cost sparkline, Prompt/Versions/Stats/Context tabs with snapshot history, Outcomes view + `/daily-summary` GUI handler.
- **v0.20.0** (`8b7038a`, 2026-04-27) — GUI Configuration, Phase 8 + follow-ups (PRs #14–#17): pydantic-settings migration, 16-section Settings editor, field-level hot-apply gating, prompt-include editor with shared-write modal.
- **Release wave** (PRs #18–#19, 2026-04-27) — `docs/v0.20.0-refresh` rewrites README/roadmap/gui.md/api.md/architecture.md/testing.md, then `release/v0.20.0` bumps `pyproject.toml`. Tags 0.16–0.19 land retroactively against past SHAs.

Tests went from 12 GUI / 1888 total at end of Phase 1 to **2174 total** at v0.20.0.

## What worked well

**1. One PR per phase, never stacked.** Each phase got its own `feat/jarvis-gui-phase-N` branch, opened against `main` *after* the previous phase merged. Blast radius stayed small: a Phase 6 regression couldn't leak into Phase 7's review. The merged-PR list in `gh pr list` reads cleanly across PRs #1, #2, #4, #5, #11, #12, #13, #14, #15, #16, #17 — every phase boundary was a single rebase-merge commit. This is the single biggest reason the wave didn't slip.

**2. `build_session()` extraction made CLI/GUI parity free.** `apps/cli/session_factory.py` is a 596-line dataclass-and-builder factory that takes an `args`/`Settings`/`ConfirmationHandler` triple and returns a `SessionComponents` bag (`stream_handler`, `logger`, `active_agent`, `tool_groups`, `mcp_manager`, …). The CLI passes `CLIConfirmationHandler()`; the GUI passes `WebConfirmationHandler()` per turn. Net effect: zero forked startup logic across two clients. New tools (RAG, Cortex, Things 3, Readwise, MCP) wire up once and both surfaces inherit them. If we'd not done this in Phase 1, every later phase would have paid the divergence tax.

**3. Plan agent's critical-review section caught real bugs before merge.** The pattern (now in `.claude/CLAUDE.md`) is: write the plan, spawn a Plan agent, append findings as `## Critical Review` to the same plan file, then ExitPlanMode. Concrete saves:
   - **Phase 7 `_daily_summary_turn_sync` `on_chunk=None`.** The Plan agent flagged that setting `handler.on_chunk` in the GUI path would intercept events mid-stream and stop chunks from reaching `on_event`. Now visible at `apps/gui/server/bridge.py:295` — the function scopes `max_tokens=4096` and `on_chunk=None` for the call and restores both afterwards.
   - **Phase 6 `jarvis_home()` helper** dropped after the Plan agent caught that `~/.jarvis/` doesn't exist on disk.
   - **Release plan B1**: v0.18.0 commit count was 8 in the plan, actually 13. **I8**: `app.py` deletion was misfiled to v0.18.0; actual SHA `910e93d` falls inside v0.20.0's range. **S5**: `gh release create` auto-flips "Latest" to highest semver — fixed by passing `--latest=false` for retroactive releases.

**4. Test density stayed roughly proportional to surface area.** PR-by-PR test deltas: Phase 2 +29, Phase 3 +18, Phase 5 +23, Phase 6 +54, Phase 7 +43, PR-8b +30, PR #16 +16, PR #17 +29. The new `tests/unit/gui/` tree mirrors the route structure. Tests stay where backend code lives (route + helper), not as integration tests in a separate pyramid.

**5. `gh pr merge --rebase` enforced via repo settings.** Documented in PR #3 (the third PR ever in this wave was a docs PR codifying the merge command). Repo settings disable merge-commits and squash, so there's no "click the wrong button" failure mode. The whole `git log --oneline v0.15.0..v0.20.0` reads as a clean linear history.

**6. Hot-apply via curated whitelist, not pydantic metadata.** When PR-8b shipped with `restart_required: true` unconditionally, the obvious "fix" was a `Field(metadata={"hot_apply": True})` annotation. PR #16 deliberately rejected that for `HOT_APPLY_PATHS = {"summarization", "paths.prompt_history_dir"}` in `packages/core/settings.py`. Reasoning logged in ADR-032's third addendum: schema metadata invites drift the moment a new `build_session()` closure captures a value — grep-then-whitelist forces review on every addition. The accompanying rebind contract (`PUT /api/settings` rebinds `session.components.settings`) is what makes hot-apply *actually take effect* — without the rebind, whitelisted fields still need restart because routes read off the in-memory `Settings`, not YAML.

## What we'd do differently

**1. Document the "no stacked branches" rule earlier.** Phase 3 was branched off unmerged Phase 2 (`feat/jarvis-gui-phase-3` from `feat/jarvis-gui-phase-2` HEAD). When PR #2 merged via rebase, the SHAs Phase 3 referenced ceased to exist and the rebase-merge surfaced phantom conflicts on files Phase 3 never touched. Cost: real session time, plus a `git reset --hard` and re-branch from new `main`. The rule (`feedback_no_stacked_branches.md`) was written *after* the incident. Branch-from-`main` should be a checklist item printed at the start of every new feature, not learned via cost.

**2. The Phase-1 file_id bugfix should have been its own PR.** `bc33b4d` "fix(gui): session_meta advertises the real on-disk conversation path" landed in PR #2 (Phase 2), not PR #1 (Phase 1) — even though it fixes Phase 1 behavior. Acceptable because both were in the same review window, but the cleaner pattern is: noticed-while-writing-Phase-2 → small PR back to `main` first → rebase Phase 2 on top. Otherwise the changelog lies about which release fixed what.

**3. PR-8b's `restart_required: true` punt was the right call, but the gap was wider than expected.** PR-8b shipped 2026-04-24 13:16Z; PR #16 (hot-apply gating) merged 2026-04-24 19:44Z — same day, six hours later. So the punt held for one afternoon. That's defensible. What we'd change: surface the punt in the changelog of the PR that creates it, with an explicit follow-up issue. PR-8b's changelog entry didn't say "hot-apply deliberately deferred — opening follow-up"; that context only lived in the plan. Future readers reading the diff in isolation would see a confusing "always restart" footer with no explanation of why.

**4. Phase 7 live-browser verification was skipped, then non-reproducible.** From the GUI roadmap memory: *"the local GUI server hung past 'Web search + fetch loaded' for 5+ min"* during Phase 7 review. Diagnosis on 2026-04-24 found it non-reproducible; the visible last log line lagged real execution because `Rich.console.print` is block-buffered when stdout isn't a TTY. Lesson: when a verification fails *and* you can't reproduce, write down the exact env (PID list, env vars, MCP processes) before moving on. Future-you will reach for that artifact. Concrete fix already known: `PYTHONUNBUFFERED=1 uv run python -m apps.gui.main --no-browser --log-level info` — codify this as the Phase-N verification command.

**5. Frontend tests stayed deferred for the entire wave.** From `project_jarvis_gui_roadmap.md` non-goals: *"Frontend tests (Vitest/Playwright) — deferred until a phase needs them."* In practice, every interactive surface (Quick Start race in Phase 3, tab-switch refresh in Phase 6, modal-confirm gate in Phase 17, footer-message branching in Phase 16) was hand-tested. That worked because the user was the only operator. The cost is invisible until a regression slips in: e.g. the Phase 3 `wsReady` gate is one boolean away from a re-broken WS-open race, and nothing automated would catch it. **The next interactive sub-loop work (delegate sub-loops on the roadmap) should not start without a one-day Vitest setup-PR first.**

## Process insights — now codified

- **Doc PR before release commit.** PR #18 (`docs/v0.20.0-refresh`) merged before PR #19 (`release/v0.20.0`). If a slice boundary turned out wrong, we'd re-tag without rolling back a `pyproject.toml` bump. Pattern lives in `feedback_release_workflow.md`.
- **5-tag retroactive slicing as the default for big waves.** A single `v0.16.0 = everything` would have flattened 12 days into one entry. The chosen split — Foundation / Tooling / Productivity / Configuration — gives each tag a coherent story. Boundaries fall *between* PRs, never mid-PR; verified in §2 sanity checks of `jarvis-docs-and-release-plan.md`.
- **Plan-agent critical review appended to the plan file**, not chat. Now mandated by `.claude/CLAUDE.md` project instructions. Means future-you (or a different session) reading the plan file gets the same caveats the planning session got. The plan files for Phases 5, 6, 7, 8b, the includes editor, and the release plan all carry `## Critical Review` sections.
- **Memory hygiene cadence.** This wave produced 12 active memory files (now consolidating to 9). Trigger for hygiene: when the index file passes ~15 entries, or when two entries demonstrably overlap (the "stacked branches" rule duplicated content in two places before consolidation). Roughly: once per release wave, not on a calendar.

## For the next wave

**1. Do the Vitest setup PR before any interactive sub-loop work.** Don't add Vitest in the same PR as the first delegate sub-loop — that PR will already be large. A standalone "add Vitest harness + 3 smoke tests for existing surfaces" PR (target: ~200 LOC, 1 day) gives every later PR a place to drop tests. Without this, the next interactive feature will repeat the Phase 3 wsReady-style verification gap.

**2. Print the verification command in every phase plan.** A line like `verification: PYTHONUNBUFFERED=1 uv run python -m apps.gui.main --no-browser --log-level info` at the top of the plan file. Hand-tested phases (4, 5 partly, 7) all skipped this; phases that wrote it down (17 — "Live browser-verified: shared status badge, affects bar, modal confirm + cancel-without-write, hidden tab on simplifier") didn't have post-merge regressions. Cheap habit, big payoff.

**3. Open the follow-up issue in the same session as the punt.** When PR-8b deliberately punted hot-apply with `restart_required: true`, the follow-up was tracked in memory + in ADR-032 but not as a GitHub issue. PR #16's changelog entry is the only durable record that the punt was intentional. Next time: file the follow-up issue *during* the punt PR, link both directions, mention it in the changelog. Cost is 60 seconds; benefit is anyone reading the repo six months later understands the gap.
