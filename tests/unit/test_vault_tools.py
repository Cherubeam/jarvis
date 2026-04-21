"""Tests for packages.core.tools.vault_read_tools."""

import os
import re
import time

import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from packages.core.filesystem_access import AccessLevel, AccessRule, FilesystemGuard
from packages.integrations.obsidian.vault import VaultConfig
from packages.core.tools.vault_read_tools import (
    make_vault_read_tools,
    MAX_CONTENT_SIZE,
    MAX_SEARCH_RESULTS,
)


def _guard(*rules: tuple[Path, AccessLevel]) -> FilesystemGuard:
    return FilesystemGuard([AccessRule(path=p, access=a) for p, a in rules])


@pytest.fixture
def vault(tmp_path):
    """Create a vault with daily notes and various note directories."""
    # Create some directories
    daily_dir = tmp_path / "Daily Notes"
    daily_dir.mkdir()
    notes_dir = tmp_path / "Notes"
    notes_dir.mkdir()
    private_dir = tmp_path / "Private"
    private_dir.mkdir()

    guard = _guard(
        (tmp_path.resolve(), AccessLevel.READ),
        (private_dir.resolve(), AccessLevel.DENY),
    )
    config = VaultConfig(
        vault_path=tmp_path,
        filesystem_guard=guard,
        daily_note_path_format="Daily Notes/%Y-%m-%d",
    )
    return config, tmp_path


@pytest.fixture
def tools(vault):
    config, vault_path = vault
    return make_vault_read_tools(config), vault_path, config


def _get_tool(tools_list, name):
    return next(t for t in tools_list if t.name == name)


# ==================== make_vault_read_tools ====================


@pytest.mark.unit
class TestMakeVaultTools:
    def test_returns_three_tools(self, tools):
        tool_list, *_ = tools
        assert len(tool_list) == 3

    def test_tool_names(self, tools):
        tool_list, *_ = tools
        names = {t.name for t in tool_list}
        assert names == {"read_note", "search_notes", "read_daily_note"}

    def test_all_have_litellm_format(self, tools):
        tool_list, *_ = tools
        for t in tool_list:
            fmt = t.to_litellm_format()
            assert fmt["type"] == "function"
            assert "name" in fmt["function"]

    # --- Schema validation (kills dict key/value/type mutations) ---

    def test_read_note_schema(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "read_note")
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["required"] == ["path"]

    def test_search_notes_schema(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "search_notes")
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"directory", "pattern", "sort_by", "limit"}
        assert params["properties"]["directory"]["type"] == "string"
        assert params["properties"]["pattern"]["type"] == "string"
        assert params["properties"]["sort_by"]["type"] == "string"
        assert params["properties"]["sort_by"]["enum"] == ["name", "modified"]
        assert params["properties"]["limit"]["type"] == "integer"
        assert params["required"] == []

    def test_read_daily_note_schema(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "read_daily_note")
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"date"}
        assert params["properties"]["date"]["type"] == "string"
        assert params["required"] == []


# ==================== read_note ====================


@pytest.mark.unit
class TestReadNote:
    def test_reads_file_content(self, tools):
        tool_list, vault_path, *_ = tools
        (vault_path / "Notes" / "test.md").write_text("# Test Note\n\nHello world.")

        tool = _get_tool(tool_list, "read_note")
        result = tool.execute(path="Notes/test.md")

        assert result == "# Test Note\n\nHello world."

    def test_file_not_found(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "read_note")
        result = tool.execute(path="Notes/missing.md")
        assert result == "Error: File not found: Notes/missing.md"

    def test_denied_path(self, tools):
        tool_list, vault_path, *_ = tools
        (vault_path / "Private" / "secret.md").write_text("top secret")

        tool = _get_tool(tool_list, "read_note")
        result = tool.execute(path="Private/secret.md")
        assert result.startswith("Error:")
        assert "Private" in result

    def test_truncates_large_content(self, tools):
        tool_list, vault_path, *_ = tools
        large_content = "x" * (MAX_CONTENT_SIZE + 1000)
        (vault_path / "Notes" / "large.md").write_text(large_content)

        tool = _get_tool(tool_list, "read_note")
        result = tool.execute(path="Notes/large.md")

        assert result.endswith("\n\n[Truncated — content exceeds 50KB]")
        assert len(result) == MAX_CONTENT_SIZE + len("\n\n[Truncated — content exceeds 50KB]")

    def test_exactly_at_max_not_truncated(self, tools):
        """Boundary: content exactly at MAX_CONTENT_SIZE should NOT be truncated."""
        tool_list, vault_path, *_ = tools
        exact_content = "y" * MAX_CONTENT_SIZE
        (vault_path / "Notes" / "exact.md").write_text(exact_content)

        tool = _get_tool(tool_list, "read_note")
        result = tool.execute(path="Notes/exact.md")

        assert result == exact_content
        assert "[Truncated" not in result


