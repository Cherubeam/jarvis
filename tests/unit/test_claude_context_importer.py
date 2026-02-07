"""Unit tests for Claude context importer (memories + projects)."""

import json
import pytest
from pathlib import Path

from packages.core.importers.claude_context import (
    ContextImportSummary,
    build_current_focus,
    build_personal_context,
    build_professional_context,
    build_project_file,
    import_context,
    parse_existing_profile,
    parse_memory_sections,
    slugify_project_name,
)


# ==================== parse_memory_sections ====================


@pytest.mark.unit
class TestParseMemorySections:
    """Tests for parse_memory_sections."""

    def test_all_four_sections(self):
        text = (
            "**Work context**\nI work in tech.\n\n"
            "**Personal context**\nI live in Berlin.\n\n"
            "**Top of mind**\nBuilding Jarvis.\n\n"
            "**Brief history**\nHumanities to AI."
        )
        result = parse_memory_sections(text)
        assert len(result) == 4
        assert "I work in tech." in result["Work context"]
        assert "I live in Berlin." in result["Personal context"]
        assert "Building Jarvis." in result["Top of mind"]
        assert "Humanities to AI." in result["Brief history"]

    def test_empty_input(self):
        assert parse_memory_sections("") == {}
        assert parse_memory_sections("   ") == {}

    def test_no_headers(self):
        assert parse_memory_sections("Just plain text without headers.") == {}

    def test_section_with_multiple_lines(self):
        text = "**Work context**\nLine one.\nLine two.\nLine three."
        result = parse_memory_sections(text)
        assert "Line one." in result["Work context"]
        assert "Line three." in result["Work context"]

    def test_inline_bold_not_treated_as_header(self):
        text = "**Work context**\nUses **Python** for scripting."
        result = parse_memory_sections(text)
        assert "**Python**" in result["Work context"]

    def test_empty_section_body(self):
        text = "**Empty section**\n\n**Next section**\nHas content."
        result = parse_memory_sections(text)
        assert "Empty section" not in result
        assert "Has content." in result["Next section"]


# ==================== parse_existing_profile ====================


@pytest.mark.unit
class TestParseExistingProfile:
    """Tests for parse_existing_profile."""

    def test_all_sections(self):
        text = (
            "# Profile\n\n"
            "## Personal Information\n- Name: Marco\n\n"
            "## Professional background\n- Consultant\n\n"
            "## Skills & knowledge\n- Python"
        )
        result = parse_existing_profile(text)
        assert "Name: Marco" in result["Personal Information"]
        assert "Consultant" in result["Professional background"]
        assert "Python" in result["Skills & knowledge"]

    def test_empty_input(self):
        assert parse_existing_profile("") == {}
        assert parse_existing_profile("  ") == {}

    def test_partial_profile(self):
        text = "## Personal Information\n- Name: Marco"
        result = parse_existing_profile(text)
        assert len(result) == 1
        assert "Name: Marco" in result["Personal Information"]

    def test_ignores_h1_header(self):
        text = "# Profile\n\nSome intro text."
        result = parse_existing_profile(text)
        assert len(result) == 0


# ==================== slugify_project_name ====================


@pytest.mark.unit
class TestSlugifyProjectName:
    """Tests for slugify_project_name."""

    def test_basic(self):
        assert slugify_project_name("My Project") == "my-project"

    def test_the_prefix_removed(self):
        assert slugify_project_name("The Technical Humanist") == "technical-humanist"

    def test_ampersand(self):
        result = slugify_project_name("Agile Product & Software Development")
        assert result == "agile-product-software-development"

    def test_truncation(self):
        long_name = "A " + "Very " * 20 + "Long Name"
        result = slugify_project_name(long_name)
        assert len(result) <= 50

    def test_special_characters(self):
        assert slugify_project_name("Project (v2.0)!") == "project-v2-0"

    def test_leading_trailing_hyphens_stripped(self):
        assert slugify_project_name("  -test-  ") == "test"


# ==================== build_personal_context ====================


@pytest.mark.unit
class TestBuildPersonalContext:
    """Tests for build_personal_context."""

    def test_full_data(self):
        profile = {
            "Personal Information": "- Name: Marco",
            "Personality Traits": "- Introvert",
        }
        memory = {"Personal context": "Lives in Berlin with family."}
        result = build_personal_context(profile, memory)
        assert "# Personal Context" in result
        assert "Name: Marco" in result
        assert "Introvert" in result
        assert "Lives in Berlin" in result

    def test_memory_only(self):
        result = build_personal_context({}, {"Personal context": "Berlin."})
        assert "# Personal Context" in result
        assert "Berlin." in result

    def test_profile_only(self):
        profile = {"Personal Information": "- Name: Marco"}
        result = build_personal_context(profile, {})
        assert "Name: Marco" in result
        assert "From Claude Memories" not in result

    def test_empty_inputs(self):
        result = build_personal_context({}, {})
        assert "# Personal Context" in result


