"""Tests for ``apps.gui.server.agents.prompt_stats``."""

from __future__ import annotations

from pathlib import Path

from apps.gui.server.agents.prompt_stats import (
    approx_tokens,
    compute_stats,
    include_status_rows,
)


def _make_agent(tmp_path: Path, system_text: str, **prompts: str) -> Path:
    agent_dir = tmp_path / "agent"
    prompts_dir = agent_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system.md").write_text(system_text, encoding="utf-8")
    for name, content in prompts.items():
        # Allow callers to distinguish .md from .md.example via a trailing
        # ".example" suffix after the name (e.g. "voice.example": "...").
        if name.endswith("_example"):
            stem = name[: -len("_example")]
            (prompts_dir / f"{stem}.md.example").write_text(content, encoding="utf-8")
        else:
            (prompts_dir / f"{name}.md").write_text(content, encoding="utf-8")
    return agent_dir


def test_approx_tokens_uses_utf8_bytes_over_four() -> None:
    assert approx_tokens("") == 0
    assert approx_tokens("abcd") == 1
    # "ü" = 2 bytes in UTF-8, so "üüüü" = 8 bytes → 2 tokens.
    assert approx_tokens("üüüü") == 2


def test_compute_stats_for_plain_system_md(tmp_path: Path) -> None:
    agent_dir = _make_agent(tmp_path, "line one\nline two\nline three")
    stats = compute_stats(
        system_prompt_path=agent_dir / "prompts" / "system.md",
        agent_dir=agent_dir,
        prompt_includes=None,
        snapshot_count=3,
    )
    assert stats.char_count == len("line one\nline two\nline three")
    assert stats.line_count == 3
    assert stats.token_estimate == len(b"line one\nline two\nline three") // 4
    assert stats.token_estimate_method == "len_utf8_over_4"
    assert stats.snapshot_count == 3
    assert stats.last_modified_iso is not None
    assert stats.prompt_includes == []


def test_compute_stats_counts_trailing_newline_as_same_line(tmp_path: Path) -> None:
    agent_dir = _make_agent(tmp_path, "one\ntwo\n")
    stats = compute_stats(
        system_prompt_path=agent_dir / "prompts" / "system.md",
        agent_dir=agent_dir,
        prompt_includes=None,
        snapshot_count=0,
    )
    assert stats.line_count == 2


