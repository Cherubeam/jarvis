"""Unit tests for Claude context importer (memories + projects)."""

import json
import pytest
from pathlib import Path

from packages.core.importers.claude_context import (
    ContextImportSummary,
    _is_starter_project,
    _sanitize_filename,
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
        assert set(result.keys()) == {
            "Work context",
            "Personal context",
            "Top of mind",
            "Brief history",
        }
        assert result["Work context"] == "I work in tech."
        assert result["Personal context"] == "I live in Berlin."
        assert result["Top of mind"] == "Building Jarvis."
        assert result["Brief history"] == "Humanities to AI."

    def test_empty_input(self):
        assert parse_memory_sections("") == {}
        assert parse_memory_sections("   ") == {}

    def test_no_headers(self):
        assert parse_memory_sections("Just plain text without headers.") == {}

    def test_section_with_multiple_lines(self):
        text = "**Work context**\nLine one.\nLine two.\nLine three."
        result = parse_memory_sections(text)
        assert result["Work context"] == "Line one.\nLine two.\nLine three."

    def test_inline_bold_not_treated_as_header(self):
        text = "**Work context**\nUses **Python** for scripting."
        result = parse_memory_sections(text)
        assert result["Work context"] == "Uses **Python** for scripting."

    def test_empty_section_body(self):
        text = "**Empty section**\n\n**Next section**\nHas content."
        result = parse_memory_sections(text)
        assert "Empty section" not in result
        assert result["Next section"] == "Has content."


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
        assert set(result.keys()) == {
            "Personal Information",
            "Professional background",
            "Skills & knowledge",
        }
        assert result["Personal Information"] == "- Name: Marco"
        assert result["Professional background"] == "- Consultant"
        assert result["Skills & knowledge"] == "- Python"

    def test_empty_input(self):
        assert parse_existing_profile("") == {}
        assert parse_existing_profile("  ") == {}

    def test_partial_profile(self):
        text = "## Personal Information\n- Name: Marco"
        result = parse_existing_profile(text)
        assert result == {"Personal Information": "- Name: Marco"}

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
        assert result.startswith("# Personal Context\n")
        assert "## Personal Information\n- Name: Marco\n" in result
        assert "## Personality Traits\n- Introvert\n" in result
        assert "## From Claude Memories\nLives in Berlin with family.\n" in result

    def test_memory_only(self):
        result = build_personal_context({}, {"Personal context": "Berlin."})
        assert result.startswith("# Personal Context\n")
        assert "## From Claude Memories\nBerlin." in result

    def test_profile_only(self):
        profile = {"Personal Information": "- Name: Marco"}
        result = build_personal_context(profile, {})
        assert "## Personal Information\n- Name: Marco\n" in result
        assert "From Claude Memories" not in result

    def test_empty_inputs(self):
        result = build_personal_context({}, {})
        assert result == "# Personal Context\n"


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
        assert result.startswith("# Professional Context\n")
        assert "## Professional background\n- Consultant\n" in result
        assert "## Industry Context\n- Automotive\n" in result
        assert "## From Claude Memories — Work\nAgile coaching in automotive.\n" in result
        assert "## From Claude Memories — Career History\nHumanities to AI.\n" in result

    def test_memory_only(self):
        result = build_professional_context({}, {"Work context": "Tech consultant."})
        assert result.startswith("# Professional Context\n")
        assert "## From Claude Memories — Work\nTech consultant." in result

    def test_profile_only(self):
        profile = {"Professional background": "- Engineer"}
        result = build_professional_context(profile, {})
        assert "## Professional background\n- Engineer\n" in result
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
        existing = "## What's top of mind this week\n- Old\n\n## Open questions\n- How to balance?"
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
        assert result.startswith("# My Project\n")
        assert "## Project Memory\nProject uses Python.\n" in result
        assert "## Prompt Template\nYou are helping with Python.\n" in result

    def test_memory_only(self):
        result = build_project_file("My Project", "Memory text.", None)
        assert "## Project Memory\nMemory text.\n" in result
        assert "Prompt Template" not in result

    def test_with_docs(self):
        result = build_project_file(
            "Research Project",
            "Research notes.",
            None,
            doc_filenames=["notes.md", "data.md"],
        )
        assert "## Reference Documents" in result
        assert "- notes.md" in result
        assert "- data.md" in result
        assert "data/context/projects/docs/research-project/" in result

    def test_empty_memory_and_prompt(self):
        result = build_project_file("Empty", "", "")
        assert result.startswith("# Empty\n")
        assert "Project Memory" not in result
        assert "Prompt Template" not in result


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
            "## Personal Information\n- Name: Marco\n\n## Professional background\n- Consultant"
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

        assert len(summary.warnings) == 1
        assert summary.warnings[0] == "Memories file not found: /nonexistent/memories.json"

    def test_missing_projects_file(self, tmp_path):
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=None,
            projects_path=Path("/nonexistent/projects.json"),
            target_dir=target_dir,
        )

        assert len(summary.warnings) == 1
        assert summary.warnings[0] == "Projects file not found: /nonexistent/projects.json"

    def test_none_paths(self, tmp_path):
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=None,
            projects_path=None,
            target_dir=target_dir,
        )

        assert summary.projects_imported == 0
        assert summary.projects_skipped == 0
        assert summary.docs_saved == 0
        assert summary.files_written == []
        assert summary.files_skipped == []
        assert summary.warnings == []

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
            "## Active projects\n- Jarvis\n\n## What's top of mind this week\n- Old stuff"
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

    def test_summary_fields_exact(self, tmp_path, fixtures_dir):
        """Verify exact summary field values for a known import."""
        memories_path = fixtures_dir / "claude_memories_sample.json"
        projects_path = fixtures_dir / "claude_projects_sample.json"
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=memories_path,
            projects_path=projects_path,
            target_dir=target_dir,
        )

        assert "personal_context.md" in summary.files_written
        assert "professional_context.md" in summary.files_written
        assert "current_focus.md" in summary.files_written
        assert summary.projects_imported >= 2
        assert summary.projects_skipped >= 1
        assert summary.warnings == []

    def test_memories_list_wrapping(self, tmp_path):
        """Memories.json as a list wrapping a single object is handled."""
        target_dir = tmp_path / "context"
        target_dir.mkdir()
        memories_path = tmp_path / "mem.json"
        memories_path.write_text(
            json.dumps(
                [
                    {
                        "conversations_memory": "**Personal context**\nTest memory data",
                    }
                ]
            )
        )

        summary = import_context(
            memories_path=memories_path,
            projects_path=None,
            target_dir=target_dir,
        )
        assert "personal_context.md" in summary.files_written

    def test_memories_dict_format(self, tmp_path):
        """Memories.json as a plain dict (not list) is handled."""
        target_dir = tmp_path / "context"
        target_dir.mkdir()
        memories_path = tmp_path / "mem.json"
        memories_path.write_text(
            json.dumps(
                {
                    "conversations_memory": "**Personal context**\nDirect dict memory",
                }
            )
        )

        summary = import_context(
            memories_path=memories_path,
            projects_path=None,
            target_dir=target_dir,
        )
        assert "personal_context.md" in summary.files_written

    def test_project_memories_list_format(self, tmp_path):
        """Project memories as a list of {project_uuid, memory} objects."""
        target_dir = tmp_path / "context"
        target_dir.mkdir()
        memories_path = tmp_path / "mem.json"
        memories_path.write_text(
            json.dumps(
                [
                    {
                        "project_memories": [
                            {"project_uuid": "proj-1", "memory": "Project 1 memory"},
                        ],
                    }
                ]
            )
        )
        projects_path = tmp_path / "proj.json"
        projects_path.write_text(
            json.dumps(
                [
                    {
                        "uuid": "proj-1",
                        "name": "Test Project",
                    }
                ]
            )
        )

        summary = import_context(
            memories_path=memories_path,
            projects_path=projects_path,
            target_dir=target_dir,
        )
        assert summary.projects_imported == 1
        content = (target_dir / "projects" / "test-project.md").read_text()
        assert "Project 1 memory" in content

    def test_doc_without_content_skipped(self, tmp_path):
        """Project docs with empty content are not written."""
        target_dir = tmp_path / "context"
        target_dir.mkdir()
        projects_path = tmp_path / "proj.json"
        projects_path.write_text(
            json.dumps(
                [
                    {
                        "uuid": "proj-1",
                        "name": "Doc Test",
                        "docs": [{"filename": "empty.md", "content": ""}],
                    }
                ]
            )
        )

        summary = import_context(
            memories_path=None,
            projects_path=projects_path,
            target_dir=target_dir,
        )
        assert summary.docs_saved == 0

    def test_project_file_content_includes_slug_in_docs_path(self, tmp_path):
        """Project file references docs using the slugified project name."""
        target_dir = tmp_path / "context"
        target_dir.mkdir()
        projects_path = tmp_path / "proj.json"
        projects_path.write_text(
            json.dumps(
                [
                    {
                        "uuid": "proj-1",
                        "name": "My Great Project",
                        "docs": [{"filename": "notes.md", "content": "content"}],
                    }
                ]
            )
        )

        import_context(
            memories_path=None,
            projects_path=projects_path,
            target_dir=target_dir,
        )
        content = (target_dir / "projects" / "my-great-project.md").read_text()
        assert "docs/my-great-project/" in content
        assert "- notes.md" in content

    def test_no_profile_sections_no_files_written(self, tmp_path):
        """Without profile sections or memories, personal/professional files not written."""
        target_dir = tmp_path / "context"
        target_dir.mkdir()

        summary = import_context(
            memories_path=None,
            projects_path=None,
            target_dir=target_dir,
        )
        assert "personal_context.md" not in summary.files_written
        assert "professional_context.md" not in summary.files_written


