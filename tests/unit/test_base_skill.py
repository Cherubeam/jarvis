"""
Unit tests for BaseSkill — from_skill_md() and run().
"""

import pytest
from unittest.mock import Mock
from pathlib import Path

from packages.skills.base import BaseSkill, SkillConfig, _import_skill_module
from packages.core.llm_client import LLMClient, TokenUsage
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.telemetry.metrics import ResponseMetrics


def _make_stream_result(text: str = "response") -> StreamResult:
    return StreamResult(
        text=text,
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        cost_usd=0.001,
        metrics=ResponseMetrics(
            ttft_ms=50,
            total_latency_ms=200,
            prompt_tokens=10,
            completion_tokens=5,
        ),
    )


@pytest.mark.unit
class TestBaseSkillRun:
    """Tests for BaseSkill.run()."""

    def _make_skill(self) -> BaseSkill:
        config = SkillConfig(
            name="test-skill",
            description="a test skill",
            system_prompt="You are a test skill.",
            command="/test-skill",
            path=Path("/tmp/test"),
        )
        client = Mock(spec=LLMClient)
        return BaseSkill(config, client)

    def test_run_builds_correct_messages(self):
        skill = self._make_skill()
        handler = Mock(spec=StreamHandler)
        handler.stream.return_value = _make_stream_result()

        skill.run("do something", handler)

        call_args = handler.stream.call_args
        messages = call_args[0][0]
        assert messages[0] == {"role": "system", "content": "You are a test skill."}
        assert messages[1] == {"role": "user", "content": "do something"}

    def test_run_with_messages_override(self):
        skill = self._make_skill()
        handler = Mock(spec=StreamHandler)
        handler.stream.return_value = _make_stream_result()

        history = [{"role": "user", "content": "earlier"}]
        skill.run("now", handler, messages_override=history)

        call_args = handler.stream.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[1] == {"role": "user", "content": "earlier"}
        assert messages[2] == {"role": "user", "content": "now"}

    def test_run_passes_print_chunks(self):
        skill = self._make_skill()
        handler = Mock(spec=StreamHandler)
        handler.stream.return_value = _make_stream_result()

        skill.run("hello", handler, print_chunks=True)
        assert handler.stream.call_args[1]["print_chunks"] is True

    def test_run_returns_stream_result(self):
        skill = self._make_skill()
        handler = Mock(spec=StreamHandler)
        expected = _make_stream_result("test output")
        handler.stream.return_value = expected

        result = skill.run("hello", handler)
        assert result is expected

    def test_run_passes_none_tool_registry_when_empty(self):
        skill = self._make_skill()
        handler = Mock(spec=StreamHandler)
        handler.stream.return_value = _make_stream_result()

        skill.run("hello", handler)
        assert handler.stream.call_args[1]["tool_registry"] is None


_SKILLS_ROOT = Path(__file__).parent.parent.parent / "packages" / "skills"
_REAL_SKILLS_PRESENT = (
    _SKILLS_ROOT / "technical-humanist-image-architect" / "SKILL.md"
).exists() and (_SKILLS_ROOT / "content-evaluator" / "SKILL.md").exists()


