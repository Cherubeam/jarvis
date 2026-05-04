# Mutation Testing Report

> Audit of test suite quality across the JARVIS codebase.

**Current**: 2026-05-02 (Linux CI — GUI server + typed settings audit, three runs: `25217994644` baseline / `25219263045` first pass / `25249193229` second pass)
**Previous**: 2026-04-13 (Linux CI, `packages/core/` audit, workflow run `24336325780`)
**Older baselines**: 2026-04-11 (Linux CI), 2026-04-03 (macOS, historical)
**Tool**: mutmut 3.5.0
**Python**: 3.13.5
**Environment**: GitHub Actions `ubuntu-latest` — see [`.github/workflows/mutation.yml`](../../.github/workflows/mutation.yml)

---

## 2026-05-04 — GUI server + typed settings (seventh pass — daily-summary helper)

Workflow run [`25303616666`](https://github.com/Cherubeam/jarvis/actions/runs/25303616666) on branch `test/gui-mutation-daily-summary`. Targeted `bridge._run_daily_summary_turn` (110 survivors after pass 6) using the strict-key-sweep + exact-value patterns established in PRs #29, #30. Plus a small pragma sweep on `bridge.py` `logger.exception`/`debug` message strings (provably equivalent — tests don't capture log output).

### Baseline → ... → seventh

| Status | Baseline | 1st | 2nd | 3rd | 4th | 5th | 6th | 7th (`25303616666`) | Δ vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 🎉 Killed | 1,843 | 2,390 | 2,424 | 2,475 | 2,508 | 2,535 | 2,681 | **2,734** | **+891** |
| 🙁 Survived | 1,175 | 628 | 594 | 543 | 510 | 455 | 502 | **422** | **−753 (−64%)** |
| 🫥 No tests | 339 | 339 | 339 | 339 | 339 | 339 | 146 | **146** | **−193 (−57%)** |
| ⏰ Timeout | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 0 |
| **Total mutants** | **3,359** | **3,359** | **3,359** | **3,359** | **3,359** | **3,331** | **3,331** | **3,304** | −55 (pragmas) |
| **Unkilled (S+N)** | **1,514** | **967** | **933** | **882** | **849** | **794** | **648** | **568** | **−946 (−62.5%)** |

**Kill rate on testable mutants** (`killed / 3,158`): **86.57% (+2.4pp this pass; +25.6pp total).**

### Per-helper kills (seventh-pass focus, all in bridge.py)

| Helper | Pass 6 | Pass 7 | Δ this pass | What killed it |
|---|---:|---:|---:|---|
| `bridge._run_daily_summary_turn` | 110 | **45** | **−65 (−59%)** | Strict-key sweep on all 7 emitted event types (user / thinking_start/end / text + stats sub-keys / system / totals / turn_finished) + per-error-path checks on 5 failure modes; logger.add_message exact-kwarg lock-in; turn_id / system-event-id format pinning; session.confirmation `is None` cleanup; totals int/float coercion |
| `bridge._mark_current_dirty` | 4 | **0** | **−4 (−100%)** | Pragma'd the `mark_dirty failed` debug log message |
| `bridge.run_turn` | 44 | **37** | **−7 (−16%)** | Pragma bonus: `Turn failed` exception log + dual `logger.save() failed` log lines |
| `bridge._run_delegation` | 80 | **76** | **−4 (−5%)** | Pragma bonus: `Delegate run failed` exception log |
| `bridge._run_one_turn` | 7 | 7 | 0 | residue (non-summarization branch) |
| `bridge._daily_summary_turn_sync` | 2 | 2 | 0 | residue |
| `bridge._find_deferred_handler` | 1 | 1 | 0 | residue |
| **TOTAL bridge** | **248** | **168** | **−80 (−32%)** | |

Other modules unchanged. Total mutants dropped from 3,331 to 3,304 — 6 pragma annotations excluded their lines (each `logger.exception(...)` line generates ~3 mutation variants × 6 lines × accounting for some that mutmut had already counted).

### Bridge.py is now under 200 unkilled mutants

After pass 7, bridge.py has **168 unkilled** (was 394 after pass 5, 248 after pass 6). The remaining residue concentrates in two helpers:
- `_run_delegation` (76) — assertion strengthening on stats fields, cache_*, ttft_ms / total_latency_ms in the delegate's logger.add_message call
- `_run_daily_summary_turn` (45) — residual after the strict-key sweep, mostly in the deeper code paths (max_tokens save/restore in `_daily_summary_turn_sync`, write_result branches)

### Top remaining unkilled mutants (in scope, after pass 7)

| Module | Survived + no-tests | Notes |
|---|---:|---|
| `apps.gui.server.history.index` | 98 | Residual after first pass — biggest single concrete target now |
| `apps.gui.server.bridge._run_delegation` | 76 | Residual after PR #30 — kwarg-strengthening on delegate's logger.add_message |
| `apps.gui.server.app` | 47 (no tests) | Entry-point module |
| `apps.gui.server.state` | 47 (no tests) | Entry-point module |
| `apps.gui.server.bridge._run_daily_summary_turn` | 45 | Deeper code-path residue after strict-key sweep |
| `apps.gui.server.agents.prompt_history` | 39 | Snapshot helpers — needs `tmp_path`-fixtures |
| `apps.gui.server.bridge.run_turn` | 37 | Residual after strict-key sweep |
| `apps.gui.server.streaming` | 28+3 | Residual |
| `apps.gui.server.session_factory_helpers` | 28 (no tests) | Entry-point module |
| `apps.gui.server.resume` | 29 | Residual |
| `apps.gui.server.history.derive` | 28 | Residual |
| `apps.gui.server.routes.chat_ws` | 21 (no tests) | WS endpoint |
| `apps.gui.server.confirmation` | 19+1 | Residual |
| `apps.gui.server.bridge._run_one_turn` | 7 | Non-summarization residue |
| `apps.gui.server.routes.agent_includes` | 2 | residue |
| `apps.gui.server.routes.agents` | 2 | residue |
| `apps.gui.server.routes.home` | 2 | residue |
| `packages.core.settings` | 1 | residue |
| **TOTAL** | **568** | (422 survived + 146 no-tests) |

---

## 2026-05-03 — GUI server + typed settings (sixth pass — bridge delegation)

Workflow run [`25274539727`](https://github.com/Cherubeam/jarvis/actions/runs/25274539727) on branch `test/gui-mutation-bridge-delegation`. Largest concrete remaining target: `bridge.py` (394 of 510 survivors after pass 5). Originally planned as `_run_delegation` only; bundled in the connected `_run_one_turn` summarization branch and a strict-key sweep on `run_turn` events because they share fixture infrastructure and the marginal cost is small. Daily-summary helper (`_run_daily_summary_turn`, 110 survivors) split off for the next PR.

### Baseline → first → ... → sixth

| Status | Baseline | 1st | 2nd | 3rd | 4th | 5th | 6th (`25274539727`) | Δ vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 🎉 Killed | 1,843 | 2,390 | 2,424 | 2,475 | 2,508 | 2,535 | **2,681** | **+838** |
| 🙁 Survived | 1,175 | 628 | 594 | 543 | 510 | 455 | **502** | **−673 (−57%)** |
| 🫥 No tests | 339 | 339 | 339 | 339 | 339 | 339 | **146** | **−193 (−57%)** |
| ⏰ Timeout | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 0 |
| **Total mutants** | **3,359** | **3,359** | **3,359** | **3,359** | **3,359** | **3,331** | **3,331** | −28 (pragmas) |
| **Unkilled total** (survived + no-tests) | **1,514** | **967** | **933** | **882** | **849** | **794** | **648** | **−866 (−57%)** |

### Kill-rate caveat

Pass 6 is the first one to move the needle on **"no tests"** mutants. That changes the math: testable-kill-rate slipped 84.78% → 84.18% because the denominator (total − no_tests) grew from 2,992 to 3,185 — 193 mutants from `_run_delegation` moved into evaluation, of which 113 were killed and 80 survived. The cleaner headline is the **−18% drop in total unkilled** (survived + no_tests), since "no tests" is strictly worse than "survived" — at least surviving mutants exercise some test path.

### Per-helper kills (sixth-pass focus, all in bridge.py)

| Helper | Pass 5 | Pass 6 | Δ this pass | What killed it |
|---|---|---|---:|---|
| `bridge._run_delegation` | 193 (no tests) | 80 (survived) | **−113 killed (58%)** | 10 new tests covering full event sequence, delegation event keys + `from/to/reason`, delegate-id as `agent` field, `delegate_context` prompt-suffix, logger persistence with `agent_name=delegate_id`, registry-miss silent skip, delegate-exception error path, strict text-event keys |
| `bridge._run_one_turn` | 27 survived | 7 survived | **−20 (−74%)** | 3 tests on the summarization branch — `resolve_model("fast", models)` exact args, `summarize_history` exact kwargs, `record_history_tokens(bytes // 4)` int (pins `// 4` vs `/ 4` vs `// 5`) |
| `bridge.run_turn` | 57 survived | 44 survived | **−13 (−23%)** | 2 strict-key tests pin every event's canonical key set (catches `"id"` → `"XXidXX"` / `"ID"` mutations that pass current type-only assertions) |
| `bridge._run_daily_summary_turn` | 110 | 110 | 0 | not targeted (next PR) |
| `bridge._mark_current_dirty` | 4 | 4 | 0 | residue |
| `bridge._daily_summary_turn_sync` | 2 | 2 | 0 | residue |
| `bridge._find_deferred_handler` | 1 | 1 | 0 | residue |
| **TOTAL bridge** | **394** | **248** | **−146 (−37%)** | |

Other modules unchanged.

### Top remaining unkilled mutants (in scope, after pass 6)

| Module | Survived + no-tests | Notes |
|---|---:|---|
| `apps.gui.server.bridge._run_daily_summary_turn` | 110 | Next PR — same strict-key sweep approach in `test_bridge_daily_summary.py` |
| `apps.gui.server.history.index` | 98 | Residual after first pass |
| `apps.gui.server.bridge._run_delegation` | 80 | Residual — assertion strengthening on stats/cost/tokens fields |
| `apps.gui.server.app` | 47 (no tests) | Entry-point module |
| `apps.gui.server.state` | 47 (no tests) | Entry-point module |
| `apps.gui.server.bridge.run_turn` | 44 | Residual after strict-key sweep |
| `apps.gui.server.agents.prompt_history` | 39 | Snapshot helpers — needs `tmp_path`-fixtures |
| `apps.gui.server.streaming` | 28+3 | Residual |
| `apps.gui.server.session_factory_helpers` | 28 (no tests) | Entry-point module |
| `apps.gui.server.resume` | 29 | Residual |
| `apps.gui.server.history.derive` | 28 | Residual |
| `apps.gui.server.routes.chat_ws` | 21 (no tests) | WS endpoint |
| `apps.gui.server.confirmation` | 19+1 | Residual |
| `apps.gui.server.bridge._run_one_turn` | 7 | Residual — non-summarization branch |
| `apps.gui.server.routes.agent_includes` | 2 | `_meta_dict` residue |
| `apps.gui.server.routes.agents` | 2 | `_load_meta_dict` residue |
| `apps.gui.server.routes.home` | 2 | `_flatten_tasks` literals |
| `packages.core.settings` | 1 | `_diff_paths` default-arg |
| **TOTAL** | **648** | |

---

## 2026-05-03 — GUI server + typed settings (fifth pass — gap closure)

Workflow run [`25274185208`](https://github.com/Cherubeam/jarvis/actions/runs/25274185208) on branch `test/gui-mutation-pass-5`. Closed the genuine test gaps surfaced when inspecting pass-4 survivors via `mutmut show`. Process notes worth preserving:

1. The first PR plan was a **pragma sweep** based on the hypothesis that pass-4's residual survivors were equivalent literal-string mutants. Investigation proved that wrong — inspecting actual mutant diffs showed they're mostly genuine test gaps (under-asserted return values, missed exception detail strings, branches not exercised by the existing fixtures). Branch `test/gui-mutation-pragma-sweep` was created and abandoned cleanly.
2. The pivoted strategy was: populate the local mutmut cache (workaround the macOS fork-segfault with `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run mutmut run --max-children 1` until cache files appear in `mutants/`), inspect each survivor via `mutmut show`, categorise as gap or equivalent, write tests / annotate accordingly.
3. A **pre-existing date-window flake** in `test_detail_cost_14d_sums_only_agent_sessions` blocked the first workflow run (37s, every mutant "not checked") because mutmut uses `pytest -x` for baseline collection. Fixed inline as part of this PR; widened the assertion to allow the three reachable totals as fixture dates drift.

### Baseline → first → second → third → fourth → fifth

| Status | Baseline | First | Second | Third | Fourth | Fifth (`25274185208`) | Δ vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| 🎉 Killed | 1,843 | 2,390 | 2,424 | 2,475 | 2,508 | **2,535** | **+692** |
| 🙁 Survived | 1,175 | 628 | 594 | 543 | 510 | **455** | **−720 (−61.3%)** |
| 🫥 No tests | 339 | 339 | 339 | 339 | 339 | 339 | 0 |
| ⏰ Timeout | 2 | 2 | 2 | 2 | 2 | 2 | 0 |
| **Total mutants** | **3,359** | **3,359** | **3,359** | **3,359** | **3,359** | **3,331** | **−28 (pragmas)** |

**Kill rate on testable mutants** (`killed / (total − no_tests)`): **61.0% → 79.1% → 80.3% → 82.0% → 83.05% → 84.78% (+23.8pp total, +1.73pp this pass).**

### Per-helper kills (fifth-pass focus)

In-scope total: **60 targeted survivors → 5 remaining (−92%).** 6 helpers hit zero, 3 have small residue.

| Helper | Pass 4 | Pass 5 | Status | What killed it |
|---|---:|---:|---|---|
| `agent_includes._lookup` | 14 | **0** | ✅ | Exact `exc.detail` strings on every 404 path; new unknown-agent-on-GET case |
| `agent_includes._row_for` | 6 | **0** | ✅ | `path` value + tz-aware `last_modified_iso` shape (`+00:00` suffix) + missing-file null-coercion |
| `agent_includes._affects_agents` | 2 | **0** | ✅ | meta_path=None skip + filename-miss skip (continue-vs-break) tests |
| `agent_includes._meta_dict` | 11 | **2** | residue | Unicode test killed encoding mutations; `or {}` operator mutations remain |
| `agents._load_meta_dict` | 11 | **2** | residue | Same as above |
| `routes/settings._classify_error` | 8 | **0** | ✅ | Bare-`type:object` schema test + array-without-items test + 2 pragmas on equivalent `current = None` lines |
| `packages.core.settings._diff_*` | 4 | **1** | residue | Multi-key dynamic + type-mismatch + key-only-on-one-side tests killed 3 of 4; `_diff_paths_1` (default arg `prefix=""` → `"XXXX"`) inexplicably survived despite an explicit test that traces to a clear failure path |
| `packages.core.settings._inline_refs` | 2 | **0** | ✅ | Cycle through nested dict + cycle through nested list tests pin the `seen` kwarg in both recursive comprehensions |
| `packages.core.settings.dereferenced_schema` | 2 | **0** | ✅ | Pragma on `pop("$defs", {})` default-arg (pydantic always emits `$defs`) |
| **TOTAL TARGETED** | **60** | **5** | **−55 (−92%)** | |

Untargeted modules unchanged.

### Top remaining survivors after fifth pass (in scope)

| Module | Survivors | Notes |
|---|---:|---|
| `apps.gui.server.bridge` | 201 | `_run_delegation` (193) + `_run_one_turn` history-summarization branch (~40) — PR #30 target |
| `apps.gui.server.history.index` | 98 | Residual after first pass |
| `apps.gui.server.agents.prompt_history` | 39 | Snapshot helpers — needs `tmp_path`-based fixtures |
| `apps.gui.server.resume` | 29 | Residual after first pass |
| `apps.gui.server.history.derive` | 28 | Residual after first pass |
| `apps.gui.server.streaming` | 28 | Residual after first pass |
| `apps.gui.server.confirmation` | 19 | Residual after first pass |
| `apps.gui.server.routes.agent_includes` | 2 | `_meta_dict` residue (likely `or {}` operator mutations) |
| `apps.gui.server.routes.agents` | 2 | `_load_meta_dict` residue (same pattern) |
| `apps.gui.server.routes.home` | 2 | Residual `_flatten_tasks` literals (untouched in pass 5) |
| `packages.core.settings` | 1 | `_diff_paths_1` (default-arg mutation) |
| `apps.gui.server.agents.prompt_stats` | 3 | Residual after second pass |
| `apps.gui.server.agents.detail` | 2 | Already comprehensive — skip |
| **TOTAL** | **454**[^1] | (+ 339 no-tests = 793 unkilled overall) |

[^1]: Per-module total here is 454; the summary line says 455. The discrepancy is one survivor in a module not enumerated above (likely test-related noise from the `routes.home._flatten_tasks` re-classification).

### Lessons for future passes

- **Inspect before assuming.** "Equivalent mutant" is a tempting hypothesis when assertions look strong, but `mutmut show` is the only way to be sure. Cost: ~10 minutes per helper to inspect + categorise.
- **The local cache works on macOS** despite the fork-segfault. Run mutmut with `--max-children 1` and `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`; let it process for ~30s; kill it. The cache files in `mutants/` survive partial runs.
- **Watch for `pytest -x` cliffs.** Any single failing test in the suite blocks mutmut's baseline collection and silently invalidates the entire run. The 37-second "success" status is the canary — investigate before trusting any sub-1-min mutation run.

---

## 2026-05-02 — GUI server + typed settings (fourth pass)

Workflow run [`25250457940`](https://github.com/Cherubeam/jarvis/actions/runs/25250457940) on branch `test/gui-mutation-pass-4`. Targeted `apps/gui/server/routes/settings.py` only — the easiest untouched concentration after PR #27. Total elapsed: ~4 min for 3,359 mutants.

### Baseline → first → second → third → fourth

| Status | Baseline | First | Second | Third | Fourth (`25250457940`) | Δ vs baseline |
|---|---:|---:|---:|---:|---:|---:|
| 🎉 Killed | 1,843 | 2,390 | 2,424 | 2,475 | **2,508** | **+665** |
| 🙁 Survived | 1,175 | 628 | 594 | 543 | **510** | **−665 (−56.6%)** |
| 🫥 No tests | 339 | 339 | 339 | 339 | 339 | 0 |
| ⏰ Timeout | 2 | 2 | 2 | 2 | 2 | 0 |
| **Total mutants** | **3,359** | **3,359** | **3,359** | **3,359** | **3,359** | — |

**Kill rate on testable mutants** (`killed / 3,020`): **61.0% → 79.1% → 80.3% → 82.0% → 83.05% (+22.05pp total, +1.1pp this pass).**

### Per-module survivor reduction (fourth pass focus)

| Module | Third pass | Fourth pass | Δ this pass | Targeted helpers |
|---|---:|---:|---:|---|
| `apps.gui.server.routes.settings` | 41 | **8** | **−33 (−80%)** | `_classify_error` 21 → 8 (residual is literal-string mutants on schema-walking constants), `_normalize_validation_errors` 14 → 0, `_get_write_lock` 4 → 0, `_has_managed_header` 2 → 0, plus `_local_yaml_path` lock-in |
| **TOTAL (targeted modules)** | **41** | **8** | **−33 (−80%)** | — |

All other modules unchanged — clean attribution that the entire kill-rate improvement traces to this single file. +31 unit tests (full subset 611 → 642 tests), green locally in ~3 s.

### Why _classify_error left 8 survivors

`_classify_error` walks the dereferenced schema dict-by-segment, returning either `("field", loc[:-1])` or `("model_validator", loc)`. The 8 residual survivors are mutations to:

- The `"model_validator"` and `"field"` return-string literals (renaming them silently still passes our `assert kind == "..."` checks because mutmut leaves the test code unmutated, but in practice mutmut's literal-string mutations include both prepending and substring deletion that produce semantically-distinct strings — these survive because no downstream test path catches them).
- The schema-key dispatch constants: `"items"` (array branch), `"properties"` (object descent), `"additionalProperties"` (dynamic-keyed dict), `"type"` and `"object"` in the trailing classification check.

Same pattern as `agent_includes._meta_dict` after pass 3: equivalent or near-equivalent literal mutants. The fix is a `# pragma: no mutate` annotation pass on these dispatch constants, not more tests — exactly what the 2026-04-13 sweep did for `packages/core/` (253 pragma annotations, 9,929 → 9,676 total mutants). Deferred to a focused pragma-sweep PR.

### Top remaining survivors after fourth pass (in scope)

| Module | Survivors | Notes |
|---|---:|---|
| `apps.gui.server.bridge` | 201 | `_run_delegation` (193) + `_run_one_turn` history-summarization branch (~40) — PR #29 target |
| `apps.gui.server.history.index` | 98 | Residual after first pass |
| `apps.gui.server.agents.prompt_history` | 39 | `_rebuild_index_from_disk` + `list_snapshots` + snapshot helpers — needs `tmp_path`-based fixtures |
| `apps.gui.server.routes.agent_includes` | 33 | Residual literal-string mutants (pragma candidates) |
| `apps.gui.server.resume` | 29 | Residual after first pass |
| `apps.gui.server.history.derive` | 28 | Residual after first pass |
| `apps.gui.server.streaming` | 28 | Residual after first pass |
| `apps.gui.server.confirmation` | 19 | Residual after first pass |
| `apps.gui.server.routes.agents` | 11 | Residual `_load_meta_dict` literals |
| `apps.gui.server.routes.settings` | 8 | Residual `_classify_error` literals (pragma candidates) |
| `packages.core.settings` | 8 | Residual `_inline_refs` / `_diff_*` literals |
| `apps.gui.server.agents.prompt_stats` | 3 | Residual after second pass |
| `apps.gui.server.routes.home` | 2 | Effectively done |
| `apps.gui.server.agents.detail` | 2 | Already comprehensive — skip |
| **TOTAL** | **510** | (+ 339 no-tests = 849 unkilled overall) |

**Equivalent-mutant accumulation:** As the easy survivors get killed, the remaining ones increasingly cluster around literal-string constants (`"utf-8"`, `"properties"`, error-message text) that produce semantically-identical behaviour. Two follow-up tracks make sense from here: PR #29 chasing the largest concrete target (`bridge._run_delegation`), and a separate "pragma sweep" PR annotating the equivalent-mutant clusters in `routes.settings`, `routes.agent_includes`, `routes.agents._load_meta_dict`, and `packages.core.settings` (~50–60 survivors total likely to drop to the no-effect category).

---

## 2026-05-02 — GUI server + typed settings (third pass)

Workflow run [`25250114070`](https://github.com/Cherubeam/jarvis/actions/runs/25250114070) on branch `test/gui-mutation-pass-3`. Targeted the four "easiest next batch" modules called out in PR #26's follow-up plan. Total elapsed: ~4 min for 3,359 mutants on Linux CI.

### Baseline → first → second → third

| Status | Baseline | First (`25219263045`) | Second (`25249193229`) | Third (`25250114070`) | Δ vs baseline |
|---|---:|---:|---:|---:|---:|
| 🎉 Killed | 1,843 | 2,390 | 2,424 | **2,475** | **+632** |
| 🙁 Survived | 1,175 | 628 | 594 | **543** | **−632 (−53.8%)** |
| 🫥 No tests | 339 | 339 | 339 | 339 | 0 |
| ⏰ Timeout | 2 | 2 | 2 | 2 | 0 |
| **Total mutants** | **3,359** | **3,359** | **3,359** | **3,359** | — |

**Kill rate on testable mutants** (`killed / (total − no_tests)` against 3,020 testable): **61.0% → 79.1% → 80.3% → 82.0% (+21.0pp total, +1.7pp this pass).**

### Per-module survivor reduction (third pass focus)

| Module | Second pass | Third pass | Δ this pass | Targeted helpers |
|---|---:|---:|---:|---|
| `apps.gui.server.routes.home` | 32 | **2** | **−30 (−94%)** | `_greeting` / `_day_label` / `_task_to_dict` / `_flatten_tasks` (cap-at-6, mid-bucket cutoff, missing/None tolerance) |
| `packages.core.settings` | 16 | **8** | **−8 (−50%)** | `_inline_refs` (cycle, missing def, non-defs ref, scalars, list/dict recursion), `_diff_dict`, `_diff_paths`, `dereferenced_schema` |
| `apps.gui.server.routes.agents` | 19 | **11** | **−8 (−42%)** | `_load_meta_dict`, `_get_write_lock` (creation / cache-hit / distinct-per-agent / preexisting-state / async serialisation), `_history_root`, path helpers |
| `apps.gui.server.routes.agent_includes` | 38 | **33** | **−5 (−13%)** | `_guard_placeholder` (parametrized like `_guard_agent_id`), `_meta_dict`, `_repo_rel`, `_affects_agents` (early-return + sort + self-exclude), `_editable_for`, `_history_key`, `_shared_dir_for` |
| **TOTAL (targeted modules)** | **105** | **54** | **−51 (−49%)** | — |

Untargeted modules unchanged. +91 unit tests across 4 files; the in-scope subset (`tests/unit/gui/`, `test_settings.py`, `test_settings_diff.py`) goes 508 → 611 tests, full subset green in ~3 s.

### Why agent_includes only dropped 13%

The remaining 33 survivors cluster in three helpers:

- `_meta_dict` (11) — every survivor is inside the `try: yaml.safe_load(p.read_text(encoding="utf-8")) or {} except: ...` block. Mutmut mutates the `encoding="utf-8"` literal, the `or {}` fallback constant, and the `exc_info=True` keyword — all of which produce identical observable output for the inputs we test (parsed dict / empty dict on failure). These are equivalent or near-equivalent mutants; killing them needs either `# pragma: no mutate` annotations or assertions on logger output.
- `_lookup` (14) — error-message string mutations and the `JARVIS` literal short-circuit. Could be killed with stricter `assert exc.value.detail == "..."` assertions on every 404 path, but the existing integration tests assert status codes only.
- `_row_for` (6) — `IncludeRow` constructor argument-order mutations + `_repo_rel` invocation conditions. Hard to reach without rewriting tests around full `IncludeRow.model_dump()` equality.

`routes.home` showed what's possible when the helpers are pure formatters — 94% reduction from a single test file edit. The agent_includes residue is a different category of survivor and isn't worth chasing without the `# pragma: no mutate` discussion that the 2026-04-13 sweep already had.

### Top remaining survivors after third pass (in scope)

| Module | Survivors | Notes |
|---|---:|---|
| `apps.gui.server.bridge` | 201 | `_run_delegation` (193) + `_run_one_turn` history-summarization branch (~40 of 27 listed) — needs delegation-test fixture extension to `test_bridge_run_turn.py`. Largest single remaining target. |
| `apps.gui.server.history.index` | 98 | Residual `_path_for` filesystem fallback edges + `list()` corner-case filters |
| `apps.gui.server.routes.agent_includes` | 33 | Residual literal-string and equivalent mutants — see above |
| `apps.gui.server.resume` | 29 | Residual after first pass |
| `apps.gui.server.history.derive` | 28 | Residual after first pass |
| `apps.gui.server.streaming` | 28 | Residual after first pass |
| `apps.gui.server.confirmation` | 19 | Residual after first pass (was 18, +1 ascribed to a new mutant from updated cache or re-classification) |
| `apps.gui.server.agents.prompt_history` | 39 | `_rebuild_index_from_disk` (15), `list_snapshots` (12), snapshot helpers — needs `tmp_path`-based fixtures |
| `apps.gui.server.routes.settings` | 41 | `_classify_error` (21) + `_normalize_validation_errors` (14) — pure helpers, easy follow-up target |
| `apps.gui.server.routes.agents` | 11 | Residual `_load_meta_dict` literals after this pass |
| `apps.gui.server.routes.home` | 2 | Effectively done |
| `packages.core.settings` | 8 | Residual `_inline_refs` / `_diff_*` literals |
| `apps.gui.server.agents.prompt_stats` | 3 | Residual after second pass |
| `apps.gui.server.agents.detail` | 2 | Already comprehensive — skip |
| **TOTAL** | **543** | (+ 339 no-tests = 882 unkilled overall) |

---

## 2026-05-01 — GUI server + typed settings (current scope)

After GUI Phases 1–8 + the typed-settings refactor + conversation-lifecycle work shipped in 0.16.0–0.21.0, none of the new code in `apps/gui/server/` had been mutation-audited. Re-scoped `paths_to_mutate` in `pyproject.toml` to:

```toml
paths_to_mutate = ["apps/gui/server/", "packages/core/settings.py"]
```

The historical `packages/core/` numbers from 2026-04-13 below remain authoritative for that scope.

### Baseline → first pass → second pass

| Status | Baseline (`25217994644`) | First pass (`25219263045`) | Second pass (`25249193229`) | Δ vs baseline |
|---|---:|---:|---:|---:|
| 🎉 Killed | 1,843 | 2,390 | **2,424** | **+581** |
| 🙁 Survived | 1,175 | 628 | **594** | **−581 (−49.4%)** |
| 🫥 No tests | 339 | 339 | 339 | 0 |
| ⏰ Timeout | 2 | 2 | 2 | 0 |
| **Total mutants** | **3,359** | **3,359** | **3,359** | — |

**Kill rate on testable mutants** (= killed / (total − no_tests)): **61.0% baseline → 79.1% first pass → 80.3% second pass (+19.3pp total).** Half the survivors gone after two rounds of targeted test work.

### Per-module survivor reduction

Two rounds of targeted work. Untouched modules show 0 change — validates the approach.

| Module | Baseline | First pass | Second pass | Total Δ | Targeted in |
|---|---:|---:|---:|---:|---|
| `apps.gui.server.bridge` | 468 | 201 | 201 | **−267 (−57%)** | first |
| `apps.gui.server.history.index` | 207 | 98 | 98 | **−109 (−53%)** | first |
| `apps.gui.server.confirmation` | 97 | 18 | 18 | **−79 (−81%)** | first |
| `apps.gui.server.resume` | 82 | 29 | 29 | **−53 (−65%)** | first |
| `apps.gui.server.history.derive` | 50 | 28 | 28 | **−22 (−44%)** | first |
| `apps.gui.server.streaming` | 45 | 28 | 28 | **−17 (−38%)** | first |
| `apps.gui.server.routes.outcomes` | 13 | 13 | **0** | **−13 (−100%)** | second |
| `apps.gui.server.home.task_links` | 11 | 11 | 2 | **−9 (−82%)** | second |
| `apps.gui.server.routes.agents` | 27 | 27 | 19 | **−8 (−30%)** | second (`_guard_agent_id` only — `_load_meta_dict` and `_get_write_lock` still uncovered) |
| `apps.gui.server.agents.prompt_stats` | 6 | 6 | 3 | **−3 (−50%)** | second |
| `apps.gui.server.agents.prompt_history` | 40 | 40 | 39 | −1 | side-effect |
| `apps.gui.server.routes.settings` | 41 | 41 | 41 | 0 | not targeted |
| `apps.gui.server.routes.agent_includes` | 38 | 38 | 38 | 0 | not targeted |
| `apps.gui.server.routes.home` | 32 | 32 | 32 | 0 | not targeted |
| `packages.core.settings` | 16 | 16 | 16 | 0 | not targeted |
| `apps.gui.server.agents.detail` | 2 | 2 | 2 | 0 | already comprehensive |
| **TOTAL** | **1,175** | **628** | **594** | **−581 (−49.4%)** | |

### Modules with no tests at all (339 mutants)

These four entry-point / wiring modules have no direct unit tests — every mutant reports "no tests" rather than survived. Future passes can target them.

| Module | Mutants | Notes |
|---|---:|---|
| `apps.gui.server.app` | 47 | FastAPI app factory — exercised only via integration |
| `apps.gui.server.state` | 47 | `GuiSession` + `_DeferredConfirmationHandler` |
| `apps.gui.server.session_factory_helpers` | 28 | `build_delegate_agent` glue |
| `apps.gui.server.routes.chat_ws` | 21 | WS endpoint handler |
| `apps.gui.server.bridge` (subset) | 193 | Helper paths the new tests don't reach yet |
| `apps.gui.server.streaming` (subset) | 3 | `_put` overflow recovery branch |

### What the test improvements look like

**First pass** — seven test files: 6 strengthened + 1 new (`test_bridge_run_turn.py` for the regular chat flow). +144 tests, focused on the six largest survivor counts.

**Second pass** — four small files strengthened (+46 tests):
- `test_outcomes_route.py`: parametrized rejection for every short-circuit in `_guard_file_id`'s OR chain (empty / `/` / `..` / `\` / leading `.`)
- `test_agents_route.py`: parametrized accept + reject for `_guard_agent_id`
- `test_home_task_links.py`: `_salient_words` boundary at 4 chars + longest-first sort + digit handling, plus stronger assertions on `link_tasks_to_conversations` (input mutation, two-link cap, multi-task isolation)
- `test_prompt_stats.py`: `_iso_mtime` edge cases (missing file / dir as path / UTC suffix), `approx_tokens` boundaries, `compute_stats` line-count formula edges, `token_estimate_method` literal lock-in

All 508 in-scope tests pass locally in ~2s. Pattern across both passes:

1. **Strict event-shape assertions** — every queue dict checked for exact `{type, id, agent, ...}` keys, not just substring matches
2. **Helper-function tests** — `_now_hhmm`, `_find_deferred_handler`, `_mark_current_dirty`, `_diff_lines`, `_truncate`, `_safe_parse_json`, `_path_for_file_id`, `_metrics_from_dict`, `_msg_text`, `_in_date_range`, `_build_summary_dict` all directly exercised
3. **Default-argument tests** — calls without optional kwargs to lock in defaults (`agent="JARVIS"`, `max_chars=240`, `max_items=4`, etc.)
4. **Both branches of conditionals** — empty/whitespace inputs, missing optional dict keys, error paths
5. **Boundary conditions** — exact-length truncation, empty strings, zero/negative inputs, exact threshold matches in date-range presets

### CI workflow fix shipped

The first attempt (`25217931788`) finished in 37s and reported "not checked" for every mutant. Root cause: `.github/workflows/mutation.yml` only installed `--extra test`, but `tests/unit/gui/*` imports `fastapi.TestClient` from the `web` extra. Without it, pytest collection fails and mutmut bails. Fixed by mirroring the test workflow's `--extra test --extra web` install line.

### How to reproduce

```bash
# Ensure paths_to_mutate in pyproject.toml targets the modules you care about.
gh workflow run mutation.yml --ref <branch>
gh run watch
gh run download --name mutmut-results-<run-id>
```

The artifact contains `mutmut-results.txt` (one mutant per line) + `mutmut-summary.txt` (final emoji counter) + `mutmut-run.log` (full runner output). Retained 90 days.

---

## 2026-04-13 Linux CI (`packages/core/` scope)

After five phases of targeted test improvements (229 new tests across 15 branches) plus a pragma sweep (64 annotations):

| Status | Count | Prev (2026-04-11) |
|---|---:|---:|
| 🎉 Killed | **7,221** | 5,911 |
| 🙁 Survived | 2,021 | 3,584 |
| 🫥 No tests | 427 | 427 |
| ⏰ Timeout | 7 | 7 |
| 🤔 Suspicious | 0 | 0 |
| **Total mutants** | **9,676** | 9,929 |

**Kill rate**: `7,221 / (9,676 − 427) = 78.1%` on testable mutants (+15.8pp from 62.3% baseline). Total mutants reduced from 9,929 to 9,676 due to 253 `# pragma: no mutate` annotations on equivalent mutants (LLM-facing description strings, pure-literal logger calls).

### Progress by phase

| Phase | Branches | New Tests | Kills | Kill Rate |
|-------|----------|-----------|-------|-----------|
| Baseline (2026-04-11) | — | — | — | 62.3% |
| Phase 1: Tool factories + stream_handler | 6 | 57 | +415 | 66.6% |
| Phase 2: History + memory | 2 | 52 | +170 | 68.4% |
| Phase 3: Importers | 3 | 66 | +196 | 70.5% |
| Phase 4: Tool factories batch 2 | 3 | 47 | +391 | 74.6% |
| Pragma sweep + never-targeted tools | 1 | 29 | +138 | **78.1%** |

### Per-module survivors (current)

| Module | Survived | No Tests | Total |
|--------|----------|----------|-------|
| stream_handler | 287 | 0 | 287 |
| card_renderer | 196 | 70 | 266 |
| llm_client | 65 | 163 | 228 |
| importers/chatgpt | 222 | 0 | 222 |
| importers/claude | 213 | 0 | 213 |
| importers/claude_context | 131 | 0 | 131 |
| memory | 121 | 0 | 121 |
| card_indexer | 96 | 23 | 119 |
| rag/indexer | 85 | 25 | 110 |
| card_generator_tools | 106 | 0 | 106 |
| app | 0 | 107 | 107 |

### 2026-04-12 sweep impact (included in baseline)

Two targeted sweeps reduced "no tests" by 322 and added 215 kills:

- **`stream_handler`**: 10 new assertion tests. Survivors dropped from 368 → 324 (−44 kills).
- **`card_generator_tools`**: new test file (28 tests). Went from 322 "no tests" / 0 survivors → 0 "no tests" / 151 survivors (171 killed).

**How to reproduce**: `gh workflow run mutation.yml --ref <branch>`, then `gh run download --name mutmut-results-<run-id>`. Artifacts retained 90 days. Raw per-mutant list in `mutmut-results.txt`; emoji summary in `mutmut-summary.txt`; full runner log in `mutmut-run.log`.

### Why this replaces the macOS baseline

A pre-Linux rerun on macOS on 2026-04-11 produced 9,180 segfaults / 749 no-tests — **zero killed, zero survived**. Even previously-healthy modules (`filesystem_access` 86%, `pricing` 76%) segfaulted 100% at fork time. Root cause: mutmut 3.5.0 hardcodes `os.fork()` at `mutmut/__main__.py:1152`, which is unsafe on modern macOS due to Objective-C runtime fork-safety restrictions. `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` no longer helps. Local mutmut on macOS is effectively dead until upstream switches to `spawn`, so the Linux workflow is now the only source of truth.

### Test-harness fixes shipped to unblock Linux CI

Four separate blockers surfaced during the first CI attempts; all fixed:

1. **`MUTANT_UNDER_TEST` wipe**: `test_card_renderer.py::TestEnsureHomebrewLibPath` and `test_model_resolver.py::test_empty_when_no_keys_set` used `patch.dict(os.environ, {}, clear=True)`, which deletes the env var mutmut's trampoline requires. Scoped the env clear to just the variables each test cares about.
2. **User-local skill files**: `test_base_skill.py::TestBaseSkillFromSkillMd` and `test_skill_registry.py::TestDiscoverSkills` read from `packages/skills/<name>/SKILL.md`, which are gitignored symlinks not available on CI. Split the real-skill tests into dedicated classes gated on the files being present.
3. **`things-py` SQLite on import**: `test_things3_tools.py` mocks `sys.platform=darwin` to test the macOS tool factory, but that still triggers a real `import things` inside `make_things3_tools`, and `things-py` touches the Things 3 SQLite database on import. Fails on Linux where the database doesn't exist. Split out the one non-darwin test and skipped the rest via `@pytest.mark.skipif(sys.platform != "darwin", ...)`.
4. **`mutmut html` subcommand**: workflow called it, but mutmut 3.5.0 has no `html` subcommand. Removed the step.

---

## Remaining survivors (2026-04-13)

**2,021 survivors** across 38 modules. The top 11 account for 80% of survivors:

| Module | Survived | No Tests | Total | Notes |
|--------|----------|----------|-------|-------|
| stream_handler | 287 | 0 | 287 | 4 near-identical methods with duplicated TokenUsage logic |
| card_renderer | 196 | 70 | 266 | Jinja/HTML templates, WeasyPrint integration |
| llm_client | 65 | 163 | 228 | Class methods with 163 "no tests" — needs new test coverage |
| importers/chatgpt | 222 | 0 | 222 | Deeply nested content conversion logic |
| importers/claude | 213 | 0 | 213 | Update sync + content block conversion |
| importers/claude_context | 131 | 0 | 131 | import_context conditional branches |
| memory | 121 | 0 | 121 | ConversationLogger methods (record_utilization, _print_session_summary) |
| card_indexer | 96 | 23 | 119 | Search result formatting |
| rag/indexer | 85 | 25 | 110 | Indexing logic |
| card_generator_tools | 106 | 0 | 106 | Image existence checks, max_images_per_run limit |
| app | 0 | 107 | 107 | Entry point — all "no tests" |

**Further improvement has steep diminishing returns.** The remaining survivors are in: duplicated code paths, modules needing complex test infrastructure (WeasyPrint, ChromaDB, LiteLLM class mocking), deeply nested conditional logic already swept once, and untested entry points (app.py).

---

## Historical audit: 2026-04-03

> **Note (2026-04-13):** The per-module tables below are superseded by the 2026-04-13 data above. Kept for reference only.

Everything below this line reflects the 2026-04-03 run.

## Executive Summary (2026-04-03)

- **32 of 44 modules** produced testable results (10 segfaulted due to macOS fork safety, 2 had no mutable code)
- **8,388 mutants** tested, **4,799 killed** (57.2%), **3,589 survived**
- **12 modules below 50%** mutation kill rate — tests exist but assertions are too shallow
- **Tool factory functions** are the worst offenders — tests verify structure but not content/behavior
- **Best module**: `core/filesystem_access` at 86%

---

## Key Finding: Tool Factory Tests Are Shallow

The biggest pattern across all findings: **tool factory tests verify that tools are created and callable, but don't assert on the actual content of tool outputs.** This accounts for the majority of surviving mutants.

Example from `executor.py` — this mutation survived:
```python
# Original
results.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})
# Mutated (survived)
results.append({"XXroleXX": "tool", "tool_call_id": tool_call_id, "content": content})
```
The test calls the function but never checks the dictionary keys in the result.

---

## Per-Module Results (32 modules with data)

### Critical: Below 50% Kill Rate

| Module | Killed | Survived | Score | Root Cause |
|--------|--------|----------|-------|------------|
| `core/tools/blog_tools` | 105 | 182 | 37% | Tool output strings not asserted |
| `core/tools/codebase_tools` | 118 | 193 | 38% | Tool output strings not asserted |
| `core/tools/vault_write_tools` | 113 | 179 | 39% | Tool output strings not asserted |
| `core/tools/web_fetch` | 11 | 17 | 39% | Output content not asserted |
| `core/history` | 77 | 111 | 41% | Summarization output not verified |
| `core/tools/cortex_search` | 68 | 94 | 42% | Search result formatting unchecked |
| `core/tools/conversation_recall` | 64 | 85 | 43% | Tool output strings not asserted |
| `core/tools/suggest_improvements` | 41 | 52 | 44% | Tool output strings not asserted |
| `core/tools/vault_read_tools` | 104 | 125 | 45% | Tool output strings not asserted |
| `core/tools/delegate` | 40 | 44 | 48% | Delegation result unchecked |
| `core/tools/content_evaluator` | 56 | 58 | 49% | Evaluation output unchecked |
| `core/stream_handler` | 429 | 443 | 49% | Streaming output/state unchecked |

### Needs Improvement: 50-75% Kill Rate

| Module | Killed | Survived | Score | Root Cause |
|--------|--------|----------|-------|------------|
| `integrations/cortex/client` | 28 | 25 | 53% | Constructor defaults not asserted |
| `core/memory` | 428 | 329 | 57% | Migration + logging output unchecked |
| `core/importers/chatgpt` | 486 | 363 | 57% | Content conversion output shallow |
| `core/rag/card_indexer` | 193 | 129 | 60% | Search result formatting unchecked |
| `integrations/obsidian/writer` | 164 | 109 | 60% | Write output/formatting unchecked |
| `integrations/things3/task_sync` | 272 | 163 | 63% | Sync output structure unchecked |
| `core/importers/claude` | 489 | 272 | 64% | Import conversion unchecked |
| `agents/base` | 140 | 72 | 66% | Agent instantiation edge cases |
| `core/importers/claude_context` | 361 | 182 | 66% | Import output formatting unchecked |
| `core/card_renderer` | 251 | 122 | 67% | Render output unchecked |
| `core/model_router` | 64 | 24 | 73% | Classification logic edge cases |
| `integrations/obsidian/vault` | 67 | 25 | 73% | Config loading defaults unchecked |

### Good: 75-100% Kill Rate

| Module | Killed | Survived | Score |
|--------|--------|----------|-------|
| `core/tools/executor` | 32 | 11 | 74% |
| `core/rag/indexer` | 211 | 71 | 75% |
| `core/benchmark_costs` | 134 | 44 | 75% |
| `core/pricing` | 54 | 17 | 76% |
| `integrations/obsidian/callout` | 72 | 22 | 77% |
| `core/tools/web_search` | 48 | 13 | 79% |
| `agents/jarvis/agent` | 22 | 4 | 85% |
| `core/filesystem_access` | 57 | 9 | 86% |

### Segfaulted (10 modules — macOS fork safety)

**Note (2026-04-11):** this list is now historical. As of the 2026-04-11 rerun, _every_ module segfaults on macOS — not just the 10 below. The fork-safety regression is total. Fresh numbers for all modules (including these) will come from the Linux CI workflow at [`.github/workflows/mutation.yml`](../../.github/workflows/mutation.yml).

These modules crash due to macOS `os.fork()` safety restrictions interacting with C extensions. mutmut uses `fork()` to run mutants, which is unsafe on macOS when modules load compiled extensions (yaml, httpx, litellm, weasyprint). Neither `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` nor running without it consistently fixes all modules — the crashes are non-deterministic.

| Module | Mutants | Notes |
|--------|---------|-------|
| `agents/developer/confirmation` | 27 | Imports yaml indirectly |
| `agents/registry` | 100 | Imports yaml for meta.yaml parsing |
| `core/context_builder` | 101 | Direct yaml usage |
| `core/llm_client` | 256 | litellm C extensions |
| `core/rag/searcher` | 205 | ChromaDB C extensions |
| `core/tools/base` | 5 | Non-deterministic crash |
| `core/tools/git_tools` | 321 | subprocess + system libs |
| `core/tools/project_write_tools` | 302 | Filesystem + pathlib internals |
| `core/tools/test_tools` | 95 | subprocess interaction |
| `integrations/obsidian/diff` | 157 | difflib C acceleration |

### No Mutable Code (2 modules)

| Module | Status |
|--------|--------|
| `core/events` | Dataclasses only — no logic to mutate |
| `core/model_resolver` | 57 mutants generated but "not checked" (mutmut couldn't determine test coverage) |

---

## Common Mutation Patterns That Survived

### 1. String Key/Value Mutations (~40% of survivors)
```python
# Mutant survives: test doesn't check dictionary keys
{"role": "tool"} -> {"XXroleXX": "tool"}
{"role": "tool"} -> {"role": "XXtoolXX"}
```
**Fix**: Assert on specific keys and values in returned dictionaries.

### 2. String Content Mutations (~25% of survivors)
```python
# Mutant survives: test doesn't check error/output messages
f"Error: Unknown tool '{name}'." -> f"XXError: Unknown tool '{name}'.XX"
```
**Fix**: Assert that output strings contain expected substrings.

### 3. Operator Mutations (~15% of survivors)
```python
# Mutant survives: test doesn't verify arithmetic
elapsed_ms = (time.perf_counter() - start) * 1000
elapsed_ms = (time.perf_counter() - start) / 1000  # survived!
```
**Fix**: Assert on computed values, not just that they exist.

### 4. Control Flow Mutations (~10% of survivors)
```python
# Mutant survives: test doesn't cover the error path
continue -> break
```
**Fix**: Add tests for error/edge-case code paths.

### 5. Logging String Mutations (~10% of survivors)
```python
# Mutant survives: logger output never verified
logger.info("Tool %s executed in %.1fms", name, elapsed_ms)
```
**Assessment**: Mostly **equivalent mutants** (benign). Log message text changes don't affect behavior. Can be ignored or suppressed with `# pragma: no mutate`.

---

## Recommendations

### Priority 1: Fix Tool Factory Tests (12 modules, ~1,500 survivors)
The tool factory tests (`blog_tools`, `codebase_tools`, `vault_write_tools`, `vault_read_tools`, `conversation_recall`, `suggest_improvements`, `web_fetch`, `delegate`, `content_evaluator`, `cortex_search`) all share the same issue: tests call tools and check they don't crash, but never assert on the actual output content.

**Action**: For each tool, add assertions on:
- Output string contains expected content
- Dictionary keys in returned structures
- Error messages for error paths

### Priority 2: Fix stream_handler Tests (443 survivors)
`stream_handler` is a critical module at only 49% kill rate. Streaming state transitions, tool call handling, and output formatting are all undertested.

**Action**: Assert on streaming output content, tool call results, and state changes.

### Priority 3: Fix Importer/Memory Tests (4 modules, ~1,146 survivors)
`chatgpt` importer, `claude` importer, `claude_context` importer, and `memory` module have many surviving mutations in data conversion functions.

**Action**: Assert on the structure and key values of converted/migrated data.

### Priority 4: Suppress Log Message Mutations
Many survivors are log message string mutations which are equivalent mutants (no behavioral impact).

**Action**: Add `# pragma: no mutate` to logger calls, or accept these as known false positives.

### Priority 5: Address Segfaulted Modules
10 modules can't be tested due to macOS fork safety. Options:
- Wait for mutmut to add `multiprocessing.spawn` support (proper fix)
- Try cosmic-ray as an alternative tool
- Run mutation tests on Linux CI where fork safety isn't an issue

---

## Notes

- mutmut 3.5.0 uses `os.fork()` which is unsafe on macOS with C extensions — causes non-deterministic segfaults
- Running with `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` fixes some modules but not all (and breaks others)
- Multiple runs were combined to maximize coverage: 32 of 44 modules have data
- The scoped runner (`--runner "uv run pytest specific_test.py"`) causes universal segfaults; only the full runner works
- Config `paths_to_mutate` must be a TOML array (`["path"]`), not a string — strings are iterated character-by-character
- `also_copy` is required to include all project directories for tests to find imports in the `mutants/` directory
