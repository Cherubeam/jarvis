"""
Unit tests for session history trimming and summarization.
"""

from unittest.mock import MagicMock, patch

import pytest

from packages.core.history import (
    trim_tool_results,
    summarize_history,
    _approx_tokens,
    _format_messages_for_summary,
    _TOOL_RESULT_SUMMARY_LEN,
    _SUMMARY_MARKER,
    _DEFAULT_TOKEN_THRESHOLD,
    _DEFAULT_KEEP_RECENT_FOR_SUMMARY,
    _KEEP_RECENT_MESSAGES,
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

    def test_prior_summary_resummarizes_when_new_content_exceeds_threshold(self):
        """When prior summary exists but new content exceeds threshold, re-summarize."""
        history = [
            {"role": "assistant", "content": f"{_SUMMARY_MARKER} Previous summary."},
            {"role": "user", "content": "x" * 8000},
            {"role": "assistant", "content": "y" * 8000},
        ] + [
            {"role": "user", "content": f"q{i}: " + "z" * 4000}
            for i in range(12)
        ]
        client = _mock_client("Re-summarized.")
        result = summarize_history(
            history, client, model_id="fast-model",
            token_threshold=100,  # low to force trigger
            keep_recent=3,
        )
        client.complete.assert_called_once()
        assert result[0]["content"].startswith(_SUMMARY_MARKER)

    def test_split_idx_at_end_returns_original(self):
        """If split_idx walks past end of history, return original."""
        # All non-user messages — split_idx can't find a user message
        history = [
            {"role": "assistant", "content": "x" * 8000},
            {"role": "tool", "tool_call_id": "t1", "content": "y" * 8000},
            {"role": "assistant", "content": "z" * 8000},
        ]
        client = _mock_client()
        result = summarize_history(
            history, client, model_id="fast-model",
            token_threshold=100, keep_recent=1,
        )
        assert result is history

    def test_summarizer_system_prompt_content(self):
        """The system message to the summarizer has role 'system' and mentions summarizer."""
        history = _make_long_history(10)
        client = _mock_client("Summary.")
        summarize_history(history, client, model_id="fast-model", token_threshold=100)

        messages = client.complete.call_args[1].get("messages") or client.complete.call_args[0][0]
        assert messages[0]["role"] == "system"
        assert "summarizer" in messages[0]["content"].lower()
        assert messages[1]["role"] == "user"

    def test_summary_output_list_structure(self):
        """Output is [summary_msg, *recent_messages] — summary has exact keys."""
        history = _make_long_history(10)
        client = _mock_client("Done.")
        result = summarize_history(
            history, client, model_id="fast-model", token_threshold=100,
        )
        summary = result[0]
        assert set(summary.keys()) == {"role", "content"}
        assert summary["role"] == "assistant"


@pytest.mark.unit
class TestApproxTokens:
    """Tests for _approx_tokens() — kills operator and string mutations."""

    def test_empty_messages(self):
        assert _approx_tokens([]) == 0

    def test_known_ascii_string(self):
        # 400 ASCII bytes / 4 = 100 tokens
        msgs = [{"content": "a" * 400}]
        assert _approx_tokens(msgs) == 100

    def test_division_not_multiplication(self):
        """Verify // 4, not * 4 or // 2."""
        msgs = [{"content": "a" * 100}]
        result = _approx_tokens(msgs)
        assert result == 25  # 100 / 4, not 400 or 50

    def test_multibyte_uses_byte_length(self):
        """Multibyte chars count by bytes, not characters."""
        # "é" is 2 bytes in UTF-8
        msgs = [{"content": "é" * 100}]
        result = _approx_tokens(msgs)
        assert result == 50  # 200 bytes / 4

    def test_missing_content_treated_as_empty(self):
        msgs = [{"role": "user"}, {"content": "x" * 40}]
        assert _approx_tokens(msgs) == 10  # 0 + 40/4

    def test_multiple_messages_summed(self):
        msgs = [{"content": "a" * 80}, {"content": "b" * 120}]
        assert _approx_tokens(msgs) == 50  # (80 + 120) / 4


@pytest.mark.unit
class TestFormatMessagesForSummary:
    """Tests for _format_messages_for_summary() — kills string format mutations."""

    def test_user_message_format(self):
        msgs = [{"role": "user", "content": "What is AI?"}]
        result = _format_messages_for_summary(msgs)
        assert result == "[user]: What is AI?"

    def test_assistant_message_format(self):
        msgs = [{"role": "assistant", "content": "AI is..."}]
        result = _format_messages_for_summary(msgs)
        assert result == "[assistant]: AI is..."

    def test_tool_result_format(self):
        msgs = [{"role": "tool", "tool_call_id": "tc_42", "content": "Tool output here"}]
        result = _format_messages_for_summary(msgs)
        assert result == "[tool result for tc_42]: Tool output here..."

    def test_tool_result_truncates_at_100(self):
        long_content = "x" * 200
        msgs = [{"role": "tool", "tool_call_id": "tc_1", "content": long_content}]
        result = _format_messages_for_summary(msgs)
        assert result == f"[tool result for tc_1]: {'x' * 100}..."

    def test_tool_result_replaces_newlines(self):
        msgs = [{"role": "tool", "tool_call_id": "tc_1", "content": "line1\nline2\nline3"}]
        result = _format_messages_for_summary(msgs)
        assert "line1 line2 line3" in result
        assert "\n" not in result.split(": ", 1)[1].rstrip(".")

    def test_assistant_with_tool_calls_format(self):
        msgs = [{
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"function": {"name": "search"}},
                {"function": {"name": "read_note"}},
            ],
        }]
        result = _format_messages_for_summary(msgs)
        assert result == "[assistant called tools: search, read_note]"

    def test_missing_role_defaults_to_unknown(self):
        msgs = [{"content": "orphan message"}]
        result = _format_messages_for_summary(msgs)
        assert result == "[unknown]: orphan message"

    def test_missing_tool_call_id_defaults_to_unknown(self):
        msgs = [{"role": "tool", "content": "result"}]
        result = _format_messages_for_summary(msgs)
        assert "[tool result for unknown]" in result

    def test_multiple_messages_newline_joined(self):
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A"},
        ]
        result = _format_messages_for_summary(msgs)
        assert result == "[user]: Q\n[assistant]: A"


