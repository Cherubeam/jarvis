"""Tests for apps.gui.server.history.derive — pure helpers."""

from apps.gui.server.history.derive import (
    HANDOFF_TOOL_NAME,
    agents_seen,
    dominant_agent,
    duration_ms,
    duration_str,
    handoff_count,
    preview_messages,
    title_from_messages,
    tool_call_count,
    tools_used,
)

# -- title_from_messages -----------------------------------------------------


def test_title_from_messages_empty_returns_sentinel():
    assert title_from_messages([]) == "(no messages)"
    assert title_from_messages([{"role": "assistant", "content": "hi"}]) == "(no messages)"


def test_title_whitespace_only_user_message_returns_sentinel():
    assert title_from_messages([{"role": "user", "content": "   \n\t  "}]) == "(no messages)"


def test_title_collapses_whitespace_and_truncates():
    text = "draft the\n\n\nweek-12 substack  with   long  context"
    title = title_from_messages([{"role": "user", "content": text}], max_len=30)
    assert title == "draft the week-12 substack wi…"
    assert len(title) == 30


def test_title_default_max_len_caps_at_80():
    raw = "x" * 200
    title = title_from_messages([{"role": "user", "content": raw}])
    assert len(title) == 80
    assert title.endswith("…")


def test_title_short_message_returned_unchanged_no_ellipsis():
    """Below the max_len boundary — no truncation, no ellipsis."""
    title = title_from_messages([{"role": "user", "content": "tiny"}])
    assert title == "tiny"


def test_title_supports_block_content():
    msgs = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}],
        }
    ]
    assert title_from_messages(msgs) == "hello world"


def test_title_block_content_skips_non_text_block_types():
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "image", "text": "ignored-image-caption"},
                {"type": "text", "text": "kept"},
            ],
        }
    ]
    assert title_from_messages(msgs) == "kept"


def test_title_block_content_with_no_type_key_treated_as_text():
    msgs = [{"role": "user", "content": [{"text": "no-type-key"}]}]
    assert title_from_messages(msgs) == "no-type-key"


def test_title_keeps_slash_commands():
    msgs = [{"role": "user", "content": "/write opening paragraph"}]
    assert title_from_messages(msgs) == "/write opening paragraph"


def test_title_uses_first_user_only_ignoring_later_users():
    msgs = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "second — should be ignored"},
    ]
    assert title_from_messages(msgs) == "first"


# -- handoff_count / tools_used / tool_call_count ----------------------------


def _assistant_with_tools(*names):
    return {
        "role": "assistant",
        "tool_calls": [{"function": {"name": n}} for n in names],
    }


def test_handoff_tool_name_constant_is_delegate_to_agent():
    """Wire-protocol tie-in — must stay 'delegate_to_agent' or History breaks."""
    assert HANDOFF_TOOL_NAME == "delegate_to_agent"


def test_handoff_count_counts_only_delegate_to_agent():
    msgs = [
        _assistant_with_tools(HANDOFF_TOOL_NAME, "read_note"),
        _assistant_with_tools("web_fetch"),
        _assistant_with_tools(HANDOFF_TOOL_NAME),
    ]
    assert handoff_count(msgs) == 2


def test_handoff_count_zero_when_no_handoff_tool_present():
    msgs = [_assistant_with_tools("read_note", "web_fetch")]
    assert handoff_count(msgs) == 0


def test_handoff_count_zero_when_no_messages():
    assert handoff_count([]) == 0


def test_tools_used_excludes_handoff_and_dedupes_sorted():
    msgs = [
        _assistant_with_tools("read_note", "web_fetch"),
        _assistant_with_tools(HANDOFF_TOOL_NAME, "read_note", "write_note"),
    ]
    # Implementation returns sorted unique names.
    assert tools_used(msgs) == ["read_note", "web_fetch", "write_note"]


def test_tools_used_skips_tool_calls_with_missing_function_name():
    msgs = [
        {"role": "assistant", "tool_calls": [{"function": {}}, {"function": {"name": "ok"}}]},
    ]
    assert tools_used(msgs) == ["ok"]