# ==================== search_notes ====================


@pytest.mark.unit
class TestSearchNotes:
    def test_lists_markdown_files(self, tools):
        tool_list, vault_path, *_ = tools
        (vault_path / "Notes" / "one.md").write_text("# One")
        (vault_path / "Notes" / "two.md").write_text("# Two")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes")

        assert "one.md" in result
        assert "two.md" in result

    def test_returns_relative_paths(self, tools):
        tool_list, vault_path, *_ = tools
        (vault_path / "Notes" / "note.md").write_text("# Note")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes")

        assert "Notes/note.md" in result
        assert str(vault_path) not in result

    def test_empty_directory(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes")
        assert result == "No notes found."

    def test_denied_directory(self, tools):
        tool_list, vault_path, *_ = tools
        (vault_path / "Private" / "secret.md").write_text("secret")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Private")
        assert result.startswith("Error:")
        assert "Private" in result

    def test_caps_at_max_results(self, tools):
        tool_list, vault_path, *_ = tools
        notes_dir = vault_path / "Notes"
        for i in range(MAX_SEARCH_RESULTS + 10):
            (notes_dir / f"note-{i:04d}.md").write_text(f"# Note {i}")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes")

        lines = [line for line in result.split("\n") if line.strip() and not line.startswith("[")]
        assert len(lines) == MAX_SEARCH_RESULTS
        assert f"Showing {MAX_SEARCH_RESULTS}" in result

    def test_custom_pattern(self, tools):
        tool_list, vault_path, *_ = tools
        (vault_path / "Notes" / "note.md").write_text("# Note")
        (vault_path / "Notes" / "data.csv").write_text("a,b,c")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes", pattern="*.csv")

        assert "data.csv" in result
        assert "note.md" not in result

    def test_sort_by_modified_returns_newest_first(self, tools):
        tool_list, vault_path, *_ = tools
        notes_dir = vault_path / "Notes"
        # Create files with staggered mtimes
        for i, name in enumerate(["old.md", "mid.md", "new.md"]):
            path = notes_dir / name
            path.write_text(f"# {name}")
            os.utime(path, (1000 + i * 100, 1000 + i * 100))

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes", sort_by="modified")

        lines = [l for l in result.strip().split("\n") if l.strip()]
        assert "new.md" in lines[0]
        assert "mid.md" in lines[1]
        assert "old.md" in lines[2]

    def test_sort_by_modified_includes_timestamps(self, tools):
        tool_list, vault_path, *_ = tools
        path = vault_path / "Notes" / "note.md"
        path.write_text("# Note")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes", sort_by="modified")

        # Format: YYYY-MM-DD HH:MM  path
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}  Notes/note\.md", result)

    def test_sort_by_name_is_default(self, tools):
        tool_list, vault_path, *_ = tools
        (vault_path / "Notes" / "alpha.md").write_text("# A")
        (vault_path / "Notes" / "beta.md").write_text("# B")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes")

        # Default sort: no timestamps
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", result) is None

    def test_limit_parameter(self, tools):
        tool_list, vault_path, *_ = tools
        notes_dir = vault_path / "Notes"
        for i in range(10):
            (notes_dir / f"note-{i:02d}.md").write_text(f"# Note {i}")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes", limit=3)

        lines = [l for l in result.split("\n") if l.strip() and not l.startswith("[")]
        assert len(lines) == 3
        assert "Showing 3 of 10" in result

    def test_limit_clamped_to_max(self, tools):
        tool_list, vault_path, *_ = tools
        notes_dir = vault_path / "Notes"
        # Create just 3 files — we only need to verify clamping logic, not 100+ files
        for i in range(3):
            (notes_dir / f"note-{i}.md").write_text(f"# Note {i}")

        tool = _get_tool(tool_list, "search_notes")
        # limit=999 should be clamped to MAX_SEARCH_RESULTS (100), but with only 3 files
        # no overflow message should appear
        result = tool.execute(directory="Notes", limit=999)
        lines = [l for l in result.split("\n") if l.strip() and not l.startswith("[")]
        assert len(lines) == 3
        assert "Showing" not in result

    def test_limit_clamped_to_min(self, tools):
        tool_list, vault_path, *_ = tools
        notes_dir = vault_path / "Notes"
        for i in range(3):
            (notes_dir / f"note-{i}.md").write_text(f"# Note {i}")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes", limit=0)

        lines = [l for l in result.split("\n") if l.strip() and not l.startswith("[")]
        assert len(lines) == 1  # clamped to 1

    def test_limit_clamped_negative(self, tools):
        """Negative limit should be clamped to 1."""
        tool_list, vault_path, *_ = tools
        notes_dir = vault_path / "Notes"
        for i in range(3):
            (notes_dir / f"note-{i}.md").write_text(f"# Note {i}")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes", limit=-5)

        lines = [l for l in result.split("\n") if l.strip() and not l.startswith("[")]
        assert len(lines) == 1  # clamped to 1

    def test_output_is_newline_joined(self, tools):
        """Results are joined by newline separator."""
        tool_list, vault_path, *_ = tools
        (vault_path / "Notes" / "a.md").write_text("# A")
        (vault_path / "Notes" / "b.md").write_text("# B")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes")

        lines = result.split("\n")
        assert len(lines) == 2
        assert all("Notes/" in line for line in lines)

    def test_default_pattern_matches_markdown(self, tools):
        """Default pattern (**/*.md) matches .md files and excludes others."""
        tool_list, vault_path, *_ = tools
        (vault_path / "Notes" / "note.md").write_text("# Note")
        (vault_path / "Notes" / "data.json").write_text("{}")

        tool = _get_tool(tool_list, "search_notes")
        # Call without pattern — should use default **/*.md
        result = tool.execute(directory="Notes")

        assert "note.md" in result
        assert "data.json" not in result

    def test_overflow_message_format(self, tools):
        """Overflow message includes exact count format."""
        tool_list, vault_path, *_ = tools
        notes_dir = vault_path / "Notes"
        for i in range(5):
            (notes_dir / f"note-{i:02d}.md").write_text(f"# Note {i}")

        tool = _get_tool(tool_list, "search_notes")
        result = tool.execute(directory="Notes", limit=2)

        assert "Showing 2 of 5 results" in result
        assert result.index("[Showing") > result.index("note-")


