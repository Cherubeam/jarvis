# Mutation Testing Report

> Audit of test suite quality across the JARVIS codebase.

**Authoritative baseline**: 2026-04-11 (Linux CI, workflow run `24285714342`)
**Previous audit**: 2026-04-03 (macOS, kept as historical reference)
**Tool**: mutmut 3.5.0
**Python**: 3.13.5
**Environment**: GitHub Actions `ubuntu-latest` — see [`.github/workflows/mutation.yml`](../../.github/workflows/mutation.yml)

---

## 2026-04-11 Linux CI baseline (authoritative)

First full mutation sweep on Linux CI. All 44 modules in `packages/core/` were exercised — no macOS segfault blackspots.

| Status | Count |
|---|---:|
| 🎉 Killed | **5,696** |
| 🙁 Survived | 3,477 |
| 🫥 No tests | 749 |
| ⏰ Timeout | 7 |
| 🤔 Suspicious | 0 |
| **Total mutants** | **9,929** |

**Kill rate**: `5,696 / (9,929 − 749) = 62.0%` on testable mutants. Modules with no tests are excluded from the denominator because "no tests" is a test-suite gap, not a test-suite weakness.

This is a ~5-point improvement over the April macOS baseline (57.2%). Two factors likely contribute: the CI workflow exercises the ~10 macOS-segfaulted modules for the first time (so those survivors are real measurements, not missing data), and a few tests shipped between April and now strengthened assertions in tool factories.

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

## Historical audit: 2026-04-03

Everything below this line reflects the 2026-04-03 run. It is the last set of numbers we trust until Linux CI produces new ones.

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