def test_tools_used_skips_non_dict_tool_call_entries():
    msgs = [
        {
            "role": "assistant",
            "tool_calls": ["not-a-dict", {"function": {"name": "real"}}],
        },
    ]
    assert tools_used(msgs) == ["real"]


def test_tools_used_returns_empty_when_no_tool_calls():
    assert tools_used([{"role": "assistant", "content": "no tools here"}]) == []


def test_tool_call_count_includes_handoff():
    msgs = [_assistant_with_tools("read_note"), _assistant_with_tools(HANDOFF_TOOL_NAME)]
    assert tool_call_count(msgs) == 2


def test_tool_call_count_zero_for_messages_without_tool_calls():
    assert tool_call_count([{"role": "assistant", "content": "plain"}]) == 0


def test_tools_used_ignores_non_assistant_roles():
    msgs = [
        {"role": "user", "tool_calls": [{"function": {"name": "read_note"}}]},
        _assistant_with_tools("web_fetch"),
    ]
    assert tools_used(msgs) == ["web_fetch"]


def test_handoff_count_ignores_non_assistant_roles():
    """Tool messages can carry tool_calls in odd imports — must not be counted."""
    msgs = [
        {"role": "tool", "tool_calls": [{"function": {"name": HANDOFF_TOOL_NAME}}]},
        _assistant_with_tools(HANDOFF_TOOL_NAME),
    ]
    assert handoff_count(msgs) == 1


# -- agents_seen / dominant_agent --------------------------------------------


def test_agents_seen_reads_top_level_agent_field():
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "agent": "JARVIS", "content": "hello"},
        {"role": "assistant", "agent": "writer", "content": "draft…"},
        {"role": "assistant", "agent": "JARVIS", "content": "done"},
    ]
    # Insertion order — JARVIS appears first, writer second, no dupes.
    assert agents_seen(msgs) == ["JARVIS", "writer"]


def test_agents_seen_returns_empty_for_legacy_messages_without_agent_field():
    msgs = [{"role": "assistant", "content": "legacy"}]
    assert agents_seen(msgs) == []


def test_agents_seen_skips_empty_agent_string():
    msgs = [
        {"role": "assistant", "agent": "", "content": "x"},
        {"role": "assistant", "agent": "writer", "content": "y"},
    ]
    assert agents_seen(msgs) == ["writer"]


def test_agents_seen_skips_user_messages_even_with_agent_field():
    msgs = [
        {"role": "user", "agent": "should-be-ignored", "content": "q"},
        {"role": "assistant", "agent": "writer", "content": "a"},
    ]
    assert agents_seen(msgs) == ["writer"]


def test_dominant_agent_picks_first_non_jarvis():
    assert dominant_agent(["JARVIS", "writer", "researcher"]) == "writer"


def test_dominant_agent_falls_back_to_jarvis_when_only_jarvis():
    assert dominant_agent(["JARVIS"]) == "JARVIS"


def test_dominant_agent_returns_empty_string_for_empty_list():
    assert dominant_agent([]) == ""


def test_dominant_agent_skips_empty_string_then_returns_first_real():
    """Empty entries must not satisfy the non-JARVIS check."""
    assert dominant_agent(["", "writer"]) == "writer"


def test_dominant_agent_returns_first_when_no_non_jarvis_candidate():
    """If only JARVIS-or-empty entries exist, return the first."""
    assert dominant_agent(["JARVIS", "JARVIS"]) == "JARVIS"


# -- duration ----------------------------------------------------------------


def test_duration_ms_handles_missing_and_bad_input():
    assert duration_ms(None, None) == 0
    assert duration_ms(None, "2026-04-19T10:00:00") == 0
    assert duration_ms("2026-04-19T10:00:00", None) == 0
    assert duration_ms("not a date", "2026-04-19T10:00:00") == 0
    assert duration_ms("2026-04-19T10:00:00", "2026-04-19T10:00:10") == 10_000


def test_duration_ms_clamps_negative_to_zero():
    """End before start → 0, not a negative number."""
    assert duration_ms("2026-04-19T10:01:00", "2026-04-19T10:00:00") == 0


