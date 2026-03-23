"""
Unit tests for session history trimming.
"""

import pytest

from packages.core.history import trim_tool_results, _TOOL_RESULT_SUMMARY_LEN


@pytest.mark.unit
class TestTrimToolResults:
    """Tests for trim_tool_results()."""

    def test_short_history_unchanged(self):
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        assert trim_tool_results(history) is history

    def test_old_tool_results_truncated(self):
        long_content = "x" * 1000
        history = [
            {"role": "user", "content": "first question"},
            {"role": "tool", "tool_call_id": "t1", "content": long_content},
            {"role": "assistant", "content": "first answer"},
            {"role": "user", "content": "second question"},
            {"role": "tool", "tool_call_id": "t2", "content": "short result"},
            {"role": "assistant", "content": "second answer"},
            # Recent messages (keep_recent=6 covers these):
            {"role": "user", "content": "third question"},
            {"role": "tool", "tool_call_id": "t3", "content": long_content},
            {"role": "assistant", "content": "third answer"},
            {"role": "user", "content": "fourth question"},
            {"role": "tool", "tool_call_id": "t4", "content": long_content},
            {"role": "assistant", "content": "fourth answer"},
        ]
        result = trim_tool_results(history)

        # Old long tool result (t1) should be truncated
        assert len(result[1]["content"]) < len(long_content)
        assert result[1]["content"].endswith("[... truncated]")
        assert result[1]["tool_call_id"] == "t1"

        # Old short tool result (t2) should be unchanged
        assert result[4]["content"] == "short result"

        # Recent tool results (t3, t4) should be intact
        assert result[7]["content"] == long_content
        assert result[10]["content"] == long_content

    def test_non_tool_messages_never_modified(self):
        long_msg = "x" * 1000
        history = [
            {"role": "user", "content": long_msg},
            {"role": "assistant", "content": long_msg},
            {"role": "user", "content": long_msg},
            {"role": "assistant", "content": long_msg},
            {"role": "user", "content": "recent"},
            {"role": "assistant", "content": "recent"},
            {"role": "user", "content": "latest"},
            {"role": "assistant", "content": "latest"},
        ]
        result = trim_tool_results(history)
        # All messages should be unchanged — no tool messages to trim
        assert result[0]["content"] == long_msg
        assert result[1]["content"] == long_msg

    def test_recent_messages_preserved_intact(self):
        long_content = "x" * 1000
        history = [
            {"role": "user", "content": "old"},
            {"role": "tool", "tool_call_id": "t1", "content": long_content},
            {"role": "assistant", "content": "old answer"},
            # These 6 are the recent ones (keep_recent=6)
            {"role": "user", "content": "q1"},
            {"role": "tool", "tool_call_id": "t2", "content": long_content},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "tool", "tool_call_id": "t3", "content": long_content},
            {"role": "assistant", "content": "a2"},
        ]
        result = trim_tool_results(history)

        # Old tool result truncated
        assert result[1]["content"].endswith("[... truncated]")

        # Recent tool results preserved
        assert result[4]["content"] == long_content
        assert result[7]["content"] == long_content

    def test_custom_keep_recent(self):
        long_content = "x" * 1000
        history = [
            {"role": "tool", "tool_call_id": "t1", "content": long_content},
            {"role": "tool", "tool_call_id": "t2", "content": long_content},
            {"role": "tool", "tool_call_id": "t3", "content": long_content},
        ]

        # keep_recent=1: only last message preserved
        result = trim_tool_results(history, keep_recent=1)
        assert result[0]["content"].endswith("[... truncated]")
        assert result[1]["content"].endswith("[... truncated]")
        assert result[2]["content"] == long_content  # last one preserved

    def test_empty_history(self):
        assert trim_tool_results([]) == []

    def test_exactly_at_keep_recent_threshold(self):
        """History with exactly keep_recent messages should pass through."""
        history = [
            {"role": "user", "content": "q"},
            {"role": "tool", "tool_call_id": "t1", "content": "x" * 1000},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "q2"},
            {"role": "tool", "tool_call_id": "t2", "content": "x" * 1000},
            {"role": "assistant", "content": "a2"},
        ]
        result = trim_tool_results(history, keep_recent=6)
        assert result is history  # identity — no changes needed

    def test_truncation_length(self):
        """Truncated content starts with first N chars of original."""
        original = "A" * 500
        history = [
            {"role": "tool", "tool_call_id": "t1", "content": original},
            # keep_recent=0 to force everything to be old
        ]
        result = trim_tool_results(history, keep_recent=0)
        assert result[0]["content"].startswith("A" * _TOOL_RESULT_SUMMARY_LEN)
