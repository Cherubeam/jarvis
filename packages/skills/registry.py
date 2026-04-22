"""
Skill registry — discovers skills by scanning for SKILL.md files.

Unlike the agent registry (which imports Python modules), skill discovery
is filesystem-based: any subdirectory of ``packages/skills/`` containing a
``SKILL.md`` file is a valid skill.

This means simple skills need zero Python code — just a SKILL.md file that
can also be used with Claude, ChatGPT, or any other LLM.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from packages.core.context_builder import parse_frontmatter

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class SkillMeta:
    """Metadata for a discovered skill."""

    name: str
    description: str
    command: str
    path: Path
    has_skill_py: bool


def discover_skills(skills_dir: Path | None = None) -> dict[str, SkillMeta]:
    """Scan for subdirectories containing SKILL.md files.

    Args:
        skills_dir: Directory to scan. Defaults to ``packages/skills/``.

    Returns:
        dict keyed by skill name, values are SkillMeta instances.
    """
    base = skills_dir or _SKILLS_DIR
    skills: dict[str, SkillMeta] = {}

    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith(("_", ".")):
            continue

        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue

        try:
            raw = skill_md.read_text(encoding="utf-8")
            frontmatter, _ = parse_frontmatter(raw)
        except Exception:
            logger.warning("Failed to parse SKILL.md in %s", child.name, exc_info=True)
            continue

        name = frontmatter.get("name", child.name)
        description = frontmatter.get("description", "")
        command = f"/{name}"

        # Check for optional skill.py (may override command)
        has_skill_py = (child / "skill.py").is_file()
        if has_skill_py:
            try:
                from packages.skills.base import _import_skill_module

                mod = _import_skill_module(child)
                config = getattr(mod, "SKILL_CONFIG", {})
                if "command" in config:
                    command = config["command"]
            except Exception:
                logger.warning(
                    "Failed to import skill.py for %s (discovery continues)",
                    name,
                    exc_info=True,
                )

        meta = SkillMeta(
            name=name,
            description=description,
            command=command,
            path=child,
            has_skill_py=has_skill_py,
        )
        skills[meta.name] = meta

    return skills


def get_skill_by_command(command: str, skills: dict[str, SkillMeta] | None = None) -> SkillMeta | None:
    """Look up a skill by its slash command.

    Args:
        command: The slash command string (e.g. ``"/content-evaluator"``).
        skills: Pre-discovered skills dict. If *None*, calls
            :func:`discover_skills` on the fly.

    Returns:
        The matching SkillMeta, or *None* if no skill handles this command.
    """
    if skills is None:
        skills = discover_skills()

    for meta in skills.values():
        if meta.command == command:
            return meta
    return None