def test_duration_ms_empty_strings_return_zero():
    assert duration_ms("", "2026-04-19T10:00:00") == 0
    assert duration_ms("2026-04-19T10:00:00", "") == 0


def test_duration_str_formats_hours_minutes_seconds():
    assert duration_str(0) == "—"
    assert duration_str(-5) == "—"  # negative also returns sentinel
    assert duration_str(42_000) == "42s"
    assert duration_str(8 * 60_000 + 12_000) == "8m 12s"
    assert duration_str(74 * 60_000) == "1h 14m"


def test_duration_str_zero_pads_seconds_under_minute_threshold():
    """3m 5s — seconds must be zero-padded to two digits."""
    assert duration_str(3 * 60_000 + 5_000) == "3m 05s"


def test_duration_str_zero_pads_minutes_under_hour_threshold():
    """2h 03m — minutes must be zero-padded."""
    assert duration_str(2 * 3_600_000 + 3 * 60_000) == "2h 03m"


def test_duration_str_under_one_second_returns_zero_seconds():
    """500ms is positive but rounds down to 0s — still uses the seconds branch."""
    assert duration_str(500) == "0s"


# -- preview_messages --------------------------------------------------------


def test_preview_messages_caps_items_and_chars():
    long_text = "x" * 500
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "agent": "JARVIS", "content": long_text},
        {"role": "tool", "content": "ignored"},
        {"role": "user", "content": "follow up"},
        {"role": "assistant", "agent": "writer", "content": "draft"},
        {"role": "user", "content": "also ignored — past cap"},
    ]
    out = preview_messages(msgs, max_items=4, max_chars=20)
    assert len(out) == 4
    roles = [p["role"] for p in out]
    assert roles == ["user", "JARVIS", "user", "writer"]
    # Truncated assistant text ends with ellipsis.
    assert out[1]["text"].endswith("…")
    assert len(out[1]["text"]) <= 20
    # Each entry is exactly {role, text} — nothing else leaks.
    for p in out:
        assert set(p.keys()) == {"role", "text"}


def test_preview_messages_default_caps_4_items_240_chars():
    """Defaults must stay (4, 240) — design contract."""
    long_text = "y" * 500
    msgs = [
        {"role": "user", "content": long_text},
        {"role": "user", "content": "u2"},
        {"role": "user", "content": "u3"},
        {"role": "user", "content": "u4"},
        {"role": "user", "content": "should-be-dropped"},
    ]
    out = preview_messages(msgs)
    assert len(out) == 4
    assert len(out[0]["text"]) == 240
    assert out[0]["text"].endswith("…")


def test_preview_messages_assistant_without_agent_falls_back_to_jarvis():
    msgs = [{"role": "assistant", "content": "no agent field"}]
    out = preview_messages(msgs)
    assert out == [{"role": "JARVIS", "text": "no agent field"}]


def test_preview_messages_skips_empty_content():
    """Empty/whitespace-only content is skipped, not emitted as a blank row."""
    msgs = [
        {"role": "user", "content": "  "},
        {"role": "assistant", "agent": "JARVIS", "content": ""},
        {"role": "user", "content": "real"},
    ]
    out = preview_messages(msgs)
    assert out == [{"role": "user", "text": "real"}]


def test_preview_messages_collapses_internal_whitespace():
    msgs = [{"role": "user", "content": "a\n\n\tb   c"}]
    out = preview_messages(msgs)
    assert out == [{"role": "user", "text": "a b c"}]


def test_preview_messages_block_content_concatenated():
    msgs = [
        {
            "role": "assistant",
            "agent": "writer",
            "content": [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}],
        }
    ]
    out = preview_messages(msgs)
    assert out == [{"role": "writer", "text": "hello world"}]


def test_preview_messages_skips_tool_role_entirely():
    """Only user + assistant get into the preview."""
    msgs = [
        {"role": "tool", "content": "tool result"},
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u"},
    ]
    out = preview_messages(msgs)
    assert out == [{"role": "user", "text": "u"}]


def test_preview_messages_returns_empty_when_no_messages():
    assert preview_messages([]) == []
