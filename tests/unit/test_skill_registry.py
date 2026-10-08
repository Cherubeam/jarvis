"""
Unit tests for skill registry — filesystem-based SKILL.md discovery.
"""

from pathlib import Path

import pytest

from packages.skills.registry import SkillMeta, discover_skills, get_skill_by_command, import_skill_module

_SKILLS_ROOT = Path(__file__).parent.parent.parent / "packages" / "skills"
_REAL_SKILLS_PRESENT = (_SKILLS_ROOT / "technical-humanist-image-architect" / "SKILL.md").exists() and (
    _SKILLS_ROOT / "content-evaluator" / "SKILL.md"
).exists()
_REAL_SKILLS_SKIP_REASON = "Real skill files are user-local symlinks not tracked in git; skipped on CI"


@pytest.mark.unit
@pytest.mark.skipif(not _REAL_SKILLS_PRESENT, reason=_REAL_SKILLS_SKIP_REASON)
class TestDiscoverRealSkills:
    """Tests for discover_skills() that assume the user's local skills are present."""

    def test_discovers_technical_humanist_image_architect(self):
        skills = discover_skills()
        assert "technical-humanist-image-architect" in skills

    def test_discovers_content_evaluator(self):
        skills = discover_skills()
        assert "content-evaluator" in skills

    def test_technical_humanist_image_architect_has_no_skill_py(self):
        skills = discover_skills()
        assert skills["technical-humanist-image-architect"].has_skill_py is False

    def test_content_evaluator_has_skill_py(self):
        skills = discover_skills()
        assert skills["content-evaluator"].has_skill_py is True

    def test_returns_skill_meta_instances(self):
        skills = discover_skills()
        for meta in skills.values():
            assert isinstance(meta, SkillMeta)
            assert meta.name
            assert meta.command.startswith("/")
            assert isinstance(meta.path, Path)

    def test_commands_derived_from_name(self):
        skills = discover_skills()
        assert skills["technical-humanist-image-architect"].command == "/technical-humanist-image-architect"
        assert skills["content-evaluator"].command == "/content-evaluator"

    def test_descriptions_from_frontmatter(self):
        skills = discover_skills()
        assert "header image" in skills["technical-humanist-image-architect"].description.lower()
        assert "evaluates" in skills["content-evaluator"].description.lower()


@pytest.mark.unit
class TestDiscoverSkills:
    """Tests for discover_skills() using self-contained tmp_path fixtures."""

    def test_skips_directories_without_skill_md(self, tmp_path):
        (tmp_path / "no_skill").mkdir()
        (tmp_path / "no_skill" / "some_file.py").write_text("pass")
        skills = discover_skills(tmp_path)
        assert len(skills) == 0

    def test_skips_hidden_directories(self, tmp_path):
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "SKILL.md").write_text("---\nname: hidden\ndescription: nope\n---\n# H")
        skills = discover_skills(tmp_path)
        assert len(skills) == 0

    def test_skips_underscore_directories(self, tmp_path):
        under = tmp_path / "_internal"
        under.mkdir()
        (under / "SKILL.md").write_text("---\nname: internal\ndescription: nope\n---\n# I")
        skills = discover_skills(tmp_path)
        assert len(skills) == 0

    def test_discovers_skill_md_only_skill(self, tmp_path):
        skill_dir = tmp_path / "simple"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: simple-test\ndescription: A test skill\n---\n# Simple\nDo stuff."
        )
        skills = discover_skills(tmp_path)
        assert "simple-test" in skills
        assert skills["simple-test"].has_skill_py is False
        assert skills["simple-test"].command == "/simple-test"

    def test_falls_back_to_dirname_when_no_name_in_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: No name field\n---\n# Stuff")
        skills = discover_skills(tmp_path)
        assert "my_skill" in skills

    def test_handles_empty_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "bare"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Just a heading\nNo frontmatter.")
        skills = discover_skills(tmp_path)
        # Falls back to directory name
        assert "bare" in skills
        assert skills["bare"].description == ""


@pytest.mark.unit
@pytest.mark.skipif(not _REAL_SKILLS_PRESENT, reason=_REAL_SKILLS_SKIP_REASON)
class TestGetSkillByCommand:
    """Tests for get_skill_by_command() — all require the user's local skills."""

    def test_finds_technical_humanist_image_architect(self):
        skills = discover_skills()
        meta = get_skill_by_command("/technical-humanist-image-architect", skills)
        assert meta is not None
        assert meta.name == "technical-humanist-image-architect"

    def test_finds_content_evaluator(self):
        skills = discover_skills()
        meta = get_skill_by_command("/content-evaluator", skills)
        assert meta is not None
        assert meta.name == "content-evaluator"

    def test_returns_none_for_unknown_command(self):
        skills = discover_skills()
        meta = get_skill_by_command("/nonexistent", skills)
        assert meta is None

    def test_discovers_skills_if_none_passed(self):
        meta = get_skill_by_command("/technical-humanist-image-architect")
        assert meta is not None
        assert meta.name == "technical-humanist-image-architect"


@pytest.mark.unit
class TestImportSkillModuleSymlink:
    """Tests for import_skill_module with symlinked skill directories."""

    def test_symlinked_skill_dir_loads_skill_py(self, tmp_path):
        """Verify import_skill_module works when skill_dir is a symlink
        pointing outside the packages/ tree (e.g. a private skills repo)."""
        # Create a fake skill.py outside the packages tree
        external = tmp_path / "external-repo" / "my-skill"
        external.mkdir(parents=True)
        (external / "skill.py").write_text('SKILL_CONFIG = {"temperature": 0.9, "max_tokens": 2048}\n')

        # Create a packages/skills/ tree with a symlink to the external skill
        packages = tmp_path / "packages" / "skills" / "my-skill"
        packages.parent.mkdir(parents=True)
        packages.symlink_to(external)

        # Import via the symlink path — should succeed
        module = import_skill_module(packages)
        assert module.SKILL_CONFIG["temperature"] == 0.9
        assert module.SKILL_CONFIG["max_tokens"] == 2048

    def test_non_packages_path_raises_import_error(self, tmp_path):
        """Paths that don't contain 'packages' should raise ImportError."""
        bogus = tmp_path / "somewhere" / "else"
        bogus.mkdir(parents=True)
        (bogus / "skill.py").write_text("SKILL_CONFIG = {}\n")

        with pytest.raises(ImportError, match="Cannot determine module path"):
            import_skill_module(bogus)
