"""
Unit tests for context_builder module.

Tests the functionality of loading context files and building system prompts.
"""

from pathlib import Path

import pytest

# Try new import path first, fall back to old for backward compatibility
try:
    from packages.core.context_builder import (
        ContextMetadata,
        ContextSection,
        _approx_tokens,
        build_system_prompt,
        build_system_prompt_with_metadata,
        load_context_file,
        parse_frontmatter,
    )
except ImportError:
    from context_builder import (
        ContextMetadata,
        ContextSection,
        _approx_tokens,
        build_system_prompt,
        build_system_prompt_with_metadata,
        load_context_file,
        parse_frontmatter,
    )


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
        unicode_content = "Hello 世界! Emojis and special chars"
        unicode_file.write_text(unicode_content, encoding="utf-8")

        result = load_context_file(unicode_file)
        assert result == unicode_content
        assert "世界" in result


@pytest.mark.unit
class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_build_system_prompt_all_files(self, sample_context_all_files: Path):
        """Test assembling prompt with all context files present."""
        (sample_context_all_files / "soul.md").write_text("You are a helpful assistant.")

        result = build_system_prompt(sample_context_all_files)

        # Check soul content is included
        assert "You are a helpful assistant." in result

        # Check all sections are present
        assert "## About this person" in result
        assert "## Professional context" in result
        assert "## Their preferences" in result
        assert "## Current focus" in result

        # Check content from each file
        assert "software engineer" in result
        assert "agile coach" in result
        assert "Be concise and technical" in result
        assert "Jarvis" in result

    def test_build_system_prompt_partial_files(self, temp_context_dir: Path):
        """Test assembling with only some files present."""
        # Create only personal_context.md and soul.md
        personal = temp_context_dir / "personal_context.md"
        personal.write_text("I am a developer.")
        (temp_context_dir / "soul.md").write_text("You are helpful.")

        result = build_system_prompt(temp_context_dir)

        # Check soul and personal context are included
        assert "You are helpful." in result
        assert "## About this person" in result
        assert "I am a developer." in result

        # Check other sections are not included
        assert "## Professional context" not in result
        assert "## Their preferences" not in result
        assert "## Current focus" not in result

    def test_build_system_prompt_no_files(self, temp_context_dir: Path):
        """Test handling of no context files gracefully."""
        result = build_system_prompt(temp_context_dir)

        # Should be empty with no files
        assert result == ""

        # Should not have section headers
        assert "## About this person" not in result
        assert "## Professional context" not in result
        assert "## Their preferences" not in result
        assert "## Current focus" not in result

    def test_build_system_prompt_section_order(self, sample_context_all_files: Path):
        """Test that sections appear in the correct order."""
        (sample_context_all_files / "soul.md").write_text("Test soul")
        result = build_system_prompt(sample_context_all_files)

        # Find positions of each section
        about_pos = result.find("## About this person")
        professional_pos = result.find("## Professional context")
        prefs_pos = result.find("## Their preferences")
        focus_pos = result.find("## Current focus")

        # All should exist
        assert about_pos != -1
        assert professional_pos != -1
        assert prefs_pos != -1
        assert focus_pos != -1

        # Check order: personal -> professional -> preferences -> focus
        assert about_pos < professional_pos < prefs_pos < focus_pos

    def test_build_system_prompt_soul_formatting(self, temp_context_dir: Path):
        """Test that soul content is formatted correctly with proper spacing."""
        # Test with trailing whitespace
        (temp_context_dir / "soul.md").write_text("You are helpful.   \n  ")
        personal = temp_context_dir / "personal_context.md"
        personal.write_text("Developer")

        result = build_system_prompt(temp_context_dir)

        # Soul should be stripped
        assert result.startswith("You are helpful.")
        assert not result.startswith("You are helpful.   ")

    def test_build_system_prompt_separator(self, sample_context_all_files: Path):
        """Test that sections are separated correctly."""
        (sample_context_all_files / "soul.md").write_text("Test soul")
        result = build_system_prompt(sample_context_all_files)

        # Check for separator between sections
        assert "\n\n---\n\n" in result

        # Count separators (should be 3 for 4 sections: personal, professional, prefs, focus)
        separator_count = result.count("\n\n---\n\n")
        assert separator_count == 3

    def test_build_system_prompt_no_soul(self, temp_context_dir: Path):
        """Test that prompt builds correctly without soul.md."""
        (temp_context_dir / "personal_context.md").write_text("I am a developer.")

        result = build_system_prompt(temp_context_dir)

        # Should still have context sections
        assert "## About this person" in result
        assert "I am a developer." in result

    def test_build_system_prompt_soul_only(self, temp_context_dir: Path):
        """Test prompt with only soul.md and no other context."""
        (temp_context_dir / "soul.md").write_text("# SOUL\nYou are JARVIS.")

        result = build_system_prompt(temp_context_dir)

        assert "# SOUL" in result
        assert "You are JARVIS." in result

    def test_build_system_prompt_soul_sections_in_prompt(self, temp_context_dir: Path):
        """Test that soul sections appear in built prompt."""
        soul_content = "# SOUL\n\n## Identity\nYou are JARVIS.\n\n## Values\nShipping > Talking."
        (temp_context_dir / "soul.md").write_text(soul_content)

        result = build_system_prompt(temp_context_dir)

        assert "## Identity" in result
        assert "You are JARVIS." in result
        assert "## Values" in result
        assert "Shipping > Talking." in result


