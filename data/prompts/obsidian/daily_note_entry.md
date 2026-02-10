# Daily Note Entry Generation

You are generating a brief end-of-day summary entry for an Obsidian daily note. This entry will be appended to a `> [!JARVIS]` callout block.

## Instructions

1. **Summarize the day's conversation highlights** — key topics discussed, decisions made, and insights gained.
2. **Note connections** — link to related concepts, people, or projects using `[[wikilinks]]` where appropriate.
3. **Surface patterns** — if recurring themes or ideas appear across conversations, mention them.
4. **Be concise** — aim for 3-8 lines. This is a quick reference, not a full transcript.
5. **Use bullet points** for individual items.
6. **Write in first person** from the user's perspective (e.g., "Explored X", "Decided to Y").

## Format

Write plain markdown (no callout prefix — that will be added automatically). Example:

- Explored Obsidian vault integration architecture for JARVIS
- Decided on five-module design: vault, callout, diff, writer, prompts
- Key insight: [[Confirmation Handler]] pattern enables GUI-readiness without complexity
- Connected to [[Personal AI Assistant]] roadmap phase 3

## Context

You will receive:
- The current conversation history
- The existing daily note content (if any)
- Today's date

Generate only the entry text. Do not include the callout header or ">" prefixes.
