"""Tests for apps.gui.server.home.task_links."""

from apps.gui.server.home.task_links import _salient_words, link_tasks_to_conversations


def _s(id_: str, title: str) -> dict:
    return {"id": id_, "title": title}


# ---- _salient_words --------------------------------------------------------


def test_salient_words_lowercases_and_extracts_alphanum():
    # Sort is stable; insertion order ("week", "substack", "draft") with stable
    # sort by length-desc → ("substack"=8, "draft"=5, "week"=4). "12" drops <4.
    assert _salient_words("Week-12 Substack DRAFT") == ["substack", "draft", "week"]


def test_salient_words_drops_words_under_4_chars():
    """Threshold is 4 characters; "of" (2) and "q1" (2) drop."""
    assert _salient_words("TL;DR of q1") == []


def test_salient_words_keeps_4_char_words_at_boundary():
    """Exactly 4 chars is kept (>= comparison, not >)."""
    assert _salient_words("week plan") == ["week", "plan"]


def test_salient_words_sorts_longest_first():
    """Longest first ensures the most-specific match runs first in the linker."""
    out = _salient_words("plan substack week")
    # "substack" (8) > "plan" (4) == "week" (4); ties keep insertion order via stable sort.
    assert out[0] == "substack"
    # Both 4-char words are present after the longest.
    assert set(out[1:]) == {"plan", "week"}


def test_salient_words_handles_empty_string():
    assert _salient_words("") == []


def test_salient_words_strips_punctuation_via_word_regex():
    """Hyphens, semicolons, and dots split words rather than appearing in them."""
    out = _salient_words("hello-world; foo.bar")
    assert "hello" in out and "world" in out
    # "foo" (3) and "bar" (3) are below the threshold.
    assert "foo" not in out and "bar" not in out


def test_salient_words_treats_digits_as_alphanum():
    """The regex matches [A-Za-z0-9]+ so digits-only words >= 4 chars stay."""
    # Stable sort: insertion ("ship", "2026", "release") → length-desc → release(7), ship(4)=2026(4).
    assert _salient_words("ship 2026 release") == ["release", "ship", "2026"]


# ---- link_tasks_to_conversations -------------------------------------------


def test_empty_inputs():
    assert link_tasks_to_conversations([], []) == []
    out = link_tasks_to_conversations(
        [{"title": "Week-12 Substack draft"}],
        [],
    )
    assert out == [{"title": "Week-12 Substack draft", "linked_conversation_ids": []}]


def test_longest_word_matches_first():
    tasks = [{"title": "Week-12 Substack draft"}]
    # "substack" is longer than "week", "draft". It should match first.
    summaries = [
        _s("2026-04-18_09-00-00", "week-12 substack · draft opening"),
        _s("2026-04-15_11-00-00", "substack pricing strategy"),
    ]
    out = link_tasks_to_conversations(tasks, summaries)
    ids = out[0]["linked_conversation_ids"]
    # Both match "substack"; order follows summary order. Capped at 2.
    assert ids == ["2026-04-18_09-00-00", "2026-04-15_11-00-00"]


def test_skips_short_words():
    tasks = [{"title": "TL;DR of q1"}]  # only "of" + "q1" both < 4 chars
    summaries = [_s("c1", "quarterly review of q1 and q2")]
    out = link_tasks_to_conversations(tasks, summaries)
    assert out[0]["linked_conversation_ids"] == []


def test_dedupes_across_words_and_caps_at_two():
    tasks = [{"title": "Ship JARVIS GUI prototype v1"}]
    # Every summary contains either "jarvis" or "prototype" or both; order
    # matters because we walk summaries in order per word.
    summaries = [
        _s("c1", "jarvis gui prototype phase 1"),
        _s("c2", "prototype iteration notes"),
        _s("c3", "jarvis config refactor"),
        _s("c4", "ship review"),
    ]
    ids = link_tasks_to_conversations(tasks, summaries)[0]["linked_conversation_ids"]
    # Only 2 ids returned; no duplicates.
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_case_insensitive_match():
    tasks = [{"title": "Weekly Substack Review"}]
    summaries = [_s("c1", "SUBSTACK planning notes")]
    assert link_tasks_to_conversations(tasks, summaries)[0]["linked_conversation_ids"] == ["c1"]


def test_preserves_task_fields():
    tasks = [{"title": "Research pricing", "project": "Blog", "priority": "high"}]
    summaries = [_s("c1", "pricing landscape for substack")]
    out = link_tasks_to_conversations(tasks, summaries)
    assert out[0]["project"] == "Blog"
    assert out[0]["priority"] == "high"
    # "pricing" (7 chars) matches as a substring.
    assert out[0]["linked_conversation_ids"] == ["c1"]


def test_does_not_mutate_inputs():
    """Caller-shared task/summary lists must stay untouched (returns new list)."""
    tasks = [{"title": "Substack drafting"}]
    summaries = [_s("c1", "substack pricing")]
    original_tasks = [dict(t) for t in tasks]
    out = link_tasks_to_conversations(tasks, summaries)
    assert tasks == original_tasks  # input untouched
    assert "linked_conversation_ids" not in tasks[0]  # field added on output only
    assert out[0]["linked_conversation_ids"] == ["c1"]


def test_missing_title_field_treated_as_empty():
    """Defensive: tasks without `title` produce empty linked list, no crash."""
    out = link_tasks_to_conversations([{}], [_s("c1", "substack pricing")])
    assert out == [{"linked_conversation_ids": []}]


def test_two_links_cap_per_task_with_three_matches():
    """The MAX_LINKS_PER_TASK cap (2) breaks the inner loop early."""
    tasks = [{"title": "substack review"}]
    summaries = [
        _s("c1", "substack pricing"),
        _s("c2", "substack growth"),
        _s("c3", "substack churn"),  # would match but capped
    ]
    out = link_tasks_to_conversations(tasks, summaries)
    assert out[0]["linked_conversation_ids"] == ["c1", "c2"]


def test_walk_continues_to_second_word_when_first_word_misses():
    """If the longest word doesn't match, the linker tries the next-longest."""
    tasks = [{"title": "Substack PROTOTYPE deck"}]
    # "prototype" is longest (9), no summary mentions it; "substack" (8) matches.
    summaries = [_s("c1", "substack growth review")]
    out = link_tasks_to_conversations(tasks, summaries)
    assert out[0]["linked_conversation_ids"] == ["c1"]


def test_handles_multiple_tasks_independently():
    """Each task gets its own linked list — no cross-contamination."""
    tasks = [
        {"title": "Substack pricing"},
        {"title": "Calendar sync"},
    ]
    summaries = [
        _s("c1", "substack draft"),
        _s("c2", "calendar bugs"),
    ]
    out = link_tasks_to_conversations(tasks, summaries)
    assert out[0]["linked_conversation_ids"] == ["c1"]
    assert out[1]["linked_conversation_ids"] == ["c2"]