@pytest.mark.unit
class TestBuildSystemPromptSplitProfile:
    """Tests for split personal + professional context files."""

    def test_personal_context_only(self, temp_context_dir: Path):
        """Test with only personal_context.md present."""
        (temp_context_dir / "personal_context.md").write_text("Name: Marco")
        result = build_system_prompt(temp_context_dir)
        assert "## About this person" in result
        assert "Name: Marco" in result
        assert "## Professional context" not in result

    def test_professional_context_only(self, temp_context_dir: Path):
        """Test with only professional_context.md present."""
        (temp_context_dir / "professional_context.md").write_text("Consultant")
        result = build_system_prompt(temp_context_dir)
        assert "## Professional context" in result
        assert "Consultant" in result
        assert "## About this person" not in result

    def test_both_contexts(self, temp_context_dir: Path):
        """Test with both personal and professional context."""
        (temp_context_dir / "personal_context.md").write_text("Name: Marco")
        (temp_context_dir / "professional_context.md").write_text("Consultant")
        result = build_system_prompt(temp_context_dir)
        assert "## About this person" in result
        assert "## Professional context" in result

    def test_missing_both_graceful(self, temp_context_dir: Path):
        """Test graceful handling when both profile files are missing."""
        (temp_context_dir / "soul.md").write_text("Test prefix")
        result = build_system_prompt(temp_context_dir)
        assert "Test prefix" in result
        assert "## About this person" not in result
        assert "## Professional context" not in result


@pytest.mark.unit
class TestBuildSystemPromptProjectsDirIgnored:
    """Tests that projects/ directory is no longer loaded into the prompt.

    Project knowledge has been migrated to Obsidian and is fetched
    on demand via vault search tools instead of static loading.
    """

    def test_projects_dir_not_loaded(self, temp_context_dir: Path):
        """Test that project files in projects/ are NOT loaded."""
        projects_dir = temp_context_dir / "projects"
        projects_dir.mkdir()
        (projects_dir / "jarvis.md").write_text("# Jarvis\nPersonal AI assistant.")

        result = build_system_prompt(temp_context_dir)
        assert "## Project context" not in result
        assert "## Project index" not in result
        assert "Personal AI assistant." not in result

    def test_no_projects_dir_still_works(self, temp_context_dir: Path):
        """Test that missing projects directory causes no issues."""
        result = build_system_prompt(temp_context_dir)
        assert "## Project context" not in result


@pytest.mark.unit
class TestParseFrontmatter:
    """Tests for parse_frontmatter function."""

    def test_valid_frontmatter(self):
        """Test parsing valid YAML frontmatter."""
        text = '---\nactive: true\ntopics: [python, ai]\nsummary: "A project"\n---\n# Content\nBody text.'
        meta, content = parse_frontmatter(text)
        assert meta == {"active": True, "topics": ["python", "ai"], "summary": "A project"}
        assert content == "# Content\nBody text."

    def test_no_frontmatter(self):
        """Test text without frontmatter returns empty dict and full text."""
        text = "# Just a heading\nSome content."
        meta, content = parse_frontmatter(text)
        assert meta == {}
        assert content == text

    def test_empty_frontmatter(self):
        """Test frontmatter with no fields returns empty dict."""
        # Minimally valid: at least one newline between delimiters
        text = "---\n\n---\n# Content"
        meta, content = parse_frontmatter(text)
        assert meta == {}
        assert content == "# Content"

    def test_adjacent_delimiters_treated_as_no_frontmatter(self):
        """Test that ---\\n---\\n (no space between) is treated as no frontmatter."""
        text = "---\n---\n# Content"
        meta, content = parse_frontmatter(text)
        assert meta == {}
        assert content == text

    def test_frontmatter_active_false(self):
        """Test parsing active: false."""
        text = '---\nactive: false\nsummary: "Inactive project"\n---\nBody'
        meta, content = parse_frontmatter(text)
        assert meta["active"] is False
        assert meta["summary"] == "Inactive project"
        assert content == "Body"

    def test_unclosed_frontmatter(self):
        """Test unclosed frontmatter is treated as no frontmatter."""
        text = "---\nactive: true\n# No closing delimiter"
        meta, content = parse_frontmatter(text)
        assert meta == {}
        assert content == text

    def test_frontmatter_not_at_start(self):
        """Test that --- not at start of text is ignored."""
        text = "Some text\n---\nactive: true\n---\nMore text"
        meta, content = parse_frontmatter(text)
        assert meta == {}
        assert content == text

    def test_frontmatter_preserves_content_whitespace(self):
        """Test that content after frontmatter preserves whitespace."""
        text = "---\nactive: true\n---\n\n# Title\n\nParagraph."
        meta, content = parse_frontmatter(text)
        assert content == "\n# Title\n\nParagraph."


