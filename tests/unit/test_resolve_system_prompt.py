"""Tests for ``packages.agents.base.resolve_system_prompt``.

This is the pure helper extracted from ``agent_from_meta`` so the GUI
Context tab can render the same placeholder-expanded text the LLM sees
without instantiating a full agent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.agents.base import resolve_system_prompt


def _make_agent(tmp_path: Path, system_text: str, **prompts: str) -> Path:
    agent_dir = tmp_path / "agent"
    prompts_dir = agent_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system.md").write_text(system_text, encoding="utf-8")
    for name, content in prompts.items():
        (prompts_dir / f"{name}.md").write_text(content, encoding="utf-8")
    return agent_dir


def test_returns_system_md_content_unchanged_when_no_placeholders(tmp_path: Path) -> None:
    agent_dir = _make_agent(tmp_path, "You are a helpful assistant.")
    out = resolve_system_prompt(agent_dir)
    assert out == "You are a helpful assistant."


def test_missing_system_md_raises_file_not_found(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agent"
    (agent_dir / "prompts").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        resolve_system_prompt(agent_dir)


def test_placeholder_substitution_from_prompt_includes(tmp_path: Path) -> None:
    agent_dir = _make_agent(
        tmp_path,
        "Voice:\n{voice}\n\nRules:\n{rules}",
        voice="terse and precise",
        rules="no preamble",
    )
    out = resolve_system_prompt(
        agent_dir,
        prompt_includes={"voice": "voice", "rules": "rules"},
    )
    assert out == "Voice:\nterse and precise\n\nRules:\nno preamble"


def test_missing_include_file_renders_as_empty_string(tmp_path: Path) -> None:
    # Include declared but file doesn't exist anywhere → placeholder blanks.
    agent_dir = _make_agent(tmp_path, "Before {x} after.")
    out = resolve_system_prompt(agent_dir, prompt_includes={"x": "does-not-exist"})
    assert out == "Before  after."


def test_override_with_empty_string_blanks_placeholder_and_skips_file(tmp_path: Path) -> None:
    agent_dir = _make_agent(
        tmp_path,
        "Hello {name}!",
        realname="Marco",
    )
    out = resolve_system_prompt(
        agent_dir,
        prompt_includes={"name": "realname"},
        prompt_includes_override={"name": ""},
    )
    assert out == "Hello !"


def test_override_replaces_filename_for_placeholder(tmp_path: Path) -> None:
    agent_dir = _make_agent(
        tmp_path,
        "Voice: {voice}",
        default_voice="formal",
        custom_voice="casual",
    )
    out = resolve_system_prompt(
        agent_dir,
        prompt_includes={"voice": "default_voice"},
        prompt_includes_override={"voice": "custom_voice"},
    )
    assert out == "Voice: casual"


def test_override_adds_new_placeholder_not_in_meta(tmp_path: Path) -> None:
    # Override can introduce a placeholder that wasn't declared in meta.
    agent_dir = _make_agent(
        tmp_path,
        "Tone: {tone}",
        tone="direct",
    )
    out = resolve_system_prompt(
        agent_dir,
        prompt_includes=None,
        prompt_includes_override={"tone": "tone"},
    )
    assert out == "Tone: direct"


def test_none_and_empty_includes_both_work(tmp_path: Path) -> None:
    agent_dir = _make_agent(tmp_path, "static")
    assert resolve_system_prompt(agent_dir, prompt_includes=None) == "static"
    assert resolve_system_prompt(agent_dir, prompt_includes={}) == "static"
