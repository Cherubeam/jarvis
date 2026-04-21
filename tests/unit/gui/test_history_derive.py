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


def test_title_collapses_whitespace_and_truncates():
    text = "draft the\n\n\nweek-12 substack  with   long  context"
    title = title_from_messages([{"role": "user", "content": text}], max_len=30)
    assert title == "draft the week-12 substack wi…"
    assert len(title) == 30


def test_title_supports_block_content():
    msgs = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}],
        }
    ]
    assert title_from_messages(msgs) == "hello world"


def test_title_keeps_slash_commands():
    # Slash commands are preserved — they're often the whole intent of the turn.
    msgs = [{"role": "user", "content": "/write opening paragraph"}]
    assert title_from_messages(msgs) == "/write opening paragraph"


# -- handoff_count / tools_used / tool_call_count ----------------------------


def _assistant_with_tools(*names):
    return {
        "role": "assistant",
        "tool_calls": [{"function": {"name": n}} for n in names],
    }


def test_handoff_count_counts_only_delegate_to_agent():
    msgs = [
        _assistant_with_tools(HANDOFF_TOOL_NAME, "read_note"),
        _assistant_with_tools("web_fetch"),
        _assistant_with_tools(HANDOFF_TOOL_NAME),
    ]
    assert handoff_count(msgs) == 2


def test_tools_used_excludes_handoff_and_dedupes_stable_order():
    msgs = [
        _assistant_with_tools("read_note", "web_fetch"),
        _assistant_with_tools(HANDOFF_TOOL_NAME, "read_note", "write_note"),
    ]
    assert tools_used(msgs) == ["read_note", "web_fetch", "write_note"]


def test_tool_call_count_includes_handoff():
    msgs = [_assistant_with_tools("read_note"), _assistant_with_tools(HANDOFF_TOOL_NAME)]
    assert tool_call_count(msgs) == 2


def test_tools_used_ignores_non_assistant_roles():
    msgs = [
        {"role": "user", "tool_calls": [{"function": {"name": "read_note"}}]},
        _assistant_with_tools("web_fetch"),
    ]
    assert tools_used(msgs) == ["web_fetch"]


# -- agents_seen / dominant_agent --------------------------------------------


def test_agents_seen_reads_top_level_agent_field():
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "agent": "JARVIS", "content": "hello"},
        {"role": "assistant", "agent": "writer", "content": "draft…"},
        {"role": "assistant", "agent": "JARVIS", "content": "done"},
    ]
    assert agents_seen(msgs) == ["JARVIS", "writer"]


def test_agents_seen_returns_empty_for_legacy_messages_without_agent_field():
    msgs = [{"role": "assistant", "content": "legacy"}]
    assert agents_seen(msgs) == []


def test_dominant_agent_picks_first_non_jarvis():
    assert dominant_agent(["JARVIS", "writer", "researcher"]) == "writer"
    assert dominant_agent(["JARVIS"]) == "JARVIS"
    assert dominant_agent([]) == ""


# -- duration ----------------------------------------------------------------


def test_duration_ms_handles_missing_and_bad_input():
    assert duration_ms(None, None) == 0
    assert duration_ms("not a date", "2026-04-19T10:00:00") == 0
    assert duration_ms("2026-04-19T10:00:00", "2026-04-19T10:00:10") == 10_000


def test_duration_str_formats_hours_minutes_seconds():
    assert duration_str(0) == "—"
    assert duration_str(42_000) == "42s"
    assert duration_str(8 * 60_000 + 12_000) == "8m 12s"
    assert duration_str(74 * 60_000) == "1h 14m"


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
