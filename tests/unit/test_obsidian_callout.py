"""Tests for packages.integrations.obsidian.callout module."""

import pytest

from packages.integrations.obsidian.callout import (
    CalloutBlock,
    CalloutNotFound,
    find_jarvis_callout,
    format_callout_entry,
    build_updated_content,
)


# ==================== find_jarvis_callout ====================


class TestFindJarvisCallout:
    def test_finds_callout_with_content(self):
        content = """\
# Daily Note

> [!JARVIS]
> First entry line
> Second entry line

Some other text"""
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutBlock)
        assert result.start_line == 2
        assert result.end_line == 4
        assert "First entry line" in result.existing_content
        assert "Second entry line" in result.existing_content

    def test_finds_empty_callout(self):
        content = """\
# Daily Note

> [!JARVIS]

Some other text"""
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutBlock)
        assert result.start_line == 2
        assert result.end_line == 2
        assert result.existing_content == ""

    def test_no_callout_returns_not_found(self):
        content = "# Daily Note\n\nJust regular content"
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutNotFound)

    def test_case_insensitive_tag(self):
        content = "> [!jarvis]\n> content here"
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutBlock)
        assert result.start_line == 0

    def test_callout_with_title(self):
        content = "> [!JARVIS] End of Day Summary\n> content here"
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutBlock)
        assert "content here" in result.existing_content

    def test_callout_at_end_of_file(self):
        content = "# Note\n\n> [!JARVIS]\n> final line"
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutBlock)
        assert result.end_line == 3

    def test_callout_stops_at_non_callout_line(self):
        content = """\
> [!JARVIS]
> line one
> line two
This is not part of callout
> [!other] not jarvis"""
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutBlock)
        assert result.end_line == 2
        assert "line two" in result.existing_content
        assert "not part" not in result.existing_content

    def test_empty_content(self):
        result = find_jarvis_callout("")
        assert isinstance(result, CalloutNotFound)

    def test_other_callout_types_ignored(self):
        content = """\
> [!NOTE]
> This is a note
> [!WARNING]
> This is a warning"""
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutNotFound)

    def test_callout_with_blank_lines_inside(self):
        content = """\
> [!JARVIS]
> line one
>
> line three"""
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutBlock)
        assert result.end_line == 3
        assert "line one" in result.existing_content
        assert "line three" in result.existing_content


# ==================== format_callout_entry ====================


class TestFormatCalloutEntry:
    def test_single_line(self):
        assert format_callout_entry("Hello world") == "> Hello world"

    def test_multi_line(self):
        result = format_callout_entry("Line one\nLine two\nLine three")
        assert result == "> Line one\n> Line two\n> Line three"

    def test_empty_lines_get_bare_prefix(self):
        result = format_callout_entry("Before\n\nAfter")
        assert result == "> Before\n>\n> After"

    def test_empty_string(self):
        assert format_callout_entry("") == ">"


# ==================== build_updated_content ====================


class TestBuildUpdatedContent:
    def test_append_to_empty_callout(self):
        original = "# Note\n\n> [!JARVIS]\n\nOther content"
        callout = CalloutBlock(start_line=2, end_line=2, existing_content="")
        result = build_updated_content(original, callout, "New entry")
        assert "> New entry" in result
        assert "Other content" in result

    def test_append_to_existing_callout(self):
        original = "# Note\n\n> [!JARVIS]\n> Existing line\n\nOther"
        callout = CalloutBlock(
            start_line=2, end_line=3, existing_content="Existing line"
        )
        result = build_updated_content(original, callout, "New entry")
        lines = result.split("\n")
        assert "> Existing line" in lines
        assert "> New entry" in lines
        # Separator between old and new
        assert ">" in lines

    def test_preserves_surrounding_content(self):
        original = "# Title\n\n> [!JARVIS]\n> Old\n\n## Section"
        callout = CalloutBlock(start_line=2, end_line=3, existing_content="Old")
        result = build_updated_content(original, callout, "New")
        assert result.startswith("# Title")
        assert "## Section" in result

    def test_multi_line_entry(self):
        original = "> [!JARVIS]\n> existing"
        callout = CalloutBlock(start_line=0, end_line=1, existing_content="existing")
        result = build_updated_content(original, callout, "Line A\nLine B")
        assert "> Line A" in result
        assert "> Line B" in result
