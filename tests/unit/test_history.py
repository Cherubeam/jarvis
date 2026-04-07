"""
Unit tests for session history trimming and summarization.
"""

from unittest.mock import MagicMock, patch

import pytest

from packages.core.history import (
    trim_tool_results,
    summarize_history,
    _TOOL_RESULT_SUMMARY_LEN,
    _SUMMARY_MARKER,
)


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

        # Old long tool result (t1) should be truncated to exactly
        # _TOOL_RESULT_SUMMARY_LEN chars + "\n[... truncated]"
        expected_truncated = long_content[:_TOOL_RESULT_SUMMARY_LEN] + "\n[... truncated]"
        assert result[1]["content"] == expected_truncated
        assert result[1]["tool_call_id"] == "t1"

        # Old short tool result (t2) should be unchanged (below threshold)
        assert result[4]["content"] == "short result"

        # Non-tool messages in old region must stay intact
        assert result[0]["content"] == "first question"
        assert result[0]["role"] == "user"
        assert result[2]["content"] == "first answer"
        assert result[2]["role"] == "assistant"

        # Recent tool results (t3, t4) should be intact
        assert result[7]["content"] == long_content
        assert result[10]["content"] == long_content

        # Exactly keep_recent=6 messages at the end are preserved
        for msg in result[6:]:
            if msg.get("role") == "tool":
                assert "\n[... truncated]" not in msg["content"]

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

        # Old tool result truncated with exact format
        expected_truncated = long_content[:_TOOL_RESULT_SUMMARY_LEN] + "\n[... truncated]"
        assert result[1]["content"] == expected_truncated
        assert result[1]["role"] == "tool"

        # Non-tool messages in old region stay intact regardless of length
        assert result[0]["content"] == "old"
        assert result[0]["role"] == "user"
        assert result[2]["content"] == "old answer"
        assert result[2]["role"] == "assistant"

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
        expected_truncated = long_content[:_TOOL_RESULT_SUMMARY_LEN] + "\n[... truncated]"
        assert result[0]["content"] == expected_truncated
        assert result[1]["content"] == expected_truncated
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
        """Truncated content is exactly prefix + truncation marker."""
        original = "A" * 500
        history = [
            {"role": "tool", "tool_call_id": "t1", "content": original},
            # keep_recent=0 to force everything to be old
        ]
        result = trim_tool_results(history, keep_recent=0)
        expected = "A" * _TOOL_RESULT_SUMMARY_LEN + "\n[... truncated]"
        assert result[0]["content"] == expected


def _make_long_history(n_exchanges: int = 20) -> list[dict]:
    """Build a history with enough content to exceed the default 40K threshold."""
    history: list[dict] = []
    for i in range(n_exchanges):
        history.append({"role": "user", "content": f"Question {i}: " + "x" * 4000})
        history.append({"role": "assistant", "content": f"Answer {i}: " + "y" * 4000})
    return history


def _mock_client(summary_text: str = "Summary of conversation.") -> MagicMock:
    """Create a mock LLMClient that returns a canned summary."""
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = summary_text
    client.complete.return_value = response
    return client


@pytest.mark.unit
class TestSummarizeHistory:
    """Tests for summarize_history()."""

    def test_short_history_unchanged(self):
        """History shorter than keep_recent is returned as-is, no LLM call."""
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        client = _mock_client()
        result = summarize_history(history, client, model_id="fast-model")
        assert result is history
        client.complete.assert_not_called()

    def test_below_token_threshold_unchanged(self):
        """History with many short messages below threshold is not summarized."""
        history = [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a"},
        ] * 20  # 40 messages but tiny content
        client = _mock_client()
        result = summarize_history(history, client, model_id="fast-model")
        assert result is history
        client.complete.assert_not_called()

    def test_above_threshold_triggers_summarization(self):
        """History exceeding threshold triggers an LLM call with the correct model."""
        history = _make_long_history(20)
        client = _mock_client("The user asked 20 questions.")
        result = summarize_history(
            history, client, model_id="openrouter/google/gemini-2.5-flash",
            token_threshold=1000,  # low threshold to force trigger
        )

        client.complete.assert_called_once()
        call_kwargs = client.complete.call_args
        assert call_kwargs.kwargs.get("model") == "openrouter/google/gemini-2.5-flash"

        # Result should start with summary + recent messages
        assert result[0]["role"] == "assistant"
        assert result[0]["content"].startswith(_SUMMARY_MARKER)
        assert "The user asked 20 questions." in result[0]["content"]
        assert len(result) == 11  # 1 summary + 10 recent (default keep_recent)

    def test_split_adjusts_to_user_message(self):
        """Split point walks forward to land on a user message, not a tool result."""
        history = [
            {"role": "user", "content": "x" * 8000},
            {"role": "assistant", "content": "called tool", "tool_calls": [{"function": {"name": "foo"}}]},
            {"role": "tool", "tool_call_id": "t1", "content": "tool output " * 500},
            {"role": "user", "content": "follow up " * 500},
            {"role": "assistant", "content": "response " * 500},
        ]
        client = _mock_client("Summary.")
        result = summarize_history(
            history, client, model_id="fast-model",
            token_threshold=100, keep_recent=3,
        )
        # With keep_recent=3, naive split_idx=2 lands on a tool message.
        # Should walk forward to idx=3 (user message).
        # So old = history[:3], recent = history[3:]
        assert result[0]["role"] == "assistant"
        assert result[0]["content"].startswith(_SUMMARY_MARKER)
        # Recent should be the last 2 messages (from idx 3 onward)
        assert result[1]["role"] == "user"
        assert result[1]["content"].startswith("follow up")

    def test_summary_message_format(self):
        """Summary message has role 'assistant' and contains the marker."""
        history = _make_long_history(10)
        client = _mock_client("Concise summary here.")
        result = summarize_history(
            history, client, model_id="fast-model", token_threshold=100,
        )
        summary = result[0]
        assert summary["role"] == "assistant"
        assert summary["content"] == (
            f"{_SUMMARY_MARKER} Here is a summary of our conversation so far:\n"
            "Concise summary here."
        )

    def test_llm_failure_returns_original(self):
        """If the LLM call fails, original history is returned unchanged."""
        history = _make_long_history(10)
        client = _mock_client()
        client.complete.side_effect = RuntimeError("API down")
        result = summarize_history(
            history, client, model_id="fast-model", token_threshold=100,
        )
        assert result is history

    def test_prior_summary_skips_resummarization(self):
        """When prior summary exists and new content is below threshold, skip."""
        history = [
            {"role": "assistant", "content": f"{_SUMMARY_MARKER} Previous summary."},
            {"role": "user", "content": "short question"},
            {"role": "assistant", "content": "short answer"},
        ]
        client = _mock_client()
        result = summarize_history(
            history, client, model_id="fast-model",
            token_threshold=40000,
        )
        assert result is history
        client.complete.assert_not_called()