@pytest.mark.unit
class TestIsStarterProject:
    """Tests for _is_starter_project — each condition tested individually."""

    def test_is_starter_project_flag(self):
        assert _is_starter_project({"is_starter_project": True}) is True

    def test_is_starter_flag(self):
        assert _is_starter_project({"is_starter": True}) is True

    def test_type_starter(self):
        assert _is_starter_project({"type": "starter"}) is True

    def test_not_starter(self):
        assert _is_starter_project({"name": "My Project"}) is False

    def test_false_flags(self):
        assert _is_starter_project({"is_starter_project": False, "is_starter": False}) is False


@pytest.mark.unit
class TestSanitizeFilename:
    """Tests for _sanitize_filename — each substitution tested."""

    def test_replaces_path_separators(self):
        assert _sanitize_filename("path/to\\file") == "path-to-file.md"

    def test_replaces_special_chars(self):
        assert _sanitize_filename('file:*?"<>|&name') == "file-name.md"

    def test_collapses_hyphens(self):
        assert _sanitize_filename("a---b") == "a-b.md"

    def test_strips_leading_trailing(self):
        assert _sanitize_filename("- name -") == "name.md"

    def test_adds_md_extension(self):
        assert _sanitize_filename("file").endswith(".md")

    def test_preserves_md_extension(self):
        assert _sanitize_filename("file.md") == "file.md"

    def test_clean_name_unchanged(self):
        assert _sanitize_filename("good-name.md") == "good-name.md"


@pytest.mark.unit
class TestSlugifyMutationTargets:
    """Additional slugify tests targeting specific mutations."""

    def test_removes_leading_the(self):
        assert slugify_project_name("The Project") == "project"

    def test_removes_ampersand(self):
        assert slugify_project_name("A & B") == "a-b"

    def test_truncates_at_50_chars(self):
        long_name = "a-" * 30  # 60 chars
        result = slugify_project_name(long_name)
        assert len(result) <= 50

    def test_strips_leading_trailing_hyphens(self):
        assert slugify_project_name("  -test-  ") == "test"

    def test_collapses_multiple_hyphens(self):
        assert slugify_project_name("a   b   c") == "a-b-c"
