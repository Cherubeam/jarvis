"""
Unit tests for context_builder module.

Tests the functionality of loading context files and building system prompts.
"""

import pytest
from pathlib import Path
from context_builder import load_context_file, build_system_prompt


@pytest.mark.unit
class TestLoadContextFile:
    """Tests for load_context_file function."""

    def test_load_context_file_exists(self, temp_context_dir: Path):
        """Test loading an existing markdown file successfully."""
        # Create a test file
        test_file = temp_context_dir / "test.md"
        test_content = "# Test Content\n\nThis is a test file."
        test_file.write_text(test_content)

        # Load and verify
        result = load_context_file(test_file)
        assert result == test_content

    def test_load_context_file_missing(self, temp_context_dir: Path):
        """Test that missing files return empty string."""
        missing_file = temp_context_dir / "nonexistent.md"
        result = load_context_file(missing_file)
        assert result == ""

    def test_load_context_file_empty(self, temp_context_dir: Path):
        """Test handling of empty files."""
        empty_file = temp_context_dir / "empty.md"
        empty_file.write_text("")

        result = load_context_file(empty_file)
        assert result == ""

    def test_load_context_file_unicode(self, temp_context_dir: Path):
        """Test handling of unicode characters."""
        unicode_file = temp_context_dir / "unicode.md"
        unicode_content = "Hello 世界! 🚀 Émojis and ñ special chars"
        unicode_file.write_text(unicode_content, encoding="utf-8")

        result = load_context_file(unicode_file)
        assert result == unicode_content
        assert "世界" in result
        assert "🚀" in result


@pytest.mark.unit
class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_build_system_prompt_all_files(self, sample_context_all_files: Path):
        """Test assembling prompt with all context files present."""
        prefix = "You are a helpful assistant."

        result = build_system_prompt(sample_context_all_files, prefix)

        # Check prefix is included
        assert "You are a helpful assistant." in result

        # Check all sections are present
        assert "## About this person" in result
        assert "## Their preferences" in result
        assert "## Current focus" in result

        # Check content from each file
        assert "software engineer" in result
        assert "Be concise and technical" in result
        assert "Jarvis" in result

    def test_build_system_prompt_partial_files(self, temp_context_dir: Path):
        """Test assembling with only some files present."""
        # Create only profile.md
        profile = temp_context_dir / "profile.md"
        profile.write_text("I am a developer.")

        prefix = "You are helpful."
        result = build_system_prompt(temp_context_dir, prefix)

        # Check prefix and profile are included
        assert "You are helpful." in result
        assert "## About this person" in result
        assert "I am a developer." in result

        # Check other sections are not included
        assert "## Their preferences" not in result
        assert "## Current focus" not in result

    def test_build_system_prompt_no_files(self, temp_context_dir: Path):
        """Test handling of no context files gracefully."""
        prefix = "You are an assistant."
        result = build_system_prompt(temp_context_dir, prefix)

        # Should still have prefix
        assert "You are an assistant." in result

        # Should not have section headers
        assert "## About this person" not in result
        assert "## Their preferences" not in result
        assert "## Current focus" not in result

    def test_build_system_prompt_section_order(self, sample_context_all_files: Path):
        """Test that sections appear in the correct order: profile → preferences → focus."""
        prefix = "Test"
        result = build_system_prompt(sample_context_all_files, prefix)

        # Find positions of each section
        about_pos = result.find("## About this person")
        prefs_pos = result.find("## Their preferences")
        focus_pos = result.find("## Current focus")

        # All should exist
        assert about_pos != -1
        assert prefs_pos != -1
        assert focus_pos != -1

        # Check order
        assert about_pos < prefs_pos < focus_pos

    def test_build_system_prompt_prefix_formatting(self, temp_context_dir: Path):
        """Test that prefix is formatted correctly with proper spacing."""
        # Test with trailing whitespace
        prefix_with_space = "You are helpful.   \n  "
        profile = temp_context_dir / "profile.md"
        profile.write_text("Developer")

        result = build_system_prompt(temp_context_dir, prefix_with_space)

        # Prefix should be stripped
        assert result.startswith("You are helpful.")
        assert not result.startswith("You are helpful.   ")

    def test_build_system_prompt_separator(self, sample_context_all_files: Path):
        """Test that sections are separated correctly."""
        prefix = "Test"
        result = build_system_prompt(sample_context_all_files, prefix)

        # Check for separator between sections
        assert "\n\n---\n\n" in result

        # Count separators (should be 2 for 3 sections)
        separator_count = result.count("\n\n---\n\n")
        assert separator_count == 2
