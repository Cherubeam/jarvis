# Token Economics: Edit Tools and Tool-Argument History

> Fact sheet for a write-up on the September 2026 token savings in agent write tools.
> Facts carry their source. Numbers are marked **billed** (exact: non-streamed usage or
> OpenRouter's generation record) or **logged** (JARVIS session log from streamed turns:
> LiteLLM estimates, known to undercount; see "Measurement caveat").

Related: [token-economics.md](token-economics.md) (strategy) ·
[token-economics-cost-status.md](token-economics-cost-status.md) (cost data, Feb–Mar 2026) ·
[token-economics-next-steps.md](token-economics-next-steps.md) (instrumentation, caching)

---

## Context

- **Setting:** a `substack_publisher` session on 2026-09-29 preparing the post "You Read an AI
  Doom Headline? Ask These 5 Questions First" for publishing. The agent is pinned to Claude
  Opus 5.5 via OpenRouter. Source: `data/conversations/2026/2026-09-29_09-56-13.json`,
  `packages/agents/substack_publisher/meta.yaml`.
- **Task that exposed it:** "Add drafts 1 and 2 to the Obsidian blog post file" (two LinkedIn
  drafts into the post's `[!LINKEDIN]` callout), then a second edit adding Substack Notes.
- **Tool design at the time:** `edit_blog_post(path, new_content, reasoning)`, where `new_content`
  was the complete file (ADR-019, 2026-03-07, `docs/product/decisions.md`). The tool diffs it
  against disk and asks for confirmation.
- **Symptom the user saw:** the approval diff marked two passages as changed that looked
  identical: a quote from OpenAI's incident post and the `*Last updated:*` footer.

## Findings

### 1. Full-file edits make the model retype everything (PR #70)

| | Edit 1 (LinkedIn) | Edit 2 (Notes) | Source |
|---|---|---|---|
| Tool-argument size | 24,637 chars | 26,328 chars | session log, `tool_calls` |
| Output tokens that turn | 6,498 | 6,718 | session log (**logged**) |
| Input tokens that turn | 61,754 | 70,469 | session log (**logged**) |
| Cost that turn | $0.377 | $0.416 | session log (**logged**) |
| Normal turns, same session | $0.07–0.10 | | session log (**logged**) |

- The requested content (two LinkedIn drafts) is about 3,500 characters, roughly 900 tokens.
  The rest of the output was the post copied back.
- Opus 5.5 on OpenRouter: $4/M input, $20/M output. Source: OpenRouter `/api/v1/models`,
  checked 2026-09-29. Output costs 5x input, so retyped text is the most expensive kind of
  token in the turn.

### 2. Retyping is a lossy copy

- The post contained three no-break spaces (U+00A0), carried over from text copied off
  openai.com. The model retyped all three as normal spaces. Those were the "identical" lines
  in the diff. Source: character diff of the `read_blog_post` result against `new_content`
  in the session log.
- The second edit was approved, so the vault file now has normal spaces there. The visible
  effect is none (rendering is identical), but the write changed text nobody asked to change.
- Same failure class as an earlier incident: a full-file rewrite corrupted `i.ytimg.com` to
  `i.yimg.com`, which is why the diff shows a "Links changed" warning
  (`packages/integrations/obsidian/diff.py`).

### 3. After: passage edits (`old_text` → `new_text`)

- `edit_blog_post(path, edits=[{old_text, new_text}, ...], reasoning)`. Edits are applied in
  order, all-or-nothing, and each `old_text` must match once. Text outside the replaced
  passages is kept byte-for-byte. Source: `packages/core/tools/text_edits.py`, PR #70.
- **Live check**, same LinkedIn edit on a copy of the post, non-streamed (**billed**-exact usage):

  | Model | Tool-argument size | Output tokens | Correct on first try |
  |---|---|---|---|
  | Claude Opus 5.5 | 504 chars | 369 | yes |
  | GPT-6 Luna | 515 chars | 263 | yes |

- **Output-token comparison:** 6,498 (logged) → 369 (billed). That's -94%, but it compares an
  estimate with an exact figure. The argument size, 24,637 → 504 chars (-98%), is exact on
  both sides.
- **Output cost per edit** at $20/M: about $0.13 → about $0.007.
- The diff now shows only the changed passage (one removed line, the new lines).

### 4. Old tool arguments were re-sent every turn (PR #71)

- History trimming shortened old tool *results* to 200 chars but kept the model's own tool
  *calls* intact. Source: `packages/core/history.py` (`trim_tool_results`).
- **Replay of the real session:** 25,110 chars of tool arguments went out again on every turn
  after the edit (about 6,300 tokens, about $0.025 per turn at $4/M). With the fix, this drops
  to 1,085 chars once the call leaves the six-message recent window.
- The token estimate that triggers history summarization counted only message text, not tool
  arguments. So large tool calls never pushed a session toward summarization.

### 5. Measurement caveat: logged numbers from streamed turns are estimates

The same prompt was sent once streamed and once non-streamed, and each was compared with
OpenRouter's generation record for that request (2026-09-29):

| | JARVIS logged (streamed) | OpenRouter billed | JARVIS logged (non-streamed) | OpenRouter billed |
|---|---|---|---|---|
| Prompt tokens | 2,615 | 3,931 | 3,933 | 3,933 |
| Completion tokens | 20 | 60 | 60 | 60 |
| Cost | $0.0109 | $0.0169 | $0.0169 | $0.0169 |

- **Cause:** in streaming mode, LiteLLM 1.82.1 drops OpenRouter's final usage chunk and
  substitutes a local token estimate with no cache fields and no cost. JARVIS then prices that
  estimate from its price table. Source: live probes; LiteLLM issues
  [#16112](https://github.com/BerriAI/litellm/issues/16112) and
  [#36168](https://github.com/BerriAI/litellm/issues/36168).
- **What this means for existing numbers:**
  - The "before" figures in section 1 are lower bounds.
  - `token-economics-cost-status.md` (the $10.94 over 28 sessions) was also built from streamed
    turns, so it is an undercount too.
- **Likely consequence, not yet verified:** the March 2026 caching conclusion ("8,026 vs 8,823
  prompt tokens, streaming breaks cache keys", `token-economics-cost-status.md`) matches this
  estimate-versus-real gap rather than a formatting difference. A 2026-09-29 probe showed
  streamed calls do write and read the cache.

## Learnings

1. **Tool schema is a cost decision.** Whatever a tool asks the model to *write* is paid at the
   output rate, often 5x input. Design write tools so the model outputs only the change (the
   `str_replace` pattern, as in Anthropic's text-editor tool and Claude Code's Edit tool).
2. **A full-file rewrite is a copy made by a model, and copies drift.** Invisible characters,
   typographic quotes and URLs are where it drifts first. The drift is hard to see, even in a
   diff.
3. **Make exact-match tools forgiving where models are predictably imprecise.** Fold no-break
   and zero-width characters and typographic quotes for matching only. Otherwise every
   near-miss costs a retry turn, which spends the savings.
4. **Fail visibly, all-or-nothing.** A failed anchor returns an error naming the edit; nothing
   is half-applied, and no diff is shown.
5. **History hygiene covers both directions of tool traffic.** Trim old tool calls as well as
   old tool results, and keep trimmed arguments valid JSON, because providers parse them.
6. **Your token estimator must count everything you send.** An estimator that ignores tool
   arguments under-triggers summarization in exactly the sessions that need it.
7. **Check your meter before optimizing.** Compare logged usage against the provider's billing
   record for a handful of requests. A mis-measured cache in March led to a wrong diagnosis
   that parked prompt caching for six months.
8. **Verify on real traffic.** Replay a real session through the change, and run one live
   non-streamed call per model so the usage figures are exact.

## Good practices checklist (for others building agent write tools)

- [ ] Edit tools take deltas (`old_text` → `new_text`, batched), not whole files; creation tools
      may take full content.
- [ ] Matching is exact first, then folded for invisible and typographic characters; ambiguous
      matches are rejected.
- [ ] Multi-edit calls are all-or-nothing, with errors written for the model to act on.
- [ ] Stale-read checks run before matching, so the error says "re-read", not "not found".
- [ ] History trimming covers tool calls and tool results; JSON stays valid.
- [ ] Token and cost telemetry is reconciled against billed usage (provider generation records)
      before it drives decisions.

## Open items

- `edit_note` (vault) and the developer agent's `edit_file` still use full-file replacement.
- Streamed usage is replaced with OpenRouter's billed records since PR #73. The records appear
  9.5–12.7 s after a stream, so the logger reconciles when it saves, and
  `scripts/backfill_billed_usage.py` fixes the rest. Prompt caching work resumes on exact numbers
  (see [token-economics-next-steps.md](token-economics-next-steps.md)).
- History summarization does not run in delegated agent sessions.

---

*Created: 2026-09-29. Sources: session log 2026-09-29_09-56-13, PRs #70, #71 and #73, live probes
2026-09-29.*
*assist: [prose, research]. Fact sheet written by Claude; not voice-profile material (P7).*