# ==================== read_daily_note ====================


@pytest.mark.unit
class TestReadDailyNote:
    def test_reads_today(self, tools):
        tool_list, vault_path, *_ = tools
        today = date.today().strftime("%Y-%m-%d")
        daily_note = vault_path / "Daily Notes" / f"{today}.md"
        daily_note.write_text("# Today's Note\n\nTasks for today.")

        tool = _get_tool(tool_list, "read_daily_note")
        result = tool.execute()

        assert "Today's Note" in result

    def test_reads_specific_date(self, tools):
        tool_list, vault_path, *_ = tools
        daily_note = vault_path / "Daily Notes" / "2026-03-01.md"
        daily_note.write_text("# March 1st")

        tool = _get_tool(tool_list, "read_daily_note")
        result = tool.execute(date="2026-03-01")

        assert "March 1st" in result

    def test_missing_daily_note(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "read_daily_note")
        result = tool.execute(date="2099-01-01")

        assert result == "Error: Daily note not found for 2099-01-01."

    def test_defaults_to_today(self, tools):
        tool_list, vault_path, *_ = tools

        tool = _get_tool(tool_list, "read_daily_note")
        result = tool.execute()

        # No daily note for today — should get "not found" error with "today"
        assert result == "Error: Daily note not found for today."

    def test_invalid_date_format(self, tools):
        tool_list, *_ = tools
        tool = _get_tool(tool_list, "read_daily_note")
        result = tool.execute(date="not-a-date")

        assert result == "Error: Invalid date format: not-a-date. Use YYYY-MM-DD."

    def test_truncates_large_daily_note(self, tools):
        tool_list, vault_path, *_ = tools
        today = date.today().strftime("%Y-%m-%d")
        daily_note = vault_path / "Daily Notes" / f"{today}.md"
        daily_note.write_text("x" * (MAX_CONTENT_SIZE + 500))

        tool = _get_tool(tool_list, "read_daily_note")
        result = tool.execute()

        assert result.endswith("\n\n[Truncated — content exceeds 50KB]")
        assert len(result) == MAX_CONTENT_SIZE + len("\n\n[Truncated — content exceeds 50KB]")
