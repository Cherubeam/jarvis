"""Tests for packages.integrations.obsidian.callout module."""

from packages.integrations.obsidian.callout import (
    CalloutBlock,
    CalloutNotFound,
    build_updated_content,
    find_jarvis_callout,
    format_callout_entry,
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
        assert result.existing_content == "First entry line\nSecond entry line"

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
        assert result.end_line == 1
        assert result.existing_content == "content here"

    def test_callout_with_title(self):
        content = "> [!JARVIS] End of Day Summary\n> content here"
        result = find_jarvis_callout(content)
        assert isinstance(result, CalloutBlock)
        assert result.start_line == 0
        assert result.end_line == 1
        assert result.existing_content == "content here"

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
        assert result.existing_content == "line one\nline two"

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
        assert result.existing_content == "line one\n\nline three"


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
        # No separator for empty callout, new entry right after header
        assert result == "# Note\n\n> [!JARVIS]\n> New entry\n\nOther content"

    def test_append_to_existing_callout(self):
        original = "# Note\n\n> [!JARVIS]\n> Existing line\n\nOther"
        callout = CalloutBlock(start_line=2, end_line=3, existing_content="Existing line")
        result = build_updated_content(original, callout, "New entry")
        # With existing content: separator ">" between old and new
        assert result == "# Note\n\n> [!JARVIS]\n> Existing line\n>\n> New entry\n\nOther"

    def test_preserves_surrounding_content(self):
        original = "# Title\n\n> [!JARVIS]\n> Old\n\n## Section"
        callout = CalloutBlock(start_line=2, end_line=3, existing_content="Old")
        result = build_updated_content(original, callout, "New")
        assert result == "# Title\n\n> [!JARVIS]\n> Old\n>\n> New\n\n## Section"

    def test_multi_line_entry(self):
        original = "> [!JARVIS]\n> existing"
        callout = CalloutBlock(start_line=0, end_line=1, existing_content="existing")
        result = build_updated_content(original, callout, "Line A\nLine B")
        assert result == "> [!JARVIS]\n> existing\n>\n> Line A\n> Line B"
