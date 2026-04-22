"""
Skill resolver — resolves skill names into prompt content and tools.

Given a list of skill names and a skill registry, produces:
- Concatenated SKILL.md bodies for simple skills (prompt appendix)
- Deck-skill names and card search tools for deck-skills
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from packages.core.context_builder import parse_frontmatter
from packages.core.tools.base import ToolDefinition
from packages.skills.registry import SkillMeta

logger = logging.getLogger(__name__)


@dataclass
class ResolvedSkills:
    """Result of resolving skill names into prompt content and tools."""

    prompt_appendix: str = ""
    deck_names: list[str] = field(default_factory=list)
    tools: list[ToolDefinition] = field(default_factory=list)


def resolve_skills(
    skill_names: list[str],
    skill_registry: dict[str, SkillMeta],
    card_search_tool: ToolDefinition | None = None,
) -> ResolvedSkills:
    """Resolve skill names into prompt content and tools.

    Args:
        skill_names: List of skill names to resolve.
        skill_registry: Registry from :func:`discover_skills`.
        card_search_tool: Optional card search tool for deck-skills.

    Returns:
        A :class:`ResolvedSkills` with prompt text, deck names, and tools.
    """
    prompt_parts: list[str] = []
    deck_names: list[str] = []

    for name in skill_names:
        meta = skill_registry.get(name)
        if meta is None:
            logger.warning("Unknown skill '%s' — skipping.", name)
            continue

        deck_yaml = meta.path / "deck.yaml"
        if deck_yaml.is_file():
            # Deck-skill: register name for prompt hint
            deck_names.append(name)
        else:
            # Simple skill: read SKILL.md body (strip frontmatter)
            skill_md = meta.path / "SKILL.md"
            if not skill_md.is_file():
                logger.warning("SKILL.md not found for '%s' — skipping.", name)
                continue
            raw = skill_md.read_text(encoding="utf-8")
            _, body = parse_frontmatter(raw)
            if body.strip():
                prompt_parts.append(body.strip())

    # Build tools list
    tools: list[ToolDefinition] = []
    if deck_names and card_search_tool is not None:
        tools.append(card_search_tool)
    elif deck_names and card_search_tool is None:
        logger.warning(
            "Deck-skills bound (%s) but no card_search_tool available — card search will not be available.",
            ", ".join(deck_names),
        )

    # Build prompt appendix
    prompt_appendix = ""
    if prompt_parts:
        prompt_appendix = "\n\n---\n\n".join(prompt_parts)

    if deck_names:
        deck_hint = (
            "\n\n## Bound Deck-Skills\n\n"
            "You have access to the following card decks via the card search tool:\n"
            + "\n".join(f"- {d}" for d in deck_names)
        )
        prompt_appendix = prompt_appendix + deck_hint if prompt_appendix else deck_hint.lstrip("\n")

    return ResolvedSkills(
        prompt_appendix=prompt_appendix,
        deck_names=deck_names,
        tools=tools,
    )