@pytest.mark.unit
class TestApproxTokens:
    """Tests for _approx_tokens helper."""

    def test_empty_string(self):
        assert _approx_tokens("") == 0

    def test_ascii_text(self):
        # 20 ASCII chars = 20 bytes / 4 = 5 tokens
        assert _approx_tokens("Hello World! Test.  ") == 5

    def test_multibyte_text(self):
        # Multibyte chars produce more bytes, so more tokens
        text = "Hallo Wörld"  # ö is 2 bytes in UTF-8
        assert _approx_tokens(text) >= len(text) // 4


@pytest.mark.unit
class TestContextMetadata:
    """Tests for ContextMetadata dataclass."""

    def test_empty_metadata(self):
        meta = ContextMetadata()
        assert meta.total_approx_tokens == 0
        assert meta.sections == []
        assert meta.section_percentages() == {}

    def test_section_percentages(self):
        meta = ContextMetadata(
            total_approx_tokens=100,
            sections=[
                ContextSection(name="soul", size_bytes=80, approx_tokens=20),
                ContextSection(name="tasks", size_bytes=320, approx_tokens=80),
            ],
        )
        pcts = meta.section_percentages()
        assert pcts["soul"] == pytest.approx(20.0)
        assert pcts["tasks"] == pytest.approx(80.0)

    def test_section_percentages_zero_total(self):
        meta = ContextMetadata(
            total_approx_tokens=0,
            sections=[ContextSection(name="soul", size_bytes=0, approx_tokens=0)],
        )
        assert meta.section_percentages() == {}


@pytest.mark.unit
class TestBuildSystemPromptWithMetadata:
    """Tests for build_system_prompt_with_metadata."""

    def test_returns_same_prompt_as_original(self, temp_context_dir: Path):
        """Metadata variant produces the same prompt text."""
        (temp_context_dir / "soul.md").write_text("I am Jarvis.")
        (temp_context_dir / "personal_context.md").write_text("User is a dev.")

        original = build_system_prompt(temp_context_dir)
        prompt, _meta = build_system_prompt_with_metadata(temp_context_dir)
        assert prompt == original

    def test_metadata_has_sections(self, temp_context_dir: Path):
        (temp_context_dir / "soul.md").write_text("I am Jarvis.")
        (temp_context_dir / "personal_context.md").write_text("User info here.")
        (temp_context_dir / "tasks.md").write_text("- Buy milk")

        _prompt, meta = build_system_prompt_with_metadata(temp_context_dir)
        section_names = [s.name for s in meta.sections]
        assert "soul" in section_names
        assert "personal" in section_names
        assert "tasks" in section_names

    def test_metadata_total_tokens_positive(self, temp_context_dir: Path):
        (temp_context_dir / "soul.md").write_text("I am Jarvis, a personal AI assistant.")

        _prompt, meta = build_system_prompt_with_metadata(temp_context_dir)
        assert meta.total_approx_tokens > 0

    def test_metadata_excludes_projects(self, temp_context_dir: Path):
        """Projects dir is no longer loaded — metadata should not include it."""
        projects_dir = temp_context_dir / "projects"
        projects_dir.mkdir()
        (projects_dir / "myproject.md").write_text("# My Project\nSome content here.")

        _prompt, meta = build_system_prompt_with_metadata(temp_context_dir)
        section_names = [s.name for s in meta.sections]
        assert "projects" not in section_names

    def test_empty_context_dir(self, temp_context_dir: Path):
        prompt, meta = build_system_prompt_with_metadata(temp_context_dir)
        assert prompt == ""
        assert meta.total_approx_tokens == 0
        assert meta.sections == []

    def test_section_tokens_are_positive(self, temp_context_dir: Path):
        (temp_context_dir / "soul.md").write_text("I am Jarvis.")
        (temp_context_dir / "preferences.md").write_text("Be concise.")

        _prompt, meta = build_system_prompt_with_metadata(temp_context_dir)
        for section in meta.sections:
            assert section.approx_tokens > 0
            assert section.size_bytes > 0