def test_compute_stats_missing_file_returns_zeros(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    stats = compute_stats(
        system_prompt_path=agent_dir / "prompts" / "system.md",
        agent_dir=agent_dir,
        prompt_includes=None,
        snapshot_count=0,
    )
    assert stats.char_count == 0
    assert stats.line_count == 0
    assert stats.token_estimate == 0
    assert stats.last_modified_iso is None


def test_include_status_rows_reports_canonical_hit(tmp_path: Path) -> None:
    agent_dir = _make_agent(tmp_path, "ignored", voice="terse")
    rows = include_status_rows(agent_dir, {"voice": "voice"})
    assert len(rows) == 1
    assert rows[0].placeholder == "voice"
    assert rows[0].filename == "voice"
    assert rows[0].status == "found_local"
    assert rows[0].path is not None and rows[0].path.endswith("voice.md")


def test_include_status_rows_reports_example_fallback(tmp_path: Path) -> None:
    agent_dir = _make_agent(tmp_path, "ignored", voice_example="starter template")
    rows = include_status_rows(agent_dir, {"voice": "voice"})
    assert rows[0].status == "found_local_example"


def test_include_status_rows_reports_missing_include(tmp_path: Path) -> None:
    agent_dir = _make_agent(tmp_path, "ignored")
    rows = include_status_rows(agent_dir, {"voice": "nowhere"})
    assert rows[0].status == "missing"
    assert rows[0].path is None


def test_compute_stats_includes_include_rows(tmp_path: Path) -> None:
    agent_dir = _make_agent(tmp_path, "Voice: {voice}", voice="terse")
    stats = compute_stats(
        system_prompt_path=agent_dir / "prompts" / "system.md",
        agent_dir=agent_dir,
        prompt_includes={"voice": "voice"},
        snapshot_count=0,
    )
    assert len(stats.prompt_includes) == 1
    assert stats.prompt_includes[0].placeholder == "voice"
    assert stats.prompt_includes[0].status == "found_local"


def test_iso_mtime_returns_none_for_missing_file(tmp_path: Path) -> None:
    """_iso_mtime hits the not-a-file branch when the path doesn't exist."""
    from apps.gui.server.agents.prompt_stats import _iso_mtime

    assert _iso_mtime(tmp_path / "does-not-exist.md") is None


def test_iso_mtime_returns_iso_format_with_utc_tz(tmp_path: Path) -> None:
    """_iso_mtime returns an ISO-8601 string ending in '+00:00' (UTC)."""
    from apps.gui.server.agents.prompt_stats import _iso_mtime

    p = tmp_path / "hello.md"
    p.write_text("hi", encoding="utf-8")
    out = _iso_mtime(p)
    assert out is not None
    # Must be UTC-tagged so the GUI can interpret consistently across timezones.
    assert out.endswith("+00:00")


def test_iso_mtime_returns_none_when_directory_is_not_a_file(tmp_path: Path) -> None:
    """A directory should not be treated as a stat-able file."""
    from apps.gui.server.agents.prompt_stats import _iso_mtime

    assert _iso_mtime(tmp_path) is None


def test_approx_tokens_boundary_at_three_bytes_rounds_down() -> None:
    """3 bytes // 4 == 0 — sub-token texts produce 0, not 1."""
    assert approx_tokens("abc") == 0


def test_approx_tokens_boundary_at_eight_bytes() -> None:
    """8 bytes // 4 == 2 — exact multiple boundary."""
    assert approx_tokens("abcdefgh") == 2


def test_compute_stats_line_count_no_trailing_newline_adds_one(tmp_path: Path) -> None:
    """Text without trailing \\n: line_count = newline-count + 1."""
    agent_dir = _make_agent(tmp_path, "a\nb\nc")  # 2 newlines, 3 lines
    stats = compute_stats(
        system_prompt_path=agent_dir / "prompts" / "system.md",
        agent_dir=agent_dir,
        prompt_includes=None,
        snapshot_count=0,
    )
    assert stats.line_count == 3


def test_compute_stats_empty_text_yields_zero_lines(tmp_path: Path) -> None:
    """Empty file: count('\\n') is 0 and the +1 branch is suppressed."""
    agent_dir = _make_agent(tmp_path, "")
    stats = compute_stats(
        system_prompt_path=agent_dir / "prompts" / "system.md",
        agent_dir=agent_dir,
        prompt_includes=None,
        snapshot_count=0,
    )
    assert stats.line_count == 0
    assert stats.char_count == 0
    assert stats.token_estimate == 0
    # Existing-but-empty file → still has a real mtime.
    assert stats.last_modified_iso is not None


def test_compute_stats_token_estimate_method_is_locked(tmp_path: Path) -> None:
    """The method label is part of the wire contract — locked literal."""
    agent_dir = _make_agent(tmp_path, "anything")
    stats = compute_stats(
        system_prompt_path=agent_dir / "prompts" / "system.md",
        agent_dir=agent_dir,
        prompt_includes=None,
        snapshot_count=0,
    )
    assert stats.token_estimate_method == "len_utf8_over_4"


def test_compute_stats_propagates_snapshot_count(tmp_path: Path) -> None:
    """snapshot_count flows through unchanged — caller-supplied."""
    agent_dir = _make_agent(tmp_path, "x")
    stats = compute_stats(
        system_prompt_path=agent_dir / "prompts" / "system.md",
        agent_dir=agent_dir,
        prompt_includes=None,
        snapshot_count=42,
    )
    assert stats.snapshot_count == 42


def test_to_json_preserves_all_fields(tmp_path: Path) -> None:
    agent_dir = _make_agent(tmp_path, "hi")
    stats = compute_stats(
        system_prompt_path=agent_dir / "prompts" / "system.md",
        agent_dir=agent_dir,
        prompt_includes=None,
        snapshot_count=5,
    )
    payload = stats.to_json()
    assert set(payload.keys()) == {
        "char_count",
        "line_count",
        "token_estimate",
        "token_estimate_method",
        "last_modified_iso",
        "snapshot_count",
        "prompt_includes",
    }
    assert payload["snapshot_count"] == 5
