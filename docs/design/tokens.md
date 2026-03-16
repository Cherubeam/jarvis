# Design Tokens

> Framework-agnostic visual primitives for the JARVIS UI.
> Grounded in the existing terminal theme from `display.py` (`JARVIS_THEME`).
> No CSS, Tailwind, or SwiftUI — just values that any implementation can consume.

See also: [principles.md](principles.md) for design principles,
[voice-and-tone.md](voice-and-tone.md) for UI copy guidelines, [components.md](components.md) for the component inventory.

---

## Colors

### Semantic Roles

Mapped directly from the CLI theme (`JARVIS_THEME` in `apps/cli/display.py`):

| Role | CLI Style | Dark Mode | Light Mode | Usage |
|------|-----------|-----------|------------|-------|
| `color.user` | `bold green` | `#4ADE80` | `#16A34A` | User messages, input prompts, "You:" label |
| `color.assistant` | `bold cyan` | `#22D3EE` | `#0891B2` | Assistant messages, agent names, "JARVIS:" label |
| `color.tool` | `dim magenta` | `#C084FC` | `#9333EA` | Tool call badges, `[Tool: name]` labels |
| `color.error` | `bold red` | `#F87171` | `#DC2626` | Error messages, failed operations |
| `color.system` | `dim yellow` | `#FBBF24` | `#D97706` | System messages, warnings, informational text |
| `color.stats` | `dim` | `#9CA3AF` | `#6B7280` | Token counts, costs, latency — the stats line |

### Extended Palette

| Token | Dark Mode | Light Mode | Usage |
|-------|-----------|------------|-------|
| `color.cost` | `#F59E0B` | `#B45309` | Cost values (amber/gold — money is attention-worthy) |
| `color.cost.high` | `#EF4444` | `#DC2626` | Cost exceeding threshold (red — same as error) |
| `color.surface.primary` | `#111827` | `#FFFFFF` | Main background |
| `color.surface.secondary` | `#1F2937` | `#F3F4F6` | Cards, panels, secondary areas |
| `color.surface.elevated` | `#374151` | `#E5E7EB` | Modals, dropdowns, popovers |
| `color.border` | `#374151` | `#D1D5DB` | Dividers, card borders |
| `color.text.primary` | `#F9FAFB` | `#111827` | Body text |
| `color.text.secondary` | `#9CA3AF` | `#6B7280` | Muted text, labels, timestamps |
| `color.text.disabled` | `#4B5563` | `#9CA3AF` | Disabled controls |

### Mode Priority

Dark mode is the primary design target — JARVIS is a terminal-native tool and most users will prefer dark. Light mode is a secondary accommodation. Design for dark first, verify in light.

---

## Typography

### Scale

7-step scale. Sizes in `rem` (base = 16px).

| Token | Size | Line Height | Usage |
|-------|------|-------------|-------|
| `text.xs` | `0.75rem` (12px) | 1.5 | Fine print, timestamps |
| `text.sm` | `0.875rem` (14px) | 1.5 | Stats line, secondary labels, metadata |
| `text.base` | `1rem` (16px) | 1.625 | Body text, messages, input |
| `text.lg` | `1.125rem` (18px) | 1.5 | Section headers within messages |
| `text.xl` | `1.25rem` (20px) | 1.5 | Agent names, conversation titles |
| `text.2xl` | `1.5rem` (24px) | 1.33 | Page-level headers |
| `text.3xl` | `1.875rem` (30px) | 1.33 | Startup banner (rare) |

### Font Stacks

| Token | Stack | Usage |
|-------|-------|-------|
| `font.sans` | `system-ui, -apple-system, sans-serif` | Primary UI text |
| `font.mono` | `'SF Mono', 'JetBrains Mono', 'Fira Code', ui-monospace, monospace` | Code blocks, file paths, stats, token counts, costs |

Monospace is a first-class citizen, not an afterthought. File paths, costs, token counts, tool names, and code blocks all use `font.mono`. In a tool like JARVIS, monospace may appear more often than sans-serif.

### Weight

| Token | Value | Usage |
|-------|-------|-------|
| `font.weight.normal` | `400` | Body text |
| `font.weight.medium` | `500` | Labels, badges |
| `font.weight.bold` | `700` | Agent names ("JARVIS:"), emphasis, headings |

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
| `space.6` | `24px` | Between message bubbles |
| `space.8` | `32px` | Section spacing |
| `space.10` | `40px` | Large section breaks |
| `space.12` | `48px` | Panel padding |
| `space.16` | `64px` | Page-level margins |

---

## Border Radius

Three values. Slightly rounded, not pill-shaped. The aesthetic is technical, not playful.

| Token | Value | Usage |
|-------|-------|-------|
| `radius.sm` | `4px` | Badges, inline code, small elements |
| `radius.md` | `8px` | Cards, message bubbles, inputs |
| `radius.lg` | `12px` | Modals, large panels |

---

## Shadows

Two levels only. In dark mode, prefer subtle borders over shadows — shadows are nearly invisible on dark backgrounds.

| Token | Value (Light Mode) | Dark Mode Alternative | Usage |
|-------|-------------------|----------------------|-------|
| `shadow.low` | `0 1px 3px rgba(0,0,0,0.1)` | `1px solid color.border` | Cards, conversation items |
| `shadow.high` | `0 4px 12px rgba(0,0,0,0.15)` | `1px solid color.border` + `color.surface.elevated` bg | Modals, dropdowns, command palette |

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

*Last updated: 2026-03-16*
