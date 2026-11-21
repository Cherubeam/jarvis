# Design Tokens

> Visual primitives for the JARVIS GUI. The values live in
> [`apps/gui/web/src/lib/tokens.ts`](../../apps/gui/web/src/lib/tokens.ts); this
> page says what each one is for and why. Since 2026-11 the GUI uses the
> "Journal" look: a page you read and write on, not a dashboard.

See also: [principles.md](principles.md) for design principles,
[voice-and-tone.md](voice-and-tone.md) for UI copy guidelines, [components.md](components.md) for the component inventory.

---

## The rules behind the values

1. **Neutral greys, one accent.** Surfaces are untinted grey. The accent marks
   links, the current selection and the one primary thing on a screen. Every
   other colour means something: an error, an expensive turn, an added or
   removed line.
2. **Two typefaces, by who wrote the text.** Serif for text you read (the
   assistant's answers, descriptions, titles). Mono for text you typed and for
   metadata (paths, times, counts, cost, commands).
3. **No cards.** No card backgrounds, no coloured left borders, no stat tiles,
   no pills. Things are grouped by a heading and, where needed, a 1px rule.
4. **Gutter, column, margin.** A page has a left gutter (time or speaker), a
   reading column of at most 640px, and a right margin for notes (tokens,
   cost, sources).
5. **Contrast.** Every text colour keeps at least 4.5:1 on the surfaces it is
   used on, including the small grey labels.

---

## Colors

### Roles

The role names come from the CLI theme (`JARVIS_THEME` in `apps/cli/display.py`).
The CLI keeps its terminal colours; the GUI maps most roles to grey.

| Token | Dark | Light | Usage |
|-------|------|-------|-------|
| `user` | `#A8A8A8` | `#5F5F5F` | Gutter label of your own turns |
| `assistant` | accent | accent | Links, specialist names, current selection (set from the accent tweak) |
| `tool` | `#A8A8A8` | `#5F5F5F` | Tool-call lines |
| `system` | `#A8A8A8` | `#5F5F5F` | System lines ("Session started.") |
| `error` | `#F0908A` | `#B3261E` | Errors, destructive actions |
| `stats` | `#909090` | `#6E6E6E` | Margin notes: tokens, timing, counts |
| `cost` | `#A8A8A8` | `#5F5F5F` | A cost below the threshold: plain, like any other number |
| `costHigh` | `#D9A94E` | `#8A5A00` | A cost above the threshold: the only cost that gets a colour |
| `add` / `addBg` | `#8FE0A5` / `#1F3326` | `#17662F` / `#E6F4EA` | Added lines in a diff |
| `del` / `delBg` | `#F0908A` / `#3A2323` | `#A3261E` / `#FBEAE8` | Removed lines in a diff, link warnings |

### Surfaces and text

| Token | Dark | Light | Usage |
|-------|------|-------|-------|
| `surface0` | `#1E1E1E` | `#FFFFFF` | The page |
| `surface1` | `#232323` | `#FAFAFA` | Floating panels (palette, tweaks, modals), the chat sidebar |
| `surface2` | `#2A2A2A` | `#F1F1F0` | Inputs, code blocks |
| `surface3` | `#363636` | `#E4E4E2` | Selected row, disabled button |
| `border` | `#303030` | `#E2E2E0` | Rules between groups and panes |
| `borderStrong` | `#4A4A4A` | `#C9C9C6` | Rule above the composer, secondary buttons, guide lines |
| `textPrimary` | `#DCDCDC` | `#1F1F1F` | Body text |
| `textSecondary` | `#A8A8A8` | `#5F5F5F` | Muted text, inactive links |
| `textDisabled` | `#909090` | `#6E6E6E` | Gutter labels, placeholders |

### Accents

One accent at a time, chosen in the Tweaks panel. Default is `blue`.

| Key | Dark | Light |
|-----|------|-------|
| `blue` | `#8FB0F8` | `#3557C9` |
| `steel` | `#7FB4CF` | `#2F6F8F` |
| `teal` | `#74DDD9` | `#0B7A76` |
| `amber` | `#D9A94E` | `#8A5A00` |
| `rose` | `#E79AB8` | `#A8325F` |

### Mode Priority

Dark is the primary design target. Light is kept working: design for dark first, verify in light.

---

## Typography

### Font Stacks

| Token | Stack | Usage |
|-------|-------|-------|
| `serif` | `'Source Serif 4', 'Iowan Old Style', Charter, Georgia, serif` | Text you read: answers, descriptions, page and section titles |
| `mono` | `'JetBrains Mono', 'JetBrainsMono Nerd Font', 'SF Mono', 'Fira Code', ui-monospace, Menlo, Consolas, monospace` | Text you typed, and all metadata |
| `theme.read` | `serif` or `mono` | The face of the assistant's answers; the "answers" tweak switches it |

No font files are bundled. The serif stack names faces that ship with macOS
and iOS; a locally installed Source Serif 4 is used when present. Trigger for
bundling a font: the GUI is used from a device that has none of them.

### Sizes

| Use | Face | Size / weight |
|-----|------|---------------|
| Page title | serif | about 32px / 600 |
| Section heading | serif | 18px / 600 |
| Answer text | `theme.read` | 17.5px serif, 14px mono; line height 1.6 |
| Your own turns, composer | mono | 14px |
| Tool lines, system lines | mono | 13px |
| Gutter labels, margin notes, status line | mono | 12px |

Nothing is set below 12px. No uppercase labels with letter-spacing.

---

## Layout

`JARVIS_MEASURE` in `tokens.ts`, mirrored by the `.jr-row` CSS in
`apps/gui/web/index.html`:

| Part | Width | Holds |
|------|-------|-------|
| Gutter | 72px | The time of a turn, a specialist's name, a date |
| Column | up to 640px | The text |
| Margin | the rest, page max 1000px | Tokens, cost, timing, who asked |

Below a pane width of 820px the margin drops under the text. That is a
container query on `.jr-pane`, because the chat pane shrinks when the sidebar
is open.

---

## Spacing

8px base unit. 10 tokens covering common spacing needs.

| Token | Value | Common Use |
|-------|-------|------------|
| `space.0` | `0` | Reset |
| `space.1` | `4px` | Tight inline gaps (icon to label) |
| `space.2` | `8px` | Default inline gap, padding within badges |
| `space.3` | `12px` | Compact vertical spacing |
| `space.4` | `16px` | Standard vertical spacing between elements |
| `space.6` | `24px` | Between turns |
| `space.8` | `32px` | Section spacing |
| `space.10` | `40px` | Large section breaks |
| `space.12` | `48px` | Panel padding |
| `space.16` | `64px` | Page-level margins |

---

## Border Radius

Small and rare. Most things have no box to round.

| Token | Value | Usage |
|-------|-------|-------|
| `radius.sm` | `4px` | Buttons, inputs, inline code, code blocks |
| `radius.md` | `4px` | Same as `sm` (kept so older call sites resolve) |
| `radius.lg` | `6px` | Floating panels: palette, tweaks, modals |

---

## Shadows

Only floating panels cast one (`0 8px 24px rgba(0,0,0,0.35)`), together with a
1px `borderStrong` outline. Nothing on the page itself has a shadow.

---

## Motion

Principles, not specifications. JARVIS is a productivity tool — animation serves orientation, not decoration.

### Guidelines

- **Streaming text**: Just append. No per-character animation, no typewriter effect. Text appears as tokens arrive from the API, exactly like the CLI. The stream IS the animation.
- **Transitions**: Fast. 100-150ms for state changes (hover, focus, expand/collapse). If the user can consciously perceive the animation, it's too slow.
- **Page transitions**: Instant content swap. No sliding panels, no page-turn effects.
- **Loading states**: The `Thinking...` spinner is the only animation that should be noticeable. It fills the gap before the first token — same as the CLI's `Spinner("dots")`.
- **Avoid**: Bounce, elastic easing, parallax, skeleton screens that shimmer, progress bars that fake progress.

### Easing

| Token | Value | Usage |
|-------|-------|-------|
| `ease.default` | `cubic-bezier(0.4, 0, 0.2, 1)` | General transitions |
| `duration.fast` | `100ms` | Hover, focus |
| `duration.normal` | `150ms` | Expand, collapse, state changes |

### Rule of Thumb

If you can't tell the animation is there, it's right.

---

## Z-Index Scale

| Token | Value | Usage |
|-------|-------|-------|
| `z.base` | `0` | Default content |
| `z.sticky` | `10` | Status bar, sticky headers |
| `z.dropdown` | `20` | Dropdowns, command palette |
| `z.modal` | `30` | Modal dialogs |
| `z.toast` | `40` | Toast notifications, error banners |

---

*These tokens are intentionally minimal. Add tokens when a real component needs them, not before. The goal is a shared vocabulary for design decisions, not an exhaustive specification.*

---

*Last updated: 2026-11-21*
