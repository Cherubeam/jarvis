"""Tests for packages/agents/prompt_includes.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.agents.prompt_includes import (
    AgentIncludeIssue,
    IncludeResolution,
    IncludeStatus,
    format_issue,
    resolve_include,
    validate_agent_includes,
)

# ---------- Fixtures ----------


def _make_agent(
    tmp_path: Path,
    name: str = "test_agent",
    prompt_includes: dict[str, str] | None = None,
) -> Path:
    """Create a minimal agent directory and return the meta.yaml path."""
    agent_dir = tmp_path / name
    (agent_dir / "prompts").mkdir(parents=True)
    lines = [f"name: {name}", "description: test", f"command: /{name}"]
    if prompt_includes:
        lines.append("prompt_includes:")
        for placeholder, filename in prompt_includes.items():
            lines.append(f"  {placeholder}: {filename}")
    meta = agent_dir / "meta.yaml"
    meta.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return meta


def _make_shared_dir(tmp_path: Path) -> Path:
    shared = tmp_path / "_shared" / "prompts"
    shared.mkdir(parents=True)
    return shared


# ---------- resolve_include ----------


@pytest.mark.unit
class TestResolveInclude:
    def test_finds_local_md_first(self, tmp_path: Path):
        meta = _make_agent(tmp_path)
        agent_dir = meta.parent
        shared = _make_shared_dir(tmp_path)
        (agent_dir / "prompts" / "voice.md").write_text("LOCAL", encoding="utf-8")
        (shared / "voice.md").write_text("SHARED", encoding="utf-8")

        res = resolve_include(agent_dir, "voice", shared)

        assert res.status is IncludeStatus.FOUND_LOCAL
        assert res.path is not None and res.path.read_text() == "LOCAL"
        assert res.is_canonical is True
        assert res.is_example is False
        assert res.is_missing is False

    def test_falls_back_to_shared_md(self, tmp_path: Path):
        meta = _make_agent(tmp_path)
        agent_dir = meta.parent
        shared = _make_shared_dir(tmp_path)
        (shared / "voice.md").write_text("SHARED", encoding="utf-8")

        res = resolve_include(agent_dir, "voice", shared)

        assert res.status is IncludeStatus.FOUND_SHARED
        assert res.path is not None and res.path.read_text() == "SHARED"
        assert res.is_canonical is True

    def test_falls_back_to_local_example_before_shared_example(self, tmp_path: Path):
        meta = _make_agent(tmp_path)
        agent_dir = meta.parent
        shared = _make_shared_dir(tmp_path)
        (agent_dir / "prompts" / "voice.md.example").write_text("LOCAL_EXAMPLE", encoding="utf-8")
        (shared / "voice.md.example").write_text("SHARED_EXAMPLE", encoding="utf-8")

        res = resolve_include(agent_dir, "voice", shared)

        assert res.status is IncludeStatus.FOUND_LOCAL_EXAMPLE
        assert res.path is not None and res.path.read_text() == "LOCAL_EXAMPLE"
        assert res.is_example is True
        assert res.is_canonical is False

    def test_falls_back_to_shared_example(self, tmp_path: Path):
        meta = _make_agent(tmp_path)
        agent_dir = meta.parent
        shared = _make_shared_dir(tmp_path)
        (shared / "voice.md.example").write_text("SHARED_EXAMPLE", encoding="utf-8")

        res = resolve_include(agent_dir, "voice", shared)

        assert res.status is IncludeStatus.FOUND_SHARED_EXAMPLE
        assert res.path is not None and res.path.read_text() == "SHARED_EXAMPLE"
        assert res.is_example is True

    def test_returns_missing_when_nothing_found(self, tmp_path: Path):
        meta = _make_agent(tmp_path)
        agent_dir = meta.parent
        shared = _make_shared_dir(tmp_path)

        res = resolve_include(agent_dir, "voice", shared)

        assert res.status is IncludeStatus.MISSING
        assert res.path is None
        assert res.is_missing is True
        assert res.is_canonical is False

    def test_md_takes_precedence_over_example(self, tmp_path: Path):
        """Canonical .md beats a same-directory .md.example."""
        meta = _make_agent(tmp_path)
        agent_dir = meta.parent
        shared = _make_shared_dir(tmp_path)
        (agent_dir / "prompts" / "voice.md").write_text("REAL", encoding="utf-8")
        (agent_dir / "prompts" / "voice.md.example").write_text("EXAMPLE", encoding="utf-8")

        res = resolve_include(agent_dir, "voice", shared)

        assert res.status is IncludeStatus.FOUND_LOCAL
        assert res.path is not None and res.path.read_text() == "REAL"


# ---------- validate_agent_includes ----------


@pytest.mark.unit
class TestValidateAgentIncludes:
    def test_canonical_hits_are_silent(self, tmp_path: Path):
        shared = _make_shared_dir(tmp_path)
        (shared / "voice.md").write_text("ok", encoding="utf-8")
        meta = _make_agent(tmp_path, prompt_includes={"voice_profile": "voice"})

        issues = validate_agent_includes([meta], shared_dir=shared)

        assert issues == []

    def test_flags_missing_include(self, tmp_path: Path):
        shared = _make_shared_dir(tmp_path)
        meta = _make_agent(tmp_path, prompt_includes={"voice_profile": "missing"})

        issues = validate_agent_includes([meta], shared_dir=shared)

        assert len(issues) == 1
        assert issues[0].agent_name == "test_agent"
        assert issues[0].placeholder == "voice_profile"
        assert issues[0].filename == "missing"
        assert issues[0].resolution.is_missing is True

    def test_flags_example_fallback(self, tmp_path: Path):
        shared = _make_shared_dir(tmp_path)
        meta = _make_agent(tmp_path, prompt_includes={"voice_profile": "voice"})
        (meta.parent / "prompts" / "voice.md.example").write_text("EXAMPLE", encoding="utf-8")

        issues = validate_agent_includes([meta], shared_dir=shared)

        assert len(issues) == 1
        assert issues[0].resolution.is_example is True
        assert issues[0].resolution.status is IncludeStatus.FOUND_LOCAL_EXAMPLE

    def test_agent_without_prompt_includes_is_skipped(self, tmp_path: Path):
        shared = _make_shared_dir(tmp_path)
        meta = _make_agent(tmp_path)

        issues = validate_agent_includes([meta], shared_dir=shared)

        assert issues == []

    def test_malformed_meta_yaml_is_skipped(self, tmp_path: Path):
        shared = _make_shared_dir(tmp_path)
        bad = tmp_path / "broken" / "meta.yaml"
        bad.parent.mkdir(parents=True)
        bad.write_text("not: valid: yaml: [", encoding="utf-8")

        issues = validate_agent_includes([bad], shared_dir=shared)

        assert issues == []

    def test_reports_one_issue_per_include(self, tmp_path: Path):
        shared = _make_shared_dir(tmp_path)
        meta = _make_agent(
            tmp_path,
            prompt_includes={"voice_profile": "voice", "anti_patterns": "anti"},
        )

        issues = validate_agent_includes([meta], shared_dir=shared)

        assert len(issues) == 2
        placeholders = {i.placeholder for i in issues}
        assert placeholders == {"voice_profile", "anti_patterns"}


# ---------- format_issue ----------


@pytest.mark.unit
class TestFormatIssue:
    def test_missing_message_is_actionable(self):
        issue = AgentIncludeIssue(
            agent_name="writer",
            placeholder="voice_profile",
            filename="voice-profile",
            resolution=IncludeResolution(None, IncludeStatus.MISSING),
        )
        msg = format_issue(issue)
        assert "writer" in msg
        assert "voice_profile" in msg
        assert "voice-profile.md" in msg
        assert "render as empty" in msg

    def test_example_message_names_fallback_file(self, tmp_path: Path):
        fallback = tmp_path / "voice-profile.md.example"
        fallback.touch()
        issue = AgentIncludeIssue(
            agent_name="writer",
            placeholder="voice_profile",
            filename="voice-profile",
            resolution=IncludeResolution(fallback, IncludeStatus.FOUND_LOCAL_EXAMPLE),
        )
        msg = format_issue(issue)
        assert "writer" in msg
        assert "voice-profile.md.example" in msg
        assert "falling back" in msg