@pytest.mark.unit
class TestTrimBoundary:
    """Boundary tests for truncation threshold — kills > vs >= mutations."""

    def test_content_exactly_at_threshold_not_truncated(self):
        """Content exactly at _TOOL_RESULT_SUMMARY_LEN chars should NOT be truncated."""
        exact_content = "B" * _TOOL_RESULT_SUMMARY_LEN
        history = [
            {"role": "tool", "tool_call_id": "t1", "content": exact_content},
            {"role": "user", "content": "recent"},
        ]
        result = trim_tool_results(history, keep_recent=1)
        assert result[0]["content"] == exact_content

    def test_content_one_over_threshold_truncated(self):
        """Content at _TOOL_RESULT_SUMMARY_LEN + 1 should be truncated."""
        over_content = "C" * (_TOOL_RESULT_SUMMARY_LEN + 1)
        history = [
            {"role": "tool", "tool_call_id": "t1", "content": over_content},
            {"role": "user", "content": "recent"},
        ]
        result = trim_tool_results(history, keep_recent=1)
        expected = "C" * _TOOL_RESULT_SUMMARY_LEN + "\n[... truncated]"
        assert result[0]["content"] == expected


@pytest.mark.unit
class TestDefaultConstants:
    """Verify default constant values are used correctly."""

    def test_default_keep_recent_is_6(self):
        assert _KEEP_RECENT_MESSAGES == 6

    def test_default_token_threshold_is_40000(self):
        assert _DEFAULT_TOKEN_THRESHOLD == 40_000

    def test_default_keep_recent_for_summary_is_10(self):
        assert _DEFAULT_KEEP_RECENT_FOR_SUMMARY == 10

    def test_tool_result_summary_len_is_200(self):
        assert _TOOL_RESULT_SUMMARY_LEN == 200