# ==================== build_professional_context ====================


@pytest.mark.unit
class TestBuildProfessionalContext:
    """Tests for build_professional_context."""

    def test_full_data(self):
        profile = {
            "Professional background": "- Consultant",
            "Industry Context": "- Automotive",
        }
        memory = {
            "Work context": "Agile coaching in automotive.",
            "Brief history": "Humanities to AI.",
        }
        result = build_professional_context(profile, memory)
        assert "# Professional Context" in result
        assert "Consultant" in result
        assert "Automotive" in result
        assert "Agile coaching" in result
        assert "Humanities to AI" in result

    def test_memory_only(self):
        result = build_professional_context({}, {"Work context": "Tech consultant."})
        assert "Tech consultant." in result

    def test_profile_only(self):
        profile = {"Professional background": "- Engineer"}
        result = build_professional_context(profile, {})
        assert "Engineer" in result
        assert "From Claude Memories" not in result


# ==================== build_current_focus ====================


@pytest.mark.unit
class TestBuildCurrentFocus:
    """Tests for build_current_focus."""

    def test_replaces_top_of_mind(self):
        existing = (
            "# Current Focus\n\n"
            "## Active projects\n- Jarvis\n\n"
            "## What's top of mind this week\n- Old stuff\n\n"
            "## Learning goals\n- AI"
        )
        memory = {"Top of mind": "- New focus on context import"}
        result = build_current_focus(existing, memory)
        assert "New focus on context import" in result
        assert "Old stuff" not in result
        assert "Active projects" in result
        assert "Learning goals" in result

    def test_appends_when_no_existing_section(self):
        existing = "# Current Focus\n\n## Active projects\n- Jarvis"
        memory = {"Top of mind": "- New stuff"}
        result = build_current_focus(existing, memory)
        assert "New stuff" in result
        assert "Active projects" in result

    def test_no_top_of_mind_returns_unchanged(self):
        existing = "# Current Focus\n\n## Active\n- stuff"
        result = build_current_focus(existing, {})
        assert result == existing

    def test_preserves_other_sections(self):
        existing = (
            "## What's top of mind this week\n- Old\n\n"
            "## Open questions\n- How to balance?"
        )
        memory = {"Top of mind": "- New priorities"}
        result = build_current_focus(existing, memory)
        assert "New priorities" in result
        assert "Open questions" in result
        assert "How to balance?" in result


# ==================== build_project_file ====================


@pytest.mark.unit
class TestBuildProjectFile:
    """Tests for build_project_file."""

    def test_memory_and_prompt(self):
        result = build_project_file(
            "My Project",
            "Project uses Python.",
            "You are helping with Python.",
        )
        assert "# My Project" in result
        assert "Project uses Python." in result
        assert "You are helping with Python." in result

    def test_memory_only(self):
        result = build_project_file("My Project", "Memory text.", None)
        assert "Memory text." in result
        assert "Prompt Template" not in result

    def test_with_docs(self):
        result = build_project_file(
            "Research Project",
            "Research notes.",
            None,
            doc_filenames=["notes.md", "data.md"],
        )
        assert "Reference Documents" in result
        assert "notes.md" in result
        assert "data.md" in result

    def test_empty_memory_and_prompt(self):
        result = build_project_file("Empty", "", "")
        assert "# Empty" in result
        assert "Project Memory" not in result


# ==================== import_context ====================


