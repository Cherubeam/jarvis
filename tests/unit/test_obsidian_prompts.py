"""Tests for packages.integrations.obsidian.prompts module."""

import pytest
from pathlib import Path

from packages.integrations.obsidian.prompts import (
    load_obsidian_prompt,
    get_daily_note_instructions,
)


# ==================== load_obsidian_prompt ====================


class TestLoadObsidianPrompt:
    def test_load_existing_prompt(self, tmp_path):
        prompt_file = tmp_path / "test_prompt.md"
        prompt_file.write_text("# Test Prompt\nDo the thing.")
        result = load_obsidian_prompt("test_prompt", prompts_dir=tmp_path)
        assert "Test Prompt" in result
        assert "Do the thing." in result

    def test_load_missing_prompt_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_obsidian_prompt("nonexistent", prompts_dir=tmp_path)

    def test_loads_from_default_dir(self):
        """The real daily_note_entry.md should exist in data/prompts/obsidian/."""
        result = load_obsidian_prompt("daily_note_entry")
        assert "Daily Note" in result

    def test_loads_general_writing(self):
        """The real general_writing.md should exist."""
        result = load_obsidian_prompt("general_writing")
        assert "Obsidian" in result


# ==================== get_daily_note_instructions ====================


class TestGetDailyNoteInstructions:
    def test_returns_daily_note_prompt(self):
        result = get_daily_note_instructions()
        assert len(result) > 0
        assert "Daily Note" in result

    def test_prompt_contains_output_constraints(self):
        result = get_daily_note_instructions()
        assert "DO NOT" in result
        assert "bullet" in result.lower()
        assert "OUTPUT ONLY" in result

    def test_custom_prompts_dir(self, tmp_path):
        prompt_file = tmp_path / "daily_note_entry.md"
        prompt_file.write_text("Custom daily instructions")
        result = get_daily_note_instructions(prompts_dir=tmp_path)
        assert result == "Custom daily instructions"
