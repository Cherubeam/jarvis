"""
Content Evaluator — JARVIS execution config.

Loads the evaluation rubric from resources/ and configures temperature
for more opinionated feedback.
"""

from pathlib import Path

_RESOURCES = Path(__file__).parent / "resources"


def _load_rubric() -> str:
    """Load the evaluation rubric resource."""
    rubric_path = _RESOURCES / "rubric.md"
    if rubric_path.is_file():
        return rubric_path.read_text(encoding="utf-8")
    return ""


# SKILL_CONFIG — discovered by BaseSkill.from_skill_md()
SKILL_CONFIG: dict = {
    "temperature": 0.8,
    "max_tokens": 4096,
}
