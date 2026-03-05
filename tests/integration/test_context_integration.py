"""
Integration tests for context system.

Tests that context files are properly loaded and integrated into system prompts.
"""

import pytest
from pathlib import Path
from packages.core.context_builder import build_system_prompt, load_context_file


@pytest.mark.integration
class TestContextIntegration:
    """Integration tests for context loading and system prompt building."""

    def test_context_files_loaded_into_prompt(self, sample_context_all_files: Path):
        """Test that all context files are loaded and included in prompt."""
        (sample_context_all_files / "soul.md").write_text(
            "You are Jarvis, a personal AI assistant."
        )

        result = build_system_prompt(sample_context_all_files)

        # Check soul
        assert "You are Jarvis" in result

        # Check all sections present
        assert "## About this person" in result
        assert "## Professional context" in result
        assert "## Their preferences" in result
        assert "## Current focus" in result

        # Check content from personal_context.md
        assert "software engineer" in result
        assert "10 years of experience" in result
        assert "Python" in result
        assert "machine learning" in result

        # Check content from professional_context.md
        assert "agile coach" in result

        # Check content from preferences.md
        assert "Be concise and technical" in result
        assert "Avoid unnecessary pleasantries" in result

        # Check content from current_focus.md
        assert "Jarvis" in result
        assert "testing framework" in result

    def test_missing_context_files_graceful(self, temp_context_dir: Path):
        """Test that system works gracefully with missing context files."""
        # Don't create any context files, directory is empty
        result = build_system_prompt(temp_context_dir)

        # Should be empty
        assert result == ""

        # Should not have any section headers since no files exist
        assert "## About this person" not in result
        assert "## Their preferences" not in result
        assert "## Current focus" not in result

    def test_context_order_preserved(self, sample_context_all_files: Path):
        """Test that context sections appear in correct order: personal -> professional -> preferences -> focus."""
        (sample_context_all_files / "soul.md").write_text("Test soul")
        result = build_system_prompt(sample_context_all_files)

        # Find positions
        personal_pos = result.find("## About this person")
        professional_pos = result.find("## Professional context")
        prefs_pos = result.find("## Their preferences")
        focus_pos = result.find("## Current focus")

        # All should be present
        assert personal_pos > 0
        assert professional_pos > 0
        assert prefs_pos > 0
        assert focus_pos > 0

        # Check ordering
        assert personal_pos < professional_pos < prefs_pos < focus_pos

        # Check content order within result
        # Personal content should come before preferences content
        software_eng_pos = result.find("software engineer")
        concise_pos = result.find("Be concise")
        jarvis_pos = result.find("testing framework")

        assert software_eng_pos < concise_pos < jarvis_pos

    def test_system_prompt_format(self, sample_context_all_files: Path):
        """Test proper formatting of system prompt with sections and separators."""
        (sample_context_all_files / "soul.md").write_text("You are Jarvis.")
        result = build_system_prompt(sample_context_all_files)

        # Check structure
        lines = result.split("\n")

        # Should start with soul content (stripped)
        assert lines[0] == "You are Jarvis."

        # Should have section separators
        separator_count = result.count("\n\n---\n\n")
        assert separator_count == 3  # Between 4 sections (personal, professional, prefs, focus)

        # Each section should have proper markdown header
        assert "## About this person" in result
        assert "## Professional context" in result
        assert "## Their preferences" in result
        assert "## Current focus" in result

        # Sections should be separated by blank lines and separators
        assert "\n\n## About this person" in result
        assert "\n\n## Professional context" in result
        assert "\n\n## Their preferences" in result
        assert "\n\n## Current focus" in result