@pytest.mark.unit
class TestImportContext:
    """Tests for the main import_context function."""

    def test_dry_run_writes_nothing(self, tmp_path, fixtures_dir):
        memories_path = fixtures_dir / "claude_memories_sample.json"
        projects_path = fixtures_dir / "claude_projects_sample.json"
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        # Create a profile.md to migrate
        profile_path = target_dir / "profile.md"
        profile_path.write_text("## Personal Information\n- Name: Marco")

        summary = import_context(
            memories_path=memories_path,
            projects_path=projects_path,
            target_dir=target_dir,
            existing_profile_path=profile_path,
            dry_run=True,
        )

        assert len(summary.files_written) > 0
        # No files actually written (except profile.md which already existed)
        assert not (target_dir / "personal_context.md").exists()
        assert not (target_dir / "professional_context.md").exists()
        # profile.md should NOT be deleted in dry run
        assert profile_path.exists()

    def test_writes_files(self, tmp_path, fixtures_dir):
        memories_path = fixtures_dir / "claude_memories_sample.json"
        projects_path = fixtures_dir / "claude_projects_sample.json"
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        # Create profile.md
        profile_path = target_dir / "profile.md"
        profile_path.write_text(
            "## Personal Information\n- Name: Marco\n\n"
            "## Professional background\n- Consultant"
        )

        # Create current_focus.md
        focus_path = target_dir / "current_focus.md"
        focus_path.write_text("## What's top of mind this week\n- Old focus")

        summary = import_context(
            memories_path=memories_path,
            projects_path=projects_path,
            target_dir=target_dir,
            existing_profile_path=profile_path,
        )

        # Check files were written
        assert (target_dir / "personal_context.md").exists()
        assert (target_dir / "professional_context.md").exists()
        assert "personal_context.md" in summary.files_written
        assert "professional_context.md" in summary.files_written

        # Check personal context content
        personal = (target_dir / "personal_context.md").read_text()
        assert "Name: Marco" in personal

        # Check professional context content
        professional = (target_dir / "professional_context.md").read_text()
        assert "Consultant" in professional

        # Check profile.md was deleted
        assert not profile_path.exists()

    def test_skips_starter_projects(self, tmp_path, fixtures_dir):
        projects_path = fixtures_dir / "claude_projects_sample.json"
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=None,
            projects_path=projects_path,
            target_dir=target_dir,
        )

        assert summary.projects_skipped >= 1
        # "Getting Started" is a starter, should be skipped

    def test_imports_real_projects(self, tmp_path, fixtures_dir):
        memories_path = fixtures_dir / "claude_memories_sample.json"
        projects_path = fixtures_dir / "claude_projects_sample.json"
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=memories_path,
            projects_path=projects_path,
            target_dir=target_dir,
        )

        assert summary.projects_imported >= 2
        # Check project files exist
        assert (target_dir / "projects" / "technical-humanist.md").exists()
        assert (target_dir / "projects" / "agile-product-software-development.md").exists()

    def test_saves_docs(self, tmp_path, fixtures_dir):
        projects_path = fixtures_dir / "claude_projects_sample.json"
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=None,
            projects_path=projects_path,
            target_dir=target_dir,
        )

        assert summary.docs_saved >= 1
        # Check doc files exist
        docs_dir = target_dir / "projects" / "docs" / "technical-humanist"
        assert docs_dir.exists()
        assert (docs_dir / "research-notes.md").exists()

    def test_missing_memories_file(self, tmp_path):
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=Path("/nonexistent/memories.json"),
            projects_path=None,
            target_dir=target_dir,
        )

        assert any("not found" in w for w in summary.warnings)

    def test_missing_projects_file(self, tmp_path):
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=None,
            projects_path=Path("/nonexistent/projects.json"),
            target_dir=target_dir,
        )

        assert any("not found" in w for w in summary.warnings)

    def test_none_paths(self, tmp_path):
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=None,
            projects_path=None,
            target_dir=target_dir,
        )

        assert summary.projects_imported == 0
        assert len(summary.files_written) == 0

    def test_project_memory_joined_by_uuid(self, tmp_path, fixtures_dir):
        """Project memories from memories.json are joined to projects by UUID."""
        memories_path = fixtures_dir / "claude_memories_sample.json"
        projects_path = fixtures_dir / "claude_projects_sample.json"
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        import_context(
            memories_path=memories_path,
            projects_path=projects_path,
            target_dir=target_dir,
        )

        # "The Technical Humanist" has uuid "proj-001-uuid" which has a project memory
        project_file = target_dir / "projects" / "technical-humanist.md"
        content = project_file.read_text()
        assert "local-first personal AI assistant" in content

    def test_current_focus_updated(self, tmp_path, fixtures_dir):
        """Top of mind from memories replaces existing section."""
        memories_path = fixtures_dir / "claude_memories_sample.json"
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        focus_path = target_dir / "current_focus.md"
        focus_path.write_text(
            "## Active projects\n- Jarvis\n\n"
            "## What's top of mind this week\n- Old stuff"
        )

        import_context(
            memories_path=memories_path,
            projects_path=None,
            target_dir=target_dir,
        )

        updated = focus_path.read_text()
        assert "Claude context import" in updated
        assert "Old stuff" not in updated
        assert "Active projects" in updated