@pytest.mark.unit
@pytest.mark.skipif(
    not _REAL_SKILLS_PRESENT,
    reason="Real skill files are user-local symlinks not tracked in git; skipped on CI",
)
class TestBaseSkillFromSkillMd:
    """Tests for BaseSkill.from_skill_md()."""

    def test_loads_from_real_technical_humanist_image_architect(self):
        skill_dir = (
            Path(__file__).parent.parent.parent
            / "packages"
            / "skills"
            / "technical-humanist-image-architect"
        )
        client = Mock(spec=LLMClient)

        skill = BaseSkill.from_skill_md(skill_dir, client)

        assert skill.name == "technical-humanist-image-architect"
        assert "header image" in skill.description.lower()
        assert skill.command == "/technical-humanist-image-architect"
        assert "Technical Humanist" in skill.config.system_prompt

    def test_loads_from_real_content_evaluator(self):
        skill_dir = (
            Path(__file__).parent.parent.parent / "packages" / "skills" / "content-evaluator"
        )
        client = Mock(spec=LLMClient)

        skill = BaseSkill.from_skill_md(skill_dir, client)

        assert skill.name == "content-evaluator"
        assert "evaluates" in skill.description.lower()
        assert skill.command == "/content-evaluator"

    def test_content_evaluator_has_custom_temperature(self):
        skill_dir = (
            Path(__file__).parent.parent.parent / "packages" / "skills" / "content-evaluator"
        )
        client = Mock(spec=LLMClient)

        skill = BaseSkill.from_skill_md(skill_dir, client)
        assert skill.config.temperature == 0.8

    def test_model_override_takes_precedence(self):
        skill_dir = (
            Path(__file__).parent.parent.parent
            / "packages"
            / "skills"
            / "technical-humanist-image-architect"
        )
        client = Mock(spec=LLMClient)

        skill = BaseSkill.from_skill_md(skill_dir, client, model="custom/model")
        assert skill.config.model == "custom/model"

    def test_from_tmp_skill_md_only(self, tmp_path):
        skill_dir = tmp_path / "minimal"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: minimal\ndescription: Minimal skill\n---\n# Minimal\nDo the thing."
        )
        client = Mock(spec=LLMClient)

        skill = BaseSkill.from_skill_md(skill_dir, client)

        assert skill.name == "minimal"
        assert skill.description == "Minimal skill"
        assert skill.command == "/minimal"
        assert "# Minimal" in skill.config.system_prompt
        assert "Do the thing." in skill.config.system_prompt

    def test_from_tmp_no_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "bare"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Just markdown\nNo frontmatter here.")
        client = Mock(spec=LLMClient)

        skill = BaseSkill.from_skill_md(skill_dir, client)

        # Falls back to directory name
        assert skill.name == "bare"
        assert skill.description == ""
        assert "# Just markdown" in skill.config.system_prompt

    def test_missing_skill_md_raises(self, tmp_path):
        skill_dir = tmp_path / "empty"
        skill_dir.mkdir()
        client = Mock(spec=LLMClient)

        with pytest.raises(FileNotFoundError):
            BaseSkill.from_skill_md(skill_dir, client)

    def test_properties(self):
        config = SkillConfig(
            name="props",
            description="test properties",
            system_prompt="prompt",
            command="/props",
            path=Path("/tmp"),
        )
        client = Mock(spec=LLMClient)
        skill = BaseSkill(config, client)

        assert skill.name == "props"
        assert skill.description == "test properties"
        assert skill.command == "/props"


@pytest.mark.unit
class TestImportSkillModuleSymlink:
    """Tests for _import_skill_module with symlinked skill directories."""

    def test_symlinked_skill_dir_loads_skill_py(self, tmp_path):
        """Verify _import_skill_module works when skill_dir is a symlink
        pointing outside the packages/ tree (e.g. a private skills repo)."""
        # Create a fake skill.py outside the packages tree
        external = tmp_path / "external-repo" / "my-skill"
        external.mkdir(parents=True)
        (external / "skill.py").write_text(
            'SKILL_CONFIG = {"temperature": 0.9, "max_tokens": 2048}\n'
        )

        # Create a packages/skills/ tree with a symlink to the external skill
        packages = tmp_path / "packages" / "skills" / "my-skill"
        packages.parent.mkdir(parents=True)
        packages.symlink_to(external)

        # Import via the symlink path — should succeed
        module = _import_skill_module(packages)
        assert module.SKILL_CONFIG["temperature"] == 0.9
        assert module.SKILL_CONFIG["max_tokens"] == 2048

    def test_non_packages_path_raises_import_error(self, tmp_path):
        """Paths that don't contain 'packages' should raise ImportError."""
        bogus = tmp_path / "somewhere" / "else"
        bogus.mkdir(parents=True)
        (bogus / "skill.py").write_text("SKILL_CONFIG = {}\n")

        with pytest.raises(ImportError, match="Cannot determine module path"):
            _import_skill_module(bogus)
