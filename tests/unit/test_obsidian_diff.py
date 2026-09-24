"""Tests for packages.integrations.obsidian.diff module."""

from packages.integrations.obsidian.diff import (
    VaultDiff,
    compute_diff,
    find_link_changes,
    format_diff_for_api,
    format_diff_for_cli,
)

# ==================== compute_diff ====================


class TestComputeDiff:
    def test_no_changes(self):
        content = "line one\nline two"
        diff = compute_diff("test.md", content, content)
        assert diff.summary == "No changes"
        assert diff.file_path == "test.md"

    def test_added_lines(self):
        original = "line one\nline two\n"
        proposed = "line one\nline two\nline three\n"
        diff = compute_diff("test.md", original, proposed)
        assert "+1 line" in diff.summary
        added = [dl for dl in diff.diff_lines if dl.type == "added"]
        assert len(added) == 1
        assert added[0].content == "line three"

    def test_removed_lines(self):
        original = "line one\nline two\nline three"
        proposed = "line one\nline three"
        diff = compute_diff("test.md", original, proposed)
        assert "-1 line" in diff.summary

    def test_mixed_changes(self):
        original = "line one\nline two"
        proposed = "line one\nline changed\nline added"
        diff = compute_diff("test.md", original, proposed)
        added = [dl for dl in diff.diff_lines if dl.type == "added"]
        removed = [dl for dl in diff.diff_lines if dl.type == "removed"]
        assert len(added) >= 1
        assert len(removed) >= 1

    def test_stores_original_and_proposed(self):
        diff = compute_diff("f.md", "old", "new")
        assert diff.original_content == "old"
        assert diff.proposed_content == "new"

    def test_context_lines_parameter(self):
        original = "\n".join(f"line {i}" for i in range(20))
        proposed = original.replace("line 10", "CHANGED")
        diff_small = compute_diff("f.md", original, proposed, context_lines=1)
        diff_large = compute_diff("f.md", original, proposed, context_lines=5)
        # More context = more unchanged lines in output
        small_unchanged = len([dl for dl in diff_small.diff_lines if dl.type == "unchanged"])
        large_unchanged = len([dl for dl in diff_large.diff_lines if dl.type == "unchanged"])
        assert large_unchanged >= small_unchanged


# ==================== find_link_changes ====================

# The case that motivated the guard: a full-file rewrite "copied" a link card
# and changed one host name while the prose edits were elsewhere.
CARD = "```cardlink\nurl: https://www.youtube.com/watch?v=W8IVKMGbUZE\nimage: https://i.ytimg.com/vi/W8IVKMGbUZE/maxresdefault.jpg\n```\n"


class TestFindLinkChanges:
    def test_no_links_no_warnings(self):
        assert find_link_changes("plain text", "other text") == []

    def test_unchanged_links_no_warnings(self):
        assert find_link_changes(CARD + "old prose", CARD + "new prose") == []

    def test_altered_url_reported_as_removed_and_new(self):
        altered = CARD.replace("i.ytimg.com", "i.yimg.com")
        assert find_link_changes(CARD, altered) == [
            "removed or changed: https://i.ytimg.com/vi/W8IVKMGbUZE/maxresdefault.jpg",
            "new: https://i.yimg.com/vi/W8IVKMGbUZE/maxresdefault.jpg",
        ]

    def test_wikilink_change(self):
        assert find_link_changes("see [[Gartner Hype Cycle]]", "see [[Gartner Hype Cylce]]") == [
            "removed or changed: Gartner Hype Cycle",
            "new: Gartner Hype Cylce",
        ]

    def test_relative_markdown_link_target(self):
        assert find_link_changes("[a](notes/a.md)", "[a](notes/b.md)") == [
            "removed or changed: notes/a.md",
            "new: notes/b.md",
        ]

    def test_url_inside_markdown_link_stops_at_paren(self):
        assert find_link_changes("[x](https://a.example/p)", "[x](https://a.example/p) more") == []


class TestComputeDiffLinkWarnings:
    def test_populated_for_existing_file(self):
        diff = compute_diff("post.md", CARD, CARD.replace("ytimg", "yimg"))
        assert len(diff.link_warnings) == 2

    def test_empty_for_new_file(self):
        """Every link in a new file is 'new'; warning about all of them is noise."""
        assert compute_diff("post.md", "", CARD).link_warnings == []

    def test_cli_shows_warning_block_above_diff(self):
        result = format_diff_for_cli(compute_diff("post.md", CARD, CARD.replace("ytimg", "yimg")))
        header = result.index("Links changed")
        assert header < result.index("@@")
        assert "removed or changed: https://i.ytimg.com" in result

    def test_cli_has_no_warning_block_when_links_unchanged(self):
        assert "Links changed" not in format_diff_for_cli(compute_diff("post.md", CARD + "a", CARD + "b"))

    def test_api_includes_link_warnings(self):
        result = format_diff_for_api(compute_diff("post.md", CARD, CARD.replace("ytimg", "yimg")))
        assert len(result["link_warnings"]) == 2


# ==================== format_diff_for_cli ====================


class TestFormatDiffForCli:
    def test_no_changes(self):
        diff = VaultDiff(
            file_path="test.md",
            original_content="same",
            proposed_content="same",
        )
        result = format_diff_for_cli(diff)
        assert "No changes" in result

    def test_contains_ansi_colors(self):
        original = "line one"
        proposed = "line one\nline two"
        diff = compute_diff("test.md", original, proposed)
        result = format_diff_for_cli(diff)
        assert "\033[32m" in result  # Green for added
        assert "\033[0m" in result  # Reset

    def test_shows_file_path_and_summary(self):
        diff = compute_diff("notes/test.md", "a", "a\nb")
        result = format_diff_for_cli(diff)
        assert "notes/test.md" in result


# ==================== format_diff_for_api ====================


class TestFormatDiffForApi:
    def test_no_changes(self):
        diff = VaultDiff(
            file_path="test.md",
            original_content="same",
            proposed_content="same",
        )
        result = format_diff_for_api(diff)
        assert result["has_changes"] is False
        assert result["file_path"] == "test.md"

    def test_with_changes(self):
        diff = compute_diff("test.md", "old", "new")
        result = format_diff_for_api(diff)
        assert result["has_changes"] is True
        assert "lines" in result
        assert isinstance(result["lines"], list)

    def test_serializable(self):
        import json

        diff = compute_diff("test.md", "a\nb", "a\nb\nc")
        result = format_diff_for_api(diff)
        # Should not raise
        json.dumps(result)
