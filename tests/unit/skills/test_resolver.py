"""
Unit tests for the skill resolver module.
"""

import logging
from pathlib import Path

import pytest

from packages.core.tools.base import ToolDefinition
from packages.skills.registry import SkillMeta
from packages.skills.resolver import ResolvedSkills, resolve_skills


def _make_skill_meta(name: str, path: Path, has_skill_py: bool = False) -> SkillMeta:
    return SkillMeta(
        name=name,
        description=f"{name} description",
        command=f"/{name}",
        path=path,
        has_skill_py=has_skill_py,
    )


def _dummy_tool(name: str = "card_search") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="Search cards",
        parameters={"type": "object", "properties": {}},
        execute=lambda: "ok",
    )


@pytest.mark.unit
class TestResolveSkillsSimple:
    """Simple skill resolution — SKILL.md body is extracted."""

    def test_simple_skill_prompt_appendix(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A skill\n---\n\n# My Skill\n\nDo things well."
        )
        registry = {"my-skill": _make_skill_meta("my-skill", skill_dir)}

        result = resolve_skills(["my-skill"], registry)

        assert "# My Skill" in result.prompt_appendix
        assert "Do things well." in result.prompt_appendix
        assert result.deck_names == []
        assert result.tools == []

    def test_simple_skill_strips_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n\nBody content only.")
        registry = {"test-skill": _make_skill_meta("test-skill", skill_dir)}

        result = resolve_skills(["test-skill"], registry)

        assert "---" not in result.prompt_appendix
        assert "Body content only." in result.prompt_appendix


@pytest.mark.unit
class TestResolveSkillsDeck:
    """Deck-skill resolution — deck.yaml triggers deck_names + tool."""

    def test_deck_skill_populates_deck_names(self, tmp_path):
        skill_dir = tmp_path / "tactics"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: tactics\n---\n\nTactics.")
        (skill_dir / "deck.yaml").write_text("name: tactics\n")
        registry = {"tactics": _make_skill_meta("tactics", skill_dir)}
        tool = _dummy_tool()

        result = resolve_skills(["tactics"], registry, card_search_tool=tool)

        assert "tactics" in result.deck_names
        assert tool in result.tools

    def test_deck_skill_without_card_search_tool_warns(self, tmp_path, caplog):
        skill_dir = tmp_path / "tactics"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: tactics\n---\n\nTactics.")
        (skill_dir / "deck.yaml").write_text("name: tactics\n")
        registry = {"tactics": _make_skill_meta("tactics", skill_dir)}

        with caplog.at_level(logging.WARNING):
            result = resolve_skills(["tactics"], registry, card_search_tool=None)

        assert "tactics" in result.deck_names
        assert result.tools == []
        assert "card_search_tool" in caplog.text


@pytest.mark.unit
class TestResolveSkillsMixed:
    """Mixed skills — both simple and deck."""

    def test_mixed_skills_produce_prompt_and_tools(self, tmp_path):
        # Simple skill
        simple_dir = tmp_path / "simple"
        simple_dir.mkdir()
        (simple_dir / "SKILL.md").write_text("---\nname: simple\n---\n\nSimple body.")

        # Deck skill
        deck_dir = tmp_path / "deck"
        deck_dir.mkdir()
        (deck_dir / "SKILL.md").write_text("---\nname: deck\n---\n\nDeck body.")
        (deck_dir / "deck.yaml").write_text("name: deck\n")

        registry = {
            "simple": _make_skill_meta("simple", simple_dir),
            "deck": _make_skill_meta("deck", deck_dir),
        }
        tool = _dummy_tool()

        result = resolve_skills(["simple", "deck"], registry, card_search_tool=tool)

        assert "Simple body." in result.prompt_appendix
        assert "deck" in result.deck_names
        assert tool in result.tools
        assert "Bound Deck-Skills" in result.prompt_appendix


@pytest.mark.unit
class TestResolveSkillsEdgeCases:
    """Edge cases: unknown skills, empty list."""

    def test_unknown_skill_warns_and_skips(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = resolve_skills(["nonexistent"], {})

        assert result.prompt_appendix == ""
        assert result.deck_names == []
        assert result.tools == []
        assert "Unknown skill" in caplog.text

    def test_empty_list_returns_empty(self):
        result = resolve_skills([], {})

        assert result == ResolvedSkills()

    def test_skill_with_missing_skill_md_skips(self, tmp_path, caplog):
        """Skill dir exists but SKILL.md is missing — graceful skip."""
        skill_dir = tmp_path / "broken"
        skill_dir.mkdir()
        registry = {"broken": _make_skill_meta("broken", skill_dir)}

        with caplog.at_level(logging.WARNING):
            result = resolve_skills(["broken"], registry)

        assert result.prompt_appendix == ""
        assert "SKILL.md not found" in caplog.text

    def test_multiple_deck_skills_share_one_tool(self, tmp_path):
        """Multiple deck-skills get one card_search_tool, not duplicates."""
        for name in ("deck-a", "deck-b"):
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n\n{name} body.")
            (d / "deck.yaml").write_text(f"name: {name}\n")

        registry = {
            "deck-a": _make_skill_meta("deck-a", tmp_path / "deck-a"),
            "deck-b": _make_skill_meta("deck-b", tmp_path / "deck-b"),
        }
        tool = _dummy_tool()

        result = resolve_skills(["deck-a", "deck-b"], registry, card_search_tool=tool)

        assert len(result.tools) == 1
        assert len(result.deck_names) == 2
